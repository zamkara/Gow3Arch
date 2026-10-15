"""Native packaging regression tests; installer tests never invoke real pacman/sudo."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import subprocess
import sys
import tempfile
import termios
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class InstallerTests(unittest.TestCase):
    def run_installer(self, installed='', corrupt=False, missing=False):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            binary = work / 'bin'
            binary.mkdir()
            package = 'gow3-2.0-1-x86_64.pkg.tar.zst'
            (work / package).write_bytes(b'native test package')
            digest = '0' * 64 if corrupt else hashlib.sha256((work / package).read_bytes()).hexdigest()
            (work / 'SHA256SUMS').write_text(f'{digest}  {package}\n')
            assets = [] if missing else [{'name': n, 'browser_download_url':
                f'https://github.com/zamkara/Gow3Arch/releases/download/arch-test/{n}'}
                for n in (package, 'SHA256SUMS')]
            (work / 'release.json').write_text(json.dumps({'assets': assets}))
            (work / 'installed').write_text(installed)
            dispatcher = '''import os,pathlib,shutil,sys
root=pathlib.Path(os.environ['FIXTURE']);args=sys.argv[1:];tool=pathlib.Path(sys.argv[0]).name
if tool=='curl':
    url=next(a for a in args if a.startswith('https://'))
    source='release.json' if url.endswith('/latest') else url.rsplit('/',1)[-1]
    shutil.copyfile(root/source,args[args.index('-o')+1])
elif tool=='pacman':
    if args[0]=='-Qp':print('gow3 2.0-1')
    elif args[0]=='-Q':
        version=(root/'installed').read_text()
        if not version:sys.exit(1)
        print('gow3 '+version)
    elif args[0]=='-U':(root/'transaction').write_text(' '.join(args))
    else:raise SystemExit('Unexpected pacman arguments: '+repr(args))
elif tool=='vercmp':print((args[0]>args[1])-(args[0]<args[1]))
elif tool=='id':print('0')
elif tool=='sudo':raise SystemExit('Real privilege escalation is forbidden in tests')
'''
            for tool in ('curl', 'pacman', 'vercmp', 'id', 'sudo'):
                path = binary / tool
                path.write_text(f'#!{sys.executable}\n' + dispatcher)
                path.chmod(0o755)
            master, slave = pty.openpty()
            def terminal():
                os.setsid()
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)
            try:
                done = subprocess.run(['bash', str(ROOT / 'packaging/arch/install.sh')],
                    stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    preexec_fn=terminal, timeout=15,
                    env={**os.environ, 'PATH': str(binary)+os.pathsep+os.environ['PATH'],
                         'FIXTURE': str(work)})
            finally:
                os.close(master)
                os.close(slave)
            return done, (work / 'transaction').exists()

    def test_first_install_uses_verified_package(self):
        done, installed = self.run_installer()
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertTrue(installed)
        self.assertIn(': OK', done.stdout)

    def test_same_command_upgrades_older_installation(self):
        done, installed = self.run_installer(installed='1.0-1')
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertTrue(installed)

    def test_current_and_newer_versions_skip_transaction(self):
        for version in ('2.0-1', '3.0-1'):
            done, installed = self.run_installer(installed=version)
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertFalse(installed)
            self.assertIn('already current', done.stdout)

    def test_corrupt_package_never_reaches_pacman(self):
        done, installed = self.run_installer(corrupt=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse(installed)

    def test_incomplete_release_never_reaches_pacman(self):
        done, installed = self.run_installer(missing=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse(installed)


class NativeIntegrationTests(unittest.TestCase):
    def test_steam_uses_native_wrapper_with_user_data_directory(self):
        sys.path.insert(0, str(ROOT / 'launcher'))
        sys.path.insert(0, str(ROOT / 'scripts'))
        import gow3_launcher_win as launcher
        with patch.dict(os.environ, {'GOW3_NATIVE_LAUNCHER': '/usr/bin/gow3'}):
            self.assertEqual(launcher.steam_launch_command(),
                             ('/usr/bin/gow3', '--play', str(launcher.DATA_DIR)))

    def test_only_native_release_workflow_is_enabled(self):
        workflows = list((ROOT / '.github/workflows').glob('*.yml'))
        self.assertEqual([p.name for p in workflows], ['archlinux.yml'])
        workflow = workflows[0].read_text()
        self.assertIn('needs: smoke', workflow)
        self.assertIn('sha256sum --check SHA256SUMS', workflow)
        self.assertNotIn('windows-2025', workflow)
