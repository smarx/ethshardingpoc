from blocks import Block, Message, SwitchMessage_BecomeAParent, SwitchMessage_ChangeParent
from blocks import MessagesLog
from blocks import MessagesLog
from config import SHARD_IDS
from config import VALIDATOR_NAMES
from config import VALIDATOR_WEIGHTS
from config import TTL_CONSTANT
from evm_transition import apply_to_state

from fork_choice import fork_choice, sharded_fork_choice

import copy

class UnresolvedDeps(Exception):
    pass


class ConsensusMessage:
    def __init__(self, block, name, justification=[]):
        self.estimate = block
        self.sender = name
        self.justification = justification

        assert isinstance(self.estimate, Block), "expected block"
        assert self.estimate.is_valid(), "expected block to be valid"

        assert self.sender in VALIDATOR_NAMES

        self.height = 0
        max_height = 0
        for m in self.justification:
            assert isinstance(m, ConsensusMessage), "expected justification to contain consensus messages"
            if m.height > max_height:
                if m.estimate.shard_ID == self.estimate.shard_ID:
                    max_height = m.height

        self.height = max_height + 1


class Validator:
    def __init__(self, name):
        assert name in VALIDATOR_NAMES, "expected a validator name"
        self.name = name
        self.consensus_messages = []

    def receive_consensus_message(self, message):
        for m in message.justification:
            assert isinstance(m, ConsensusMessage), "expected consensus message"
            if m not in self.consensus_messages:
                raise UnresolvedDeps

        self.consensus_messages.append(message)

    # assumes no equivocations exist
    def latest_messages(self):
        max_heights = dict.fromkeys(VALIDATOR_NAMES)
        L_M = dict.fromkeys(VALIDATOR_NAMES)
        for v in VALIDATOR_NAMES:
            max_heights[v] = -1

        for m in self.consensus_messages:
            if m.height > max_heights[m.sender]:
                max_heights[m.sender] = m.height
                L_M[m.sender] = m

        return L_M

    def get_weighted_blocks(self):
        weighted_blocks = {}
        L_M = self.latest_messages()
        for v in VALIDATOR_NAMES:
            if L_M[v] is not None:
                if L_M[v].estimate in weighted_blocks.keys():
                    weighted_blocks[L_M[v].estimate] += VALIDATOR_WEIGHTS[v]
                else:
                    weighted_blocks[L_M[v].estimate] = VALIDATOR_WEIGHTS[v]

        return weighted_blocks

    def get_blocks_from_consensus_messages(self):
        blocks = []
        for m in self.consensus_messages:
            blocks.append(m.estimate)
        return blocks

    # TODO: memoize? this shouldn't change
    def genesis_blocks(self):
        genesis_blocks = {}
        for m in self.consensus_messages:
            if m.sender == 0:
                genesis_blocks[m.estimate.shard_ID] = m.estimate
        return genesis_blocks


    def make_fork_choice(self, shard_ID):
        # the blocks in the view are the genesis blocks and blocks from consensus messages
        blocks = self.get_blocks_from_consensus_messages()
        weighted_blocks = self.get_weighted_blocks()
        genesis_blocks = self.genesis_blocks()

        next_fork_choice = sharded_fork_choice(shard_ID, genesis_blocks, blocks, weighted_blocks)


        #print("shard_sequence", shard_sequence)
        #print("shard_ID", next_fork_choice.shard_ID, shard_ID)
        assert next_fork_choice.shard_ID == shard_ID, "expected fork choice to be on requested shard"

        return next_fork_choice

    def make_all_fork_choices(self):

        fork_choices = {}
        for shard_ID in SHARD_IDS:
            fork_choices[shard_ID] = self.make_fork_choice(shard_ID)
        return fork_choices

    def next_hop(self, routing_table, target_shard_ID):
        return routing_table[target_shard_ID] if target_shard_ID in routing_table else None

    def make_block(self, shard_ID, mempools, drain_amount, genesis_blocks, TTL=TTL_CONSTANT):
        genesis_blocks = self.genesis_blocks()
        # RUN FORK CHOICE RULE ON SELF
        # will only have fork choices for parent and children
        my_fork_choice = self.make_fork_choice(shard_ID)
        # --------------------------------------------------------------------#


        # GET PREVBLOCK POINTER FROM FORK CHOICE
        prevblock = my_fork_choice
        # --------------------------------------------------------------------#


        # EXTEND THE TRANSACTION LOG FROM THE MEMPOOL
        prev_txn_log = prevblock.txn_log
        new_txn_log = copy.copy(prev_txn_log)
        data = []
        num_prev_txs = len(prev_txn_log)


        neighbor_shard_IDs = []
        if my_fork_choice.parent_ID is not None:
            neighbor_shard_IDs.append(my_fork_choice.parent_ID)
        for IDs in my_fork_choice.child_IDs:
            neighbor_shard_IDs.append(IDs)

        # BUILD SOURCES
        sources = {ID : genesis_blocks[ID] for ID in SHARD_IDS}
        for ID in neighbor_shard_IDs:
            if ID == shard_ID:
                continue

            #if len(prevblock.received_log.log[ID]):
            #    assert prevblock.received_log.log[ID][-1].base.shard_ID == ID
            #    sources[ID] = prevblock.received_log.log[ID][-1].base

            neighbor_fork_choice = self.make_fork_choice(ID)
            # SOURCES = FORK CHOICE (except for self)
            sources[ID] = neighbor_fork_choice
            assert sources[ID].is_in_chain(prevblock.sources[ID]), "Sources inconsistent, new block shard id: %s, source from shard: %s, heights: %s over %s, new_source_parent_ID: %s, old_source_parent_ID: %s, first_children: %s, three_parent: %s" % (shard_ID, ID, sources[ID].height, prevblock.sources[ID].height, sources[ID].parent_ID, prevblock.sources[ID].parent_ID, self.make_fork_choice(1).child_IDs, self.make_fork_choice(3).parent_ID)
        #for ID in SHARD_IDS:
        #    if ID not in neighbor_shard_IDs and ID != shard_ID:
        #        sources[ID] = prevblock.sources[ID]
        # --------------------------------------------------------------------#

        if num_prev_txs < len(mempools[shard_ID]) and 'opcode' in mempools[shard_ID][num_prev_txs]:
            child_to_become_parent = mempools[shard_ID][num_prev_txs]['child_to_become_parent']
            child_to_move_down = mempools[shard_ID][num_prev_txs]['child_to_move_down']
            # TODO: for swapping with root only one message will be needed
            sources = copy.copy(prevblock.sources)
            msg1 = SwitchMessage_BecomeAParent(sources[child_to_become_parent], 1, child_to_become_parent, child_to_move_down, sources[child_to_move_down])
            msg2 = SwitchMessage_ChangeParent(sources[child_to_move_down], 1, child_to_move_down, child_to_become_parent, sources[child_to_become_parent])

            mempools[shard_ID] = mempools[shard_ID][:num_prev_txs] + mempools[shard_ID][num_prev_txs + 1:]

            sent_log = copy.copy(prevblock.sent_log)
            received_log = copy.copy(prevblock.received_log)

            sent_log.add_message(msg1.target_shard_ID, msg1)
            sent_log.add_message(msg2.target_shard_ID, msg2)

            ret = Block(shard_ID, prevblock, new_txn_log, sent_log, received_log, sources, prevblock.vm_state)
            ret.child_IDs.remove(child_to_move_down)
            ret.routing_table[child_to_move_down] = child_to_become_parent
            print("IMPORTANT: %s" % ret.routing_table)
            return ret


        for i in range(drain_amount):
            if num_prev_txs + i < len(mempools[shard_ID]):
                new_tx = mempools[shard_ID][num_prev_txs + i]
                if 'opcode' in new_tx:
                    # this is a switch message, stop processing messages
                    break
                new_txn_log.append(new_tx)
                data.append(new_tx)
        # --------------------------------------------------------------------#


        # BUILD RECEIVED LOG WITH:
        received_log = MessagesLog()
        for ID in SHARD_IDS:
            if ID == shard_ID:
                continue

            if ID in neighbor_shard_IDs:
                neighbor_fork_choice = self.make_fork_choice(ID)
                # RECEIVED = SENT MESSAGES FROM FORK CHOICE
                received_log.log[ID] = copy.copy(neighbor_fork_choice.sent_log.log[shard_ID])
            else:
                received_log.log[ID] = copy.copy(prevblock.received_log.log[ID])
        # --------------------------------------------------------------------#


        # PREP NEWLY RECEIVED PMESSAGES IN A RECEIVEDLOG FOR EVM:
        newly_received_messages = {}
        new_sent_messages = MessagesLog()
        for ID in SHARD_IDS:
            previous_received_log_size = len(prevblock.received_log.log[ID])
            newly_received_messages[ID] = received_log.log[ID][previous_received_log_size:]

        become_a_parent_of = None
        change_parent_to = None

        newly_received_payloads = MessagesLog()
        for ID in SHARD_IDS:
            for m in newly_received_messages[ID]:
                if m.target_shard_ID == shard_ID:
                    if isinstance(m, SwitchMessage_BecomeAParent):
                        become_a_parent_of = (m.new_child_ID, m.new_child_source)
                    elif isinstance(m, SwitchMessage_ChangeParent):
                        change_parent_to = (m.new_parent_ID, m.new_parent_source)

        routing_table = copy.copy(prevblock.routing_table)
        new_parent_ID = prevblock.parent_ID

        if become_a_parent_of is not None:
            routing_table[become_a_parent_of[0]] = become_a_parent_of[0]
            neighbor_fork_choice = self.make_fork_choice(become_a_parent_of[0])
            sources[become_a_parent_of[0]] = neighbor_fork_choice

            ID = become_a_parent_of[0]
            received_log.log[ID] = copy.copy(neighbor_fork_choice.sent_log.log[shard_ID])
            previous_received_log_size = len(prevblock.received_log.log[ID])
            newly_received_messages[ID] = received_log.log[ID][previous_received_log_size:]

        if change_parent_to is not None:
            new_parent_ID = change_parent_to[0]
            neighbor_fork_choice = self.make_fork_choice(change_parent_to[0])
            sources[change_parent_to[0]] = neighbor_fork_choice

            ID = change_parent_to[0]
            received_log.log[ID] = copy.copy(neighbor_fork_choice.sent_log.log[shard_ID])
            previous_received_log_size = len(prevblock.received_log.log[ID])
            newly_received_messages[ID] = received_log.log[ID][previous_received_log_size:]

        for ID in SHARD_IDS:
            for m in newly_received_messages[ID]:
                if m.target_shard_ID == shard_ID:
                    if isinstance(m, SwitchMessage_BecomeAParent):
                        become_a_parent_of = (m.new_child_ID, m.new_child_source)
                    elif isinstance(m, SwitchMessage_ChangeParent):
                        change_parent_to = (m.new_parent_ID, m.new_parent_source)
                    else:
                        newly_received_payloads.add_message(ID, m)

                else:
                    next_hop_ID = self.next_hop(routing_table, m.target_shard_ID)
                    if next_hop_ID is not None:
                        assert next_hop_ID in prevblock.child_IDs, "shard_ID: %s, destination: %s, next_hop: %s, children: %s" % (shard_ID, ID, next_hop_ID, prevblock.child_IDs)
                    else:
                        next_hop_ID = new_parent_ID
                    assert next_hop_ID is not None
                    new_sent_messages.log[next_hop_ID].append(Message(sources[next_hop_ID], m.TTL, m.target_shard_ID, m.payload))

        # --------------------------------------------------------------------#


        # KEY EVM INTEGRATION HERE

        # this is where we have this function that produces the new vm state and the new outgoing payloads
        # new_vm_state, new_outgoing_payloads = apply_to_state(prevblock.vm_state, data, newly_received_payloads)

        new_vm_state, new_outgoing_payloads = apply_to_state(prevblock.vm_state, data, newly_received_payloads, genesis_blocks)

        # --------------------------------------------------------------------#


        # BUILD SENT LOG FROM NEW OUTGOING PAYLOADS
        # by this time new_sent_messages might already have some messages from rerouting above
        for ID in SHARD_IDS:
            if ID != shard_ID:
                for m in new_outgoing_payloads.log[ID]:
                    # if TTL == 0, then we'll make an invalid block
                    # one that sends a message that must be included by the base
                    # which already exists and therefore cannot include this message
                    if TTL > 0:
                        first_hop_ID = self.next_hop(routing_table, ID)
                        if first_hop_ID is not None:
                            assert first_hop_ID in prevblock.child_IDs, "shard_ID: %s, target: %s, first_hop_ID: %s, parent: %s, children: %s, rtable: %s" % (shard_ID, ID, first_hop_ID, prevblock.parent_ID, prevblock.child_IDs, prevblock.routing_table)
                        else:
                            first_hop_ID = new_parent_ID
                        assert first_hop_ID is not None
                        new_sent_messages.log[first_hop_ID].append(Message(sources[first_hop_ID], TTL, ID, m.payload))
                    else:
                        print("Warning: Not sending message because TTL == 0")

        sent_log = prevblock.sent_log.append_MessagesLog(new_sent_messages)
        # --------------------------------------------------------------------#




        ret = Block(shard_ID, prevblock, new_txn_log, sent_log, received_log, sources, new_vm_state, postpone_validation=True)
        if become_a_parent_of is not None:
            assert become_a_parent_of[0] not in ret.child_IDs, "shard_ID: %s, become_of: %s, child_IDs: %s" % (shard_ID, become_a_parent_of[0], ret.child_IDs)
            ret.child_IDs.append(become_a_parent_of[0])
            ret.routing_table[become_a_parent_of[0]] = become_a_parent_of[0]

        if change_parent_to is not None:
            assert change_parent_to[0] not in ret.child_IDs
            assert change_parent_to[0] != ret.parent_ID
            ret.parent_ID = change_parent_to[0]

        check = ret.is_valid()
        assert check[0], check[1]

        return ret

    def make_new_consensus_message(self, shard_ID, mempools, drain_amount, genesis_blocks, TTL=TTL_CONSTANT):

        assert shard_ID in SHARD_IDS, "expected shard ID"
        assert isinstance(drain_amount, int), "expected int"
        assert isinstance(TTL, int), "expected int"
        assert isinstance(mempools, dict), "expected dict"
        new_block = self.make_block(shard_ID, mempools, drain_amount, genesis_blocks, TTL)
        new_message = ConsensusMessage(new_block, self.name, copy.copy(self.consensus_messages))
        self.receive_consensus_message(new_message)
        return new_message
