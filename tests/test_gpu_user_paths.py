"""Execute the production GPU path initializer without linking the renderer."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
CXX = shutil.which('c++') or shutil.which('clang++')


@unittest.skipUnless(CXX, 'A C++ compiler is required')
class GpuUserPathsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        # Compile the actual static initializer and its actual path declarations.
        # Renderer/logging functions are intentionally not linked into this focused test.
        source = (ROOT / 'gpu/shadps4/common/path_util.cpp').read_text()
        initializer = source.split('static auto UserPaths = [] {', 1)[1].split('}();', 1)[0]
        program = directory / 'paths.cpp'
        program.write_text('''#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <unordered_map>
#include "common/path_util.h"
namespace Common::FS {
namespace fs = std::filesystem;
static auto UserPaths = [] {''' + initializer + '''}();
}
int main() {
    for (const auto& [kind, path] : Common::FS::UserPaths) {
        if (!std::filesystem::is_directory(path)) return 1;
    }
    std::cout << Common::FS::UserPaths.at(Common::FS::PathType::UserDir) << '\\n';
}
''')
        cls.binary = directory / 'paths'
        subprocess.run([CXX, '-std=c++17', '-I'+str(ROOT / 'gpu/shadps4'),
                        str(program), '-o', str(cls.binary)], check=True, capture_output=True, text=True)

    def check_initialization(self, custom_xdg):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / 'home'
            home.mkdir()
            env = dict(os.environ)
            env.pop('XDG_DATA_HOME', None)
            env.pop('GOW3_GPU_USER_DIR', None)
            env['HOME'] = str(home)
            if custom_xdg:
                env['XDG_DATA_HOME'] = str(root / 'missing/parent/data')
                expected = root / 'missing/parent/data/shadPS4'
            else:
                expected = home / '.local/share/shadPS4'
            self.assertFalse(expected.parent.exists())
            result = subprocess.run([str(self.binary)], env=env, cwd=root,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertTrue((expected / 'cache').is_dir())
            self.assertTrue((expected / 'custom_trophy/Notice.txt').is_file())
            self.assertFalse((root / 'user').exists())

    def test_fresh_home_without_local_share(self):
        self.check_initialization(custom_xdg=False)

    def test_custom_xdg_without_parent_directories(self):
        self.check_initialization(custom_xdg=True)
