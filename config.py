import random as rand
from web3 import Web3
import copy
from collections import defaultdict

NUM_SHARDS = 8
NUM_VALIDATORS_PER_SHARD = 5
NUM_VALIDATORS = 1 + NUM_VALIDATORS_PER_SHARD*NUM_SHARDS

SHARD_IDS = list(range(NUM_SHARDS))
VALIDATOR_NAMES = []
for i in range(NUM_VALIDATORS):
    VALIDATOR_NAMES.append(i)
VALIDATOR_WEIGHTS = {}
for v in VALIDATOR_NAMES:
    VALIDATOR_WEIGHTS[v] = rand.uniform(5, 25)

INITIAL_TOPOLOGY = [[1, 2], [3, 4], [5], [], [], [6], [7], []]

assert len(INITIAL_TOPOLOGY) == NUM_SHARDS
assert all([x > y for (y, lst) in enumerate(INITIAL_TOPOLOGY) for x in lst])

VALIDATOR_SHARD_ASSIGNMENT = {}
SHARD_VALIDATOR_ASSIGNMENT = {}

remaining_validators = copy.copy(VALIDATOR_NAMES)
remaining_validators.remove(0)

for ID in SHARD_IDS:
    sample = rand.sample(remaining_validators, NUM_VALIDATORS_PER_SHARD)

    SHARD_VALIDATOR_ASSIGNMENT[ID] = sample
    for v in sample:
        remaining_validators.remove(v)
        VALIDATOR_SHARD_ASSIGNMENT[v] = ID
print(VALIDATOR_SHARD_ASSIGNMENT)


TTL_CONSTANT = 10

NUM_TRANSACTIONS = 50

# Experiment parameters
NUM_ROUNDS = 1000
NUM_WITHIN_SHARD_RECEIPTS_PER_ROUND = 10
NUM_BETWEEN_SHARD_RECEIPTS_PER_ROUND = 30
MEMPOOL_DRAIN_RATE = 1
REPORT_INTERVAL = 1
PAUSE_LENGTH = 0.000001

# Instant broadcast
FREE_INSTANT_BROADCAST = False

# Validity check options
VALIDITY_CHECKS_WARNING_OFF = True
VALIDITY_CHECKS_OFF = False

DEADBEEF = Web3.toChecksumAddress(hex(1271270613000041655817448348132275889066893754095))

# Reporting Parameters
REPORTING = True
DISPLAY_WIDTH = 250
DISPLAY_HEIGHT = 250
DISPLAY_MARGIN = 5
SHARD_X_SPACING = 5
SHARD_Y_SPACING = 5
SHARD_MESSAGE_YOFFSET = 10
SHARD_MESSAGE_XOFFSET = 5

CONSENSUS_MESSAGE_HEIGHTS_TO_DISPLAY_IN_ROOT = 25

# Set to True to restrict routing to paths specified in MSG_ROUTES
RESTRICT_ROUTING = True

# Define message routes in a dict {source: [destination1, destination2, ...]}
MSG_ROUTES = {3: [7], 7: [3]}
