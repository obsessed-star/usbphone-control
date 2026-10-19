import shlex
import struct
import subprocess

import pytest

from usbphone.adb import ADB, Device, PhoneError, parse_devices
from usbphone.controller import Phone, parse_ui

XML = b'''<hierarchy><node text="Settings" clickable="true" enabled="true"
 resource-id="android:id/title" bounds="[0,0][200,100]"/>
 <node text="secret" password="true" bounds="[0,100][200,200]"/></hierarchy>'''


class FakeADB:
    def __init__(self):
        self.calls = []
        self.device = Device("usb-001", "device", True, "Fixture")
        self.fail_capture = False
        self.fail_action = False

    def select(self, serial=None):
        if serial and serial != self.device.serial:
            raise PhoneError("Selected phone disconnected")
        return self.device

    def run(self, *args):
        self.calls.append(args)
        if self.fail_capture:
            raise PhoneError("Capture failed")
        return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1080, 1920)

    def shell(self, serial, *args):
        self.calls.append((serial, *args))
        if args[0] == "cat":
            return XML
        if self.fail_action and args[0] == "input":
            raise PhoneError("Timeout: outcome unknown")
        return b""


@pytest.fixture
def phone(tmp_path):
    return Phone(FakeADB(), output=tmp_path)


def test_usb_marker_excludes_tcp_and_emulator():
    devices = parse_devices("""List of devices attached
ABC device usb:1-2 product:foo model:Pixel transport_id:1
192.168.1.4:5555 device model:Pixel transport_id:2
emulator-5554 device model:sdk transport_id:3
DEF unauthorized usb:1-3 transport_id:4
""")
    assert [d.serial for d in devices if d.usb] == ["ABC", "DEF"]
    assert devices[-1].state == "unauthorized"


@pytest.mark.parametrize("listing", ["", "TCP device model:P", "A device usb:1\nB device usb:2"])
def test_device_selection_fails_closed(monkeypatch, listing):
    adb = ADB()
    monkeypatch.setattr(adb, "run", lambda *a: listing.encode())
    with pytest.raises(PhoneError, match="exactly one USB"):
        adb.select()


def test_unauthorized_device_has_useful_error(monkeypatch):
    adb = ADB()
    monkeypatch.setattr(adb, "run", lambda *a: b"A unauthorized usb:1")
    with pytest.raises(PhoneError, match="RSA"):
        adb.select("A")


def test_remote_shell_quotes_metacharacters(monkeypatch):
    adb = ADB()
    calls = []
    monkeypatch.setattr(adb, "run", lambda *args: calls.append(args) or b"")
    text = "hello;$(id)'&"
    adb.shell("A", "input", "text", text)
    assert shlex.split(calls[0][-1]) == ["input", "text", text]
    assert calls[0][:3] == ("-s", "A", "shell")


def test_host_never_uses_shell(monkeypatch):
    def run(argv, **kwargs):
        assert argv == ["adb", "devices", "-l"]
        assert not kwargs.get("shell")
        return subprocess.CompletedProcess(argv, 0, b"", b"")
    monkeypatch.setattr(subprocess, "run", run)
    assert ADB("adb").devices() == []


def test_ui_filters_password_and_centers():
    assert parse_ui(XML) == [{
        "index": 0, "text": "Settings", "description": "", "resource_id": "android:id/title",
        "bounds": [0, 0, 200, 100], "center": [100, 50], "clickable": True, "enabled": True,
    }]


def test_observe_action_observe_and_no_replay(phone, monkeypatch):
    monkeypatch.setattr("usbphone.controller.time.sleep", lambda _: None)
    first = phone.observe()
    result = phone.act("tap_element", first["observation_id"], index=0)
    assert ("usb-001", "input", "tap", "100", "50") in phone.adb.calls
    assert result["verified"]
    assert result["observation"]["observation_id"] != first["observation_id"]
    with pytest.raises(PhoneError, match="Stale"):
        phone.act("key", first["observation_id"], key="HOME")
    with pytest.raises(PhoneError, match="consumed"):
        Phone(phone.adb, output=phone.output).restore(first["observation_id"])


@pytest.mark.parametrize("action,params", [
    ("tap", {"x": -1, "y": 0}), ("tap", {"x": 1080, "y": 0}),
    ("tap", {"x": True, "y": 0}), ("tap_element", {"index": -1}),
    ("type_text", {"text": "Türkçe"}), ("type_text", {"text": "%s"}),
    ("key", {"key": "POWER"}), ("launch", {"package": "com.foo;rm -rf /"}),
    ("swipe", {"x1": 0, "y1": 0, "x2": 10, "y2": 10, "duration_ms": 0}),
])
def test_invalid_actions_do_not_dispatch(phone, action, params):
    before = phone.observe()
    n = len(phone.adb.calls)
    with pytest.raises(PhoneError):
        phone.act(action, before["observation_id"], **params)
    assert len(phone.adb.calls) == n


def test_expired_observation(phone):
    first = phone.observe()
    phone._observed_at -= 31
    with pytest.raises(PhoneError, match="Stale"):
        phone.act("key", first["observation_id"], key="HOME")


def test_disconnect_never_retargets_another_phone(phone):
    first = phone.observe()
    phone.adb.device = Device("other-phone", "device", True, "Other")
    with pytest.raises(PhoneError, match="disconnected"):
        phone.act("key", first["observation_id"], key="HOME")


def test_dispatch_timeout_consumes_observation(phone):
    first = phone.observe()
    phone.adb.fail_action = True
    with pytest.raises(PhoneError, match="unknown"):
        phone.act("key", first["observation_id"], key="HOME")
    with pytest.raises(PhoneError, match="Stale"):
        phone.act("key", first["observation_id"], key="HOME")


def test_post_action_capture_failure_is_not_success(phone, monkeypatch):
    first = phone.observe()
    monkeypatch.setattr("usbphone.controller.time.sleep", lambda _: None)
    phone.adb.fail_capture = True
    result = phone.act("key", first["observation_id"], key="HOME")
    assert result == {"dispatched": True, "verified": False, "error": "Capture failed"}


def test_malformed_xml_is_error():
    with pytest.raises(PhoneError, match="invalid accessibility"):
        parse_ui(b"bad")
