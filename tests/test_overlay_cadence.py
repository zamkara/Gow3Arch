"""Compile and exercise the actual overlay formatter with a deterministic clock."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
CXX = shutil.which('c++') or shutil.which('clang++')


@unittest.skipUnless(CXX, 'A C++ compiler is required')
class OverlayCadenceTests(unittest.TestCase):
    def test_displayed_fps_and_frametime_stay_fixed_until_interval_expires(self):
        source = (ROOT/'gpu/shim/gow3_overlay.cpp').read_text()
        start = source.index('std::string OverlayText() {')
        end = source.index('\n}\n', start)+2
        # Keep production logic; replace only the clock read so no real sleep is needed.
        formatter = source[start:end].replace('P::RefreshTimer::Clock::now()', 'fake_now')
        program = '''#include "gow3_perf_stats.h"
#include "gow3_settings.h"
#include <cassert>
#include <cstdio>
namespace Gow3Settings { Values& Get() { static Values values; return values; } }
namespace Gow3PerfStats {
Sample Latest() { return {}; }
void Start(const Vulkan::Instance&) {}
}
float frame_ms_avg = 10.0f;
const Vulkan::Instance* overlay_instance = nullptr;
const char* UpscalerLabel(int) { return "Native"; }
Gow3PerfStats::RefreshTimer::Clock::time_point fake_now{};
''' + formatter + '''
int main() {
    using namespace std::chrono;
    auto& settings = Gow3Settings::Get();
    const auto start = fake_now;
    const auto first = OverlayText();
    assert(first.find("100 FPS") != std::string::npos);
    assert(first.find("10.0 ms") != std::string::npos);
    for (int ms = 1; ms < 1000; ++ms) {
        fake_now = start + milliseconds(ms);
        frame_ms_avg = 20.0f + ms;
        assert(OverlayText() == first);
    }
    frame_ms_avg = 20.0f;
    fake_now = start + milliseconds(1000);
    assert(OverlayText().find("50 FPS") != std::string::npos);
    assert(OverlayText().find("20.0 ms") != std::string::npos);
    settings.overlay_interval_ms = 2000;
    fake_now = start + milliseconds(1500);
    frame_ms_avg = 40.0f;
    const auto second = OverlayText();
    assert(second.find("25 FPS") != std::string::npos);
    frame_ms_avg = 100.0f;
    fake_now = start + milliseconds(3499);
    assert(OverlayText() == second);
    fake_now = start + milliseconds(3500);
    assert(OverlayText().find("10 FPS") != std::string::npos);
    assert(OverlayText().find("100.0 ms") != std::string::npos);
    std::puts("PASS: production FPS and frametime text obey 1s and 2s intervals");
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            cpp = path/'overlay.cpp';cpp.write_text(program)
            binary = path/'overlay-test'
            subprocess.run([CXX, '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            '-I'+str(ROOT/'gpu/shim'), str(cpp), '-o', str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn('production FPS and frametime text obey', result.stdout)
