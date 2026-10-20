# Changelog

## 0.2.0 — 2026-10-20

- Open HTTP(S) sites on the USB phone using Android VIEW intents, with optional browser selection.
- List public Downloads and export a bounded file with byte-count and device/local SHA-256 verification.
- Expose browser navigation and download tools through Python, JSON CLI and MCP.
- Reject unsafe URL schemes, remote paths, symlinks, oversized and changing downloads.
- Exercise the real controller in website/download fixtures; physical-device validation remains pending.

## 0.1.1 — 2026-10-20

- Migrate optional MCP support to SDK 2.3's `MCPServer`, compatible with the agent's model-tool pipeline.
- Preserve expected phone errors as actionable MCP tool errors and verify native images/annotations over the real SDK.
- Invalidate saved captures before device discovery so unplugging a cable cannot leave a reusable old observation.

## 0.1.0 — 2026-10-19

Initial USB-only Python/CLI/MCP preview. SDK integration and discovery-failure behavior are corrected in 0.1.1.
