import random
import copy
import json
import hashlib
from visualizer import report, init_plt

from blocks import Block
from validator import Validator
from validator import ConsensusMessage
from validator import UnresolvedDeps
from validator import have_made_block
from generate_transactions import gen_alice_and_bob_tx

from config import *

def add_switch_message(parent_shard, child_to_become_parent, shard_to_move_down, position):
    global mempools
    # mempools[parent_shard].insert(position, {'opcode': 'switch', 'child_to_become_parent': child_to_become_parent, 'child_to_move_down': child_to_move_down})
    mempools[parent_shard].insert(position, {'opcode': 'switch', 'child_to_become_parent': child_to_become_parent, 'shard_to_move_down': shard_to_move_down})

# Setup
GENESIS_BLOCKS = {}
GENESIS_MESSAGES = []
print("SHARD_IDS", SHARD_IDS)
for ID in SHARD_IDS:
    GENESIS_BLOCKS[ID] = Block(ID, sources={}) # temporarily set sources to {}, since genesis blocks are not known yet
    print("GENESIS_BLOCKS[ID].shard_ID")
    print("ID", ID)
    print(GENESIS_BLOCKS[ID].shard_ID)
    GENESIS_MESSAGES.append(ConsensusMessage(GENESIS_BLOCKS[ID], 0, []))  # The watcher is the sender of the genesis blocks
    for ID2 in SHARD_IDS:
        print("len(GENESIS_BLOCKS[ID].sent_log.log[ID2]", len(GENESIS_BLOCKS[ID].sent_log[ID2]))


for ID in SHARD_IDS:
    GENESIS_BLOCKS[ID].sources = {ID : GENESIS_BLOCKS[ID] for ID in SHARD_IDS}
    GENESIS_BLOCKS[ID].parent_ID = None
    for _ in SHARD_IDS:
        if ID in INITIAL_TOPOLOGY[_]:
            GENESIS_BLOCKS[ID].parent_ID = _
    GENESIS_BLOCKS[ID].child_IDs = INITIAL_TOPOLOGY[ID]

for ID in SHARD_IDS:
    GENESIS_BLOCKS[ID].compute_routing_table()

validators = {}
for name in VALIDATOR_NAMES:
    validators[name] = Validator(name)

#  Watcher lives at validator name 0 and receives all the messages
watcher = validators[0]

for v in VALIDATOR_NAMES:
    for genesis_message in GENESIS_MESSAGES:
        validators[v].receive_consensus_message(genesis_message)

# GLOBAL MEMPOOLS
mempools = {}
if RESTRICT_ROUTING:
    for ID in SHARD_IDS:
        if ID in MSG_ROUTES:
            mempools[ID] = gen_alice_and_bob_tx(MSG_ROUTES[ID])
        else:
            mempools[ID] = []
else:
    txs = gen_alice_and_bob_tx()
    for ID in SHARD_IDS:
        mempools[ID] = copy.copy(txs)


# GLOBAL VIEWABLES
viewables = {}
for v in VALIDATOR_NAMES:
    viewables[v] = {}
    for w in VALIDATOR_NAMES:
        viewables[v][w] = []

max_height = 0

# SIMULATION LOOP:
for i in range(NUM_ROUNDS):
    # Make a new message from a random validator on a random shard
    rand_ID = i % len(SHARD_IDS) #random.choice(SHARD_IDS)
    next_proposer = random.choice(SHARD_VALIDATOR_ASSIGNMENT[rand_ID])

    while next_proposer == 0:
        rand_ID = random.choice(SHARD_IDS)
        next_proposer = random.choice(SHARD_VALIDATOR_ASSIGNMENT[rand_ID])

    for k in range(10):
        if i == SWITCH_ROUND + 20*k:
            for j in range(100000):
                print("ADDING SWITCH")
            add_switch_message(0, 1, 0, SWITCH_ROUND + 1)


        if i == SWITCH_ROUND + 10 + 20*k:
            for j in range(100000):
                print("ADDING SWITCH")
            add_switch_message(1, 0, 1, SWITCH_ROUND + 11)

    # MAKE CONSENSUS MESSAGE
    new_message = validators[next_proposer].make_new_consensus_message(rand_ID, mempools, drain_amount=MEMPOOL_DRAIN_RATE, genesis_blocks=GENESIS_BLOCKS)
    watcher.receive_consensus_message(new_message)  # here the watcher is, receiving all the messages

    # keep max_height
    if new_message.height > max_height:
        max_height = new_message.height

    if FREE_INSTANT_BROADCAST:
        for v in VALIDATOR_NAMES:
            if v != 0:
                validators[v].receive_consensus_message(new_message)
    else:
        # MAKE NEW MESSAGE VIEWABLE
        for v in VALIDATOR_NAMES:
            if v == next_proposer or v == 0:
                continue
            viewables[v][next_proposer].append(new_message)  # validators have the possibility of later viewing this message

        # RECEIVE CONSENSUS MESSAGES WITHIN SHARD
        for j in range(NUM_WITHIN_SHARD_RECEIPTS_PER_ROUND):

            next_receiver = random.choice(SHARD_VALIDATOR_ASSIGNMENT[rand_ID])

            pool = copy.copy(SHARD_VALIDATOR_ASSIGNMENT[rand_ID])
            pool.remove(next_receiver)

            new_received = False
            while(not new_received and len(pool) > 0):

                receiving_from = random.choice(pool)
                pool.remove(receiving_from)

                if len(viewables[next_receiver][receiving_from]) > 0:  # if they have any viewables at all
                    received_message = viewables[next_receiver][receiving_from][0]
                    try:
                        validators[next_receiver].receive_consensus_message(received_message)
                        viewables[next_receiver][receiving_from].remove(received_message)
                        new_received = True
                    except UnresolvedDeps:
                        pass

        # RECEIVE CONSENSUS MESSAGES BETWEEN SHARDS
        for j in range(NUM_BETWEEN_SHARD_RECEIPTS_PER_ROUND):

            pool = copy.copy(VALIDATOR_NAMES)
            pool.remove(0)

            next_receiver = random.choice(pool)
            pool.remove(next_receiver)

            new_received = False
            while(not new_received and len(pool) > 0):

                receiving_from = random.choice(pool)
                pool.remove(receiving_from)

                if len(viewables[next_receiver][receiving_from]) > 0:  # if they have any viewables at all
                    received_message = viewables[next_receiver][receiving_from][0]  # receive the next one in the list
                    try:
                        validators[next_receiver].receive_consensus_message(received_message)
                        viewables[next_receiver][receiving_from].remove(received_message)
                        new_received = True
                    except UnresolvedDeps:
                        pass

    blocks = watcher.get_blocks_from_consensus_messages()
    for b in blocks:
        assert have_made_block(b)

    for v in validators.values():
        assert v.check_have_made_blocks()

    # REPORTING:
    print("Step: ", i)
    if not REPORTING:
        continue
    if i == 0:
        init_plt(FIG_SIZE)
    if (i + 1) % REPORT_INTERVAL == 0:
        report(watcher, i, GENESIS_BLOCKS)
