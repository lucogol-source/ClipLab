import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import launch


class LaunchTests(unittest.TestCase):
    def test_stop_never_signals_a_reused_pid_from_another_instance(self):
        with tempfile.TemporaryDirectory() as folder:
            record = Path(folder) / "server.json"
            record.write_text(json.dumps({"pid": 12345, "instance": "old-instance"}))
            current = {"application": "cliplab", "app_root": str(launch.ROOT), "data_dir":str(launch.DATA), "pid": 12345, "instance_id": "new-instance"}
            with patch.object(launch, "RECORD", record), patch.object(launch, "health", return_value=current), patch.object(launch.os, "kill") as kill:
                with self.assertRaisesRegex(RuntimeError, "riavviato"):
                    launch.stop()
                kill.assert_not_called()

    def test_finder_finds_nvm_node_without_a_shell_path(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            node = home / ".nvm/versions/node/v24.0.0/bin/node"
            node.parent.mkdir(parents=True)
            node.write_text("#!/bin/sh\nexit 0\n")
            node.chmod(0o755)
            real_is_file = Path.is_file
            def only_fixture(path):
                return path == node and real_is_file(path)
            with patch.object(engine.shutil, "which", return_value=None), patch.object(engine.Path, "home", return_value=home), patch.object(Path, "is_file", only_fixture):
                self.assertEqual(engine.javascript_runtime(), {"node": {"path": str(node)}})


if __name__ == "__main__":
    unittest.main()
