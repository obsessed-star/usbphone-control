"""Observation only. Does not touch, type, launch apps or send data to a model."""

import json

from usbphone.controller import Phone

if __name__ == "__main__":
    observation = Phone().observe()
    print(json.dumps(observation, ensure_ascii=False, indent=2))
