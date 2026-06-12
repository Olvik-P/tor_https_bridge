"""Bidirectional async data forwarding between two streams."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from tor_https_bridge.config.constants import BUFFER_SIZE

logger = logging.getLogger(__name__)


class DataForwarderProtocol(Protocol):
    """Protocol for data forwarder implementations."""

    async def forward_bidirectional(
        self,
        stream1: tuple[asyncio.StreamReader, asyncio.StreamWriter],
        stream2: tuple[asyncio.StreamReader, asyncio.StreamWriter],
    ) -> None:
        """Forward data bidirectionally between two streams.

        Args:
            stream1: (reader, writer) tuple for the first stream.
            stream2: (reader, writer) tuple for the second stream.

        Raises:
            ConnectionError: If a connection is lost during forwarding.
        """
        ...


class DataForwarder:
    """Bidirectional async data forwarding between two streams.

    Reads data from one stream's reader and writes it to the other
    stream's writer, and vice versa. Uses :func:`asyncio.wait` with
    ``FIRST_COMPLETED`` to handle connection closure in either direction.

    Usage::

        forwarder = DataForwarder(buffer_size=16384)
        await forwarder.forward_bidirectional(
            (client_reader, client_writer),
            (tor_reader, tor_writer),
        )

    Args:
        buffer_size: Maximum bytes to read per iteration.
    """

    def __init__(self, buffer_size: int = BUFFER_SIZE) -> None:
        self._buffer_size = buffer_size

    async def forward_one_way(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        name: str,
    ) -> None:
        """Forward data from *reader* to *writer* until EOF.

        The *writer* is **not** closed by this method — the caller is
        responsible for closing both writers after
        :meth:`forward_bidirectional` completes. This avoids duplicate
        ``close()`` / ``wait_closed()`` calls that trigger
        ``ConnectionResetError`` on Windows ``ProactorEventLoop``.

        Args:
            reader: Source stream reader.
            writer: Destination stream writer.
            name: Human-readable label for logging (e.g. ``client->tor``).

        Raises:
            ConnectionError: If the connection is reset or closed.
            OSError: On socket-level errors.
        """
        try:
            while True:
                data = await reader.read(self._buffer_size)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except (ConnectionError, OSError) as e:
            logger.debug("%s: Connection closed - %s", name, e)
        except asyncio.CancelledError:
            # Task was cancelled during shutdown — exit cleanly
            logger.debug("%s: Forwarding cancelled", name)

    async def forward_bidirectional(
        self,
        stream1: tuple[asyncio.StreamReader, asyncio.StreamWriter],
        stream2: tuple[asyncio.StreamReader, asyncio.StreamWriter],
    ) -> None:
        """Forward data bidirectionally between two streams.

        Creates two concurrent tasks — one for each direction — and
        waits for the first to complete (indicating connection closure).
        The remaining task is stopped by closing the corresponding
        writer, which avoids ``Cancelling an overlapped future failed``
        errors on Windows ``ProactorEventLoop``.

        Args:
            stream1: ``(reader, writer)`` for the first stream.
            stream2: ``(reader, writer)`` for the second stream.
        """
        reader1, writer1 = stream1
        reader2, writer2 = stream2

        task1 = asyncio.create_task(
            self.forward_one_way(reader1, writer2, "client->tor"),
        )
        task2 = asyncio.create_task(
            self.forward_one_way(reader2, writer1, "tor->client"),
        )

        done, pending = await asyncio.wait(
            [task1, task2],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Instead of task.cancel() (which triggers WinError 6 on
        # Windows ProactorEventLoop when the underlying handle is
        # already closed), close the writer of the pending task.
        # This causes the pending forward_one_way to exit naturally
        # via ConnectionError/OSError on its next read/write.
        for task in pending:
            # Determine which writer belongs to the pending task
            if task is task1:
                # task1 = forward_one_way(reader1, writer2, ...)
                # Close writer2 so task1's write/drain fails
                try:
                    writer2.close()
                except OSError:
                    pass
            else:
                # task2 = forward_one_way(reader2, writer1, ...)
                # Close writer1 so task2's write/drain fails
                try:
                    writer1.close()
                except OSError:
                    pass

        # Wait for both tasks to finish naturally.
        # Use return_exceptions=True to prevent CancelledError from
        # propagating if a task was cancelled during shutdown.
        results = await asyncio.gather(
            *pending,
            return_exceptions=True,
        )
        # Log any unexpected exceptions (but not CancelledError)
        for result in results:
            if isinstance(result, Exception) and not isinstance(
                result,
                (asyncio.CancelledError, ConnectionError, OSError),
            ):
                logger.error(
                    "Unexpected error in forwarder: %s",
                    result,
                )
