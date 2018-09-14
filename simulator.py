import random
import json 
import random
import hashlib
import numpy as np 
import networkx as nx
import matplotlib.pyplot as plt

from config import SHARD_IDS
from blocks import Block
from validator import Validator
from validator import ConsensusMessage
from validator import UnresolvedDeps
from config import VALIDATOR_NAMES

import generate_transactions


# Experiment parameters
NUM_PROPOSALS = 100
NUM_RECEIPTS_PER_PROPOSAL = 30
MEMPOOL_DRAIN_RATE = 1
REPORT_INTERVAL = 10
PAUSE_LENGTH = 0.01

# Setup
GENESIS_BLOCKS = {}
GENESIS_MESSAGES = []
for ID in SHARD_IDS:
    GENESIS_BLOCKS[ID] = Block(ID)
    GENESIS_MESSAGES.append(ConsensusMessage(GENESIS_BLOCKS[ID], 0, []))  # The watcher is the sender of the genesis blocks

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
for ID in SHARD_IDS:
    mempools[ID] = generate_transactions.gen_alice_and_bob_tx()

# GLOBAL VIEWABLES
viewables = {}
for v in VALIDATOR_NAMES:
    viewables[v] = []

# SIMULATION LOOP:
for i in range(NUM_PROPOSALS):
    # Make a new message from a random validator on a random shard
    rand_ID = random.choice(SHARD_IDS)
    next_proposer = 3*rand_ID + random.randint(1, 3)

    if next_proposer == 0:
        assert False, "watcher should never propose"

    # MAKE CONSENSUS MESSAGE
    new_message = validators[next_proposer].make_new_consensus_message(rand_ID, mempools, drain_amount=MEMPOOL_DRAIN_RATE)

    # print("new_message.sender()", new_message.sender)
    watcher.receive_consensus_message(new_message)  # here the watcher is, receiving all the messages

    # print("rand_ID", rand_ID)
    # print("data", data)
    # print("proposal", i, "shard ID", rand_ID, "block", new_message.estimate, "height", new_message.estimate.height)

    # MAKE NEW MESSAGE VIEWABLE
    for v in VALIDATOR_NAMES:
        if v == next_proposer or v == 0:
            continue
        viewables[v].append(new_message)  # validators have the possibility of later viewing this message

    # RECEIVE CONSENSUS MESSAGE
    for j in range(NUM_RECEIPTS_PER_PROPOSAL):
        # recieve a new message for a random validator
        next_receiver = random.choice(VALIDATOR_NAMES)
        if next_receiver == 0:
            continue
        if len(viewables[next_receiver]) > 0:  # if they have any viewables at all
            received_message = random.choice(viewables[next_receiver])
            viewables[next_receiver].remove(received_message)

            try:
                validators[next_receiver].receive_consensus_message(received_message)
            except UnresolvedDeps:
                continue

    # DRAW VISUALIZATION:
    if (i + 1) % REPORT_INTERVAL == 0:
        plt.clf()
        fork_choice = watcher.fork_choice()
        SHARD_SPACING_CONSTANT = 3
        BlocksGraph = nx.Graph();
        ValidChainGraph = nx.Graph();
        MessagesGraph = nx.Graph();

        blockPos = {}
        senders = {}

        blocks = watcher.get_blocks_from_consensus_messages()
        for ID in SHARD_IDS:
            block = GENESIS_BLOCKS[ID]
            blocks.append(block)
            blockPos[block] = (block.height, SHARD_SPACING_CONSTANT*block.shard_ID + 3*ID + 1.5)

        for ID in SHARD_IDS:
            for ID2 in SHARD_IDS:
                if fork_choice[ID].received_log.sources[ID2] is not None:
                    MessagesGraph.add_edge(fork_choice[ID], fork_choice[ID].received_log.sources[ID2])

        for message in watcher.consensus_messages:
            if message.sender != 0:
                block = message.estimate
                BlocksGraph.add_node(block)
                ValidChainGraph.add_node(block)
                blockPos[block] = (message.height, SHARD_SPACING_CONSTANT*block.shard_ID + message.sender)
                if block.prevblock is not None and block.prevblock in blocks:
                    BlocksGraph.add_edge(block, block.prevblock)
                nx.draw_networkx_nodes(BlocksGraph, blockPos, node_shape='s', node_color='b', node_size=20)
                nx.draw_networkx_edges(BlocksGraph, blockPos) 


        for ID in SHARD_IDS:
            this_block = fork_choice[ID]
            while(this_block.prevblock is not None):
                ValidChainGraph.add_edge(this_block, this_block.prevblock)
                this_block = this_block.prevblock
            nx.draw_networkx_edges(ValidChainGraph, blockPos, edge_color='g', width = 5)
            nx.draw_networkx_edges(MessagesGraph, blockPos, edge_color='y', width = 0.5, style='dashed')

        plt.axis('off')
        plt.draw()
        plt.pause(PAUSE_LENGTH)

# Leave plot open after going over all proposals 
plt.show(block=True)
