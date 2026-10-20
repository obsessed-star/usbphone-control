import hashlib

import pytest
from test_phone import FakeADB

from usbphone.adb import PhoneError
from usbphone.controller import Phone
from usbphone.downloads import MAX_BYTES, export_download, list_downloads


@pytest.mark.parametrize("url", ["https://example.org/a?q=1&x=2", "https://example.org/belge/%C3%B6"])
def test_url_opens_on_phone_with_one_intent_and_fresh_capture(tmp_path, monkeypatch, url):
    monkeypatch.setattr("usbphone.controller.time.sleep", lambda _: None)
    phone = Phone(FakeADB(), output=tmp_path)
    before = phone.observe()
    after = phone.act("open_url", before["observation_id"], url=url, package="com.android.chrome")
    assert (
        "usb-001",
        "am",
        "start",
        "-W",
        "-a",
        "android.intent.action.VIEW",
        "-d",
        url,
        "-p",
        "com.android.chrome",
    ) in phone.adb.calls
    assert after["observation"]["observation_id"] != before["observation_id"]


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///sdcard/a",
        "https://u:p@x/",
        "https://x:abc/",
        "https://x/\n",
        "https://",
        "intent://foo",
    ],
)
def test_invalid_urls_never_dispatch(tmp_path, url):
    phone = Phone(FakeADB(), output=tmp_path)
    before = phone.observe()
    count = len(phone.adb.calls)
    with pytest.raises(PhoneError):
        phone.act("open_url", before["observation_id"], url=url)
    assert len(phone.adb.calls) == count


def test_android_intent_error_is_not_reported_as_dispatch_success(tmp_path):
    class NoBrowser(FakeADB):
        def shell(self, serial, *args):
            return b"Error: Activity not started" if args[0] == "am" else super().shell(serial, *args)

    phone = Phone(NoBrowser(), output=tmp_path)
    before = phone.observe()
    with pytest.raises(PhoneError, match="could not open"):
        phone.act("open_url", before["observation_id"], url="https://example.org")
    with pytest.raises(PhoneError, match="consumed"):
        phone.restore(before["observation_id"])


class DownloadADB(FakeADB):
    data = b"%PDF-1.7\nsynthetic document fixture, not an issued document"
    kind = "regular file"
    size = None
    wrong_hash = False

    def shell(self, serial, *args):
        self.calls.append((serial, *args))
        if args[0] == "find":
            return b"/sdcard/Download/belge.pdf\0/sdcard/Download/old.pdf\0"
        if args[0] == "stat":
            return f"{self.kind}:{self.size or len(self.data)}".encode()
        if args[0] == "sha256sum":
            return (
                ("0" * 64 if self.wrong_hash else hashlib.sha256(self.data).hexdigest()) + "  file"
            ).encode()
        if args[0] == "head":
            assert int(args[2]) == MAX_BYTES + 1
            return self.data
        return super().shell(serial, *args)


def test_download_list_and_byte_verified_export(tmp_path):
    phone = Phone(DownloadADB(), output=tmp_path)
    assert list_downloads(phone)["files"] == ["belge.pdf", "old.pdf"]
    result = export_download(phone, "belge.pdf")
    from pathlib import Path

    assert Path(result["path"]).read_bytes() == phone.adb.data
    assert result["transfer_verified"] and not result["content_verified"]
    assert result["sha256"] == hashlib.sha256(phone.adb.data).hexdigest()


@pytest.mark.parametrize("name", ["../private", "/sdcard/secret", "a\\b", "x:stream", ".secret", "x\n"])
def test_export_rejects_paths_before_device_access(tmp_path, name):
    phone = Phone(DownloadADB(), output=tmp_path)
    with pytest.raises(PhoneError, match="filename"):
        export_download(phone, name)
    assert not phone.adb.calls


@pytest.mark.parametrize(
    "change", [{"kind": "symbolic link"}, {"size": MAX_BYTES + 1}, {"wrong_hash": True}, {"data": b""}]
)
def test_incomplete_oversize_or_linked_download_never_creates_copy(tmp_path, change):
    adb = DownloadADB()
    for key, value in change.items():
        setattr(adb, key, value)
    with pytest.raises(PhoneError):
        export_download(Phone(adb, output=tmp_path), "belge.pdf")
    assert not (tmp_path / "downloads").exists()
