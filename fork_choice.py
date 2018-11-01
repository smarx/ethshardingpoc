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
    #assert parent_ID == child.prevblock.parent_ID, "Expected parent fork choice to be on the parent shard of the prevblock"

    child_ID = child.shard_ID

    # filter condition for sources:
    if not parent_fork_choice.is_in_chain(child.sources[parent_ID]):  # c.sources[c.parent_ID] != parent_fork_choice_until_source:
        print("Reason 1")
        return True

    # Fiter blocks that don't agree with parent source for child
    if not parent_fork_choice.sources[child_ID].agrees(child):
        print("Reason 2")
        return True

    # Filter blocks that send messages that are not received and expired in parent fork choice
    for shard_message in child.sent_log[parent_ID]:
        if not parent_fork_choice.agrees(shard_message.base):
            print("Reason 3")
            return True

        if shard_message not in parent_fork_choice.received_log[child_ID]:
            if shard_message.base.height + shard_message.TTL <= parent_fork_choice.height:
                print("Reason 4. parent_ID: %s, shard_message.base.height: %s, parent_fork.h: %s. My block: %s, msg_base: %s" % (parent_ID, shard_message.base.height, parent_fork_choice.height, child.hash, shard_message.base.hash))
                return True

    # Filter blocks that haven't received all expired messages from parent fork choice
    for shard_message in parent_fork_choice.sent_log[child_ID]:
        if not child.agrees(shard_message.base):
            print("Reason 5")
            return True

        if shard_message not in child.received_log[parent_ID]:
            if shard_message.base.height + shard_message.TTL <= child.height:
                print("Reason 6")
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

def fork_choice(target_shard_ID, starting_block, blocks, block_weights, genesis_blocks, current=None):
    if current is None:
        current = {}
        for shard_ID, block in genesis_blocks.items():
            current[shard_ID] = block

    # some unnecessary redundancy
    assert starting_block.shard_ID == target_shard_ID
    assert current[target_shard_ID] == starting_block

    children = [b for b in [b for b in blocks if b.prevblock is not None] if b.prevblock == starting_block]

    if starting_block.parent_ID is not None:
        the_source = starting_block.sources[starting_block.parent_ID]
        assert the_source.agrees(current[starting_block.parent_ID])
        if not current[starting_block.parent_ID].is_in_chain(the_source, strict=True):
            fork_choice(starting_block.parent_ID, current[starting_block.parent_ID], blocks, block_weights, genesis_blocks, current)
            if not current[starting_block.parent_ID].is_in_chain(the_source):
                assert False

            if current[target_shard_ID] != starting_block: # we ended up recursively calling back
                old = current[target_shard_ID]
                try_it = fork_choice(target_shard_ID, current[target_shard_ID], blocks, block_weights, genesis_blocks, current)
                assert try_it == old
                return current[target_shard_ID]

        filter_block = current[starting_block.parent_ID]
        additional_filter_block = None
        if starting_block.prevblock is not None and starting_block.prevblock.parent_ID != starting_block.parent_ID and starting_block.prevblock.parent_ID not in starting_block.child_IDs and starting_block.prevblock.parent_ID is not None:
            assert starting_block.prevblock.parent_ID == 1, starting_block.prevblock.parent_ID
            additional_filter_block = current[starting_block.prevblock.parent_ID]

        filter_child = {}
        print("Start filtering blocks for block in shard %s" % target_shard_ID)
        for c in children:
            filter_child[c] = is_block_filtered(c, filter_block)  # deals with filter_block = None by not filtering
            #if not filter_child[c] and additional_filter_block is not None:
            #    filter_child[c] = is_block_filtered(c, additional_filter_block)

        children = [c for c in children if not filter_child[c]]

    if len(children) == 0:
       return current[target_shard_ID]

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

    assert winning_child.is_in_chain(current[target_shard_ID])
    assert current[target_shard_ID] == starting_block
    current[target_shard_ID] = winning_child
    return fork_choice(target_shard_ID, winning_child, blocks, block_weights, genesis_blocks, current)

