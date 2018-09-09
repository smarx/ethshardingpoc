import random as rand

SHARD_IDS = [0, 1, 2]
VALIDATOR_NAMES = [1, 2, 3, 4, 5, 6, 7, 8, 9]
VALIDATOR_WEIGHTS = {}
for v in VALIDATOR_NAMES:
    VALIDATOR_WEIGHTS[v] = rand.uniform(5, 25)

TTL_CONSTANT = 10
