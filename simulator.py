import random
import copy
import json 
import random
import hashlib
import numpy as np 
import networkx as nx
import matplotlib.pyplot as plt

from blocks import Block
from validator import Validator
from validator import ConsensusMessage
from validator import UnresolvedDeps
from generate_transactions import gen_alice_and_bob_tx

from config import *

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

shard_assignment = {}
for ID in SHARD_IDS:
    shard_assignment[ID] = []  # Keeps track of to which shards the validators are assigned
    for i in range(3):
        shard_assignment[ID].append(3*ID + i + 1)

# GLOBAL MEMPOOLS
mempools = {}
txs = gen_alice_and_bob_tx()
for ID in SHARD_IDS:
    mempools[ID] = txs

# GLOBAL VIEWABLES
viewables = {}
for v in VALIDATOR_NAMES:
    viewables[v] = {}
    for w in VALIDATOR_NAMES:
        viewables[v][w] = []

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

    if FREE_INSTANT_BROADCAST:
        for v in VALIDATOR_NAMES:
            validators[v].receive_consensus_message(new_message)
    else:
        # MAKE NEW MESSAGE VIEWABLE
        for v in VALIDATOR_NAMES:
            if v == next_proposer or v == 0:
                continue
            viewables[v][next_proposer].append(new_message)  # validators have the possibility of later viewing this message

        # RECEIVE CONSENSUS MESSAGES WITHIN SHARD
        for j in range(NUM_WITHIN_SHARD_RECEIPTS_PER_PROPOSAL):
            # recieve a new message for a random validator
            next_receiver = random.choice(shard_assignment[rand_ID])\

            pool = copy.copy(shard_assignment[rand_ID])
            pool.remove(next_receiver)

            new_received = False
            while(not new_received and len(pool) > 0):

                receiving_from = random.choice(pool)
                pool.remove(receiving_from)
                assert next_receiver != watcher.name, "didn't except the watcher"
                print("len(viewables[",next_receiver,"][",receiving_from,"]) : ", len(viewables[next_receiver][receiving_from]))
                if len(viewables[next_receiver][receiving_from]) > 0:  # if they have any viewables at all
                    received_message = viewables[next_receiver][receiving_from][0]
                    try:
                        validators[next_receiver].receive_consensus_message(received_message)
                        viewables[next_receiver][receiving_from].remove(received_message)
                        new_received = True
                    except UnresolvedDeps:
                        pass


            # RECEIVE CONSENSUS MESSAGES BETWEEN SHARDS
            for j in range(NUM_BETWEEN_SHARD_RECEIPTS_PER_PROPOSAL):
                # recieve a new message for a random validator
                next_receiver = random.choice(VALIDATOR_NAMES)

                pool = copy.copy(VALIDATOR_NAMES)
                pool.remove(next_receiver)

                new_received = False
                while(not new_received and len(pool) > 0):

                    receiving_from = random.choice(pool)
                    pool.remove(receiving_from)

                    if next_receiver == 0 or receiving_from == 0:
                        continue
                    print("len(viewables[",next_receiver,"][",receiving_from,"]) : ", len(viewables[next_receiver][receiving_from]))
                    if len(viewables[next_receiver][receiving_from]) > 0:  # if they have any viewables at all
                        received_message = viewables[next_receiver][receiving_from][0]
                        try:
                            validators[next_receiver].receive_consensus_message(received_message)
                            viewables[next_receiver][receiving_from].remove(received_message)
                            new_received = True
                        except UnresolvedDeps:
                            pass


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
                nx.draw_networkx_nodes(BlocksGraph, blockPos, node_shape='s', node_color='b', node_size=5)
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
