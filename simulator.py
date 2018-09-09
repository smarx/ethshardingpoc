from config import SHARD_IDS
from blocks import Block
from validator import Validator
from config import VALIDATOR_NAMES
import random as rand


# Experiment parameters
NUM_PROPOSALS = 10
NUM_RECEIPTS_PER_PROPOSAL = 3

# Setup
GENESIS_BLOCKS = {}
for i in SHARD_IDS:
    GENESIS_BLOCKS[i] = Block(i)

validators = {}
for name in VALIDATOR_NAMES:
    validators[name] = Validator(name, GENESIS_BLOCKS)

# maybe we will draw this from a mempool soon!
data = []

viewables = {}
for v in VALIDATOR_NAMES:
    viewables[v] = []

for i in range(NUM_PROPOSALS):
    # make a new message from a random validator on a random shard
    next_proposer = rand.choice(VALIDATOR_NAMES)
    rand_ID = rand.choice(SHARD_IDS)
    new_message = validators[next_proposer].make_new_consensus_message(rand_ID, data)
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
