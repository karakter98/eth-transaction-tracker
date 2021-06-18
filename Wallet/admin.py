from decimal import Decimal

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.helpers import ActionForm
from django.db.models import QuerySet
from django import forms
from django.http import HttpRequest
from web3 import Web3

from Wallet.models import Account, SentTransaction, ReceivedTransaction, validate_public_address, Token


@admin.register(Token)
class AdminToken(admin.ModelAdmin):
    readonly_fields = ["name", "symbol", "decimals"]
    list_display = ["name", "symbol"]

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Account)
class AdminAccount(admin.ModelAdmin):
    readonly_fields = ["public_key", "balance", "erc20_balances"]
    exclude = ["tokens"]
    list_display = ["name", "public_key", "balance"]

    class SendForm(ActionForm):
        amount = forms.DecimalField()
        address = forms.CharField(validators=[validate_public_address])
        token = forms.ModelChoiceField(Token.objects.all(), required=False)

    @admin.action(description="Send ETH to another address")
    def send_eth(self, request: HttpRequest, queryset: QuerySet):
        for account in queryset:
            account: Account

            web3_client = Web3(Web3.HTTPProvider(settings.INFURA_URL))
            # noinspection PyTypeChecker
            signed_transaction = web3_client.eth.account.sign_transaction(
                dict(
                    to=request.POST["address"],
                    value=Web3.toWei(Decimal(request.POST["amount"]), "ether"),
                    gas=1000000,
                    gasPrice=web3_client.eth.gas_price,
                    nonce=web3_client.eth.get_transaction_count(account.public_key)
                ),
                account.private_key.hex()
            )
            web3_client.eth.send_raw_transaction(signed_transaction.rawTransaction)

    @admin.action(description="Send ERC20 to another address")
    def send_erc20(self, request: HttpRequest, queryset: QuerySet):
        for account in queryset:
            account: Account
            web3_client = Web3(Web3.HTTPProvider(settings.INFURA_URL))
            # noinspection PyTypeChecker
            token = Token.objects.get(pk=request.POST["token"])
            # noinspection PyTypeChecker
            contract = web3_client.eth.contract(
                address=token.contract_address,
                abi=token.abi
            )
            # noinspection PyTypeChecker
            signed_transaction = web3_client.eth.account.signTransaction(
                contract.functions.transfer(
                    request.POST["address"],
                    token.to_lowest_denomination(request.POST["amount"])
                ).buildTransaction({
                    "gas": 1000000,
                    "gasPrice": web3_client.eth.gas_price,
                    "nonce": web3_client.eth.get_transaction_count(account.public_key)
                }),
                account.private_key
            )

            web3_client.eth.send_raw_transaction(signed_transaction.rawTransaction)

    actions = [send_eth, send_erc20]
    action_form = SendForm


@admin.register(SentTransaction)
class AdminSentTransaction(admin.ModelAdmin):
    readonly_fields = ("tx_hash", "amount")
    list_display = ["tx_hash", "amount", "token", "sender", "receiver"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


@admin.register(ReceivedTransaction)
class AdminReceivedTransaction(admin.ModelAdmin):
    readonly_fields = ("tx_hash", "amount")
    list_display = ["tx_hash", "amount", "token", "sender", "receiver"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False
