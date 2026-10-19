"""Small, deliberately explicit ADB boundary; host commands never use shell=True."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, replace


class PhoneError(RuntimeError):
    """An actionable transport, device-selection or input error."""


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    usb: bool
    model: str


def parse_devices(output: str) -> list[Device]:
    devices = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0] == "List" or line.startswith("*"):
            continue
        fields = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        # ADB's USB transport marker is required, even with an explicit serial.
        devices.append(Device(parts[0], parts[1], "usb" in fields, fields.get("model", "")))
    return devices


class ADB:
    def __init__(self, executable: str | None = None, timeout: float = 20):
        candidate = executable or os.getenv("ADB_PATH", "adb")
        self.executable = shutil.which(candidate) or candidate
        self.timeout = timeout

    def run(self, *args: str) -> bytes:
        try:
            result = subprocess.run(
                [self.executable, *args],
                capture_output=True,
                timeout=self.timeout,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as exc:
            raise PhoneError("ADB not found. Install Android Platform Tools and set ADB_PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise PhoneError("ADB timed out; device state is unknown. Observe before retrying.") from exc
        if result.returncode:
            detail = result.stderr.decode("utf-8", errors="replace").strip()[:500]
            raise PhoneError(f"ADB failed: {detail}")
        return result.stdout

    def devices(self) -> list[Device]:
        devices = parse_devices(self.run("devices", "-l").decode("utf-8", errors="replace"))
        # Native Windows ADB can omit devpath (and therefore the usb: field).
        # Ask ADB's USB-only selector instead of guessing from the serial format.
        if devices and any(not d.usb for d in devices):
            try:
                usb_serial = self.run("-d", "get-serialno").decode("utf-8").strip()
            except PhoneError:
                usb_serial = None
            if usb_serial:
                devices = [replace(d, usb=True) if d.serial == usb_serial else d for d in devices]
        return devices

    def select(self, serial: str | None = None) -> Device:
        devices = self.devices()
        matches = [d for d in devices if d.usb and (serial is None or d.serial == serial)]
        if len(matches) != 1:
            raise PhoneError(
                "Select exactly one USB device with --serial / ANDROID_SERIAL. "
                "Connect one data cable, enable USB debugging and approve the RSA prompt. "
                "TCP and emulators are excluded. If ADB omits USB paths, connect only one USB phone."
            )
        device = matches[0]
        if device.state != "device":
            raise PhoneError(
                f"USB device is {device.state}. Unlock it and approve this computer's RSA prompt."
            )
        return device

    def shell(self, serial: str, *args: str) -> bytes:
        # ADB shell concatenates argv on Android. Quote EACH argument for the remote POSIX shell.
        return self.run("-s", serial, "shell", shlex.join(args))


def validate_package(package: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
        raise PhoneError("Expected an Android package name, for example com.android.settings.")
    return package
