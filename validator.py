from blocks import Block, Message, SwitchMessage_BecomeAParent, SwitchMessage_ChangeParent

from config import SHARD_IDS
from config import VALIDATOR_NAMES
from config import VALIDATOR_WEIGHTS
from config import TTL_CONSTANT
from evm_transition import apply_to_state
import random as rand
from fork_choice import fork_choice

import copy


class UnresolvedDeps(Exception):
    pass


class ConsensusMessage:
    def __init__(self, block, name, justification=[]):
        self.estimate = block
        self.sender = name
        self.justification = justification
        self.hash = rand.randint(1, 10000000)

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

    def __hash__(self):
        return self.hash

    def __eq__(self, message):
        return self.hash == message.hash

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

    def make_fork_choice(self, shard_ID, genesis_blocks):
        # the blocks in the view are the genesis blocks and blocks from consensus messages
        blocks = self.get_blocks_from_consensus_messages()
        weighted_blocks = self.get_weighted_blocks()

        next_fork_choice = fork_choice(genesis_blocks[shard_ID], blocks, weighted_blocks, genesis_blocks)

        assert next_fork_choice.shard_ID == shard_ID, "expected fork choice to be on requested shard"

        return next_fork_choice

    def make_all_fork_choices(self, genesis_blocks):
        fork_choices = {}
        for shard_ID in SHARD_IDS:
            fork_choices[shard_ID] = self.make_fork_choice(shard_ID, genesis_blocks)
        return fork_choices

    def next_hop(self, routing_table, target_shard_ID):
        return routing_table[target_shard_ID] if target_shard_ID in routing_table else None

    # 3 kinds of blocks:
    # regular block
    # switch sending block
    # switch receiving block

    def make_block(self, shard_ID, mempools, drain_amount, genesis_blocks, TTL=TTL_CONSTANT):

        # First, the previous block pointer:
        prevblock = copy.deepcopy(self.make_fork_choice(shard_ID, genesis_blocks))
        assert prevblock.shard_ID == shard_ID, "expected consistent IDs"

        new_txn_log = copy.deepcopy(prevblock.txn_log)
        new_received_log = copy.deepcopy(prevblock.received_log)
        new_sources = copy.deepcopy(prevblock.sources)
        new_sent_log = copy.deepcopy(prevblock.sent_log)
        new_routing_table = copy.deepcopy(prevblock.routing_table)
        new_parent_ID = copy.deepcopy(prevblock.parent_ID)
        new_child_IDs = copy.deepcopy(prevblock.child_IDs)

        # --------------------------------------------------------------------#
        # This part determines whether our block is a switch block:
        # --------------------------------------------------------------------#

        # Assume not, and look for switch messages as the next pending messages in tx and message queues:
        switch_block = False

        switch_tx = None
        switch_message = None
        # look in the mempool
        num_prev_txs = len(new_txn_log)
        if num_prev_txs < len(mempools[shard_ID]) and 'opcode' in mempools[shard_ID][num_prev_txs]:
            switch_tx = mempools[shard_ID][num_prev_txs]
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", shard_ID)
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", prevblock.height)

            switch_block = True
        else:  # look at sent messages of prevblock's neighbors
            neighbor_shard_IDs = prevblock.get_neighbors()
            old_neighbor_sources = copy.deepcopy(prevblock.sources)
            for ID in neighbor_shard_IDs:
                old_neighbor_sources[ID] = self.make_fork_choice(ID, genesis_blocks)
                print("ID in new_child_IDs")
                print(ID in new_child_IDs)
                print("ID == new_parent_IDs")
                print(ID == new_parent_ID)
                assert old_neighbor_sources[ID].is_in_chain(prevblock.sources[ID]), "expected monotonic sources - error 0"

                last_receive_log_length = len(prevblock.received_log[ID])
                if len(old_neighbor_sources[ID].sent_log[shard_ID]) > last_receive_log_length:
                    next_message = old_neighbor_sources[ID].sent_log[shard_ID][last_receive_log_length]
                    if isinstance(next_message, SwitchMessage_BecomeAParent) or isinstance(next_message, SwitchMessage_ChangeParent):
                        switch_source_ID = ID
                        switch_source = old_neighbor_sources[ID]
                        switch_message = next_message
                        switch_block = True
                        break

        if switch_block:
            assert switch_message is not None or switch_tx is not None
        # --------------------------------------------------------------------#
        # If our block is a switch block, then we won't process anything
        # against the EVM, nor receiving or sending messages that are not switch messages
        # --------------------------------------------------------------------#

        # We will first process switch blocks:

        if switch_block:

            if switch_tx is not None:
                new_txn_log.append(switch_tx)

                child_to_become_parent = mempools[shard_ID][num_prev_txs]['child_to_become_parent']
                child_to_move_down = mempools[shard_ID][num_prev_txs]['child_to_move_down']

                # this could be a more conservative choice, using fork choice is a bit high risk bc we might have more switch blocks in here
                fork_choice_of_child_to_become_parent = self.make_fork_choice(child_to_become_parent, genesis_blocks)  # new_sources[child_to_become_parent]
                fork_choice_of_child_to_move_down = self.make_fork_choice(child_to_move_down, genesis_blocks)  # new_sources[child_to_move_down]

                msg1 = SwitchMessage_BecomeAParent(fork_choice_of_child_to_become_parent, TTL_CONSTANT, child_to_become_parent, child_to_move_down, fork_choice_of_child_to_move_down)
                msg2 = SwitchMessage_ChangeParent(fork_choice_of_child_to_move_down, TTL_CONSTANT, child_to_move_down, child_to_become_parent, fork_choice_of_child_to_become_parent)

                # they have the switch messages in the sent message queues
                new_sent_log[child_to_become_parent].append(msg1)
                new_sent_log[child_to_move_down].append(msg2)

                # removing child from the switch block
                new_child_IDs.remove(child_to_move_down)

                # now the routing table
                for ID in new_routing_table.keys():
                    if new_routing_table[ID] == child_to_move_down:
                        new_routing_table[ID] = child_to_become_parent

                # may be redundant, but won't hurt anyone:
                new_routing_table[child_to_move_down] = child_to_become_parent

                # parent_ID unchanged
                # received_log unchanged
                # sources unchanged

            elif switch_message is not None:
                new_received_log[switch_source_ID].append(switch_message)
                # only update source the minimum amount to receive only the switch message
                new_sources[switch_source_ID] = switch_source.first_block_with_message_in_sent_log(shard_ID, switch_message)
                print("switch_source", switch_source)
                print("switch_message", switch_message)
                print("switch_source_ID", switch_source_ID)
                print("new_sources[switch_source_ID]", new_sources[switch_source_ID])
                print("switch message in new_sources[switch_source_ID].sent_log[shard_ID]", switch_message in new_sources[switch_source_ID].sent_log[shard_ID])
                print("switch message in new_sources[switch_source_ID].prevblock.sent_log[shard_ID]", switch_message in new_sources[switch_source_ID].prevblock.sent_log[shard_ID])
                print("new_sources[switch_source_ID].switch_block", new_sources[switch_source_ID].switch_block)
                assert new_sources[switch_source_ID].switch_block

                if isinstance(switch_message, SwitchMessage_BecomeAParent):
                    new_child_IDs.append(switch_message.new_child_ID)
                    for ID in switch_message.new_child_source.routing_table.keys():
                        new_routing_table[ID] = switch_message.new_child_ID
                elif isinstance(switch_message, SwitchMessage_ChangeParent):
                    new_parent_ID = switch_message.new_parent_ID

                # new_txn_log unchanged
                # new_sent_log unchanged

            new_block = Block(shard_ID, prevblock, True, new_txn_log, new_sent_log, new_received_log, new_sources, new_parent_ID, new_child_IDs, new_routing_table, prevblock.vm_state)

            assert new_block.switch_block
            print("new_block", new_block)
            print("new_block.switch_block", new_block.switch_block)

            check = new_block.is_valid()
            if not check[0]:
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("shard_ID", prevblock.shard_ID)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("txn_log", new_txn_log)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("self.sent_log", new_sent_log)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("self.received_log", new_received_log)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("shard_ID", shard_ID)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("txn_log", new_txn_log)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("self.sent_log", new_sent_log)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("self.received_log", new_received_log)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
                print("receiving_opcode: ", switch_block)
                print("---------------------------------------------------------")
                print("---------------------------------------------------------")
            assert check[0], "Invalid Block: " + check[1]

            return new_block

        # --------------------------------------------------------------------#
        # --------------------------------------------------------------------#
        # --------------------------------------------------------------------#
        # --------------------------------------------------------------------#
        # --------------------------------------------------------------------#

        # And now for the rest of the blocks, the ones that don't change the routing table
        # But which do routing and execution of state against the EVM

        data = []

        for i in range(drain_amount):
            if num_prev_txs + i < len(mempools[shard_ID]):
                new_tx = mempools[shard_ID][num_prev_txs + i]
                if 'opcode' in new_tx:
                    # Don't add switch transaction to tx log 
                    break
                new_txn_log.append(new_tx)
                data.append(new_tx)

        # print("NEW TXN LEN: ", len(new_txn_log))
        # print("PRE NEW RECEIPTS DATA LEN: ", len(data))

        # BUILD SOURCES FOR PREVBLOCK NEIGHBORS
        neighbor_shard_IDs = prevblock.get_neighbors()
        for ID in neighbor_shard_IDs:
            if ID == shard_ID:
                continue

            new_sources[ID] = self.make_fork_choice(ID, genesis_blocks)
            assert new_sources[ID].shard_ID == ID, "expected consistent IDs"

            if ID == prevblock.parent_ID:
                assert new_sources[ID].is_in_chain(prevblock.sources[ID]), "expected monotonic consistent sources - error 1.1"
            elif ID in prevblock.child_IDs:
                assert new_sources[ID].is_in_chain(prevblock.sources[ID]), "expected monotonic consistent sources - error 1.2"
            else:
                assert False, "expected neighbor ID to be either parent or child ID"

            # check that fork choices have consistent sources
            # try to make sure that we don't make a block with a source that isn't in fork_choice's
            assert prevblock.shard_ID == shard_ID
            print("ID in new_child_IDs")
            print(ID in new_child_IDs)
            print("ID in new_parent_ID")
            print(ID == new_parent_ID)
            assert prevblock.is_in_chain(new_sources[ID].sources[shard_ID]), "expected  - error 1"

        receiving_opcode = False
        # --------------------------------------------------------------------#
        # BUILD RECEIVED LOG WITH:
        newly_received_messages = {}
        for ID in SHARD_IDS:
            newly_received_messages[ID] = []
        for ID in neighbor_shard_IDs:
            if ID == shard_ID:
                continue

            prev_received_log_length = len(prevblock.received_log[ID])
            while(len(newly_received_messages[ID]) < len(new_sources[ID].sent_log[shard_ID]) - prev_received_log_length):
                log_length = len(newly_received_messages[ID])
                new_message = new_sources[ID].sent_log[shard_ID][log_length + prev_received_log_length]
                if isinstance(new_message, SwitchMessage_BecomeAParent) or isinstance(new_message, SwitchMessage_ChangeParent):
                    break  #but only receive messages up to the first switch opcod

                newly_received_messages[ID].append(new_message)



        new_received_log = {}
        for ID in SHARD_IDS:
            new_received_log[ID] = prevblock.received_log[ID] + newly_received_messages[ID]

        # --------------------------------------------------------------------#

        # BUILD NEW SENT MESSAGES
        new_sent_messages = {}  # for now we're going to fill this with routed messages
        for ID in SHARD_IDS:
            new_sent_messages[ID] = []
        newly_received_payloads = {}  # destined for this shard's evm
        for ID in SHARD_IDS:
            newly_received_payloads[ID] = []

        # ROUTING
        for ID in neighbor_shard_IDs:
            for m in newly_received_messages[ID]:
                if m.target_shard_ID == shard_ID:
                    if isinstance(m, SwitchMessage_BecomeAParent):
                        continue
                    elif isinstance(m, SwitchMessage_ChangeParent):
                        continue
                    else:
                        newly_received_payloads[ID].append(m)
                else:
                    next_hop_ID = self.next_hop(new_routing_table, m.target_shard_ID)
                    if next_hop_ID is not None:
                        assert next_hop_ID in prevblock.child_IDs, "shard_ID: %s, destination: %s, next_hop: %s, children: %s" % (shard_ID, ID, next_hop_ID, prevblock.child_IDs)
                    else:
                        next_hop_ID = new_parent_ID
                    assert next_hop_ID is not None
                    new_sent_messages[next_hop_ID].append(Message(new_sources[next_hop_ID], m.TTL, m.target_shard_ID, m.payload))


        # --------------------------------------------------------------------#

        # EVM integration here

        # this is where we have this function that produces the new vm state and the new outgoing payloads
        # new_vm_state, new_outgoing_payloads = apply_to_state(prevblock.vm_state, data, newly_received_payloads)
        # 'data' is the new txn list

        new_vm_state, new_outgoing_payloads = apply_to_state(prevblock.vm_state, data, newly_received_payloads, genesis_blocks)


        # --------------------------------------------------------------------#

        # print("OUTGOING PAYLOAD LENGTH", len(new_outgoing_payloads.values()))
        # BUILD SENT LOG FROM NEW OUTGOING PAYLOADS
        # by this time new_sent_messages might already have some messages from rerouting above
        for ID in SHARD_IDS:
            if ID != shard_ID:
                for m in new_outgoing_payloads[ID]:
                    # print("HERE !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    first_hop_ID = self.next_hop(new_routing_table, ID)
                    if first_hop_ID is not None:
                        assert first_hop_ID in prevblock.child_IDs, "shard_ID: %s, target: %s, first_hop_ID: %s, parent: %s, children: %s, rtable: %s" % (shard_ID, ID, first_hop_ID, prevblock.parent_ID, prevblock.child_IDs, prevblock.routing_table)
                    else:
                        first_hop_ID = new_parent_ID
                    assert first_hop_ID is not None
                    new_sent_messages[first_hop_ID].append(Message(new_sources[first_hop_ID], TTL, ID, m.payload))


        SUM = 0
        for k in new_sent_messages.keys():
            SUM += len(new_sent_messages[k])
        # print("NUM NEW SENT: ", SUM)

        new_sent_log = {}
        for ID in SHARD_IDS:
            new_sent_log[ID] = prevblock.sent_log[ID] + new_sent_messages[ID]


        # MAKE BLOCK AND CHECK VALIDITY
        # Block(ID, prevblock=None, txn_log=[], sent_log=None, received_log=None, sources=None, parent_ID=None, child_IDs=None, routing_table=None, vm_state=genesis_state):

        ret = Block(shard_ID, prevblock, False, new_txn_log, new_sent_log, new_received_log, new_sources, new_parent_ID, new_child_IDs, new_routing_table, new_vm_state)

        assert not ret.switch_block

        check = ret.is_valid()
        if not check[0]:
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("shard_ID", prevblock.shard_ID)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("txn_log", new_txn_log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("self.sent_log", new_sent_log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("self.received_log", newly_received_messages)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("shard_ID", shard_ID)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("txn_log", new_txn_log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("self.sent_log", new_sent_log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("self.received_log", newly_received_messages)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("receiving_opcode: ", receiving_opcode)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
        assert check[0], "Invalid Block: " + check[1]

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
