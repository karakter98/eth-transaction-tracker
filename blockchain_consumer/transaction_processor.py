import logging
from abc import ABCMeta, abstractmethod
from typing import Dict, Any, Tuple, List

from web3 import Web3
from web3.types import TxData, BlockData


class TransactionProcessor(metaclass=ABCMeta):
    CONFIRMATIONS_REQUIRED = 6
    _logger = None

    def __init__(self, web3_client: Web3):
        self._unconfirmed_transactions: Dict[TxData, Dict[str, Any]] = {}
        self._web3_client = web3_client

    @classmethod
    def _get_logger(cls) -> logging.Logger:
        if cls._logger is None:
            cls._logger = logging.getLogger(cls.__name__)
        return cls._logger

    def process_block(self, block: BlockData):
        self._unconfirmed_transactions |= {
            transaction: {
                "block_number": block["number"],
                "args": args,
                "kwargs": kwargs
            }
            for transaction, args, kwargs in self._filter_transactions(block)
        }
        if self._unconfirmed_transactions:
            self.__class__._get_logger().info(f"{len(self._unconfirmed_transactions)} pending transactions.")

        confirmed_transactions = set()
        for transaction, tx_info in self._unconfirmed_transactions.items():
            tx_block_number, args, kwargs = tx_info["block_number"], tx_info["args"], tx_info["kwargs"]
            if block["number"] - tx_block_number >= self.CONFIRMATIONS_REQUIRED:
                self.__class__._get_logger().info(f"Transaction {transaction['hash']} received {self.CONFIRMATIONS_REQUIRED} confirmations!")
                confirmed_transactions.add(transaction)
                self._process_transaction(transaction, *args, **kwargs)

        for transaction in confirmed_transactions:
            del self._unconfirmed_transactions[transaction]

    @abstractmethod
    def _filter_transactions(self, block: BlockData) -> List[Tuple[TxData, list, dict]]:
        pass

    @abstractmethod
    def _process_transaction(self, transaction_raw: TxData, *args, **kwargs):
        pass
