import json
import networkx as nx
import numpy as np 
import matplotlib.pyplot as plt
import random
import hashlib 

SHARD_COUNT = 3
MAX_BLOCK_HEIGHT = 5 
VALIDATOR_COUNT = 3
SHARD_SPACING_CONSTANT = 3
VALIDATOR_SPACING_CONSTANT = 0.5 
blocksPerHeight = {}
messageMap = {}
MessageGraph = nx.DiGraph();
BlocksGraph = nx.Graph();
ValidatorLineGraph = nx.Graph();
previousGoodBlock = [None, None, None]

def checkIfGood(block):
	return True

with open("placeholder_blocks.json") as json_file:
    json_data = json.load(json_file)

blocks = json_data['blocks']

for block in blocks: 
	if block['height'] not in blocksPerHeight:
		blocksPerHeight[block['height']] = [block]
	else:
		blocksPerHeight[block['height']] = blocksPerHeight[block['height']] + [block]

blockPos = {}
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

for height in blocksPerHeight:
	for block in blocksPerHeight[height]: 
		blockID = hashlib.sha256(json.dumps(block)).hexdigest()
		BlocksGraph.add_node(blockID)

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
			messPos[hashedMessage] = (block['height'] + random.uniform(-0.15, 0.15), SHARD_SPACING_CONSTANT*block['shard'] + VALIDATOR_SPACING_CONSTANT*block['validator'] + random.uniform(-0.15, 0.15))

		# Positioning the different shards 
		blockPos[blockID] = (block['height'], SHARD_SPACING_CONSTANT*block['shard'] + VALIDATOR_SPACING_CONSTANT*block['validator'])
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
		nx.draw_networkx_edges(BlocksGraph, blockPos, edge_color='g', width = 3)
		nx.draw_networkx_nodes(MessageGraph, messPos, node_shape='o', node_color='b', node_size=10)
		nx.draw_networkx_edges(MessageGraph, messPos) 
		nx.draw_networkx_nodes(BlocksGraph, blockPos, node_shape='s', node_size=100)
		# Shows the block height and shard on each block 
		# nx.draw_networkx_labels(BlocksGraph, blockPos, blockLabels)

		plt.axis('off')
		plt.draw()
		plt.pause(0.001)

plt.show()