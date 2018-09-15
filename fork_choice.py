from blocks import Block
from config import SHARD_IDS

# Returns children of a block tht are not in the filter
def filtered_children(block, blocks, block_filter):
    children = []
    for b in blocks:
        if b.prevblock is not None:
            if b.prevblock == block and b not in block_filter:
                children.append(b)
    return children

# Returns an unfiltered child with maximum score
# The score of a block is the total weight of weighted blocks that agree
def best_child(block, blocks, weighted_blocks, block_filter):
    children = filtered_children(block, blocks, block_filter)

    # If there are no children, we just return the function's input
    if len(children) == 0:
        return block

    # scorekeeping stuff
    max_score = 0
    winning_child = children[0]

    for c in children:

        # calculates sum of agreeing weight
        score = 0
        for b in weighted_blocks.keys():
            if b.is_in_chain(c):
                score += weighted_blocks[b]

        # check if this is a high score
        if score > max_score:
            winning_child = c
            max_score = score

    return winning_child

# Filtered GHOST: like GHOST but it ignores blocks in "block_filter"
def fork_choice(starting_block, blocks, weighted_blocks, block_filter=[]):
    assert starting_block not in block_filter, "expected starting block to not be filtered"

    # This loop replaces this_block with this_block's best filtered child
    this_block = starting_block
    next_block = best_child(this_block, blocks, weighted_blocks, block_filter)
    while (next_block != this_block):
        this_block = next_block
        next_block = best_child(this_block, blocks, weighted_blocks, block_filter)

    return this_block

# Sharded fork choice rule returns a block for every shard
def sharded_fork_choice(starting_blocks, blocks, weighted_blocks):

    # TYPE GUARD
    for ID in starting_blocks.keys():
        assert ID in SHARD_IDS, "expected shard IDs"
        assert isinstance(starting_blocks[ID], Block), "expected starting blocks to be blocks"
        assert starting_blocks[ID] in blocks, "expected starting blocks to appear in blocks"
        assert starting_blocks[ID].is_valid(), "expected valid blocks"

    for b in blocks:
        assert isinstance(b, Block), "expected blocks"
        assert b.is_valid(), "expected valid blocks"

    assert isinstance(weighted_blocks, dict), "expected dictionary"
    for b in weighted_blocks.keys():
        assert b in blocks, "expected weighted blocks to appear in blocks"
        assert isinstance(b, Block), "expected block"
        assert b.is_valid(), "expected valid blocks"
        assert weighted_blocks[b] > 0, "expected positive weights"
    # --------------------------------------------------------------------#


    # one day this won't be hard coded:
    parent_ID = 0
    child_ID = 1


    # THE PARENT SHARD FORK CHOICE IS INDEPENDENT OF THE CHILD SHARD
    parent_shard_fork_choice = fork_choice(starting_blocks[parent_ID], blocks, weighted_blocks)
    # --------------------------------------------------------------------#

    # THE CHILD SHARD HAS TO FILTER BLOCKS FROM ITS FORK CHOICE
    # AS A FUNCTION OF THE FORK CHOICE OF THE PARENT
    block_filter = []
    for b in blocks:

        # blocks on the parent shard aren't filtered
        if b.shard_ID == parent_ID:
            continue

        # FILTER BLOCKS THAT DONT AGREE WITH MOST RECENT SOURCE
        if parent_shard_fork_choice.received_log.sources[child_ID] is not None:
            if not parent_shard_fork_choice.received_log.sources[child_ID].is_in_chain(b):
                if not b.is_in_chain(parent_shard_fork_choice.received_log.sources[child_ID]):
                    block_filter.append(b)
                    continue
        # --------------------------------------------------------------------#


        # FILTER BLOCKS WITH ORPHANED SOURCES
        if b.received_log.sources[parent_ID] is not None:
            if not parent_shard_fork_choice.is_in_chain(b.received_log.sources[parent_ID]):
                block_filter.append(b)
                continue
        # --------------------------------------------------------------------#


        # FILTER BLOCKS WITH ORPHANED BASES
        filtered = False
        for m in b.newly_sent()[parent_ID]:
            if not parent_shard_fork_choice.is_in_chain(m.base):
                block_filter.append(b)
                filtered = True
                break
        if filtered:
            continue
        # --------------------------------------------------------------------#


        # FILTER BLOCKS THAT FAIL TO RECEIVE MESSAGES FROM PARENT ON TIME
        filtered = False
        for m in parent_shard_fork_choice.sent_log.log[b.shard_ID]:  # inefficient
            if m in b.received_log.log[parent_ID]:
                continue
            if b.height >= m.base.height + m.TTL:  # EXPIRY CONDITION
                block_filter.append(b)
                filtered = True
                break
        if filtered:
            continue
        # --------------------------------------------------------------------#


        # FILTER BLOCKS THAT SEND MESSAGES THAT WERE NOT RECEIVED IN TIME
        filtered = False
        for m in b.sent_log.log[parent_ID]:  # inefficient
            if m in parent_shard_fork_choice.received_log.log[b.shard_ID]:
                continue
            if parent_shard_fork_choice.height >= m.base.height + m.TTL:   # EXPIRY CONDITION
                block_filter.append(b)
                filtered = True
                continue
        # --------------------------------------------------------------------#


    # CALCULATE CHILD FORK CHOICE (FILTERED GHOST)
    child_fork_choice = fork_choice(starting_blocks[child_ID], blocks, weighted_blocks, block_filter)

    return {parent_ID: parent_shard_fork_choice, child_ID: child_fork_choice}
