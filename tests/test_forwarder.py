"""Tests for tor_https_bridge.core.forwarder."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from tor_https_bridge.core.forwarder import DataForwarder


class TestDataForwarderInit:
    """Tests for DataForwarder.__init__."""

    def test_default_buffer_size(self) -> None:
        forwarder = DataForwarder()
        assert forwarder._buffer_size == 8192

    def test_custom_buffer_size(self) -> None:
        forwarder = DataForwarder(buffer_size=16384)
        assert forwarder._buffer_size == 16384


class TestDataForwarderForwardOneWay:
    """Tests for DataForwarder.forward_one_way."""

    @pytest.mark.asyncio
    async def test_forward_data(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(
            side_effect=[b"hello", b"world", b""],
        )
        writer = AsyncMock(spec=asyncio.StreamWriter)
        writer.drain = AsyncMock()

        forwarder = DataForwarder(buffer_size=1024)
        await forwarder.forward_one_way(reader, writer, "test")

        assert reader.read.call_count == 3
        writer.write.assert_any_call(b"hello")
        writer.write.assert_any_call(b"world")
        assert writer.drain.call_count == 2
        writer.close.assert_not_called()
        writer.wait_closed.assert_not_called()

    @pytest.mark.asyncio
    async def test_forward_no_data(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(return_value=b"")
        writer = AsyncMock(spec=asyncio.StreamWriter)
        writer.drain = AsyncMock()

        forwarder = DataForwarder(buffer_size=1024)
        await forwarder.forward_one_way(reader, writer, "test")

        reader.read.assert_called_once()
        writer.write.assert_not_called()
        writer.drain.assert_not_called()
        writer.close.assert_not_called()
        writer.wait_closed.assert_not_called()

    @pytest.mark.asyncio
    async def test_forward_connection_error(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(side_effect=ConnectionError("reset"))
        writer = AsyncMock(spec=asyncio.StreamWriter)
        writer.drain = AsyncMock()

        forwarder = DataForwarder(buffer_size=1024)
        await forwarder.forward_one_way(reader, writer, "test")

        writer.close.assert_not_called()
        writer.wait_closed.assert_not_called()

    @pytest.mark.asyncio
    async def test_forward_os_error(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(side_effect=OSError("socket error"))
        writer = AsyncMock(spec=asyncio.StreamWriter)
        writer.drain = AsyncMock()

        forwarder = DataForwarder(buffer_size=1024)
        await forwarder.forward_one_way(reader, writer, "test")

        writer.close.assert_not_called()
        writer.wait_closed.assert_not_called()

    @pytest.mark.asyncio
    async def test_forward_multiple_chunks(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(
            side_effect=[b"chunk1", b"chunk2", b"chunk3", b""],
        )
        writer = AsyncMock(spec=asyncio.StreamWriter)
        writer.drain = AsyncMock()

        forwarder = DataForwarder(buffer_size=1024)
        await forwarder.forward_one_way(reader, writer, "test")

        assert reader.read.call_count == 4
        assert writer.write.call_count == 3
        assert writer.drain.call_count == 3


class TestDataForwarderForwardBidirectional:
    """Tests for DataForwarder.forward_bidirectional."""

    @pytest.mark.asyncio
    async def test_bidirectional_forwarding(self) -> None:
        reader1 = AsyncMock(spec=asyncio.StreamReader)
        reader1.read = AsyncMock(side_effect=[b"data1", b""])
        writer1 = AsyncMock(spec=asyncio.StreamWriter)
        writer1.drain = AsyncMock()

        reader2 = AsyncMock(spec=asyncio.StreamReader)
        reader2.read = AsyncMock(side_effect=[b"data2", b""])
        writer2 = AsyncMock(spec=asyncio.StreamWriter)
        writer2.drain = AsyncMock()

        forwarder = DataForwarder(buffer_size=1024)
        await forwarder.forward_bidirectional(
            (reader1, writer1),
            (reader2, writer2),
        )

        writer1.close.assert_not_called()
        writer2.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_bidirectional_one_side_closes_first(self) -> None:
        """When one side closes, the other should be cancelled."""
        reader1 = AsyncMock(spec=asyncio.StreamReader)
        reader1.read = AsyncMock(side_effect=[b"data", b""])
        writer1 = AsyncMock(spec=asyncio.StreamWriter)
        writer1.drain = AsyncMock()

        # This side never finishes (simulates still open)
        reader2 = AsyncMock(spec=asyncio.StreamReader)
        reader2.read = AsyncMock(side_effect=[b"more data"])
        writer2 = AsyncMock(spec=asyncio.StreamWriter)
        writer2.drain = AsyncMock()

        forwarder = DataForwarder(buffer_size=1024)
        await forwarder.forward_bidirectional(
            (reader1, writer1),
            (reader2, writer2),
        )

        writer1.close.assert_not_called()
        writer2.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_bidirectional_both_sides_close(self) -> None:
        """Both sides close at the same time."""
        reader1 = AsyncMock(spec=asyncio.StreamReader)
        reader1.read = AsyncMock(return_value=b"")
        writer1 = AsyncMock(spec=asyncio.StreamWriter)
        writer1.drain = AsyncMock()

        reader2 = AsyncMock(spec=asyncio.StreamReader)
        reader2.read = AsyncMock(return_value=b"")
        writer2 = AsyncMock(spec=asyncio.StreamWriter)
        writer2.drain = AsyncMock()

        forwarder = DataForwarder(buffer_size=1024)
        await forwarder.forward_bidirectional(
            (reader1, writer1),
            (reader2, writer2),
        )

        writer1.close.assert_not_called()
        writer2.close.assert_not_called()
