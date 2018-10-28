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

    # filter condition for sources:
    if not parent_fork_choice.is_in_chain(child.sources[parent_ID]):  # c.sources[c.parent_ID] != parent_fork_choice_until_source:
        return True

    # Fiter blocks that don't agree with parent source for child
    if not parent_fork_choice.sources[child_ID].agrees(child):
        return True

    # Filter blocks that send messages that are not received and expired in parent fork choice
    for shard_message in child.sent_log[parent_ID]:
        if not parent_fork_choice.agrees(shard_message.base):
            return True

        if shard_message not in parent_fork_choice.received_log[child_ID]:
            if shard_message.base.height + shard_message.TTL <= parent_fork_choice.height:
                return True

    # Filter blocks that haven't received all expired messages from parent fork choice
    for shard_message in parent_fork_choice.sent_log[child_ID]:
        if not child.agrees(shard_message.base):
            return True

        if shard_message not in child.received_log[parent_ID]:
            if shard_message.base.height + shard_message.TTL <= child.height:
                return True

    return False


# now going to "give" all blocks weights, blocks without weights don't get their weight added in (basically weight 0)

forks = {}
already_jumped = []

def update_forks(block):
    global forks
    global already_jumped

    if block.is_in_chain(forks[block.shard_ID]):
        forks[block.shard_ID] = block

        return True
    else:
        return False

def fork_choice(target_shard_ID, starting_block, blocks, block_weights, genesis_blocks, first=True, filter_block=None):

    global forks
    global already_jumped
    if first:
        forks = {0 : genesis_blocks[0], 1 : genesis_blocks[1]}
        already_jumped = []

    if target_shard_ID == 1 and starting_block == genesis_blocks[1] and filter_block is None:
        return fork_choice(target_shard_ID, forks[0], blocks, block_weights, genesis_blocks,  False)

    # get filtered children
    children = [b for b in [b for b in blocks if b.prevblock is not None] if b.prevblock == starting_block]
    # children of parents with root parent IDs are not filtered

    if starting_block.parent_ID is not None:

        filter_child = {}
        for c in children:
            filter_child[c] = is_block_filtered(c, filter_block)  # deals with filter_block = None by not filtering

        children = [c for c in children if not filter_child[c]]

    if len(children) == 0 and starting_block.shard_ID == target_shard_ID:
       return starting_block

    if len(children) == 0 and starting_block.shard_ID != target_shard_ID:
        update_forks(starting_block)
        update_forks(starting_block.sources[target_shard_ID])
        already_jumped.append(starting_block.sources[target_shard_ID])
        if starting_block.parent_ID is None:
            return fork_choice(target_shard_ID, forks[target_shard_ID], blocks, block_weights, genesis_blocks, False, starting_block)
        else:
            return fork_choice(target_shard_ID, forks[target_shard_ID], blocks, block_weights, genesis_blocks, False)

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

    update_forks(winning_child)

    # case where we have a switch block winning in the root:
    if winning_child.switch_block and starting_block.parent_ID is None:
        update_forks(winning_child.sources[starting_block.child_IDs[0]])
        return fork_choice(target_shard_ID, forks[starting_block.child_IDs[0]], blocks, block_weights, genesis_blocks, False, winning_child)

    # case where we have a swich block winning in the child
    if winning_child.switch_block and starting_block.parent_ID is not None:
        return fork_choice(target_shard_ID, forks[winning_child.shard_ID], blocks, block_weights, genesis_blocks, False)

    return fork_choice(target_shard_ID, forks[winning_child.shard_ID], blocks, block_weights, genesis_blocks, False, filter_block)
