#!/usr/bin/env python3
import requests
import time
import random
import threading
from mnemonic import Mnemonic
import bip32utils
from eth_account import Account
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)
Account.enable_unaudited_hdwallet_features()

class KeyManager:
    def __init__(self, api_keys, requests_per_second=5):
        self.keys = api_keys
        self.rps = requests_per_second
        self.timestamps = {key: 0 for key in self.keys}
        self.lock = threading.Lock()
        self.last_rate_check = 0
        self.btc_rate = 0
        self.eth_rate = 0

    def get_key(self):
        with self.lock:
            now = time.time()
            valid_keys = [k for k, t in self.timestamps.items() if now - t >= 1/self.rps]
            
            if valid_keys:
                key = random.choice(valid_keys)
                self.timestamps[key] = now
                return key
            
            # Find the key that becomes available first
            oldest_key = min(self.timestamps, key=lambda k: self.timestamps[k])
            wait_time = (self.timestamps[oldest_key] + 1/self.rps) - now
            if wait_time > 0:
                time.sleep(wait_time)
            self.timestamps[oldest_key] = time.time()
            return oldest_key

    def refresh_rates(self):
        if time.time() - self.last_rate_check > 30:  # Refresh every 30 seconds
            try:
                response = requests.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
                    timeout=5
                )
                rates = response.json()
                self.btc_rate = rates['bitcoin']['usd']
                self.eth_rate = rates['ethereum']['usd']
                self.last_rate_check = time.time()
            except:
                pass

def derive_addresses(seed):
    try:
        # BTC Address
        mnemo = Mnemonic("english")
        seed_bytes = mnemo.to_seed(seed)
        root = bip32utils.BIP32Key.fromEntropy(seed_bytes)
        child = root.ChildKey(44+0x80000000).ChildKey(0+0x80000000)
        child = child.ChildKey(0+0x80000000).ChildKey(0).ChildKey(0)
        btc_addr = child.Address()

        # ETH Address
        eth_addr = Account.from_mnemonic(seed).address

        return btc_addr, eth_addr
    except:
        return None, None

def check_balances(seed, key_manager):
    btc_addr, eth_addr = derive_addresses(seed)
    if not btc_addr or not eth_addr:
        return None

    # Check BTC balance
    try:
        btc_response = requests.get(
            f"https://blockchain.info/balance?active={btc_addr}",
            timeout=5
        )
        btc_balance = btc_response.json()[btc_addr]['final_balance']
    except:
        btc_balance = 0

    # Check ETH balance with proper key rotation
    eth_balance = 0
    try:
        api_key = key_manager.get_key()
        eth_response = requests.get(
            f"https://api.etherscan.io/api?module=account&action=balance&address={eth_addr}&tag=latest&apikey={api_key}",
            timeout=5
        )
        eth_balance = int(eth_response.json().get('result', 0))
    except:
        pass

    # Update exchange rates
    key_manager.refresh_rates()

    # Prepare output
    output = [
        f"{Fore.BLUE}[*] Processing Seed: {seed}",
        f"{Fore.CYAN}[+] BTC Address: {btc_addr}",
        f"{Fore.CYAN}[+] ETH Address: {eth_addr}",
        f"{Fore.YELLOW}[-] BTC Balance: ${(btc_balance / 1e8) * key_manager.btc_rate:.2f}",
        f"{Fore.YELLOW}[-] ETH Balance: ${(eth_balance / 1e18) * key_manager.eth_rate:.2f}",
        f"{Fore.GREEN}[*] Total USD Balance: ${(btc_balance / 1e8 * key_manager.btc_rate) + (eth_balance / 1e18 * key_manager.eth_rate):.2f}"
    ]

    print('\n'.join(output) + '\n')

    if btc_balance > 0 or eth_balance > 0:
        return {
            'seed': seed,
            'btc': btc_addr,
            'eth': eth_addr,
            'balances': (btc_balance, eth_balance)
        }

def main():

    #  Banner
    print(f"\n{Fore.CYAN}┌───────────────────────────────────────────────┐")
    print(f"{Fore.WHITE}│💰 {Fore.BLUE}C R Y P T O   B A L A N C E   C H E C K E R  {Fore.WHITE}")
    print(f"{Fore.CYAN}├───────────────────────────────────────────────┤")
    print(f"{Fore.WHITE}│         {Fore.CYAN}Version: 1.0 • Author: 0xlipon           {Fore.WHITE}")
    print(f"{Fore.CYAN}└───────────────────────────────────────────────┘{Style.RESET_ALL}\n")

    API_KEYS = [
        "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
             [Add More Fifty API KEYs]
        "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    ]

    key_manager = KeyManager(API_KEYS, requests_per_second=5)
    key_manager.refresh_rates()

    try:
        with open("seeds.txt") as f:
            seeds = [s.strip() for s in f.readlines() if s.strip()]
    except:
        print(f"{Fore.RED}[-] Error loading seeds.txt{Style.RESET_ALL}")
        return

    with ThreadPoolExecutor(max_workers=len(API_KEYS) * 2) as executor:
        futures = {executor.submit(check_balances, seed, key_manager): seed for seed in seeds}
        results = []
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    # Completion message here
    print(f"{Fore.GREEN}✓ Checked Completed! 🚀{Style.RESET_ALL}")

    if results:
        with open("balances.txt", "w") as f:
            for r in results:
                f.write(f"Seed: {r['seed']}\n")
                f.write(f"BTC Address: {r['btc']}\n")
                f.write(f"ETH Address: {r['eth']}\n")
                f.write(f"BTC Balance: {r['balances'][0]} satoshi\n")
                f.write(f"ETH Balance: {r['balances'][1]} wei\n\n")


if __name__ == "__main__":
    main()
