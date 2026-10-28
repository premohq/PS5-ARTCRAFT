import json
import tempfile
import unittest
from pathlib import Path

from artcraft_ps5 import deploy, edition, stage
from tests import fixtures

REMOTE_MANIFEST = '/data/artcraft/prefixes/artcraft/' + deploy.REMOTE_MANIFEST


class Settings(unittest.TestCase):
    def test_env_file_then_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / '.env'
            env.write_text('# the console\nexport PS5_HOST="192.168.1.50"\nFTP_PORT=1337\n')
            console = deploy.console_settings(env_file=env, environ={})
            self.assertEqual((console.host, console.port, console.user), ('192.168.1.50', 1337, 'anonymous'))
            console = deploy.console_settings(env_file=env, environ={'PS5_HOST': '10.0.0.9'})
            self.assertEqual(console.host, '10.0.0.9')
            self.assertEqual(deploy.console_settings('10.1.2.3', 2121, env, environ={}).port, 2121)

    def test_needs_an_address(self):
        with self.assertRaisesRegex(edition.EditionError, 'PS5_HOST'):
            deploy.console_settings(environ={})

    def test_address_is_masked(self):
        self.assertEqual(deploy.Console('192.168.1.50').masked, '192.*.*.50:2121')
        self.assertEqual(deploy.Console('ps5.lan', 9).masked, 'ps***:9')


class Deploy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        e = edition.load(fixtures.make_edition(tmp / 'edition', tmp / 'downloads'), need_lock=True)
        session, wallpaper = tmp / 'session.exe', tmp / 'wall.bmp'
        session.write_bytes(b'MZ')
        wallpaper.write_bytes(b'BM')
        self.staged = tmp / 'staged'
        stage.stage(e, tmp / 'downloads', self.staged, session, wallpaper, installed_at=1, say=lambda _: None)
        self.manifest = json.loads((self.staged / 'manifest.json').read_text())
        self.console = deploy.Console('192.168.1.50')

    def tearDown(self):
        self.tmp.cleanup()

    def deploy(self, ftp, **options):
        return deploy.deploy(self.staged, self.console, connect=ftp, say=lambda _: None, **options)

    def test_sends_everything_then_only_what_changed(self):
        ftp = fixtures.FakeFTP()
        sent = self.deploy(ftp)
        self.assertEqual(len(sent), len(self.manifest['files']))
        self.assertFalse(ftp.self_on)
        for entry in self.manifest['files']:
            self.assertEqual(ftp.files[entry['path']], (self.staged / entry['path'].lstrip('/')).read_bytes())
        self.assertFalse([path for path in ftp.files if path.endswith('.upload')])
        remote = json.loads(ftp.files[REMOTE_MANIFEST])
        self.assertEqual(len(remote['files']), len(self.manifest['files']))

        self.assertEqual(self.deploy(ftp), [])
        self.assertEqual(len(self.deploy(ftp, force=True)), len(self.manifest['files']))

        session_ini = next(e for e in self.manifest['files'] if e['path'].endswith('session.ini'))
        changed = dict(json.loads(ftp.files[REMOTE_MANIFEST]))
        changed['files'][session_ini['path']] = '0' * 64
        ftp.files[REMOTE_MANIFEST] = json.dumps(changed).encode()
        self.assertEqual([e['path'] for e in self.deploy(ftp)], [session_ini['path']])

    def test_files_go_in_through_a_temporary_name(self):
        ftp = fixtures.FakeFTP()
        self.deploy(ftp)
        stored = [path for path in ftp.stored if path != REMOTE_MANIFEST]
        self.assertTrue(stored and all(path.rsplit('/', 1)[1].startswith('.') and path.endswith('.upload')
                                       for path in stored))

    def test_dry_run_connects_to_nothing(self):
        sent = deploy.deploy(self.staged, None, dry_run=True, say=lambda _: None,
                             connect=lambda: self.fail('connected'))
        self.assertEqual(len(sent), len(self.manifest['files']))

    def test_never_writes_c_windows(self):
        self.manifest['files'].append({'path': '/data/artcraft/prefixes/artcraft/drive_c/windows/x.dll',
                                       'size': 1, 'sha256': '0' * 64})
        (self.staged / 'manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(edition.EditionError, 'wineboot'):
            self.deploy(fixtures.FakeFTP())


if __name__ == '__main__':
    unittest.main()
