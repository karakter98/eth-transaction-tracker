from typing import List, Tuple

from web3.types import BlockData, TxData
from Wallet.models import Account, ReceivedTransaction, Token, TokenBalance
from blockchain_consumer.block_fetcher import TransactionProcessor


class IncomingTransactionProcessor(TransactionProcessor):
    def _filter_transactions(self, block: BlockData) -> List[Tuple[TxData, list, dict]]:
        result = []
        for transaction in block["transactions"]:
            transaction: TxData
            try:
                account = Account.objects.get(public_key=transaction["to"])
                # This processor only processes ETH transactions
                if not transaction["value"]:
                    continue
            except Account.DoesNotExist:
                pass
            else:
                result.append((transaction, [], {"account": account}))
        return result

    def _process_transaction(self, transaction_raw: TxData, *args, **kwargs):
        self._get_logger().info(f"Processing ETH transaction {transaction_raw['hash']}")

        account = kwargs["account"]

        transaction = ReceivedTransaction(
            transaction_hash=transaction_raw["hash"],
            amount_wei=transaction_raw["value"],
            sender=transaction_raw["from"],
            receiver=account
        )
        transaction.save()

        account.update_balance(web3_client=self._web3_client)


class IncomingERC20Processor(TransactionProcessor):
    def _filter_transactions(self, block: BlockData) -> List[Tuple[TxData, list, dict]]:
        result = []
        for transaction in block["transactions"]:
            transaction: TxData
            try:
                # This processor only processes ERC20 transactions
                if transaction["value"]:
                    continue
                token = Token.objects.get(contract_address=transaction["to"])
                contract = self._web3_client.eth.contract(
                    address=token.contract_address,
                    abi=token.abi
                )
                _, parameters = contract.decode_function_input(transaction["input"])
                account = Account.objects.get(public_key=parameters.get("to"))

            except (Account.DoesNotExist, Token.DoesNotExist):
                pass
            else:
                result.append((transaction, [], {"account": account, "token": token, "contract": contract}))
        return result

    def _process_transaction(self, transaction_raw: TxData, *args, **kwargs):
        self._get_logger().info(f"Processing ERC20 transaction {transaction_raw['hash']}")

        token = kwargs["token"]

        contract = kwargs["contract"]

        _, parameters = contract.decode_function_input(transaction_raw["input"])
        account = kwargs["account"]

        token_balance = TokenBalance(
            account=account,
            token=token
        )
        token_balance.update_balance(contract)

        transaction = ReceivedTransaction(
            transaction_hash=transaction_raw["hash"],
            amount_wei=parameters["tokens"],
            sender=transaction_raw["from"],
            receiver=account,
            token=token
        )
        transaction.save()
