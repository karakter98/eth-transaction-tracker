import logging
import threading

from django.apps import AppConfig


class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Wallet'

    def ready(self):
        def _background_task():
            from django.conf import settings
            from web3 import Web3

            from blockchain_consumer.block_fetcher import BlockFetcher
            from blockchain_consumer.incoming import IncomingTransactionProcessor
            from blockchain_consumer.incoming import IncomingERC20Processor
            from blockchain_consumer.outgoing import OutgoingTransactionProcessor
            from blockchain_consumer.outgoing import OutgoingERC20Processor

            web3_client = Web3(Web3.HTTPProvider(settings.INFURA_URL))

            block_fetcher = BlockFetcher(web3_client)
            block_fetcher.subscribe(IncomingTransactionProcessor(web3_client))
            block_fetcher.subscribe(IncomingERC20Processor(web3_client))
            block_fetcher.subscribe(OutgoingTransactionProcessor(web3_client))
            block_fetcher.subscribe(OutgoingERC20Processor(web3_client))

            logging.basicConfig(level=logging.INFO)

            block_fetcher.start()

        threading.Thread(target=_background_task, daemon=True).start()
