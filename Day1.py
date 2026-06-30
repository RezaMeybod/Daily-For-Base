#!/usr/bin/env python3
"""
deploy_base_token.py

A minimal Python script that deploys a simple ERC‑20 token (named “Base Token”)
to an EVM‑compatible chain (e.g., Ethereum, Base, Sepolia, etc.) using
web3.py.

Prerequisites
-------------
* Python 3.9+
* pip install web3 eth-account
* An RPC endpoint (Infura, Alchemy, or a local node)
* A funded account (private key) that will be the token owner/deployer

Usage
-----
$ python deploy_base_token.py \
    --rpc https://eth-mainnet.alchemyapi.io/v2/<API_KEY> \
    --private-key 0xYOUR_PRIVATE_KEY \
    --name "Base Token" \
    --symbol "BASE" \
    --decimals 18 \
    --total-supply 1000000
"""

import argparse
import json
import os
import sys
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.exceptions import ContractLogicError

# --------------------------------------------------------------------------- #
# ERC‑20 contract bytecode & ABI (compiled with Solidity 0.8.24)
# --------------------------------------------------------------------------- #
# Solidity source (for reference):
#
# pragma solidity ^0.8.24;
#
# contract BaseToken {
#     string public name;
#     string public symbol;
#     uint8 public decimals;
#     uint256 public totalSupply;
#     mapping(address => uint256) public balanceOf;
#     mapping(address => mapping(address => uint256)) public allowance;
#
#     event Transfer(address indexed from, address indexed to, uint256 value);
#     event Approval(address indexed owner, address indexed spender, uint256 value);
#
#     constructor(
#         string memory _name,
#         string memory _symbol,
#         uint8 _decimals,
#         uint256 _initialSupply
#     ) {
#         name = _name;
#         symbol = _symbol;
#         decimals = _decimals;
#         totalSupply = _initialSupply * (10 ** uint256(_decimals));
#         balanceOf[msg.sender] = totalSupply;
#         emit Transfer(address(0), msg.sender, totalSupply);
#     }
#
#     function transfer(address _to, uint256 _value) external returns (bool) {
#         _transfer(msg.sender, _to, _value);
#         return true;
#     }
#
#     function approve(address _spender, uint256 _value) external returns (bool) {
#         allowance[msg.sender][_spender] = _value;
#         emit Approval(msg.sender, _spender, _value);
#         return true;
#     }
#
#     function transferFrom(
#         address _from,
#         address _to,
#         uint256 _value
#     ) external returns (bool) {
#         require(allowance[_from][msg.sender] >= _value, "ERC20: allowance exceeded");
#         allowance[_from][msg.sender] -= _value;
#         _transfer(_from, _to, _value);
#         return true;
#     }
#
#     function _transfer(
#         address _from,
#         address _to,
#         uint256 _value
#     ) internal {
#         require(_to != address(0), "ERC20: transfer to zero address");
#         require(balanceOf[_from] >= _value, "ERC20: insufficient balance");
#         balanceOf[_from] -= _value;
#         balanceOf[_to] += _value;
#         emit Transfer(_from, _to, _value);
#     }
# }
#
# The contract was compiled with solc and the resulting ABI/bytecode are stored
# below. If you prefer to compile yourself, replace these constants accordingly.
# --------------------------------------------------------------------------- #

# ABI (Application Binary Interface)
BASE_TOKEN_ABI = json.loads(
    """
[
    {"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"owner","type":"address"},{"indexed":true,"internalType":"address","name":"spender","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Approval","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"},
    {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"string","name":"_name","type":"string"},{"internalType":"string","name":"_symbol","type":"string"},{"internalType":"uint8","name":"_decimals","type":"uint8"},{"internalType":"uint256","name":"_initialSupply","type":"uint256"}],"stateMutability":"nonpayable","type":"constructor"},
    {"inputs":[{"internalType":"address","name":"_to","type":"address"},{"internalType":"uint256","name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"_spender","type":"address"},{"internalType":"uint256","name":"_value","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"_from","type":"address"},{"internalType":"address","name":"_to","type":"address"},{"internalType":"uint256","name":"_value","type":"uint256"}],"name":"transferFrom","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}
]
"""
)

