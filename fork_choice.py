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
    assert starting_block not in block_filter, "expected starting block to not be filtered"
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
        assert starting_blocks[ID].is_valid(), "expected valid blocks"

    for b in blocks:
        assert isinstance(b, Block), "expected blocks"
        assert b.is_valid(), "expected valid blocks"

    # the weighted blocks map is a map from some of our blocks to positive weights
    assert isinstance(weighted_blocks, dict), "expected dictionary"
    for b in weighted_blocks.keys():
        assert b in blocks, "expected weighted blocks to appear in view"
        assert isinstance(b, Block), "expected block"
        assert b.is_valid(), "expected valid blocks"
        assert weighted_blocks[b] > 0, "expected positive weights"

    root_shard_ID = 0
    child_ID = 1

    root_shard_fork_choice = fork_choice(starting_blocks[root_shard_ID], blocks, weighted_blocks)

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
                    continue

        # FILTER BLOCKS WITH ORPHANED SOURCES
        if b.received_log.sources[root_shard_ID] is not None:
            if not root_shard_fork_choice.is_in_chain(b.received_log.sources[root_shard_ID]):
                block_filter.append(b)
                continue

        # FILTER BLOCKS WITH ORPHANED BASES
        filtered = False
        for m in b.newly_sent()[root_shard_ID]:
            if not root_shard_fork_choice.is_in_chain(m.base):
                block_filter.append(b)
                filtered = True
                break
        if filtered:
            continue

        # FILTER BLOCKS THAT FAIL TO RECEIVE MESSAGES FROM PARENT ON TIME
        filtered = False
        for m in root_shard_fork_choice.sent_log.log[b.shard_ID]:  # inefficient
            if m in b.received_log.log[root_shard_ID]:
                continue
            if b.height >= m.base.height + m.TTL:  # EXPIRY CONDITION
                block_filter.append(b)
                filtered = True
                break
        if filtered:
            continue

        # FILTER BLOCKS THAT SEND MESSAGES THAT WERE NOT RECEIVED IN TIME
        filtered = False
        for m in b.sent_log.log[root_shard_ID]:  # inefficient
            if m in root_shard_fork_choice.received_log.log[b.shard_ID]:
                continue
            if root_shard_fork_choice.height >= m.base.height + m.TTL:   # EXPIRY CONDITION
                block_filter.append(b)
                filtered = True
                continue

    child_fork_choice = fork_choice(starting_blocks[child_ID], blocks, weighted_blocks, block_filter)

    return {root_shard_ID: root_shard_fork_choice, child_ID: child_fork_choice}
