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

    def test_launcher_identifies_native_build_and_handles_missing_metadata(self):
        sys.path.insert(0, str(ROOT / 'launcher'))
        sys.path.insert(0, str(ROOT / 'scripts'))
        import gow3_launcher_win as launcher
        with tempfile.TemporaryDirectory() as folder, patch.object(launcher, 'PORT_DIR', Path(folder)):
            self.assertEqual(launcher.build_label(), 'v'+launcher.VERSION)
            info=Path(folder)/'build-info.json'
            info.write_text(json.dumps({'commit':'a'*40, 'package_version':'2.3.0.r400-1'}))
            self.assertEqual(launcher.build_label(), 'v'+launcher.VERSION+' · Arch '+'a'*12)
            info.write_text('broken json')
            self.assertEqual(launcher.build_label(), 'v'+launcher.VERSION)

    def test_only_native_release_workflow_is_enabled(self):
        workflows = list((ROOT / '.github/workflows').glob('*.yml'))
        self.assertEqual([p.name for p in workflows], ['archlinux.yml'])
        workflow = workflows[0].read_text()
        self.assertIn('needs: [sync, smoke]', workflow)
        self.assertIn('sha256sum --check SHA256SUMS', workflow)
        self.assertNotIn('windows-2025', workflow)

    def test_source_cache_does_not_collide_with_launcher(self):
        recipe = (ROOT / 'packaging/arch/PKGBUILD').read_text()
        self.assertIn('gow3-source::git+', recipe)
        self.assertNotIn('"gow3::git+', recipe)

    def test_native_wrapper_does_not_write_bytecode_to_system_directory(self):
        wrapper = (ROOT / 'packaging/arch/gow3').read_text()
        self.assertIn('export PYTHONDONTWRITEBYTECODE=1', wrapper)


class UpstreamSyncTests(unittest.TestCase):
    def test_code_updates_keep_fork_policy_and_remove_added_upstream_workflow(self):
        self.exercise(conflict=False)

    def test_conflicting_code_aborts_and_keeps_original_head(self):
        self.exercise(conflict=True)

    def exercise(self, conflict):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);upstream=root/'upstream';fork=root/'fork'
            def git(where,*args,check=True):
                return subprocess.run(['git','-C',str(where),*args],check=check,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            upstream.mkdir();git(upstream,'init','-b','main')
            git(upstream,'config','user.name','Test');git(upstream,'config','user.email','test@example.invalid')
            for name,text in [('README.md','upstream original'),('README.es.md','original'),('README.pt-BR.md','original'),('.github/workflows/old.yml','old'),('packaging/base','original'),('docs/UPSTREAM.md','original'),('tests/test_arch_packaging.py','original'),('src/runtime.c','base')]:
                path=upstream/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text+'\n')
            git(upstream,'add','.');git(upstream,'commit','-m','base')
            subprocess.run(['git','clone',str(upstream),str(fork)],check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            git(fork,'config','user.name','Test');git(fork,'config','user.email','test@example.invalid')
            (fork/'README.md').write_text('native Arch fork\n')
            (fork/'packaging/base').write_text('native package\n')
            if conflict:(fork/'src/runtime.c').write_text('fork code\n')
            git(fork,'add','.');git(fork,'commit','-m','fork policy')
            before=git(fork,'rev-parse','HEAD').stdout.strip()
            (upstream/'README.md').write_text('new AppImage instructions\n')
            (upstream/'packaging/base').write_text('Windows package\n')
            (upstream/'.github/workflows/windows.yml').write_text('new upstream runner\n')
            (upstream/'src/runtime.c').write_text('fixed upstream code\n')
            git(upstream,'add','.');git(upstream,'commit','-m','upstream fixes')
            result=subprocess.run(['bash',str(ROOT/'packaging/arch/sync-upstream.sh'),str(upstream),'main'],cwd=fork,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            self.assertEqual((fork/'README.md').read_text(),'native Arch fork\n')
            self.assertEqual((fork/'packaging/base').read_text(),'native package\n')
            self.assertFalse((fork/'.github/workflows/windows.yml').exists())
            self.assertEqual(git(fork,'status','--porcelain').stdout,'')
            if conflict:
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertEqual(git(fork,'rev-parse','HEAD').stdout.strip(),before)
                self.assertEqual((fork/'src/runtime.c').read_text(),'fork code\n')
            else:
                self.assertEqual(result.returncode,0,result.stdout)
                self.assertEqual((fork/'src/runtime.c').read_text(),'fixed upstream code\n')
                second=subprocess.run(['bash',str(ROOT/'packaging/arch/sync-upstream.sh'),str(upstream),'main'],cwd=fork,capture_output=True,text=True)
                self.assertEqual(second.returncode,0,second.stdout+second.stderr)
                self.assertIn('already synchronized',second.stdout)
