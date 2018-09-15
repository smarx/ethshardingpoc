from blocks import Block
from config import SHARD_IDS

def filtered_children(block, blocks, block_filter):
    children = []
    for b in blocks:
        if b.prevblock is not None:
            if b.prevblock == block and b not in block_filter:
                children.append(b)
    return children

def best_child(block, blocks, weighted_blocks, block_filter):
    children = filtered_children(block, blocks, block_filter)

    if len(children) == 0:
        return block

    scores = dict.fromkeys(children)
    max_score = 0
    winning_child = children[0]
    for c in children:
        scores[c] = 0
        for b in weighted_blocks.keys():
            if b.is_in_chain(c):
                scores[c] += weighted_blocks[b]
        if scores[c] > max_score:
            winning_child = c
            max_score = scores[c]

    return winning_child


def fork_choice(starting_block, blocks, weighted_blocks, block_filter=[]):
    this_block = starting_block
    next_block = best_child(this_block, blocks, weighted_blocks, block_filter)
    while (next_block != this_block):
        this_block = next_block
        next_block = best_child(this_block, blocks, weighted_blocks, block_filter)

    return this_block

def sharded_fork_choice(starting_blocks, blocks, weighted_blocks):

    for ID in starting_blocks.keys():
        assert ID in SHARD_IDS, "expected shard IDs"
        assert isinstance(starting_blocks[ID], Block), "expected starting blocks to be blocks"

    for b in blocks:
        assert isinstance(b, Block), "expected blocks"

    # the weighted blocks map is a map from some of our blocks to positive weights
    assert isinstance(weighted_blocks, dict), "expected dictionary"
    for b in weighted_blocks.keys():
        assert b in blocks, "expected weighted blocks to appear in view"
        assert isinstance(b, Block), "expected block"
        assert weighted_blocks[b] > 0, "expected positive weights"

    root_shard_ID = 0
    root_shard_fork_choice = fork_choice(starting_blocks[root_shard_ID], blocks, weighted_blocks)

    child_ID = 1

    block_filter = []
    for b in blocks:

        # blocks on the root shard aren't filtered
        if b.shard_ID == root_shard_ID:
            continue

        # FILTER BLOCKS THAT DONT AGREE WITH MOST RECENT SOURCE
        if root_shard_fork_choice.received_log.sources[child_ID] is not None:
            if not root_shard_fork_choice.received_log.sources[child_ID].is_in_chain(b):
                if not b.is_in_chain(root_shard_fork_choice.received_log.sources[child_ID]):
                    block_filter.append(b)

        # FILTER BLOCKS WITH ORPHANED SOURCES
        if b.received_log.sources[root_shard_ID] is not None:
            if not root_shard_fork_choice.is_in_chain(b.received_log.sources[root_shard_ID]):
                block_filter.append(b)
                continue

        # FILTER BLOCKS WITH ORPHANED BASES
        if b.sent_log.log[root_shard_ID] != []:
            for m in b.newly_sent()[root_shard_ID]:
                if not root_shard_fork_choice.is_in_chain(m.base):
                    block_filter.append(b)
                    continue


        # FILTER BLOCKS THAT FAIL TO RECEIVE MESSAGES FROM PARENT ON TIME
        for m in root_shard_fork_choice.sent_log.log[b.shard_ID]:
            if m not in b.received_log.log[root_shard_ID]:
                if b.height >= m.base.height + m.TTL:  # EXPIRY CONDITION
                    block_filter.append(b)
                    continue

        # FILTER BLOCKS THAT SEND MESSAGES THAT WERE NOT RECEIVED IN TIME
        for m in b.sent_log.log[root_shard_ID]:
            if m not in root_shard_fork_choice.received_log.log[b.shard_ID]:
                if root_shard_fork_choice.height >= m.base.height + m.TTL:   # EXPIRY CONDITION
                    block_filter.append(b)
                    continue



        '''
        # if they conflict with the most recent source of the root
        if root_shard_fork_choice.received_log.sources[b.shard_ID] is not None:
            if not b.is_in_chain(root_shard_fork_choice.received_log.sources[b.shard_ID]):
                block_filter.append(b)
                continue

        # if they conflict with the most recent source of the root
        if b.received_log.sources[root_shard_ID] is not None:
            if not root_shard_fork_choice.is_in_chain(b.received_log.sources[root_shard_ID]):
                block_filter.append(b)
        '''

    child_fork_choice = fork_choice(starting_blocks[child_ID], blocks, weighted_blocks, block_filter)

    '''
    right_child_ID = 2
    right_child_fork_choice = fork_choice(starting_blocks[right_child_ID], blocks, weighted_blocks, block_filter)
    '''
    return {root_shard_ID: root_shard_fork_choice, child_ID: child_fork_choice}


def test():

    g0 = Block(0)
    g1 = Block(1)
    g2 = Block(2)
    a = Block(1, g1)
    b = Block(1, g1)
    c = Block(1, b)
    d = Block(1, c)
    e = Block(1, c)
    f = Block(1, e)

    weighted_blocks = {g0: 1, b: 1, g2: 1, f: 1, d: 100}
    starting_blocks = {0: g0, 1: g1, 2: g2}
    blocks = [g0, g1, g2, a, b, c, d, e, f]

    result = sharded_fork_choice(starting_blocks, blocks, weighted_blocks)

    print("0", result[0])
    print("1", result[1])
    print("2", result[2])

    print("height f", f.height)

    return result
