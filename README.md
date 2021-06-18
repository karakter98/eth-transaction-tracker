### Setup
1. Go to **Entrypoint/settings.py** and replace `INFURA_URL = "<HTTP URL>"` with your Infura project HTTP URL.
2. Open a terminal and go to the project root:
   
    `cd <project root location>`
3. Install requirements from requirements.txt:
   
    `pip3 install -r requirements.txt`
4. Run `python3 manage.py makemigrations`
5. Run `python3 manage.py migrate`
6. Create an admin account so you can access the admin panel:
   
   `python3 manage.py createsuperuser`
7. Run the server without hot reloading enabled.
   This is needed because when hot reloading, Django
   starts 2 separate background threads for the app.
   This would spawn 2 different instances of the block consumer service,
   and would capture all transactions twice.
   
    `python3 manage.py runserver --noreload 8000`
8. Open a browser and navigate to the admin panel at http://127.0.0.1:8000/admin
9. Log into the admin panel
10. Go to "Tokens" and click "Add"
11. Insert the contract address and the ABI for any ERC20 token you want to track transactions for.
    
   Example for Yeenus: https://ropsten.etherscan.io/address/0xF6fF95D53E08c9660dC7820fD5A775484f77183A#code

12. Go to "Accounts" and click "Add"
13. Give a name to the auto-generated account.
14. You're all set to start tracking transactions!

### Architecture overview
When starting the server, in **Wallet/apps.py**, the app is using Django's `ready()` hook to 
start a background thread when the Django server starts. This background thread listens for 
new blocks being produced on the blockchain. Whenever a new block is picked up, the transaction
processors are notified. Each type of processor receives the newly mined block and scans it
for transactions that are of interest to it.

The transaction processors defined in this project are:
- `IncomingTransactionProcessor` - processes ETH transactions that were sent to wallets in our database.
- `IncomingERC20Processor` - processes ERC20 transactions that were sent to wallets in our database.
- `OutgoingTransactionProcessor` - processes ETH transactions that were sent from wallets in our database.
- `OutgoingERC20Processor` - processes ERC20 transactions that were sent from wallets in our database.

This system can be further expanded to allow for different types of processors if needed.

When the processor is notified that a block has been produced, it tracks the block number
for all transactions that are of interest. Based on the block number, it also tracks the number of
confirmations for all of these transactions. When enough confirmations arrived, then the transactions are processed.

### System robustness
From my tests, I noticed that sometimes, some blocks could be skipped if only listening to the
latest block produced. I added a failsafe mechanism for this in `BlockFetcher.poll()` such that,
if any blocks have been skipped, it first fetches the skipped blocks before proceeding to the latest one.

This ensures all blocks are processed correctly while the service is running.

Only transactions that happened while the service is running can be tracked to the database.
This happens because going through the whole blockchain to bootstrap a correct state at startup
would take far too much processing time for a toy project. That said, if we wanted to be truly robust
even allowing for system downtime, the last processed block could be persisted on disk so that when restarting,
the processing resumes from that block.

This will only track ERC20 token transactions for tokens added to the database.

Sometimes, it seems the `BlockFetcher` doesn't receive any blocks from the Infura node.
If no logs in the following format appear in 1-2 minutes:

`INFO:blockchain_consumer.block_fetcher:Found block 10458899`

a restart of the Django app should solve the issue

### But how do I test it?

**_The following scenarios assume that you followed the Setup instructions and there are at least
1 wallet and 1 ERC20 token in the database._**

#### Receive ETH transaction
1. Use Metamask or any other Ethereum wallet
2. In Django Admin, go to "Accounts" and copy the public address of the account generated in the database
3. Send ETH from Metamask to this address
4. Wait for the transaction to receive 6 confirmations and be picked up by the service
5. In Django Admin, go to "Received transactions". The transaction should show up here, with a
blank "Token" field (since this is ETH not an ERC20 token)
   
#### Receive ERC20 transaction
Same as above, but the transaction should appear with the "Token" field populated in Django Admin.

#### Send ETH transaction
1. In Django Admin, go to "Accounts"
2. Select the account you want to transfer ETH from by ticking the box next to it
3. From the "Action" dropdown, select "Send ETH to another address"
4. Complete the amount of ETH you want to send and the destination address
5. Hit "Go"
6. Wait for the transaction to receive 6 confirmations and be picked up by the service
7. In Django Admin, go to "Sent transactions". The transaction should show up here, with a
blank "Token" field (since this is ETH not an ERC20 token)
8. The transaction should also show up in your wallet (e.g. Metamask)
   
#### Send ERC20 transaction
1. In Django Admin, go to "Accounts"
2. Select the account you want to transfer tokens from by ticking the box next to it
3. From the "Action" dropdown, select "Send ERC20 to another address"
4. Complete the amount of ERC20 tokens you want to send and the destination address. 
   Select which token to send from the "Token" dropdown
5. Hit "Go"
6. Wait for the transaction to receive 6 confirmations and be picked up by the service
7. In Django Admin, go to "Sent transactions". The transaction should show up here, with the
corresponding "Token" field
8. The transaction should also show up in your wallet (e.g. Metamask)
