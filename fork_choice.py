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
    assert parent_ID == child.parent_ID, "Expected parent fork choice to be on the parent shard of the prevblock"

    child_ID = child.shard_ID

    # Filter blocks that send messages that are not received and expired in parent fork choice
    for shard_message in child.sent_log[parent_ID]:
        if not parent_fork_choice.is_in_chain(shard_message.base):  # children should never point ahead of the parent fork choice
            return True

        if shard_message not in parent_fork_choice.received_log[child_ID]:
            if shard_message.base.height + shard_message.TTL <= parent_fork_choice.height:
                return True

    # Filter blocks that haven't received all expired messages from parent fork choice
    for shard_message in parent_fork_choice.sent_log[child_ID]:
        if not child.agrees(shard_message.base):  # Agrees allows the children to get ahead of the fork choice
           return True

        if shard_message not in child.received_log[parent_ID]:
            if shard_message.base.height + shard_message.TTL <= child.height:
                return True

    return False


# now going to "give" all blocks weights, blocks without weights don't get their weight added in (basically weight 0)
def fork_choice(starting_block, blocks, block_weights, genesis_blocks, up_to_height=None):
    if up_to_height == starting_block.height:
        return starting_block

    # get filtered children
    children = [b for b in [b for b in blocks if b.prevblock is not None] if b.prevblock == starting_block]

    filter_child = {}
    for c in children:
        filter_child[c] = False

    for c in children:
        if c.parent_ID is None:
            break

        # filter condition for sources:
        source_height = c.sources[c.parent_ID].height
        parent_fork_choice_until_source = fork_choice(genesis_blocks[c.parent_ID], blocks, block_weights, genesis_blocks, source_height)
        if not c.sources[c.parent_ID].agrees(parent_fork_choice_until_source):
            filter_child[c] = True

        potential_parent_fork_choices = [b for b in blocks if b.is_in_chain(c.sources[c.parent_ID])]
        # filter condition for the TTL
        for b in potential_parent_fork_choices:
            if is_block_filtered(c, b):
                filter_child[c] = True
                break
    children = [c for c in children if not filter_child[c]]

    # If there are no children, we just return the function's input
    if len(children) == 0:
        return starting_block

    # scorekeeping stuff
    max_score = 0
    winning_child = children[0]

    for c in children:

        # calculates sum of agreeing weight
        score = 0
        for b in block_weights.keys():
            if b.is_in_chain(c):
                score += block_weights[b]

        # check if this is a high score
        if score > max_score:
            winning_child = c
            max_score = score

    if winning_child == starting_block:
        return starting_block

    return fork_choice(winning_child, blocks, block_weights, genesis_blocks, up_to_height)
