from blocks import Block
from config import SHARD_IDS
import copy as copy



# filter blocks with any orphaned sources in parent

#  This checks filter conditions
#  Filter conditions are like validity conditions for the fork choice
#  They can't be checked from the block data structure!
def is_block_filtered(child, parent_fork_choice=None):

    # No parent? No filter
    if parent_fork_choice is None:
        return False

    assert isinstance(parent_fork_choice, Block), "Expected parent fork choice to be a block"

    parent_ID = parent_fork_choice.shard_ID
    assert parent_ID == child.prevblock.parent_ID, "Expected parent fork choice to be on the parent shard of the prevblock"

    child_ID = child.shard_ID


    # Filter blocks whose sources don't agree with parent fork choice:
    if not parent_fork_choice.is_in_chain(child.sources[parent_ID]):
        return True

    # Filter children who disagree with sources of the parent
    if not child.agrees(parent_fork_choice.sources[child_ID]):
        return True

    # Filter blocks that send messages that are not received and expired in parent fork choice
    for shard_message in child.sent_log.log[parent_ID]:
        if not parent_fork_choice.is_in_chain(shard_message.base):  # children should never point ahead of the parent fork choice
            return True

        if shard_message not in parent_fork_choice.received_log.log[child_ID]:
            if shard_message.base.height + shard_message.TTL <= parent_fork_choice.height:
                return True

    # Filter blocks that haven't received all expired messages from parent fork choice
    for shard_message in parent_fork_choice.sent_log.log[child_ID]:
        if not child.agrees(shard_message.base):  # Agrees allows the children to get ahead of the fork choice
           return True

        if shard_message not in child.received_log.log[parent_ID]:
            if shard_message.base.height + shard_message.TTL <= child.height:
                return True

    return False


# maybe consider mandating in blocks.py that a block's source needs to be at least one block later than the previous source.
# i.e. the same source is invalid. This is necessary to make a new block that makes process but not to make a valid block.
# we can use only ghost on valid blocks if we never make progress, no need to filter (validity is enough) ?

# Returns children of a block tht are not in the filter
def filtered_children(block, blocks, parent_fork_choice=None):
    children = []
    if parent_fork_choice is not None:
        for b in blocks:
            if b.prevblock is not None:
                if b.prevblock == block and not is_block_filtered(b, parent_fork_choice):
                    children.append(b)
    else:
        for b in blocks:
            if b.prevblock is not None:
                if b.prevblock == block:
                    children.append(b)

    return children

# Returns an unfiltered child with maximum score
# The score of a block is the total weight of weighted blocks that agree
def filtered_best_child(parent_block, blocks, block_weights, parent_fork_choice=None):
    good_children = filtered_children(parent_block, blocks, parent_fork_choice)

    # If there are no children, we just return the function's input
    if len(good_children) == 0:
        return parent_block

    # scorekeeping stuff
    max_score = 0
    winning_child = good_children[0]

    for c in good_children:

        # calculates sum of agreeing weight
        score = 0
        for b in block_weights.keys():
            if b.is_in_chain(c):
                score += block_weights[b]

        # check if this is a high score
        if score > max_score:
            winning_child = c
            max_score = score

    return winning_child

# now going to "give" all blocks weights, blocks without weights don't get their weight added in (basically weight 0)
def fork_choice(starting_block, blocks, block_weights):
    if starting_block.parent_ID is None:
        winning_child = filtered_best_child(starting_block, blocks, block_weights)
    else:
        parent_fork_choice = fork_choice(starting_block.sources[starting_block.parent_ID], blocks, block_weights)
        winning_child = filtered_best_child(starting_block, blocks, block_weights, parent_fork_choice)

    if winning_child == starting_block:
        return winning_child

    return fork_choice(winning_child, blocks, block_weights)
