# Validation record

Initial local validation: **19 October 2026**, Windows, Python 3.14.7.

| Check | Observed result |
|---|---|
| Controller, CLI and MCP tests | See current count in [validation.json](validation.json) |
| Ruff lint and formatting | Passed |
| Wheel and source distribution | Built successfully |
| MCP protocol | Real stdio subprocess initialized; tools discovered; stale action returned a protocol error |
| MCP image output | SDK emits native PNG image content for a labeled 1×1 fixture |
| USB transport logic | Marker-based USB and Windows pathless USB-selector fixtures tested |
| Dispatch uncertainty | Timeout consumes ID; post-action capture failure returns unverified result |
| Physical device test | Not performed; local ADB returned no attached devices |

Tests replace ADB with a deterministic fixture; they do not constitute a successful real-device demonstration. Screenshots used in transport-unit tests are minimal synthetic PNG headers for dimension parsing. The MCP image test uses a separate valid tiny PNG. No personal phone screenshots are published.

Machine-readable local commands, result summaries and artifact hashes are in [validation.json](validation.json). Reproduce with [requirements-dev.lock](../requirements-dev.lock). CI additionally targets Windows/Linux and Python 3.11/3.14; see the live workflow status rather than assuming success from this configuration.

The Windows compatibility branch is based on AOSP's native Windows USB backend registering devices without a device path. The tool confirms such a connection through ADB's `-d` USB selector rather than classifying every non-IP-looking serial as USB. Multiple pathless USB devices require disconnecting the others before use.

Next hardware validation: select an owner-authorized Android device, capture its screen, send a benign Home key with that observation ID, inspect the new capture, then repeat with a tap, swipe and ASCII text field. Device-specific limitations should be documented with the Android/ADB versions actually tested.
