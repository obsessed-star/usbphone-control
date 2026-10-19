import pytest
from test_phone import FakeADB

from usbphone.adb import PhoneError
from usbphone.controller import Phone


def test_disconnected_refresh_invalidates_previously_saved_capture(tmp_path, monkeypatch):
    phone = Phone(FakeADB(), output=tmp_path)
    old = phone.observe()

    def disconnected(*_args):
        raise PhoneError("Device disconnected")

    monkeypatch.setattr(phone.adb, "select", disconnected)
    with pytest.raises(PhoneError, match="disconnected"):
        phone.observe()
    with pytest.raises(PhoneError, match="superseded"):
        Phone(FakeADB(), output=tmp_path).restore(old["observation_id"])
