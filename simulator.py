from config import SHARD_IDS
from blocks import Block
from validator import Validator
from config import VALIDATOR_NAMES
import random
import random as rand
import json 
import networkx as nx
import numpy as np 
import matplotlib.pyplot as plt
import hashlib



# Experiment parameters
NUM_PROPOSALS = 100
NUM_RECEIPTS_PER_PROPOSAL = 10
MEMPOOL_DRAIN_RATE = 1

REPORT_INTERVAL = NUM_PROPOSALS/5


# Setup
GENESIS_BLOCKS = {0: Block(0), 1: Block(1), 2: Block(2)}

validators = {}
for name in VALIDATOR_NAMES:
    validators[name] = Validator(name, GENESIS_BLOCKS)

watcher = Validator(0, GENESIS_BLOCKS)

mempools = {}
for ID in SHARD_IDS:
    mempools[ID] = []

    #fill me up!


viewables = {}
winning_blocks = []
consensus_messages = []
for v in VALIDATOR_NAMES:
    viewables[v] = []

for i in range(NUM_PROPOSALS):
    winning_blocks.append([])
    # make a new message from a random validator on a random shard
    rand_ID = rand.choice(SHARD_IDS)
    next_proposer = 3*rand_ID + rand.randint(1,3)

    data = []
    for j in range(MEMPOOL_DRAIN_RATE):
        if len(mempools[rand_ID]) > 0:
            payload = mempools[rand_ID][j]
            data.append(payload)
            mempools[rand_ID].remove(payload)

    print "rand_ID", rand_ID
    print "data", data
    new_message = validators[next_proposer].make_new_consensus_message(rand_ID, data)
    consensus_messages.append(new_message)

    print "proposal", i, "shard ID", rand_ID, "block", new_message.estimate, "height", new_message.estimate.height

    for v in VALIDATOR_NAMES:
        if v == next_proposer:
            continue
        viewables[v].append(new_message)
        watcher.receive_consensus_messages([new_message])

    for j in range(NUM_RECEIPTS_PER_PROPOSAL):
        # recieve a new message for a random validator
        next_receiver = rand.choice(VALIDATOR_NAMES)
        if len(viewables[next_receiver]) > 0:  # if they have any viewables at all
            received_message = rand.choice(viewables[next_receiver])
            viewables[next_receiver].remove(received_message)
            validators[next_receiver].receive_consensus_messages([received_message])


    if (i + 1) % REPORT_INTERVAL == 0:

        fork_choice = watcher.fork_choice()

        SHARD_COUNT = 3
        MAX_BLOCK_HEIGHT = 50
        VALIDATOR_COUNT = 3
        SHARD_SPACING_CONSTANT = 3
        VALIDATOR_SPACING_CONSTANT = 1
        blocksPerHeight = {}
        messageMap = {}
        MessageGraph = nx.DiGraph();
        BlocksGraph1 = nx.Graph();
        BlocksGraph2 = nx.Graph();
        ValidatorLineGraph = nx.Graph();
        previousGoodBlock = [None, None, None]

        def checkIfGood(block):
            return block['Winning']

        with open("blocks.json") as json_file:
            json_data = json.load(json_file)

        blocks = json_data['blocks']

        for block in blocks: 
            if block['height'] not in blocksPerHeight:
                blocksPerHeight[block['height']] = [block]
            else:
                blocksPerHeight[block['height']] = blocksPerHeight[block['height']] + [block]

        blockPos1 = {}
        blockPos2 = {}
        blockLabels = {}
        messPos = {}
        validatorLinePos = {}

        # Lines for each validator on each shard
        i = j = 0
        while i < SHARD_COUNT:
            while j < VALIDATOR_COUNT:
                startNode = str(i) + str(j) + str(1)
                ValidatorLineGraph.add_node(startNode)
                endNode = str(i) + str(j) + str(MAX_BLOCK_HEIGHT)
                ValidatorLineGraph.add_node(endNode)
                ValidatorLineGraph.add_edge(startNode, endNode)
                validatorLinePos[startNode] = (1, SHARD_SPACING_CONSTANT*i+VALIDATOR_SPACING_CONSTANT*j)
                validatorLinePos[endNode] = (MAX_BLOCK_HEIGHT, SHARD_SPACING_CONSTANT*i+VALIDATOR_SPACING_CONSTANT*j)
                j += 1
            i += 1
            j=0


        senders = {}

        blocks = watcher.get_blocks_from_consensus_messages()
        for ID in SHARD_IDS:
            block = GENESIS_BLOCKS[ID]
            blocks.append(block)
            blockPos1[block] = (block.height, SHARD_SPACING_CONSTANT*block.shard_ID + 3*ID + 1.5)        
            blockPos2[block] = (block.height, SHARD_SPACING_CONSTANT*block.shard_ID + 3*ID + 1.5)        


        for message in watcher.consensus_messages:
            block = message.estimate
            senders[block] = message.sender
            BlocksGraph1.add_node(block)
            BlocksGraph2.add_node(block)
            blockPos1[block] = (block.height, SHARD_SPACING_CONSTANT*block.shard_ID + senders[block])
            blockPos2[block] = (block.height, SHARD_SPACING_CONSTANT*block.shard_ID + senders[block])
            if block.prevblock is not None and block.prevblock in blocks:
                BlocksGraph1.add_edge(block, block.prevblock)
            nx.draw_networkx_nodes(BlocksGraph1, blockPos1, node_shape='o', node_color='b', node_size=10)
            nx.draw_networkx_edges(BlocksGraph1, blockPos1) 

        for ID in SHARD_IDS:
            this_block = fork_choice[ID]
            blockPos2[this_block] = (this_block.height, SHARD_SPACING_CONSTANT*this_block.shard_ID + senders[this_block])
            while(this_block.prevblock is not None):
                BlocksGraph2.add_edge(this_block, this_block.prevblock)
                this_block = this_block.prevblock
            blockPos2[this_block] = (this_block.height, SHARD_SPACING_CONSTANT*this_block.shard_ID + 3*ID + 1.5)

            nx.draw_networkx_edges(BlocksGraph2, blockPos2, edge_color='g', width = 2)

            # nx.draw(BlocksGraph2)
        '''

        for height in blocksPerHeight:
            for block in blocksPerHeight[height]: 
                blockID = hashlib.sha256(json.dumps(block)).hexdigest()
                BlocksGraph.add_node(blockID)
                if block['height'] != 1:
                    BlocksGraph2.add_edge(block['shard'], blockID)


                if checkIfGood(block): 
                    if block['height'] != 1: 
                        BlocksGraph.add_edge(previousGoodBlock[block['shard']], blockID)
                    previousGoodBlock[block['shard']] = blockID;


                if block['height'] != 1: 
                    for message in block['ReceivedMessages']:
                        hashedMessage = hashlib.sha256(json.dumps(message)).hexdigest()
                        sentBlockID = messageMap[hashedMessage]
                        MessageGraph.add_edge(blockID, sentBlockID)

                for message in block['SentMessages']:
                    hashedMessage = hashlib.sha256(json.dumps(message)).hexdigest()
                    messageMap[hashedMessage] = blockID
                    MessageGraph.add_node(hashedMessage)
                    messPos[hashedMessage] = (block['height'] + random.uniform(-0.15, 0.15), SHARD_SPACING_CONSTANT*block['shard'] + VALIDATOR_SPACING_CONSTANT*block['validator']-1 + random.uniform(-0.15, 0.15))

                # Positioning the different shards 
                blockPos[blockID] = (block['height'], SHARD_SPACING_CONSTANT*block['shard'] + VALIDATOR_SPACING_CONSTANT*block['validator']-1)
                blockLabels[blockID] = "Shard: " + str(block['shard']) + " Height: " + str(block['height'])

                nonMessageNodesinMessageGraph = []
                for mn in nx.nodes(MessageGraph): 
                    if mn not in messPos:
                        nonMessageNodesinMessageGraph.append(mn)

                for node in nonMessageNodesinMessageGraph:
                    if node not in blockPos:
                        MessageGraph.remove_node(node)
                    else:
                        messPos[node] = blockPos[node]

                nx.draw_networkx_edges(ValidatorLineGraph, validatorLinePos, style='dashed')
                nx.draw_networkx_edges(BlocksGraph, blockPos, edge_color='g', width = 2)
                nx.draw_networkx_edges(BlocksGraph2, blockPos, edge_color='y', width = 1)
                nx.draw_networkx_nodes(MessageGraph, messPos, node_shape='o', node_color='b', node_size=10)
                nx.draw_networkx_edges(MessageGraph, messPos) 
                nx.draw_networkx_nodes(BlocksGraph, blockPos, node_shape='s', node_size=100)
                # Shows the block height and shard on each block 
                # nx.draw_networkx_labels(BlocksGraph, blockPos, blockLabels)
        '''
        plt.axis('off')
        plt.draw()
        plt.pause(0.001)

        plt.show()