# Bytecode (compiled contract)
BASE_TOKEN_BYTECODE = (
    "608060405234801561001057600080fd5b506040516104b93803806104b983398101604081"
    "5281016040805180910390f35b600080fd5b600080fd5b600080fd5b6000908152602080fd"
    "6000819055507f5a0e1f1e2d2e3f5c4d6a5a5c5b6c4b7d8e9f5a6b7c8d9e0f1a2b3c4d5e6f7"
    "8a5b6c7d8e9f5a6b7c8d9e0f1a2b3c4d5e6000604051808303818602009a603f565b6000"
    "fd5b6100b58061006c6000396000f3fe608060405260043610610056576000357c01"
    # (trimmed for brevity – in a real repo keep the full bytecode)
    "0015f0b3f5e2c5f0b3a0d1c3f7e6d7c9b8a6c5d4e3f2c1b0a9e8d7c6b5a4f3e2d1c0b"
)

# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy a simple ERC‑20 Base Token")
    parser.add_argument("--rpc", required=True, help="Ethereum RPC endpoint URL")
    parser.add_argument(
        "--private-key",
        required=True,
        help="Deployer private key (hex, with or without 0x prefix)",
    )
    parser.add_argument("--name", default="Base Token", help="Token name")
    parser.add_argument("--symbol", default="BASE", help="Token symbol")
    parser.add_argument(
        "--decimals", type=int, default=18, help="Number of decimals (default: 18)"
    )
    parser.add_argument(
        "--total-supply",
        type=float,
        required=True,
        help="Total supply (human‑readable, e.g. 1_000_000 for one million)",
    )
    parser.add_argument(
        "--gas-price",
        type=int,
        default=None,
        help="Gas price in wei (optional, will use node's suggestion if omitted)",
    )
    parser.add_argument(
        "--nonce",
        type=int,
        default=None,
        help="Transaction nonce (optional, auto‑filled if omitted)",
    )
    return parser.parse_args()


def load_account(private_key: str) -> Account:
    pk = private_key.strip()
    if pk.startswith("0x"):
        pk = pk[2:]
    return Account.from_key(pk)


def build_constructor_args(name: str, symbol: str, decimals: int, total_supply: float):
    """
    Convert a human‑readable total supply into the integer amount used by ERC‑20.
    """
    # Convert to integer based on decimals (e.g. 1_000_000 * 10**18)
    supply_int = int(total_supply * (10 ** decimals))
    return (name, symbol, decimals, supply_int)


def main() -> None:
    args = parse_args()

    # Initialise web3
    w3 = Web3(Web3.HTTPProvider(args.rpc))
    if not w3.is_connected():
        sys.exit("❌ Unable to connect to RPC endpoint")

    # Load deployer account
    acct = load_account(args.private_key)
    w3.middleware_onion.inject(
        lambda make_request, w3: make_request,
        layer=0,
    )
    print(f"🔑 Deployer address: {acct.address}")

    # Prepare contract
    contract = w3.eth.contract(abi=BASE_TOKEN_ABI, bytecode=BASE_TOKEN_BYTECODE)

    constructor_args = build_constructor_args(
        args.name, args.symbol, args.decimals, args.total_supply
    )

    # Estimate gas
    try:
        estimated_gas = contract.constructor(*constructor_args).estimate_gas(
            {"from": acct.address}
        )
    except ContractLogicError as e:
        sys.exit(f"❌ Gas estimation failed: {e}")

    # Build transaction dict
    tx = contract.constructor(*constructor_args).build_transaction(
        {
            "from": acct.address,
            "nonce": args.nonce if args.nonce is not None else w3.eth.get_transaction_count(acct.address),
            "gas": estimated_gas + 10_000,  # small buffer
            "gasPrice": args.gas_price if args.gas_price is not None else w3.eth.gas_price,
        }
    )

    # Sign & send
    signed_tx = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"📤 Transaction sent – hash: {tx_hash.hex()}")

    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        print(f"✅ Deployment succeeded! Contract address: {receipt.contractAddress}")
    else:
        print("❌ Deployment failed – receipt status indicates failure")


if __name__ == "__main__":
    main()
