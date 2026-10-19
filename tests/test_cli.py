import json
import subprocess
import sys


def test_missing_adb_is_actionable_json_error():
    result = subprocess.run(
        [sys.executable, "-m", "usbphone.cli", "--adb", "this-executable-does-not-exist-7392", "devices"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "ADB not found" in json.loads(result.stderr)["error"]
