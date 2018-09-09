import random as rand
from blocks import Block

SHARD_IDS = [0, 1, 2]
VALIDATOR_NAMES = [1, 2, 3, 4, 5, 6, 7, 8, 9]
VALIDATOR_WEIGHTS = {}
for v in VALIDATOR_NAMES:
    VALIDATOR_WEIGHTS[v] = rand.uniform(5, 25)

GENESIS_BLOCKS = {}
for i in SHARD_IDS:
    GENESIS_BLOCKS[i] = Block(i)

TTL_CONSTANT = 10
