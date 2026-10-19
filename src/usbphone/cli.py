from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from usbphone.adb import ADB, PhoneError
from usbphone.controller import Phone


def main():
    parser = argparse.ArgumentParser(description="Observe and control an owner-authorized USB Android phone.")
    parser.add_argument("--adb", default=None, help="ADB executable; also reads ADB_PATH")
    parser.add_argument("--serial", default=None)
    parser.add_argument("--output", default=".usbphone")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("devices")
    sub.add_parser("observe")
    action = sub.add_parser("act")
    action.add_argument("action", choices=["tap", "tap_element", "swipe", "type_text", "key", "launch"])
    action.add_argument("--observation", required=True)
    action.add_argument("--params", default="{}", help='JSON object, e.g. {"x":100,"y":200}')
    args = parser.parse_args()
    try:
        adb = ADB(args.adb)
        if args.command == "devices":
            result = [asdict(d) for d in adb.devices()]
        else:
            phone = Phone(adb=adb, serial=args.serial, output=args.output)
            if args.command == "observe":
                result = phone.observe()
            else:
                params = json.loads(args.params)
                if not isinstance(params, dict):
                    raise PhoneError("--params must be a JSON object.")
                phone.restore(args.observation)
                result = phone.act(args.action, args.observation, **params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (PhoneError, ValueError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
