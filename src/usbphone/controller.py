"""Observation-bound actions, with independent capture artifacts for each step."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from usbphone.adb import ADB, PhoneError, validate_package

KEYS = {"HOME": "3", "BACK": "4", "ENTER": "66", "BACKSPACE": "67", "RECENTS": "187"}


def parse_ui(xml: bytes) -> list[dict]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise PhoneError("Android returned invalid accessibility XML.") from exc
    elements = []
    for node in root.iter("node"):
        a = node.attrib
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", a.get("bounds", ""))
        if not bounds or a.get("password") == "true":
            continue
        x1, y1, x2, y2 = map(int, bounds.groups())
        if x2 <= x1 or y2 <= y1:
            continue
        if not any((a.get("text"), a.get("content-desc"), a.get("clickable") == "true")):
            continue
        elements.append(
            {
                "index": len(elements),
                "text": a.get("text", ""),
                "description": a.get("content-desc", ""),
                "resource_id": a.get("resource-id", ""),
                "bounds": [x1, y1, x2, y2],
                "center": [(x1 + x2) // 2, (y1 + y2) // 2],
                "clickable": a.get("clickable") == "true",
                "enabled": a.get("enabled") == "true",
            }
        )
    return elements


class Phone:
    def __init__(
        self,
        adb: ADB | None = None,
        serial: str | None = None,
        output: str | Path = ".usbphone",
        max_age: float = 30,
    ):
        self.adb = adb or ADB()
        self.serial = serial or os.getenv("ANDROID_SERIAL") or None
        self.output = Path(output)
        self.max_age = max_age
        self._last: dict | None = None
        self._observed_at = 0.0

    def _device(self):
        device = self.adb.select(self.serial)
        # Pin auto-selection: disconnecting one phone must never redirect to another.
        self.serial = device.serial
        return device

    def _latest_file(self, serial: str) -> Path:
        identity = hashlib.sha256(serial.encode()).hexdigest()[:16]
        return self.output / f"latest-{identity}.txt"

    def _is_latest(self, observation_id: str, serial: str) -> bool:
        try:
            return self._latest_file(serial).read_text("utf-8") == observation_id
        except OSError:
            return False

    def observe(self) -> dict:
        self._last = None
        # Invalidate disk state before probing the transport: even discovery can
        # fail when a cable is unplugged. A later process must not reuse that view.
        if self.output.exists():
            pointers = [self._latest_file(self.serial)] if self.serial else self.output.glob("latest-*.txt")
            for pointer in pointers:
                if pointer.exists():
                    pointer.write_text("", encoding="utf-8")
        device = self._device()
        serial = device.serial
        self.output.mkdir(parents=True, exist_ok=True)
        # A failed refresh must not resurrect the preceding CLI capture.
        self._latest_file(serial).write_text("", encoding="utf-8")
        png = self.adb.run("-s", serial, "exec-out", "screencap", "-p")
        captured_at, observed_at = time.time(), time.monotonic()
        if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR":
            raise PhoneError("Invalid screenshot. Secure Android screens may block capture.")
        width, height = struct.unpack(">II", png[16:24])
        if not 0 < width <= 20000 or not 0 < height <= 20000:
            raise PhoneError("Invalid screenshot dimensions.")
        capture_id = uuid.uuid4().hex
        directory = self.output / capture_id
        directory.mkdir(parents=True)
        (directory / "screen.png").write_bytes(png)
        elements, warning = [], None
        remote = f"/sdcard/usbphone-{capture_id}.xml"
        try:
            self.adb.shell(serial, "uiautomator", "dump", "--compressed", remote)
            xml = self.adb.shell(serial, "cat", remote)
            elements = parse_ui(xml)
            # Raw XML can include password values. Persist only filtered elements.
        except PhoneError as exc:
            warning = str(exc)
        finally:
            try:
                self.adb.shell(serial, "rm", "-f", remote)
            except PhoneError:
                pass
        observation = {
            "observation_id": capture_id,
            "device": asdict(device),
            "width": width,
            "height": height,
            "screenshot": str((directory / "screen.png").resolve()),
            "screenshot_sha256": hashlib.sha256(png).hexdigest(),
            "elements": elements,
            "warning": warning,
            "captured_at": captured_at,
        }
        (directory / "observation.json").write_text(
            json.dumps(observation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._last = observation
        self._observed_at = observed_at
        self._latest_file(serial).write_text(capture_id, encoding="utf-8")
        return observation

    def restore(self, observation_id: str) -> None:
        """Load a CLI capture, while retaining its original age and serial binding."""
        if not re.fullmatch(r"[a-f0-9]{32}", observation_id):
            raise PhoneError("Invalid observation ID.")
        try:
            if (self.output / observation_id / "consumed").exists():
                raise PhoneError("Observation already consumed. Observe again.")
            item = json.loads((self.output / observation_id / "observation.json").read_text("utf-8"))
        except (OSError, ValueError) as exc:
            raise PhoneError("Observation not found. Run usbphone observe first.") from exc
        age = time.time() - item["captured_at"]
        if age < 0 or age > self.max_age:
            raise PhoneError("Observation expired. Observe the screen again.")
        if self.serial and self.serial != item["device"]["serial"]:
            raise PhoneError("Observation belongs to another device.")
        if not self._is_latest(observation_id, item["device"]["serial"]):
            raise PhoneError("Observation was superseded or a refresh failed. Observe again.")
        self.serial = item["device"]["serial"]
        self._last = item
        self._observed_at = time.monotonic() - age

    def _fresh(self, observation_id: str) -> dict:
        if (
            not self._last
            or self._last["observation_id"] != observation_id
            or time.monotonic() - self._observed_at > self.max_age
            or not self._is_latest(observation_id, self._last["device"]["serial"])
        ):
            raise PhoneError("Stale or unknown observation. Observe before acting.")
        self._device()
        return self._last

    @staticmethod
    def _point(x, y, observation):
        if (
            type(x) is not int
            or type(y) is not int
            or not 0 <= x < observation["width"]
            or not 0 <= y < observation["height"]
        ):
            raise PhoneError("Coordinates must be integer pixels inside the latest screenshot.")

    def act(self, action: str, observation_id: str, **params) -> dict:
        observation = self._fresh(observation_id)
        serial = self.serial
        if action == "tap_element":
            index = params.get("index")
            elements = observation["elements"]
            if type(index) is not int or not 0 <= index < len(elements):
                raise PhoneError("Element index not present in this observation.")
            if not elements[index]["enabled"]:
                raise PhoneError("Element is disabled.")
            params = dict(zip(("x", "y"), elements[index]["center"], strict=True))
            action = "tap"
        if action == "tap":
            self._point(params.get("x"), params.get("y"), observation)
            command = ["input", "tap", str(params["x"]), str(params["y"])]
        elif action == "swipe":
            self._point(params.get("x1"), params.get("y1"), observation)
            self._point(params.get("x2"), params.get("y2"), observation)
            duration = params.get("duration_ms", 400)
            if type(duration) is not int or not 50 <= duration <= 3000:
                raise PhoneError("Swipe duration must be 50..3000 milliseconds.")
            command = ["input", "swipe", *(str(params[k]) for k in ("x1", "y1", "x2", "y2")), str(duration)]
        elif action == "type_text":
            value = params.get("text", "")
            # Stock Android input does not support arbitrary Unicode reliably.
            if not isinstance(value, str) or not value or len(value) > 1000:
                raise PhoneError("Text must contain 1..1000 characters.")
            if not value.isascii() or any(ord(c) < 32 for c in value) or "%" in value:
                raise PhoneError(
                    "Stock ADB typing accepts printable ASCII without %. Enter Unicode on device."
                )
            command = ["input", "text", value.replace(" ", "%s")]
        elif action == "key":
            key = params.get("key", "")
            if key not in KEYS:
                raise PhoneError(f"Allowed keys: {', '.join(KEYS)}")
            command = ["input", "keyevent", KEYS[key]]
        elif action == "launch":
            package = validate_package(params.get("package", ""))
            command = ["monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"]
        elif action == "open_url":
            url = params.get("url", "")
            if not isinstance(url, str) or len(url) > 4096 or any(c.isspace() for c in url):
                raise PhoneError("Provide an HTTP(S) URL without whitespace (up to 4096 characters).")
            try:
                parsed = urlsplit(url)
                valid = (
                    parsed.scheme in {"https", "http"}
                    and parsed.hostname
                    and parsed.username is None
                    and parsed.password is None
                )
                _ = parsed.port  # Reject malformed ports before dispatch.
            except ValueError:
                valid = False
            if not valid or any(ord(c) < 32 or ord(c) == 127 for c in url):
                raise PhoneError("Only HTTP(S) URLs with a hostname and without credentials are allowed.")
            # Android resolves the URL on the phone; no desktop browser is involved.
            command = ["am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", url]
            if params.get("package"):
                command.extend(["-p", validate_package(params["package"])])
        else:
            raise PhoneError(f"Unknown action: {action}")
        # Consume the observation BEFORE dispatch. A timeout must not allow blind replay.
        try:
            with (self.output / observation_id / "consumed").open("x"):
                pass
        except FileExistsError as exc:
            raise PhoneError("Observation already consumed. Observe again.") from exc
        self._last = None
        response = self.adb.shell(serial, *command)
        if action == "launch" and b"No activities found" in response:
            raise PhoneError("Package has no launcher activity or is not installed.")
        if action == "open_url" and any(
            token in response for token in (b"Error:", b"Exception", b"unable to resolve Intent")
        ):
            raise PhoneError("Android could not open the URL. Check the browser package and device.")
        time.sleep(0.3)
        try:
            after = self.observe()
        except PhoneError as exc:
            return {"dispatched": True, "verified": False, "error": str(exc)}
        return {"dispatched": True, "verified": True, "observation": after}
