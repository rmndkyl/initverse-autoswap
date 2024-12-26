import os
import sys
import time
import random
import logging
import json
import requests
from web3 import Web3
from eth_account import Account
from typing import Dict, List, Optional
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
NETWORKS = {
    'InitVerse': {
        'rpc_url': 'https://rpc-testnet.iniscan.com',
        'chain_id': 233,
        'contract_address': '0x4ccB784744969D9B63C15cF07E622DDA65A88Ee7'
    }
}

TOKENS = {
    'USDT': '0x36AA81a7aEeAB8f09e154d3E779Bb81beA54501A',
    'INI': '0x9e66cd15226464EFBa8b7B2847A0880AFC236c5C',
    'TOKEN': '0xcF259Bca0315C6D32e877793B6a10e97e7647FdE'
}

# Transaction Values
TX_VALUES = {
    "INI to TOKEN": 0,  # Change to 0
    "INI to USDT": 0,   # Change to 0
    "USDT to INI": 0,   # Keep as 0
    "TOKEN to INI": 0    # Keep as 0
}

SWAP_AMOUNTS = {
    "INI to TOKEN": 0.01,
    "INI to USDT": 0.01,
    "USDT to INI": 0.006,
    "TOKEN to INI": 0.006
}

# Constants
GAS_LIMIT = 200000
GAS_PRICE_GWEI = 10
RETRY_COUNT = 3
RETRY_DELAY = 5

# Contract ABIs
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function"
    }
]

ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

class SwapError(Exception):
    """Base exception for swap-related errors"""
    pass

class TransactionManager:
    def __init__(self, web3: Web3, account: Account):
        self.web3 = web3
        self.account = account
        self.nonce = None

    def get_nonce(self) -> int:
        if self.nonce is None:
            self.nonce = self.web3.eth.get_transaction_count(self.account.address)
        else:
            self.nonce += 1
        return self.nonce

    def estimate_gas_with_buffer(self, transaction, buffer_percentage: int = 10) -> int:
        try:
            estimated_gas = self.web3.eth.estimate_gas(transaction)
            return int(estimated_gas * (1 + buffer_percentage / 100))
        except Exception as e:
            logger.warning(f"Failed to estimate gas: {e}")
            return GAS_LIMIT

    def send_transaction_with_retry(self, signed_txn, max_retries: int = RETRY_COUNT) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                # Change this line to handle both attributes
                tx_raw = signed_txn.raw_transaction if hasattr(signed_txn, 'raw_transaction') else signed_txn.rawTransaction
                tx_hash = self.web3.eth.send_raw_transaction(tx_raw)
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
                if receipt.status == 1:
                    return self.web3.to_hex(tx_hash)
                raise SwapError("Transaction failed")
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Transaction failed after {max_retries} attempts: {e}")
                    return None
                time.sleep(RETRY_DELAY * (attempt + 1))
        return None

class SwapManager:
    def __init__(self, web3: Web3, account: Account):
        self.web3 = web3
        self.account = account
        self.tx_manager = TransactionManager(web3, account)
        
    def approve_token(self, token_address: str, spender_address: str, amount: int) -> Optional[str]:
        try:
            token_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address), 
                abi=ERC20_ABI
            )
        
            # Use max uint256 for approval amount
            max_amount = (2 ** 256 - 1)
        
            txn = token_contract.functions.approve(spender_address, max_amount).build_transaction({
                'from': self.account.address,
                'nonce': self.tx_manager.get_nonce(),
                'gas': GAS_LIMIT,
                'gasPrice': self.web3.to_wei(GAS_PRICE_GWEI, 'gwei'),
                'chainId': NETWORKS['InitVerse']['chain_id'],
                'value': '0x0'  # No ETH value for approvals
            })
        
            signed_txn = self.web3.eth.account.sign_transaction(txn, private_key=self.account.key)
            return self.tx_manager.send_transaction_with_retry(signed_txn)
        
        except Exception as e:
            logger.error(f"Error approving token: {e}")
            return None

    def execute_swap(self, swap_type: str, amount_in_wei: int, path: List[str]) -> Optional[str]:
        try:
            router_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(NETWORKS['InitVerse']['contract_address']),
                abi=ROUTER_ABI
            )
        
            txn = router_contract.functions.swapExactTokensForTokens(
                amount_in_wei,
                0,  # amount_out_min
                path,
                self.account.address,
                int(time.time()) + 600  # deadline
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.tx_manager.get_nonce(),
                'gas': GAS_LIMIT,
                'gasPrice': self.web3.to_wei(GAS_PRICE_GWEI, 'gwei'),
                'chainId': NETWORKS['InitVerse']['chain_id'],
                'value': 0  # Set value to 0 for all swaps
            })
        
            signed_txn = self.web3.eth.account.sign_transaction(txn, private_key=self.account.key)
            return self.tx_manager.send_transaction_with_retry(signed_txn)
        
        except Exception as e:
            logger.error(f"Error executing swap: {e}")
            return None

