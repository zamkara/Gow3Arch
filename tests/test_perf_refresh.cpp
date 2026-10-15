// SPDX-License-Identifier: GPL-2.0-or-later
#include "gow3_perf_stats.h"
#include <cassert>
#include <chrono>
#include <cstdio>
int main() {
    using namespace std::chrono;
    using Gow3PerfStats::RefreshTimer;
    const RefreshTimer::Clock::time_point start{};
    RefreshTimer timer;
    assert(timer.Due(start, 1000));
    for (int ms = 1; ms < 1000; ++ms) assert(!timer.Due(start + milliseconds(ms), 1000));
    assert(timer.Due(start + milliseconds(1000), 1000));
    assert(!timer.Due(start + milliseconds(1999), 1000));
    assert(timer.Due(start + milliseconds(2000), 1000));
    // A changed display setting takes effect immediately, then the new interval applies.
    assert(timer.Due(start + milliseconds(2100), 2000, true));
    assert(!timer.Due(start + milliseconds(4099), 2000));
    assert(timer.Due(start + milliseconds(4100), 2000));
    RefreshTimer minimum;
    assert(minimum.Due(start, 0));
    assert(!minimum.Due(start + milliseconds(999), 0));
    assert(minimum.Due(start + milliseconds(1000), 0));
    RefreshTimer maximum;
    assert(maximum.Due(start, 99999));
    assert(maximum.Due(start + seconds(10), 99999));
    std::puts("PASS: 1s/2s cadence, immediate settings changes and interval bounds");
}
