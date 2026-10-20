"""Bounded reads of public Downloads; never accept arbitrary remote or host paths."""

from __future__ import annotations

import hashlib
import re
import uuid

from usbphone.adb import PhoneError

MAX_BYTES = 20 * 1024 * 1024
ROOT = "/sdcard/Download"


def download_name(name: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or len(name) > 180
        or name.startswith(".")
        or any(c in name for c in '/\\:<>"|?*')
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
        or name.endswith((".", " "))
    ):
        raise PhoneError("Use a plain Downloads filename, not a path.")
    return name


def list_downloads(phone) -> dict:
    serial = phone._device().serial
    raw = phone.adb.shell(serial, "find", ROOT, "-maxdepth", "1", "-type", "f", "-print0")
    names = []
    for item in raw.decode("utf-8", errors="replace").split("\0"):
        if item.startswith(ROOT + "/"):
            name = item[len(ROOT) + 1 :]
            try:
                names.append(download_name(name))
            except PhoneError:
                continue
    names = sorted(set(names))
    return {"directory": ROOT, "files": names[:100], "truncated": len(names) > 100}


def export_download(phone, name: str) -> dict:
    """Verify exact bytes against the device hash before saving a local copy."""
    name = download_name(name)
    serial = phone._device().serial
    remote = ROOT + "/" + name
    info = phone.adb.shell(serial, "stat", "-c", "%F:%s", remote).decode().strip()
    kind, _, size = info.rpartition(":")
    if kind != "regular file" or not size.isdigit() or not 0 < int(size) <= MAX_BYTES:
        raise PhoneError("Download must be a regular, nonempty file of at most 20 MiB.")
    digest = phone.adb.shell(serial, "sha256sum", remote).decode().split()
    if not digest or not re.fullmatch(r"[a-fA-F0-9]{64}", digest[0]):
        raise PhoneError("Device did not return a valid download hash.")
    data = phone.adb.shell(serial, "head", "-c", str(MAX_BYTES + 1), remote)
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != int(size) or actual != digest[0].lower():
        raise PhoneError("Download changed or is incomplete. Wait for completion and inspect again.")
    # A generated prefix avoids Windows reserved filenames and accidental overwrites.
    directory = phone.output / "downloads"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (uuid.uuid4().hex + "-" + name)
    target.write_bytes(data)
    return {
        "name": name,
        "path": str(target.resolve()),
        "bytes": len(data),
        "sha256": actual,
        "device_serial": serial,
        "transfer_verified": True,
        "content_verified": False,
    }