class UIManager:
    @staticmethod
    def print_banner():
        banner = """
\033[96m
==============================================================================================
██╗░░░░░░█████╗░██╗░░░██╗███████╗██████╗░  ░█████╗░██╗██████╗░██████╗░██████╗░░█████╗░██████╗░
██║░░░░░██╔══██╗╚██╗░██╔╝██╔════╝██╔══██╗  ██╔══██╗██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔══██╗
██║░░░░░███████║░╚████╔╝░█████╗░░██████╔╝  ███████║██║██████╔╝██║░░██║██████╔╝██║░░██║██████╔╝
██║░░░░░██╔══██║░░╚██╔╝░░██╔══╝░░██╔══██╗  ██╔══██║██║██╔══██╗██║░░██║██╔══██╗██║░░██║██╔═══╝░
██║░░░░░██║░░██║░░░██║░░░███████╗██║░░██║  ██║░░██║██║██║░░██║██████╔╝██║░░██║╚█████╔╝██║░░░░░
╚══════╝╚═╝░░╚═╝░░░╚═╝░░░╚══════╝╚═╝░░╚═╝  ╚═╝░░╚═╝╚═╝╚═╝░░╚═╝╚═════╝░╚═╝░░╚═╝░╚════╝░╚═╝░░░░░
==============================================================================================

                    INITVERSE SCRIPT AUTO SWAP
    ==========================================================
    Community Telegram Channel  : https://t.me/layerairdrop
    Community Telegram Group    : https://t.me/layerairdropdiskusi
    ==========================================================
    Tips:
    - Make sure each wallet already claimed faucet > https://faucet-testnet.iniscan.com/
    - This script using an Pioneer Testnet Chain from Initverse.
    - You can configure (Active/Inactive) Tokens by your own.
    - DWYOR & Always use a New Wallet when running the bot, I am not responsible for any loss of assets.
    ==========================================================
\033[0m
        """
        print(banner)

    @staticmethod
    def clear_screen():
        os.system('clear' if os.name == 'posix' else 'cls')

    @staticmethod
    def print_menu():
        print("\n    \033[96m=== Main Menu ===\033[0m")
        print("    1. Run Swap Network")
        print("    2. Exit")
        print("    \033[96m==================\033[0m\n")

class SwapExecutor:
    def __init__(self, web3: Web3, accounts: List[Account]):
        self.web3 = web3
        self.accounts = accounts
        self.swap_managers = [SwapManager(web3, account) for account in accounts]

    def run_swaps(self, swap_count: int, active_swaps: Dict[str, bool]):
        logger.info(f"Starting {swap_count} swaps for {len(self.accounts)} accounts")
        total_success = 0

        for _ in range(swap_count):
            for account_index, swap_manager in enumerate(self.swap_managers):
                logger.info(f"\nProcessing account {account_index + 1}/{len(self.accounts)}")
                print(f"\033[96mWallet Address: {self.accounts[account_index].address}\033[0m")

                for swap_type, active in active_swaps.items():
                    if not active:
                        continue

                    try:
                        # Determine swap parameters
                        if swap_type in ["INI to TOKEN", "INI to USDT"]:
                            input_token = 'INI'
                            output_token = swap_type.split(' to ')[1]
                        elif swap_type in ["USDT to INI", "TOKEN to INI"]:
                            input_token = swap_type.split(' to ')[0]
                            output_token = 'INI'
                        else:
                            logger.error(f"Unknown swap type: {swap_type}")
                            continue

                        amount = SWAP_AMOUNTS[swap_type]
                        amount_wei = self.web3.to_wei(amount, 'ether')
                        path = [TOKENS[input_token], TOKENS[output_token]]

                        # Check and approve token if needed
                        token_contract = self.web3.eth.contract(
                            address=Web3.to_checksum_address(TOKENS[input_token]),
                            abi=ERC20_ABI
                        )

                        allowance = token_contract.functions.allowance(
                            self.accounts[account_index].address,
                            NETWORKS['InitVerse']['contract_address']
                        ).call()

                        if allowance < amount_wei:
                            logger.info(f"Approving {input_token} for swap...")
                            approval_tx = swap_manager.approve_token(
                                TOKENS[input_token],
                                NETWORKS['InitVerse']['contract_address'],
                                amount_wei
                            )
                            if not approval_tx:
                                logger.error(f"Failed to approve {input_token}")
                                continue

                        # Execute swap
                        tx_hash = swap_manager.execute_swap(swap_type, amount_wei, path)
                        if tx_hash:
                            logger.info(f"Swap successful: {tx_hash}")
                            logger.info(f"Type: {swap_type}, Amount: {amount} {input_token}")
                            total_success += 1

                        # Wait between swaps
                        wait_time = random.uniform(610, 650)
                        for remaining in range(int(wait_time), 0, -1):
                            sys.stdout.write(f"\rWaiting for next swap: {remaining} seconds remaining")
                            sys.stdout.flush()
                            time.sleep(1)
                        print()

                    except KeyboardInterrupt:
                        logger.info("Bot stopped by user")
                        return total_success
                    except Exception as e:
                        logger.error(f"Error processing {swap_type}: {e}")

                # Wait between accounts
                if account_index < len(self.accounts) - 1:
                    wait_time = random.uniform(30, 60)
                    for remaining in range(int(wait_time), 0, -1):
                        sys.stdout.write(f"\rWaiting for next account: {remaining} seconds remaining")
                        sys.stdout.flush()
                        time.sleep(1)
                    print()

        return total_success
    
