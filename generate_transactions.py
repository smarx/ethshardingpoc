import json
from web3 import Web3
from config import NUM_TRANSACTIONS
from config import DEADBEEF

web3 = Web3()

alice_key = '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318'
alice_address = web3.eth.account.privateKeyToAccount(alice_key).address.lower()[2:]

abi = json.loads('[{"constant":false,"inputs":[{"name":"_shard_ID","type":"uint256"},{"name":"_sendGas","type":"uint256"},{"name":"_sendToAddress","type":"address"},{"name":"_data","type":"bytes"}],"name":"send","outputs":[],"payable":true,"stateMutability":"payable","type":"function"},{"anonymous":false,"inputs":[{"indexed":true,"name":"shard_ID","type":"uint256"},{"indexed":false,"name":"sendGas","type":"uint256"},{"indexed":false,"name":"sendFromAddress","type":"address"},{"indexed":true,"name":"sendToAddress","type":"address"},{"indexed":false,"name":"value","type":"uint256"},{"indexed":false,"name":"data","type":"bytes"},{"indexed":true,"name":"base","type":"uint256"},{"indexed":false,"name":"TTL","type":"uint256"}],"name":"SentMessage","type":"event"}]')
contract = web3.eth.contract(address='0x000000000000000000000000000000000000002A', abi=abi)


def format_transaction(tx, signed):
    if isinstance(tx["data"], bytes):
        data = tx["data"].hex()
    else:
        data = tx["data"]

    return {
        "gas": hex(tx["gas"]),
        "gasPrice": tx["gasPrice"],
        "hash": signed["hash"].hex(),
        "input": data,
        "nonce": tx["nonce"],
        "r": hex(signed["r"]),
        "s": hex(signed["s"]),
        "v": hex(signed["v"]),
        "to": tx["to"],
        "value": hex(tx["value"]),
    }


# Alice sends cross shard transactions
def gen_cross_shard_tx(nonce):
    cross_shard_tx = contract.functions.send(1, 300000, DEADBEEF, bytes(0)).buildTransaction({ "gas": 3000000, "gasPrice": "0x2", "nonce": hex(nonce), "value": 1})

    cross_shard_tx_signed = web3.eth.account.signTransaction(cross_shard_tx, alice_key)
    cross_shard_tx_formatted = format_transaction(cross_shard_tx, cross_shard_tx_signed)
    return cross_shard_tx_formatted


'''
# Bob sends simple transfers between account in the same shard
def gen_in_shard_tx(nonce):
    private_key_bob = '0x5c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318'
    address_bob = web3.eth.account.privateKeyToAccount(private_key_bob).address.lower()[2:]
    in_shard_tx = {
      "gas": 3000000,
      "gasPrice": "0x2",
      "nonce": "0x0",  # we will need to overwrite this by getting the nonce from the state
      "to": "0x000000000000000000000000000000000000002F",
      "value": 20,
      "data": "0x",
    }

    in_shard_tx_signed = web3.eth.account.signTransaction(in_shard_tx, private_key_bob)
    in_shard_tx_formatted = format_transaction(in_shard_tx, in_shard_tx_signed)
    return in_shard_tx_formatted


def gen_payloads():
    private_key_alice = '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318'
    address_alice = web3.eth.account.privateKeyToAccount(private_key_alice).address.lower()[2:]

    payloadA = {
        "fromAddress": address_alice,
        "toAddress": "0x000000000000000000000000000000000000002A",
        "value": 100,
        "data": cross_shard_tx["data"]
    }

    # MessagePayload(address_alice, "0x000000000000000000000000000000000000002A", 100, cross_shard_tx["data"])
    tx = []
    for x in range(0, 100):
        tx.append(payloadA)
    return tx

'''

def gen_alice_and_bob_tx():
    tx = []
    for x in range(0, NUM_TRANSACTIONS):
        # tx.append(gen_in_shard_tx(hex(x)))
        tx.append(gen_cross_shard_tx(x))
    # print(tx[0])
    return tx
