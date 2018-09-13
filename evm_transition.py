import binascii
from collections import defaultdict
import json
import os
import subprocess

from blocks import *
from web3 import Web3
from genesis_state import genesis_state

web3 = Web3()

private_key = '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318'
address = web3.eth.account.privateKeyToAccount(private_key).address.lower()[2:]

abi = json.loads('[{"constant":false,"inputs":[{"name":"_shard_ID","type":"uint256"},{"name":"_sendGas","type":"uint256"},{"name":"_sendToAddress","type":"address"},{"name":"_data","type":"bytes"}],"name":"send","outputs":[],"payable":true,"stateMutability":"payable","type":"function"},{"anonymous":false,"inputs":[{"indexed":true,"name":"shard_ID","type":"uint256"},{"indexed":false,"name":"sendGas","type":"uint256"},{"indexed":false,"name":"sendFromAddress","type":"address"},{"indexed":true,"name":"sendToAddress","type":"address"},{"indexed":false,"name":"value","type":"uint256"},{"indexed":false,"name":"data","type":"bytes"},{"indexed":true,"name":"base","type":"uint256"},{"indexed":false,"name":"TTL","type":"uint256"}],"name":"SentMessage","type":"event"}]')

evm_path = './evm-ubuntu'
if(os.getenv("_system_type")):
    evm_path = './evm-macos'

contract = web3.eth.contract(address='0x000000000000000000000000000000000000002A', abi=abi)
tx = contract.functions.send(1, 300000, '0xDeaDbeefdEAdbeefdEadbEEFdeadbeEFdEaDbeeF', '0x1234').buildTransaction({ "gas": 3000000, "gasPrice": "0x2", "nonce": hex(0), "value": 5 })

signed = web3.eth.account.signTransaction(tx, private_key)

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

vm_state = {}
vm_state["env"] = genesis_state["env"]
vm_state["pre"] = genesis_state["pre"]

transactions = [
    # Removed so as not to clobber the nonce
    # format_transaction(tx, signed),
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

def convert_state_to_pre(state):
    ''' The evm output isn't quite how we want it '''
    pre = {}
    for key, value in state["state"]["accounts"].items():
        # print(value)
        pre[key] = value
    return pre

# NOTES: from convo with steve
# The “vm state” is really the “pre” part of what we send to evm.
# The “env” stuff is constant
# the “transactions” list is a list of transactions that come from the
#   mempool (originally a file full of test data?) and ones that are constructed from
#   `MessagePayload`s. (This is done via `web3.eth.account.signTransaction(…)`.)
# function apply(vm_state, [tx], mapping(S => received)) -> (vm_state, mapping(S => received) )
def apply_to_state(pre_state, tx, received_log):
    # print(pre_state["pre"][address]["nonce"])   
    nonce = int(pre_state["pre"][address]["nonce"], 0)
    flattened_payloads = [message.message_payload for l in received_log.values() for message in l]
    for payload in flattened_payloads:
        transaction = {
            "gas": 3000000,
            "gasPrice": "0x2",
            "nonce": hex(nonce),
            "to": payload.toAddress.lower()[2:],
            "value": payload.value,
            "data": payload.data,
        }
        nonce += 1
        signed = web3.eth.account.signTransaction(transaction, private_key)
        tx.append(format_transaction(transaction, signed))

    # create inputst evm by combining the pre_state, env, and transactions
    transition_inputs = {}
    transition_inputs["pre"] = pre_state["pre"]
    transition_inputs["env"] = pre_state["env"]
    transition_inputs["transactions"] = tx

    # open evm
    evm = subprocess.Popen([evm_path, 'apply', '/dev/stdin'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # pipe state into that process
    print(transition_inputs)
    print("hello")
    #print(type(evm.communicate(json.dumps(transition_inputs).encode())[0]))
    #print((evm.communicate(json.dumps(transition_inputs).encode())[0]))
    print("in1")

    out = evm.communicate(json.dumps(transition_inputs).encode())[0].decode('utf-8')
    print("out2", out)
    result = json.loads(out)
    new_state = {
        "env": pre_state["env"],
        "pre": result["state"]["accounts"].copy(),
    }
    for addr, account in new_state["pre"].items():
        for key in ("nonce", "balance"):
            account[key] = hex(int(account[key]))
        for key in ("code", "codeHash"):
            account[key] = "0x" + account[key]

    # look through logs for outgoing messages
    sent_log = SentLog()
    for receipt in result.get('receipts', []):
        if receipt['logs'] is not None:
            for log in receipt['logs']:
                log['topics'] = [binascii.unhexlify(t[2:]) for t in log['topics']]
                log['data'] = binascii.unhexlify(log['data'][2:])

            for event in contract.events.SentMessage().processReceipt(receipt):
                sent_log.add_sent_message(
                    event.args.shard_ID,
                    MessagePayload(
                        event.args.sendFromAddress.lower()[2:],
                        event.args.sendToAddress.lower()[2:],
                        event.args.value,
                        event.args.data,
                    )
                )
    return new_state, sent_log.log

# received_log = ReceivedLog()
# received_log.add_received_message(2, Message(
#     None, # base
#     5, # TTL
#     MessagePayload(
#         0, # from address
#         "0x1234567890123456789012345678901234567890", # to address
#         42, # value
#         "0x", # data
#     )
# ))
# new_state, sent_log = apply_to_state(vm_state, transactions, received_log)
# print(json.dumps(new_state))
# print(sent_log.log)
