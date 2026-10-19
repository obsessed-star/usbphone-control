# Security and privacy

Use only a phone you own or are authorized to control. USB debugging grants the connected computer powerful device access. This toolkit does not enable debugging or approve the Android RSA dialog on your behalf.

The package runs local ADB subprocesses and has no network server. MCP uses stdio. A client with access to the MCP server can invoke the allowed phone actions; the host is responsible for confirming user intent. Tool annotations are hints, not an authorization boundary.

Default capture folders are ignored by Git. Captures include screenshots, UI labels and a device serial. They are not encrypted or automatically deleted. Do not commit real device captures, share them in issues, or run a public demo on personal account screens. Password XML filtering does not redact screenshot pixels.

Fresh observation IDs and single-use markers reduce stale and repeated inputs. They do not prove the screen stayed unchanged, secure the device against another process, or provide exactly-once delivery across ADB failures. Use one controlling process per phone.

The ADB binary is supplied by the operator. Install Platform Tools from Android's official distribution and keep it updated. The tool never downloads or executes an ADB binary by itself.
