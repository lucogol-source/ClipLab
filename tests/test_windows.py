"""Portable regression tests; Windows branches are simulated on macOS/Linux."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from filelock import FileLock,Timeout
import engine
import platform_support
import server
import windows_setup


class WindowsSupportTests(unittest.TestCase):
    def test_windows_detaches_server_and_hides_worker_consoles(self):
        with patch('platform_support.is_windows',return_value=True):
            self.assertEqual(platform_support.process_options(True),{'creationflags':0x8|0x200})
            self.assertEqual(platform_support.process_options(),{'creationflags':0x08000000})
        with patch('platform_support.is_windows',return_value=False):
            self.assertEqual(platform_support.process_options(True),{'start_new_session':True})
            self.assertEqual(platform_support.process_options(),{})

    def test_windows_ffmpeg_uses_exe_copy_without_symlink_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);binary=root/'bundled-ffmpeg.exe';binary.write_bytes(b'EXE fixture')
            with patch('platform_support.is_windows',return_value=True),patch.object(Path,'symlink_to',side_effect=AssertionError('No symlink on Windows')):
                target=platform_support.ffmpeg_tool(binary,root/'tools')
                self.assertEqual(target.name,'ffmpeg.exe')
                self.assertEqual(target.read_bytes(),binary.read_bytes())
                binary.write_bytes(b'updated executable fixture')
                platform_support.ffmpeg_tool(binary,root/'tools')
                self.assertEqual(target.read_bytes(),binary.read_bytes())

    def test_portable_lock_prevents_second_engine_and_releases(self):
        with tempfile.TemporaryDirectory() as temp:
            path=str(Path(temp)/'engine.lock')
            a,b=FileLock(path),FileLock(path)
            with a:
                with self.assertRaises(Timeout):b.acquire(timeout=0)
            with b.acquire(timeout=0):self.assertTrue(b.is_locked)

    def test_controlled_shutdown_uses_server_flag_not_unix_signals(self):
        instance=SimpleNamespace(should_exit=False)
        original=getattr(server.app.state,'server',None)
        server.app.state.server=instance
        try:
            with patch('os.kill',side_effect=AssertionError('No process signals')):
                server.request_shutdown()
            self.assertTrue(instance.should_exit)
        finally:server.app.state.server=original

    def test_windows_frontend_names_cmd_launcher(self):
        with patch('server.is_windows',return_value=True):html=server.index().body.decode('utf-8')
        self.assertIn('Avvia ClipLab.cmd',html)
        self.assertNotIn('__CLIPLAB_LAUNCH_EXT__',html)
        self.assertNotIn('Avvia ClipLab.command',html)

    def test_local_node_precedes_older_path_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);local=root/'.tools/node.exe';local.parent.mkdir();local.write_bytes(b'fixture');local.chmod(0o755)
            with patch('engine.ROOT',root),patch('engine.is_windows',return_value=True),patch('engine.shutil.which',return_value='old-node-from-path'):
                self.assertEqual(engine.javascript_runtime(),{'node':{'path':str(local)}})

    def test_project_names_and_captions_are_utf8(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'projects').mkdir()
            with patch('engine.PROJECTS',root/'projects'):
                p=engine.new_project({},'Città 東京 🎬')
                raw=(engine.project_dir(p['id'])/'project.json').read_bytes()
                self.assertEqual(json.loads(raw.decode('utf-8'))['title'],'Città 東京 🎬')
                self.assertEqual(engine.read_project(p['id'])['title'],'Città 東京 🎬')
                engine.EVENTS.pop(p['id'],None)


class WindowsRuntimeTests(unittest.TestCase):
    def test_download_extracts_only_expected_executable_and_license(self):
        filename='node-v22.23.5-win-x64.zip';prefix=filename.removesuffix('.zip')+'/'
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr(prefix+'node.exe',b'Windows executable fixture')
            z.writestr(prefix+'LICENSE',b'MIT license fixture')
            z.writestr('../escape.txt',b'must not be extracted')
        digest=__import__('hashlib').sha256(data.getvalue()).hexdigest()
        response=MagicMock(text=digest+'  '+filename+'\n')
        def download(url,target,sha):
            self.assertEqual(sha,digest)
            self.assertEqual(url,windows_setup.NODE_BASE+filename)
            target.write_bytes(data.getvalue())
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch('windows_setup.requests.get',return_value=response),patch('windows_setup.download',side_effect=download),patch('windows_setup.node_version',return_value='v22.23.5'):
                node=windows_setup.ensure_node(root)
            self.assertEqual(node.read_bytes(),b'Windows executable fixture')
            self.assertTrue((root/'.tools/NODE-LICENSE.txt').exists())
            self.assertFalse((root/'escape.txt').exists())
            self.assertFalse((root/'.tools/node-runtime.zip').exists())

    def test_node_checks_version_before_reusing_installation(self):
        for version,works in [('v22.23.5\n',True),('v20.0.0\n',False),('unrecognized',False)]:
            with self.subTest(version=version),patch('windows_setup.subprocess.run',return_value=SimpleNamespace(stdout=version)):
                if works:self.assertEqual(windows_setup.node_version('node.exe'),'v22.23.5')
                else:
                    with self.assertRaises(ValueError):windows_setup.node_version('node.exe')

    def test_unexpected_download_manifest_is_rejected(self):
        response=MagicMock(text='bad  ../../escape.zip')
        with tempfile.TemporaryDirectory() as temp,patch('windows_setup.requests.get',return_value=response),patch('windows_setup.download') as download:
            with self.assertRaises(ValueError):windows_setup.ensure_node(Path(temp))
            download.assert_not_called()


if __name__=='__main__':unittest.main()