'''
print winning_blocks[-1]

# Save blocks information in json format to a file 
blocks = {"blocks": []}
for m in consensus_messages:
    json_block = {}
    block = m.estimate
    validator = m.sender

    # print "print block.shard_ID", block.shard_ID
    # print "block.height", block.height
    # print "block.prevblock", block.prevblock
    # print "validator", validator

    json_block["shard"] = block.shard_ID
    json_block["height"] = block.height
    if block.prevblock is not None: 
        json_block["prevBlock"] = hash(block.prevblock)
    else:
        json_block["prevBlock"] = None
    json_block["validator"] = validator

    json_block["SentMessages"] = []
    json_block["ReceivedMessages"] = []

    if block in winning_blocks[-1]:
        json_block["Winning"] = True 
    else: 
        json_block["Winning"] = False

    for ID in SHARD_IDS:
        if ID == block.shard_ID:
            continue

        for sent_message in block.sent_log.log[ID]:
            break
            # print "sent_message.base", sent_message.base
            # print "sent_message.TTL", sent_message.TTL
            # print "sent_message.message_payload.fromAddress", sent_message.message_payload.fromAddress
            # print "sent_message.message_payload.toAddress", sent_message.message_payload.toAddress
            # print "sent_message.message_payload.value", sent_message.message_payload.value
            # print "sent_message.message_payload.data", sent_message.message_payload.data

        for received_message in block.received_log.log[ID]:
            break
            # print "sent_message.base", sent_message.base
            # print "sent_message.TTL", sent_message.TTL

    blocks["blocks"].append(json_block)

with open("blocks.json", 'w') as f:
    json.dump(blocks, f)
json_string = json.dumps(blocks)
# print json_string
'''
