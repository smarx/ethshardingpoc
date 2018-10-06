import binascii
from collections import defaultdict
import json
import os
import subprocess
import sys

from blocks import *
from web3 import Web3
from genesis_state import *
from config import DEADBEEF
from generate_transactions import format_transaction

abi = json.loads('[{"constant":false,"inputs":[{"name":"_shard_ID","type":"uint256"},{"name":"_sendGas","type":"uint256"},{"name":"_sendToAddress","type":"address"},{"name":"_data","type":"bytes"}],"name":"send","outputs":[],"payable":true,"stateMutability":"payable","type":"function"},{"anonymous":false,"inputs":[{"indexed":true,"name":"shard_ID","type":"uint256"},{"indexed":false,"name":"sendGas","type":"uint256"},{"indexed":false,"name":"sendFromAddress","type":"address"},{"indexed":true,"name":"sendToAddress","type":"address"},{"indexed":false,"name":"value","type":"uint256"},{"indexed":false,"name":"data","type":"bytes"},{"indexed":true,"name":"base","type":"uint256"},{"indexed":false,"name":"TTL","type":"uint256"}],"name":"SentMessage","type":"event"}]')

evm_path = './evm-ubuntu'
if (sys.platform == 'darwin'):
    evm_path = './evm-macos'

contract = web3.eth.contract(address='0x000000000000000000000000000000000000002A', abi=abi)



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
    assert isinstance(received_log, MessagesLog), "expected received log"
    # print(pre_state["pre"][address]["nonce"])   
    nonce = int(pre_state["pre"][pusher_address]["nonce"], 0)
    flattened_payloads = [message.payload for l in received_log.log.values() for message in l]
    for payload in flattened_payloads:
        transaction = {
            "gas": 3000000,
            "gasPrice": "0x2",
            "nonce": hex(nonce),
            "to": payload.toAddress,
            "value": payload.value,
            "data": payload.data,
        }
        nonce += 1
        signed = web3.eth.account.signTransaction(transaction, pusher_key)
        tx.append(format_transaction(transaction, signed))

    # create inputst evm by combining the pre_state, env, and transactions
    transition_inputs = {}
    transition_inputs["pre"] = pre_state["pre"]
    transition_inputs["env"] = pre_state["env"]
    transition_inputs["transactions"] = tx

    # open evm
    evm = subprocess.Popen([evm_path, 'apply', '/dev/stdin'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    out = evm.communicate(json.dumps(transition_inputs).encode())[0].decode('utf-8')
    # print("out2", out)

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
    sent_log = MessagesLog()
    for receipt in result.get('receipts', []):
        if receipt['logs'] is not None:
            for log in receipt['logs']:
                log['topics'] = [binascii.unhexlify(t[2:]) for t in log['topics']]
                log['data'] = binascii.unhexlify(log['data'][2:])
            for event in contract.events.SentMessage().processReceipt(receipt):
                sent_log.add_message(
                    event.args.shard_ID,
                    Message(
                        Block(event.args.shard_ID),
                        10,
                        event.args.shard_ID,
                        MessagePayload(
                            event.args.sendFromAddress.lower()[2:],
                            event.args.sendToAddress.lower()[2:],
                            event.args.value,
                            event.args.data,
                        )
                    )
                )
    return new_state, sent_log

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
