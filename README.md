# USBPhone Control

[![CI](https://github.com/obsessed-star/usbphone-control/actions/workflows/ci.yml/badge.svg)](https://github.com/obsessed-star/usbphone-control/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Transport](https://img.shields.io/badge/transport-USB%20ADB-3DDC84)

**A handwritten Android control toolkit for the observe → act → observe loop.**

Read the screen, choose an element or pixel coordinate, perform one action, then inspect a new capture. Every action is bound to a short-lived, single-use observation ID. The core has no Python runtime dependencies and does not require Appium, scrcpy, root or a cloud control service.

Use it as a Python package, a JSON CLI or an optional MCP stdio server. The separate [GraphPilot agent](https://github.com/obsessed-star/graphpilot-agent) adds LangGraph reasoning and human approval without coupling this toolkit to a model provider.

## Capabilities

| Observe | Act | Guard |
|---|---|---|
| USB device discovery | Tap a coordinate or UI element | Explicit USB transport and pinned serial |
| PNG screenshot and dimensions | Swipe / long press via equal endpoints | Coordinate and duration validation |
| UI labels, IDs, bounds and centers | Printable ASCII typing | Remote-shell argument quoting |
| Timestamped capture artifacts | Home, Back, Enter, Backspace, Recents | Fresh, single-use observation IDs |
| Post-action screen capture | Launch a validated app package | Unknown outcomes require observation |

## Install

```bash
git clone https://github.com/obsessed-star/usbphone-control.git
cd usbphone-control
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -e .
```

Install official [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools). Connect an authorized Android phone using a data-capable USB cable, enable USB debugging and accept its RSA prompt on the device. The toolkit does not perform those approvals for you.

```powershell
# Only if adb is not already on PATH:
$env:ADB_PATH = 'C:\Android\platform-tools\adb.exe'
python -m usbphone.cli devices
python -m usbphone.cli observe
```

On Linux/macOS use `export ADB_PATH=/path/to/adb`. Choose `--serial SERIAL` before the subcommand if multiple USB phones are connected. TCP devices, emulators, unauthorized phones and ambiguous selection are rejected.

## Python example

```python
from usbphone.controller import Phone

phone = Phone(output="captures")
before = phone.observe()
print(before["elements"])  # Inspect labels, bounds and centers first.

# This is a user-authorized action. MCP/agent hosts must collect their own approval.
result = phone.act("key", before["observation_id"], key="HOME")
if result["verified"]:
    print(result["observation"]["screenshot"])
# verified means a new capture exists; inspect it to evaluate the intended outcome.
```

See [the runnable observation-only example](examples/inspect_phone.py) and [the transport design](docs/design.md).

## JSON CLI

`observe` returns an `observation_id` and capture paths. Use that exact ID within 30 seconds:

```bash
python -m usbphone.cli act key --observation CAPTURE_ID --params '{"key":"HOME"}'
```

For PowerShell, avoid native JSON quoting issues with Python's argument list:

```powershell
$capture = python -m usbphone.cli observe | ConvertFrom-Json
python -c 'import subprocess,sys,json; subprocess.run([sys.executable,"-m","usbphone.cli","act","key","--observation",sys.argv[1],"--params",json.dumps({"key":"HOME"})],check=True)' $capture.observation_id
```

Successful commands emit JSON to stdout. Actionable errors emit JSON to stderr with exit status 2. A transport timeout consumes the old ID because the action may already have occurred. Capture files stay local and are ignored by Git.

## MCP server

### Browser tasks and documents

`phone.act("open_url", observation_id, url="https://example.org", package="com.android.chrome")`
opens the URL on the phone and returns the next screen. Omit `package` to use Android's default handler.
Only HTTP(S) URLs without embedded credentials are accepted. Capture/action freshness rules still apply.

```bash
python -m usbphone.cli downloads
python -m usbphone.cli export-download certificate.pdf
```

These read only `/sdcard/Download`. Export saves a generated filename under the local capture directory,
checks a 20 MiB size limit and compares device/local SHA-256. `transfer_verified=true` proves matching
bytes; `content_verified=false` does not certify document identity or authenticity. Rejects symlinks,
paths, empty files and changing/incomplete bytes. An old file is not evidence of a new download.

The planner lives in the separate [GraphPilot agent](https://github.com/obsessed-star/graphpilot-agent).
It can use these primitives for goal-driven application/document tasks. Real-site/device validation
is pending; synthetic workflow fixtures do not demonstrate arbitrary website compatibility.

```bash
python -m pip install -e ".[mcp]"
python -m usbphone.mcp_server
```

Configure an MCP client with [examples/mcp.json](examples/mcp.json), replacing the interpreter and ADB paths.
The stdio server exposes `phone_observe` (text + image), `phone_act` (one action + new capture),
`phone_list_downloads` and `phone_export_download`. It opens no HTTP port. **The host must authorize
actions and export writes**; annotations are hints, not an access-control system.

## Verify

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
ruff check .
ruff format --check .
python -m pytest -q
python -m build
```

Tests cover device selection, remote quoting, action bounds, stale/replayed captures, disconnects, unknown outcomes, CLI errors and a real MCP stdio handshake. Hardware is replaced by a labeled test fixture, not presented as a live phone demonstration. CI runs on Windows/Linux and Python 3.11/3.14.

[Validation evidence](docs/validation.md) · [Design and failure semantics](docs/design.md) · [Security](SECURITY.md) · [Türkçe başlangıç](docs/tr.md)

## Current scope

Android USB only. Stock ADB typing is limited to printable ASCII without `%`; arbitrary Unicode and a native IME companion are not implemented. Secure screens can block capture, and some apps expose little accessibility data. A real USB phone was not available for the initial hardware validation; see the validation record before relying on a device-specific workflow.

Development uses AI assistance. The transport implementation is written in this repository rather than delegated to a phone-automation framework. Commit history records actual development steps without backdating.
