import asyncio
import sys

import pytest

mcp = pytest.importorskip("mcp")


def test_stdio_handshake_tool_discovery_and_rejected_action():
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def exercise():
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "usbphone.mcp_server"])
        async with stdio_client(parameters) as (read, write):
            async with mcp.ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "USBPhone Control"
                listing = await session.list_tools()
                assert {t.name for t in listing.tools} == {"phone_observe", "phone_act"}
                result = await session.call_tool(
                    "phone_act",
                    {
                        "action": "key",
                        "observation_id": "0" * 32,
                        "params": {"key": "HOME"},
                    },
                )
                assert result.isError
                assert "Stale" in result.content[0].text

    asyncio.run(exercise())
