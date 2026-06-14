#define _GNU_SOURCE
#include <asm/unistd.h>
#include <errno.h>
#include <linux/perf_event.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

typedef struct {
    int fd;
    const char *name;
    long long last_value;
} PerfCounter;

typedef struct {
    double dtlb_mpki;
    double llc_mpki;
    double pf_per_sec;
    double score;
} SampleMetrics;

typedef struct {
    int thp_enabled;
    int cooldown_left;
    int stable_low_count;
} ControllerState;

static volatile sig_atomic_t g_stop = 0;

static void on_sigint(int signo) {
    (void)signo;
    g_stop = 1;
}

static int perf_open(__u32 type, __u64 config, const char *name) {
    struct perf_event_attr attr;
    memset(&attr, 0, sizeof(attr));
    attr.type = type;
    attr.size = sizeof(attr);
    attr.config = config;
    attr.disabled = 0;
    attr.exclude_kernel = 1;
    attr.exclude_hv = 1;
    attr.read_format = 0;

    int fd = (int)syscall(__NR_perf_event_open, &attr, 0, -1, -1, 0);
    if (fd < 0) {
        fprintf(stderr, "[warn] open %s failed: %s\n", name, strerror(errno));
    }
    return fd;
}

static long long read_counter(int fd, const char *name) {
    long long value = 0;
    ssize_t ret = read(fd, &value, sizeof(value));
    if (ret != (ssize_t)sizeof(value)) {
        fprintf(stderr, "[warn] read %s failed: %s\n", name, strerror(errno));
        return -1;
    }
    return value;
}

static int init_counters(PerfCounter *ins, PerfCounter *dtlb_miss, PerfCounter *llc_miss, PerfCounter *page_faults) {
    ins->name = "instructions";
    ins->fd = perf_open(PERF_TYPE_HARDWARE, PERF_COUNT_HW_INSTRUCTIONS, ins->name);

    dtlb_miss->name = "dtlb_load_miss";
    dtlb_miss->fd = perf_open(
        PERF_TYPE_HW_CACHE,
        PERF_COUNT_HW_CACHE_DTLB |
            (PERF_COUNT_HW_CACHE_OP_READ << 8) |
            (PERF_COUNT_HW_CACHE_RESULT_MISS << 16),
        dtlb_miss->name
    );

    llc_miss->name = "llc_read_miss";
    llc_miss->fd = perf_open(
        PERF_TYPE_HW_CACHE,
        PERF_COUNT_HW_CACHE_LL |
            (PERF_COUNT_HW_CACHE_OP_READ << 8) |
            (PERF_COUNT_HW_CACHE_RESULT_MISS << 16),
        llc_miss->name
    );
    if (llc_miss->fd < 0) {
        llc_miss->name = "cache_miss_fallback";
        llc_miss->fd = perf_open(PERF_TYPE_HARDWARE, PERF_COUNT_HW_CACHE_MISSES, llc_miss->name);
    }

    page_faults->name = "page_faults";
    page_faults->fd = perf_open(PERF_TYPE_SOFTWARE, PERF_COUNT_SW_PAGE_FAULTS, page_faults->name);

    return (ins->fd >= 0 && dtlb_miss->fd >= 0 && llc_miss->fd >= 0 && page_faults->fd >= 0) ? 0 : -1;
}

static void close_counter(PerfCounter *counter) {
    if (counter->fd >= 0) {
        close(counter->fd);
    }
}

static inline uint64_t xorshift64(uint64_t *state) {
    uint64_t x = *state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    return x;
}

static void run_memory_workload(char *buf, size_t len, size_t loops) {
    size_t pages = len / 4096;
    uint64_t rng = 0x9e3779b97f4a7c15ULL;

    for (size_t round = 0; round < loops; ++round) {
        for (size_t i = 0; i < pages; ++i) {
            size_t page_idx = (size_t)(xorshift64(&rng) % pages);
            size_t offset = page_idx * 4096;
            buf[offset] = (char)(buf[offset] + 1);
        }
    }
}

static double clamp01(double value) {
    if (value < 0.0) return 0.0;
    if (value > 1.0) return 1.0;
    return value;
}

static SampleMetrics compute_metrics(
    PerfCounter *ins,
    PerfCounter *dtlb_miss,
    PerfCounter *llc_miss,
    PerfCounter *page_faults,
    double sample_seconds
) {
    SampleMetrics m = {0};
    long long ins_now = read_counter(ins->fd, ins->name);
    long long dtlb_now = read_counter(dtlb_miss->fd, dtlb_miss->name);
    long long llc_now = read_counter(llc_miss->fd, llc_miss->name);
    long long pf_now = read_counter(page_faults->fd, page_faults->name);

    long long d_ins = ins_now - ins->last_value;
    long long d_dtlb = dtlb_now - dtlb_miss->last_value;
    long long d_llc = llc_now - llc_miss->last_value;
    long long d_pf = pf_now - page_faults->last_value;
    if (d_ins < 1) d_ins = 1;

    m.dtlb_mpki = (double)d_dtlb * 1000.0 / (double)d_ins;
    m.llc_mpki = (double)d_llc * 1000.0 / (double)d_ins;
    m.pf_per_sec = (double)d_pf / sample_seconds;

    /* Multi-feature score:
     * - dTLB miss pressure (weight 0.50)
     * - LLC miss pressure   (weight 0.30)
     * - page fault pressure (weight 0.20)
     */
    double n_dtlb = clamp01(m.dtlb_mpki / 8.0);
    double n_llc = clamp01(m.llc_mpki / 12.0);
    double n_pf = clamp01(m.pf_per_sec / 30.0);
    m.score = 0.50 * n_dtlb + 0.30 * n_llc + 0.20 * n_pf;

    ins->last_value = ins_now;
    dtlb_miss->last_value = dtlb_now;
    llc_miss->last_value = llc_now;
    page_faults->last_value = pf_now;
    return m;
}

