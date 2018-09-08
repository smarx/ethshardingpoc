import json
import subprocess
import os

import blocks
from web3 import Web3

abi = json.loads('[{"constant":false,"inputs":[{"name":"_shard_ID","type":"uint256"},{"name":"_sendGas","type":"uint256"},{"name":"_sendToAddress","type":"address"},{"name":"_data","type":"bytes"}],"name":"send","outputs":[],"payable":true,"stateMutability":"payable","type":"function"},{"anonymous":false,"inputs":[{"indexed":true,"name":"shard_ID","type":"uint256"},{"indexed":false,"name":"sendGas","type":"uint256"},{"indexed":false,"name":"sendFromAddress","type":"address"},{"indexed":false,"name":"sendToAddress","type":"address"},{"indexed":false,"name":"value","type":"uint256"},{"indexed":false,"name":"data","type":"bytes"},{"indexed":true,"name":"base","type":"uint256"},{"indexed":false,"name":"TTL","type":"uint256"}],"name":"SentMessage","type":"event"}]')

web3 = Web3()

vladvm_path = './vladvm-ubuntu'
if(os.getenv("_system_type")):
    vladvm_path = './vladvm-macos'

contract = web3.eth.contract(address='0x000000000000000000000000000000000000002A', abi=abi)
tx = contract.functions.send(1, 300000, '0xDeaDbeefdEAdbeefdEadbEEFdeadbeEFdEaDbeeF', '0x1234').buildTransaction({ "gas": 3000000, "gasPrice": "0x2", "nonce": "0x0", "value": 5 })

signed = web3.eth.account.signTransaction(tx, '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318')
address = web3.eth.account.privateKeyToAccount('0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318').address

def format_transaction(tx, signed):
    return {
        "gas": hex(tx["gas"]),
        "gasPrice": tx["gasPrice"],
        "hash": signed["hash"].hex(),
        "input": tx["data"],
        "nonce": tx["nonce"],
        "r": hex(signed["r"]),
        "s": hex(signed["s"]),
        "v": hex(signed["v"]),
        "to": tx["to"],
        "value": hex(tx["value"]),
    }

vm_state = {
    "env": {
      "currentCoinbase": "0xc94f5374fce5edbc8e2a8697c15331677e6ebf0b",
      "currentDifficulty": "0x20000",
      "currentGasLimit": "0x750a163df65e8a",
      "currentNumber": "1",
      "currentTimestamp": "1000",
      "previousHash": "dac58aa524e50956d0c0bae7f3f8bb9d35381365d07804dd5b48a5a297c06af4"
    },
    "pre": {
      address: {
        "balance": "0x5ffd4878be161d74",
        "code": "0x",
        "nonce": "0x0",
        "storage": {}
      },
      "a94f5374fce5edbc8e2a8697c15331677e6ebf0b": {
        "balance": "0x5ffd4878be161d74",
        "code": "0x",
        "nonce": "0xac",
        "storage": {}
      },
      "0x8a8eafb1cf62bfbeb1741769dae1a9dd47996192":{
        "balance": "0xfeedbead",
        "nonce" : "0x00"
      },
      "0x000000000000000000000000000000000000002a": {
        "balance": "0x00",
        "nonce": "0x00",
        "storage": {},
        "code": "0x608060405260043610610041576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff168063e09ee87014610046575b600080fd5b6100a66004803603810190808035906020019092919080359060200190929190803573ffffffffffffffffffffffffffffffffffffffff1690602001909291908035906020019082018035906020019190919293919293905050506100a8565b005b600080600043925034915033905073012345678901234567890123456789012345678973ffffffffffffffffffffffffffffffffffffffff166108fc349081150290604051600060405180830381858888f19350505050158015610110573d6000803e3d6000fd5b5043887fe9fbdfd23831dbc2bdec9e9ef0d5ac734f56996d4211992cc083e97f2770ba4289338a348b8b600054604051808881526020018773ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020018673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200185815260200180602001838152602001828103825285858281815260200192508082843782019150509850505050505050505060405180910390a350505050505050505600a165627a7a7230582084f095946c34c082d1308f4543d2878d4714089fab5e007b332bced03711c3010029",
        # "code": "0x608060405260043610610041576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff168063e09ee87014610046575b600080fd5b6100a66004803603810190808035906020019092919080359060200190929190803573ffffffffffffffffffffffffffffffffffffffff1690602001909291908035906020019082018035906020019190919293919293905050506100a8565b005b600080600043925034915033905043887fe9fbdfd23831dbc2bdec9e9ef0d5ac734f56996d4211992cc083e97f2770ba4289338a348b8b600054604051808881526020018773ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020018673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200185815260200180602001838152602001828103825285858281815260200192508082843782019150509850505050505050505060405180910390a350505050505050505600a165627a7a72305820f91b731c0b1c9bdc53b21fd97a6c50034272a0500678f63633f84b8c7953b96e0029",
      },
    },
    "transactions": [
      format_transaction(tx, signed),
      # {
      #   "gas": "0x5208",
      #   "gasPrice": "0x2",
      #   "hash": "0x0557bacce3375c98d806609b8d5043072f0b6a8bae45ae5a67a00d3a1a18d673",
      #   "input": "0x",
      #   "nonce": "0x0",
      #   "r": "0x9500e8ba27d3c33ca7764e107410f44cbd8c19794bde214d694683a7aa998cdb",
      #   "s": "0x7235ae07e4bd6e0206d102b1f8979d6adab280466b6a82d2208ee08951f1f600",
      #   "to": "0x8a8eafb1cf62bfbeb1741769dae1a9dd47996192",
      #   "v": "0x1b",
      #   "value": "0x1"
      # },
      {
        "gas": "0x5208",
        "gasPrice": "0x2",
        "hash": "0x0557bacce3375c98d806609b8d5043072f0b6a8bae45ae5a67a00d3a1a18d673",
        "input": "0x",
        "nonce": "0x0",
        "r": "0x9500e8ba27d3c33ca7764e107410f44cbd8c19794bde214d694683a7aa998cdb",
        "s": "0x7235ae07e4bd6e0206d102b1f8979d6adab280466b6a82d2208ee08951f1f600",
        "to": "0x8a8eafb1cf62bfbeb1741769dae1a9dd47996192",
        "v": "0x1b",
        "value": "0x1"
      }

    ]
}

vladvm = subprocess.Popen([vladvm_path, 'apply', '/dev/stdin'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
out = vladvm.communicate(json.dumps(vm_state).encode())[0].decode('utf-8')
print(out)
new_state = json.loads(out)
