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
from config import VALIDATOR_NAMES

# Experiment parameters
NUM_PROPOSALS = 100
NUM_RECEIPTS_PER_PROPOSAL = 20
MEMPOOL_DRAIN_RATE = 1
REPORT_INTERVAL = 10

# Setup
GENESIS_BLOCKS = {0: Block(0), 1: Block(1), 2: Block(2)}

validators = {}
for name in VALIDATOR_NAMES:
    validators[name] = Validator(name, GENESIS_BLOCKS)

watcher = Validator(0, GENESIS_BLOCKS)

mempools = {}
for ID in SHARD_IDS:
    mempools[ID] = []

    # Fill me up!

viewables = {}
for v in VALIDATOR_NAMES:
    viewables[v] = []

for i in range(NUM_PROPOSALS):
    # Make a new message from a random validator on a random shard
    rand_ID = random.choice(SHARD_IDS)
    next_proposer = 3*rand_ID + random.randint(1,3)

    data = []
    for j in range(MEMPOOL_DRAIN_RATE):
        if len(mempools[rand_ID]) > 0:
            payload = mempools[rand_ID][j]
            data.append(payload)
            mempools[rand_ID].remove(payload)
    new_message = validators[next_proposer].make_new_consensus_message(rand_ID, data)

    print "rand_ID", rand_ID
    print "data", data
    print "proposal", i, "shard ID", rand_ID, "block", new_message.estimate, "height", new_message.estimate.height

    for v in VALIDATOR_NAMES:
        if v == next_proposer:
            continue
        viewables[v].append(new_message)
        watcher.receive_consensus_messages([new_message])

    for j in range(NUM_RECEIPTS_PER_PROPOSAL):
        # recieve a new message for a random validator
        next_receiver = random.choice(VALIDATOR_NAMES)
        if len(viewables[next_receiver]) > 0:  # if they have any viewables at all
            received_message = random.choice(viewables[next_receiver])
            viewables[next_receiver].remove(received_message)
            validators[next_receiver].receive_consensus_messages([received_message])

    # Time to report 
    if (i + 1) % REPORT_INTERVAL == 0:

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
            block = message.estimate
            senders[block] = message.sender
            BlocksGraph.add_node(block)
            ValidChainGraph.add_node(block)
            blockPos[block] = (block.height, SHARD_SPACING_CONSTANT*block.shard_ID + senders[block])
            if block.prevblock is not None and block.prevblock in blocks:
                BlocksGraph.add_edge(block, block.prevblock)
            nx.draw_networkx_nodes(BlocksGraph, blockPos, node_shape='s', node_color='b', node_size=20)
            nx.draw_networkx_edges(BlocksGraph, blockPos) 


        for ID in SHARD_IDS:
            this_block = fork_choice[ID]
            while(this_block.prevblock is not None):
                ValidChainGraph.add_edge(this_block, this_block.prevblock)
                this_block = this_block.prevblock
            nx.draw_networkx_edges(ValidChainGraph, blockPos, edge_color='g', width = 2)
            nx.draw_networkx_edges(MessagesGraph, blockPos, edge_color='y', width = 0.5, style='dashed')

        plt.axis('off')
        plt.draw()
        plt.pause(0.001)

        # Only close the plot as new blocks come in 
        if i != (NUM_PROPOSALS-1): 
            plt.close()

# Leave plot open after going over all proposals 
plt.show(block=True)
