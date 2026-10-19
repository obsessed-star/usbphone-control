import asyncio
import base64
import sys

import pytest

mcp = pytest.importorskip("mcp")


def test_mcp_observation_returns_native_image_content(tmp_path):
    from usbphone.mcp_server import create_server

    image = tmp_path / "screen.png"
    # A valid 1x1 PNG fixture, not a device screenshot.
    image.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aYJkAAAAASUVORK5CYII="
        )
    )

    class FixturePhone:
        def observe(self):
            return {"observation_id": "0" * 32, "screenshot": str(image)}

    result = asyncio.run(create_server(FixturePhone()).call_tool("phone_observe", {}))
    assert not result.is_error
    assert any(item.type == "image" and item.mime_type == "image/png" for item in result.content)


def test_stdio_handshake_tool_discovery_and_rejected_action():
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def exercise():
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "usbphone.mcp_server"])
        async with stdio_client(parameters) as (read, write):
            async with mcp.ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert initialized.server_info.name == "USBPhone Control"
                listing = await session.list_tools()
                assert {t.name for t in listing.tools} == {"phone_observe", "phone_act"}
                annotations = {t.name: t.annotations for t in listing.tools}
                assert annotations["phone_observe"].read_only_hint
                assert not annotations["phone_act"].read_only_hint
                result = await session.call_tool(
                    "phone_act",
                    {
                        "action": "key",
                        "observation_id": "0" * 32,
                        "params": {"key": "HOME"},
                    },
                )
                assert result.is_error
                assert "Stale" in result.content[0].text

    asyncio.run(exercise())