def load_private_keys():
    """Load private keys and settings from privateKeys.json"""
    try:
        if not os.path.exists('privateKeys.json'):
            logger.error("privateKeys.json not found")
            return [], {}
            
        with open('privateKeys.json', 'r') as file:
            data = json.load(file)
            
        keys = data.get('private_keys', [])
        keys = ['0x' + key if not key.startswith('0x') else key for key in keys]
        
        settings = {
            'gas_limit': data.get('gas_limit', 200000),
            'gas_price_gwei': data.get('gas_price_gwei', 10)
        }
        
        return keys, settings
    except Exception as e:
        logger.error(f"Error loading private keys: {e}")
        return [], {}

def main():
    ui = UIManager()
    ui.clear_screen()
    ui.print_banner()

    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider(NETWORKS['InitVerse']['rpc_url']))
    
    # Load private keys and settings
    private_keys, settings = load_private_keys()
    if not private_keys:
        logger.error("No valid private keys found in privateKeys.json")
        return
        
    # Update global constants with settings from json
    global GAS_LIMIT, GAS_PRICE_GWEI
    GAS_LIMIT = settings.get('gas_limit', GAS_LIMIT)
    GAS_PRICE_GWEI = settings.get('gas_price_gwei', GAS_PRICE_GWEI)
    
    try:
        accounts = [Account.from_key(pk) for pk in private_keys]
        print(f"\033[92mLoaded {len(accounts)} accounts successfully\033[0m")
        for i, account in enumerate(accounts, 1):
            print(f"Account {i}: {account.address}")
    except Exception as e:
        logger.error(f"Error creating accounts: {e}")
        return

    active_swaps = {
        "INI to TOKEN": True,
        "INI to USDT": True,
        "USDT to INI": True,
        "TOKEN to INI": True
    }

    while True:
        ui.clear_screen()
        ui.print_banner()
        print("\n\033[96m    Select Swaps to Toggle \033[0m")
        
        for idx, (swap, active) in enumerate(active_swaps.items(), start=1):
            status = "\033[92mActive\033[0m" if active else "\033[91mInactive\033[0m"
            print(f"    {idx}. {swap} [{status}]")
        print(f"    {len(active_swaps) + 1}. Start Swaps (Will execute every 10 Minutes)")
        print(f"    {len(active_swaps) + 2}. Exit")

        try:
            choice = int(input(f"\n    \033[96mSelect option (1-{len(active_swaps) + 2}): \033[0m"))
            
            if 1 <= choice <= len(active_swaps):
                swap_name = list(active_swaps.keys())[choice - 1]
                active_swaps[swap_name] = not active_swaps[swap_name]
            elif choice == len(active_swaps) + 1:
                try:
                    swap_count = int(input("\033[96mHow many times to make Transactions: \033[0m"))
                    executor = SwapExecutor(web3, accounts)  # Instead of single account
                    total_success = executor.run_swaps(swap_count, active_swaps)
                    input(f"\n\033[92mCompleted {total_success} successful swaps. Press Enter to continue...\033[0m")
                except ValueError:
                    logger.error("Invalid number of transactions")
            elif choice == len(active_swaps) + 2:
                print("\n\033[93mExiting...\033[0m")
                break
            else:
                print("\033[91mInvalid choice\033[0m")
                time.sleep(1)
        except ValueError:
            print("\033[91mInvalid input\033[0m")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[93mBot stopped by user\033[0m")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
