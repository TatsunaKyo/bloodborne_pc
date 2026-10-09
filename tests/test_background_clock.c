/* SPDX-License-Identifier: GPL-2.0-or-later
 * Exercise the actual guest clock implementation with deterministic host time.
 * Build with -ffunction-sections -fdata-sections -Wl,--gc-sections. */
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <x86intrin.h>
static uint64_t host_ns, paused_ns, fake_tsc;
static int test_clock(clockid_t id, struct timespec *value) {
    uint64_t ns = id == CLOCK_MONOTONIC ? host_ns : UINT64_C(50000000000);
    value->tv_sec = (time_t)(ns / 1000000000);
    value->tv_nsec = (long)(ns % 1000000000);
    return 0;
}
#define clock_gettime test_clock
#define __rdtsc() fake_tsc
#include "../src/runtime_kernel.c"
uint64_t runtime_background_paused_ns(void) { return paused_ns; }
int32_t *runtime_errno(void) { static int32_t error; return &error; }

int main(void) {
    process_start = (struct timespec){.tv_sec = 1, .tv_nsec = 900000000};
    host_ns = UINT64_C(2100000000);
    fake_tsc = host_ns;
    tsc_hz = 1000000000;
    GuestTimespec before, after, wall;
    assert(!clock_read(4, &before));
    assert(process_time() == 200000);
    assert(process_time_counter() == 200000000);
    const uint64_t ticks = read_tsc();
    host_ns += UINT64_C(10000000000);
    fake_tsc += UINT64_C(10000000000);
    paused_ns = UINT64_C(10000000000);
    assert(!clock_read(4, &after));
    assert(before.sec == after.sec && before.nsec == after.nsec);
    assert(process_time() == 200000 && process_time_counter() == 200000000);
    assert(read_tsc() == ticks && runtime_read_tsc() == ticks);
    assert(!clock_read(0, &wall) && wall.sec == 50 && wall.nsec == 0);
    host_ns += 16000000;
    fake_tsc += 16000000;
    assert(process_time() == 216000 && process_time_counter() == 216000000);
    assert(read_tsc() == ticks + 16000000);
    puts("PASS: guest clocks and GPU timestamps exclude background pause; wall clock unchanged; fractional-second elapsed time stays positive.");
}
