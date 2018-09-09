from config import SHARD_IDS
from blocks import Block
from validator import Validator
from config import VALIDATOR_NAMES
import random as rand

from generate_transactions import *

# Experiment parameters
NUM_PROPOSALS = 100
NUM_RECEIPTS_PER_PROPOSAL = 1
MEMPOOL_DRAIN_RATE = 1

# Setup
GENESIS_BLOCKS = {0: Block(0), 1: Block(1), 2: Block(2)}

validators = {}
for name in VALIDATOR_NAMES:
    validators[name] = Validator(name, GENESIS_BLOCKS)

mempools = {}
for ID in SHARD_IDS:
    mempools[ID] = gen_alice_and_bob_tx()

    


viewables = {}
for v in VALIDATOR_NAMES:
    viewables[v] = []

for i in range(NUM_PROPOSALS):
    # make a new message from a random validator on a random shard
    next_proposer = rand.choice(VALIDATOR_NAMES)
    rand_ID = rand.choice(SHARD_IDS)

    data = []
    for j in range(MEMPOOL_DRAIN_RATE):
        if len(mempools[rand_ID]) > 0:
            payload = mempools[rand_ID][j]
            data.append(payload) # expects a payload formatted message, but we're giving it a full tx.
            mempools[rand_ID].remove(payload)

    print( "rand_ID", rand_ID)
    print( "data", data)    
    new_message = validators[next_proposer].make_new_consensus_message(rand_ID, data)

    print( "proposal", i, "shard ID", rand_ID, "block", new_message.estimate, "height", new_message.estimate.height)

    for v in VALIDATOR_NAMES:
        if v == next_proposer:
            continue
        viewables[v].append(new_message)

    for j in range(NUM_RECEIPTS_PER_PROPOSAL):
        # recieve a new message for a random validator
        next_receiver = rand.choice(VALIDATOR_NAMES)
        if len(viewables[next_receiver]) > 0:  # if they have any viewables at all
            received_message = rand.choice(viewables[next_receiver])
            viewables[next_receiver].remove(received_message)
            validators[next_receiver].receive_consensus_messages([received_message])
