"""
Databento Live streaming client wrapper.
Prepared for real-time data ingestion from Databento.

Usage (future):
    client = DatabentoLiveClient()
    client.on_record(my_callback)
    await client.start(["MU", "NVDA"], schema="mbp-10")
    ...
    await client.stop()
"""
import os
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("DatabentoLive")


class DatabentoLiveClient:
    """Wraps databento.Live for real-time L2/trades streaming."""

    def __init__(self, dataset: str = "XNAS.ITCH"):
        self.dataset = dataset
        self._client = None
        self._running = False
        self._callbacks: List[Callable] = []
        self._task: Optional[asyncio.Task] = None

    @staticmethod
    def _get_api_key() -> str:
        key = os.environ.get("DATABENTO_API_KEY")
        if not key:
            raise RuntimeError("DATABENTO_API_KEY not set")
        return key

    async def start(self, symbols: List[str], schema: str = "mbp-10"):
        """Start live streaming for given symbols.

        The Databento Live client connects via TCP and receives records
        as they arrive. Each record is forwarded to registered callbacks.
        """
        import databento as db

        if self._running:
            raise RuntimeError("Live client already running")

        self._client = db.Live(key=self._get_api_key())
        self._client.subscribe(
            dataset=self.dataset,
            schema=schema,
            symbols=symbols,
            stype_in="raw_symbol",
        )
        self._running = True
        logger.info(f"Live stream started: {symbols} / {schema} / {self.dataset}")

        # Process records in background
        self._task = asyncio.create_task(self._process_loop())

    async def _process_loop(self):
        """Read records from the live client and dispatch to callbacks."""
        try:
            for record in self._client:
                if not self._running:
                    break
                for cb in self._callbacks:
                    try:
                        result = cb(record)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
        except Exception as e:
            logger.error(f"Live stream error: {e}")
        finally:
            self._running = False
            logger.info("Live stream ended")

    def on_record(self, callback: Callable):
        """Register a callback for incoming records.

        Callback signature: (record) -> None or coroutine
        The record is a databento Record object with fields like:
        - ts_event, ts_recv
        - price, size, side, action
        - bid_px_00..09, ask_px_00..09, bid_sz_00..09, ask_sz_00..09
        """
        self._callbacks.append(callback)

    async def stop(self):
        """Stop the live stream."""
        self._running = False
        if self._client:
            try:
                self._client.stop()
            except Exception:
                pass
            self._client = None
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Live client stopped")

    @property
    def is_running(self) -> bool:
        return self._running
