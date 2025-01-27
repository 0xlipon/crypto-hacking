import requests
import logging
import time
from mnemonic import Mnemonic
import bip32utils
from eth_account import Account

# Enable unaudited HD wallet features in eth_account
Account.enable_unaudited_hdwallet_features()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to derive Bitcoin address from seed phrase
def derive_btc_address(seed_phrase):
    try:
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(seed_phrase)
        root_key = bip32utils.BIP32Key.fromEntropy(seed)
        child_key = root_key.ChildKey(44 + bip32utils.BIP32_HARDEN).ChildKey(0 + bip32utils.BIP32_HARDEN).ChildKey(0 + bip32utils.BIP32_HARDEN).ChildKey(0).ChildKey(0)
        return child_key.Address()
    except Exception as e:
        logging.error(f"Error deriving BTC address: {e}")
        return None

# Function to derive Ethereum address from seed phrase
def derive_eth_address(seed_phrase):
    try:
        account = Account.from_mnemonic(seed_phrase)
        return account.address
    except Exception as e:
        logging.error(f"Error deriving ETH address: {e}")
        return None

# Function to check balance of a given Bitcoin address
def check_btc_balance(address):
    try:
        api_url = f"https://blockstream.info/api/address/{address}"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            funded = data.get('chain_stats', {}).get('funded_txo_sum', 0)
            spent = data.get('chain_stats', {}).get('spent_txo_sum', 0)
            return funded - spent
        else:
            logging.error(f"Error fetching balance for BTC address {address}: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error in BTC balance check: {e}")
        return None

# Function to check balance of a given Ethereum address using Etherscan
def check_eth_balance(address, api_key):
    try:
        api_url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
        response = requests.get(api_url)
        if response.status_code == 200:
            return int(response.json().get('result', 0))  # Balance in wei
        else:
            logging.error(f"Error fetching balance for ETH address {address}: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error in ETH balance check: {e}")
        return None

# Function to get current exchange rates for BTC and ETH
def get_exchange_rates():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd")
        if response.status_code == 200:
            rates = response.json()
            return rates['bitcoin']['usd'], rates['ethereum']['usd']
        else:
            logging.error(f"Error fetching exchange rates: {response.status_code}")
            return None, None
    except Exception as e:
        logging.error(f"Error in exchange rate fetch: {e}")
        return None, None

# Function to load seed phrases from a file
def load_seeds_from_file(file_path):
    try:
        with open(file_path, "r") as file:
            seeds = file.readlines()
        logging.info("Loaded seeds.")
        return [seed.strip() for seed in seeds if seed.strip()]
    except Exception as e:
        logging.error(f"Error reading seed file: {e}")
        return []

# Function to validate a seed phrase
def is_valid_seed(seed):
    mnemo = Mnemonic("english")
    return mnemo.check(seed)

# Function to save results to a file
def save_results_to_file(results, file_path):
    try:
        with open(file_path, "w") as file:
            for result in results:
                file.write(result + "\n")
        logging.info("Results saved.")
    except Exception as e:
        logging.error(f"Error writing results to file: {e}")

# Main function to check balances
def check_balances(input_file, output_file, eth_api_key):
    seeds = load_seeds_from_file(input_file)
    btc_usd_rate, eth_usd_rate = get_exchange_rates()

    if btc_usd_rate is None or eth_usd_rate is None:
        logging.error("Error fetching exchange rates. Exiting.")
        return

    results = []

    for seed in seeds:
        if not is_valid_seed(seed):
            logging.warning(f"Invalid Seed Phrase: {seed}")
            continue

        try:
            logging.info(f"Checking seed: {seed}")

            btc_address = derive_btc_address(seed)
            eth_address = derive_eth_address(seed)

            if not btc_address or not eth_address:
                continue

            logging.info(f"BTC Address: {btc_address}, ETH Address: {eth_address}")

            btc_balance = check_btc_balance(btc_address)
            eth_balance = check_eth_balance(eth_address, eth_api_key)

            logging.info(f"BTC Balance: {btc_balance}, ETH Balance: {eth_balance}")

            btc_balance_usd = (btc_balance / 1e8) * btc_usd_rate if btc_balance else 0
            eth_balance_usd = (eth_balance / 1e18) * eth_usd_rate if eth_balance else 0
            total_usd_balance = btc_balance_usd + eth_balance_usd

            logging.info(f"Total USD Balance: ${total_usd_balance:.2f}")

            if btc_balance > 0 or eth_balance > 0:
                result = (f"Seed Phrase: {seed}\n"
                          f"Bitcoin Address: {btc_address}\n"
                          f"Bitcoin Balance: {btc_balance} satoshis (${btc_balance_usd:.2f} USD)\n"
                          f"Ethereum Address: {eth_address}\n"
                          f"Ethereum Balance: {eth_balance} wei (${eth_balance_usd:.2f} USD)\n"
                          f"Total USD Balance: ${total_usd_balance:.2f}\n")
                results.append(result)
                logging.info(result)

            # Add delay to avoid rate-limiting
            time.sleep(1)

        except Exception as e:
            logging.error(f"Error processing seed {seed}: {e}")

    if results:
        save_results_to_file(results, output_file)

# Automatically use seeds.txt as input and results.txt as output
if __name__ == "__main__":
    input_file = "seeds.txt"
    output_file = "results.txt"
    eth_api_key = "Q1RSCRCHHKC47KHU1MJ4HPIIC7YHYUTRFEEE8"  # Replace with your Etherscan API key
    check_balances(input_file, output_file, eth_api_key)
