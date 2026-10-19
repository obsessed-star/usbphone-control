import pytest
from test_phone import FakeADB

from usbphone.adb import PhoneError
from usbphone.controller import Phone


def test_another_process_cannot_restore_a_superseded_capture(tmp_path):
    phone = Phone(FakeADB(), output=tmp_path)
    old = phone.observe()
    latest = phone.observe()
    other = Phone(FakeADB(), output=tmp_path)
    with pytest.raises(PhoneError, match="superseded"):
        other.restore(old["observation_id"])
    other.restore(latest["observation_id"])


def test_failed_capture_invalidates_the_previous_disk_capture(tmp_path):
    phone = Phone(FakeADB(), output=tmp_path)
    old = phone.observe()
    phone.adb.fail_capture = True
    with pytest.raises(PhoneError, match="Capture failed"):
        phone.observe()
    with pytest.raises(PhoneError, match="superseded"):
        Phone(FakeADB(), output=tmp_path).restore(old["observation_id"])
