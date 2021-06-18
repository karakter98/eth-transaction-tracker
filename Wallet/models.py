from decimal import Decimal
from typing import Union

import eth_utils
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from hexbytes import HexBytes
from eth_account import Account as EthAccount
from web3 import Web3
from web3.contract import Contract


def validate_public_address(address: str):
    if not eth_utils.is_hex_address(address):
        raise ValidationError(f"{address} is not a valid Ethereum address.")


def validate_private_key(key: HexBytes):
    # 32 bytes = 64 hex characters = 256 bits
    if len(key.hex().strip("0x")) != 32:
        raise ValidationError(f"{key} is not a valid Ethereum private key.")


def validate_tx_hash(tx_hash: HexBytes):
    # 32 bytes = 64 hex characters = 256 bits
    if len(tx_hash.hex().strip("0x")) != 64:
        raise ValidationError(f"{tx_hash} is not a valid Ethereum transaction hash.")


def validate_contract_address(contract_address: str):
    # 20 bytes = 40 hex characters
    if len(HexBytes(contract_address).hex().strip("0x")) != 40:
        raise ValidationError(f"{contract_address} is not a valid Ethereum contract address.")


class Token(models.Model):
    contract_address = models.CharField(unique=True, max_length=128, validators=[validate_contract_address])
    abi = models.CharField(max_length=100000)
    name = models.CharField(max_length=128)
    symbol = models.CharField(max_length=10)
    decimals = models.PositiveSmallIntegerField()

    def __str__(self):
        return self.name

    def clean(self):
        web3_client = Web3(Web3.HTTPProvider(settings.INFURA_URL))
        contract = web3_client.eth.contract(
            address=HexBytes.fromhex(self.contract_address.strip("0x")),
            abi=self.abi
        )

        self.name = contract.functions.name().call()
        self.symbol = contract.functions.symbol().call()
        self.decimals = contract.functions.decimals().call()

        super().clean()

    def to_lowest_denomination(self, value: Union[int, float, Decimal]) -> int:
        result = Decimal(value)
        for _ in range(self.decimals):
            result *= 10
        return int(result)

    def from_lowest_denomination(self, value: Union[int, float, Decimal]) -> Decimal:
        result = Decimal(value)
        for _ in range(self.decimals):
            result /= 10
        return result


class Account(models.Model):
    name = models.CharField(max_length=128)
    public_key = models.CharField(unique=True, max_length=128, validators=[validate_public_address])
    private_key = models.BinaryField(unique=True, validators=[validate_private_key], editable=False)
    # Balance in ETH wei
    balance_wei = models.PositiveBigIntegerField(editable=False)
    tokens = models.ManyToManyField(to=Token, through="TokenBalance")

    def __str__(self):
        return self.name

    def erc20_balances(self) -> str:
        return ", ".join([
            " ".join([
                token_balance.token.symbol,
                str(token_balance.token.from_lowest_denomination(token_balance.balance))
            ])
            for token_balance in TokenBalance.objects.filter(account=self)
        ])

    def __init__(self, *args, **kwargs):
        account = EthAccount.create()
        kwargs["private_key"], kwargs["public_key"] = account.key, Web3.toChecksumAddress(account.address)
        kwargs["balance_wei"] = 0
        super().__init__(*args, **kwargs)

    def balance(self) -> Decimal:
        return Web3.fromWei(self.balance_wei, "ether")

    def update_balance(self, web3_client: Web3):
        self.balance_wei = web3_client.eth.get_balance(self.public_key)
        self.save()


class TokenBalance(models.Model):
    class Meta:
        unique_together = ("token", "account",)

    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    balance = models.PositiveBigIntegerField()

    def __str__(self):
        return " ".join([self.token.symbol, str(self.token.to_lowest_denomination(self.balance))])

    def update_balance(self, contract: Contract):
        try:
            existing_item = self.__class__.objects.get(token=self.token, account=self.account)
            self.pk = existing_item.pk
        except self.__class__.DoesNotExist:
            pass

        self.balance = contract.functions.balanceOf(self.account.public_key).call()

        self.save()


class Transaction(models.Model):
    class Meta:
        abstract = True

    transaction_hash = models.BinaryField(unique=True, validators=[validate_tx_hash])
    # Amount in the smallest denomination of the transacted token. If ETH, amount in wei.
    amount_wei = models.PositiveBigIntegerField(editable=False)
    token = models.ForeignKey(Token, on_delete=models.CASCADE, null=True)

    def tx_hash(self) -> str:
        return "0x" + self.transaction_hash.hex()

    def amount(self) -> Decimal:
        result = Decimal(self.amount_wei)

        decimals = 18 if not self.token else self.token.decimals
        for _ in range(decimals):
            result /= 10

        return result


class SentTransaction(Transaction):
    sender = models.ForeignKey(Account, on_delete=models.CASCADE)
    receiver = models.CharField(max_length=128, validators=[validate_public_address])


class ReceivedTransaction(Transaction):
    sender = models.CharField(max_length=128, validators=[validate_public_address])
    receiver = models.ForeignKey(Account, on_delete=models.CASCADE)
