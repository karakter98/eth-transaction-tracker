import logging
from collections import Generator
from time import sleep
from typing import Union

from web3 import Web3
from web3.exceptions import BlockNotFound
from web3.types import BlockData

from blockchain_consumer.transaction_processor import TransactionProcessor

logger = logging.getLogger(__name__)


class BlockFetcher:
    def __init__(self, web3_client: Web3, polling_delay: Union[int, float] = 10):
        self._observers = set()
        self._client = web3_client
        self._polling_delay = polling_delay
        self._last_processed_block = None

    def subscribe(self, observer: TransactionProcessor):
        self._observers.add(observer)

    def _notify_all(self, block: BlockData):
        for observer in self._observers:
            try:
                observer.process_block(block)
            except Exception as e:
                logger.exception(f"An exception occurred while processing block: {e}")

    def _latest_block(self) -> BlockData:
        return self._client.eth.get_block("latest", full_transactions=True)

    def _next_block(self) -> BlockData:
        return self._client.eth.get_block(self._last_processed_block["number"] + 1, full_transactions=True)

    def _poll(self) -> Generator[BlockData, None, None]:
        self._last_processed_block = self._latest_block()
        while True:
            latest_block = self._latest_block()
            if self._last_processed_block == latest_block:
                sleep(self._polling_delay)
            else:
                try:
                    self._last_processed_block = self._next_block()
                    logger.info(f"Found block {self._last_processed_block['number']}")
                    yield self._last_processed_block
                except BlockNotFound:
                    # For some reason the next block call failed, retry
                    sleep(self._polling_delay)

    def start(self):
        logger.info("Starting polling for blocks...")
        for block in self._poll():
            self._notify_all(block)