static void maybe_switch_thp(
    ControllerState *state,
    char *buf,
    size_t len,
    const SampleMetrics *m,
    double high_threshold,
    double low_threshold
) {
    if (state->cooldown_left > 0) {
        state->cooldown_left--;
    }

    if (!state->thp_enabled) {
        if (m->score > high_threshold && state->cooldown_left == 0) {
            if (madvise(buf, len, MADV_HUGEPAGE) == 0) {
                state->thp_enabled = 1;
                state->cooldown_left = 5;
                state->stable_low_count = 0;
                printf("[switch] THP ON  score=%.3f (dtlb=%.3f, llc=%.3f, pf=%.2f/s)\n",
                    m->score, m->dtlb_mpki, m->llc_mpki, m->pf_per_sec);
            }
        }
        return;
    }

    if (m->score < low_threshold) {
        state->stable_low_count++;
    } else {
        state->stable_low_count = 0;
    }

    if (state->stable_low_count >= 3 && state->cooldown_left == 0) {
        if (madvise(buf, len, MADV_NOHUGEPAGE) == 0) {
            state->thp_enabled = 0;
            state->cooldown_left = 5;
            state->stable_low_count = 0;
            printf("[switch] THP OFF score=%.3f (dtlb=%.3f, llc=%.3f, pf=%.2f/s)\n",
                m->score, m->dtlb_mpki, m->llc_mpki, m->pf_per_sec);
        }
    }
}

int main(int argc, char **argv) {
    const size_t default_len = 256UL * 1024UL * 1024UL;  /* 256 MB */
    const int default_seconds = 60;
    const double sample_seconds = 1.0;
    const double high_threshold = 0.65;
    const double low_threshold = 0.35;
    size_t len = default_len;
    int run_seconds = default_seconds;

    if (argc >= 2) {
        long mb = atol(argv[1]);
        if (mb > 16) {
            len = (size_t)mb * 1024UL * 1024UL;
        }
    }
    if (argc >= 3) {
        int sec = atoi(argv[2]);
        if (sec > 5) {
            run_seconds = sec;
        }
    }

    signal(SIGINT, on_sigint);
    printf("[info] buffer=%zu MB, duration=%d s\n", len / 1024UL / 1024UL, run_seconds);

    char *buf = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (buf == MAP_FAILED) {
        fprintf(stderr, "[error] mmap failed: %s\n", strerror(errno));
        return 1;
    }

    PerfCounter ins = {.fd = -1}, dtlb = {.fd = -1}, llc = {.fd = -1}, pf = {.fd = -1};
    if (init_counters(&ins, &dtlb, &llc, &pf) != 0) {
        fprintf(stderr, "[error] perf counters unavailable. Check perf_event_paranoid and permissions.\n");
        munmap(buf, len);
        return 2;
    }

    ins.last_value = read_counter(ins.fd, ins.name);
    dtlb.last_value = read_counter(dtlb.fd, dtlb.name);
    llc.last_value = read_counter(llc.fd, llc.name);
    pf.last_value = read_counter(pf.fd, pf.name);

    ControllerState state = {.thp_enabled = 0, .cooldown_left = 0, .stable_low_count = 0};
    madvise(buf, len, MADV_NOHUGEPAGE);

    for (int t = 0; t < run_seconds && !g_stop; ++t) {
        run_memory_workload(buf, len, 2);
        struct timespec ts = {.tv_sec = 1, .tv_nsec = 0};
        nanosleep(&ts, NULL);

        SampleMetrics m = compute_metrics(&ins, &dtlb, &llc, &pf, sample_seconds);
        maybe_switch_thp(&state, buf, len, &m, high_threshold, low_threshold);

        printf("[t=%02d] score=%.3f dtlb_mpki=%.3f llc_mpki=%.3f pf_rate=%.2f/s state=%s\n",
            t + 1,
            m.score,
            m.dtlb_mpki,
            m.llc_mpki,
            m.pf_per_sec,
            state.thp_enabled ? "THP_ON" : "THP_OFF");
        fflush(stdout);
    }

    close_counter(&ins);
    close_counter(&dtlb);
    close_counter(&llc);
    close_counter(&pf);
    munmap(buf, len);
    return 0;
}
