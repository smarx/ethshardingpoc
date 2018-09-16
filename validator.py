from blocks import Block, Message
from blocks import ReceivedLog
from blocks import SentLog
from config import SHARD_IDS
from config import VALIDATOR_NAMES
from config import VALIDATOR_WEIGHTS
from config import TTL_CONSTANT
from evm_transition import apply_to_state

from fork_choice import sharded_fork_choice

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

    def fork_choice(self):
        # the blocks in the view are the genesis blocks and blocks from consensus messages
        blocks = self.get_blocks_from_consensus_messages()

        #  maybe this should be a parameter, but it's not so bad
        genesis_blocks = {}
        for m in self.consensus_messages:
            if m.sender == 0:
                genesis_blocks[m.estimate.shard_ID] = m.estimate

        return sharded_fork_choice(genesis_blocks, blocks, self.get_weighted_blocks())

    def make_block(self, shard_ID, mempools, drain_amount, TTL=TTL_CONSTANT):

        # RUN FORK CHOICE RULE
        fork_choice = self.fork_choice()
        # --------------------------------------------------------------------#


        # GET PREVBLOCK POINTER FROM FORK CHOICE
        prevblock = fork_choice[shard_ID]
        # --------------------------------------------------------------------#


        # EXTEND THE TRANSACTION LOG FROM THE MEMPOOL
        prev_txn_log = prevblock.txn_log
        new_txn_log = copy.copy(prev_txn_log)
        data = []
        num_prev_txs = len(prev_txn_log)
        for i in range(drain_amount):
            if num_prev_txs + i < len(mempools[shard_ID]):
                new_tx = mempools[shard_ID][num_prev_txs + i]
                new_txn_log.append(new_tx)
                data.append(new_tx)
        # --------------------------------------------------------------------#


        # BUILD RECEIVED LOG WITH:
        received_log = ReceivedLog()
        for ID in SHARD_IDS:
            if ID == shard_ID:
                continue

            # SOURCES = FORK CHOICE (except for self)
            received_log.sources[ID] = fork_choice[ID]
            # RECEIVED = SENT MESSAGES FROM FORK CHOICE
            received_log.log[ID] = fork_choice[ID].sent_log.log[shard_ID]
        # --------------------------------------------------------------------#


        # PREP NEWLY RECEIVED PMESSAGES IN A RECEIVEDLOG FOR EVM:
        newly_received_messages = {}
        for ID in SHARD_IDS:
            previous_received_log_size = len(prevblock.received_log.log[ID])
            current_received_log_size = len(received_log.log[ID])
            newly_received_messages[ID] = received_log.log[ID][previous_received_log_size:]

        newly_received_payloads = ReceivedLog()
        for ID in SHARD_IDS:
            for m in newly_received_messages[ID]:
                newly_received_payloads.add_received_message(ID, m)
        # --------------------------------------------------------------------#


        # KEY EVM INTEGRATION HERE

        # this is where we have this function that produces the new vm state and the new outgoing payloads
        # new_vm_state, new_outgoing_payloads = apply_to_state(prevblock.vm_state, data, newly_received_payloads)

        # NOTE: we aren't executing the received logs because the EVM throws errors on them
        # But at least we are receiving them in our blocks, with our fork choice rule
        newly_received_payloads = ReceivedLog()

        new_vm_state, new_outgoing_payloads = apply_to_state(prevblock.vm_state, data, newly_received_payloads)

        if shard_ID == 1:
            new_outgoing_payloads.log[0], new_outgoing_payloads.log[1] = new_outgoing_payloads.log[1], new_outgoing_payloads.log[0]
        # --------------------------------------------------------------------#


        # BUILD SENT LOG FROM NEW OUTGOING PAYLOADS
        new_sent_messages = SentLog()
        for ID in SHARD_IDS:
            if ID != shard_ID:
                for m in new_outgoing_payloads.log[ID]:
                    # if TTL == 0, then we'll make an invalid block
                    # one that sends a message that must be included by the base
                    # which already exists and therefore cannot include this message
                    if TTL > 0:
                        new_sent_messages.log[ID].append(Message(fork_choice[ID], TTL, m.message_payload))
                    else:
                        print("Warning: Not sending message because TTL == 0")

        sent_log = prevblock.sent_log.append_SentLog(new_sent_messages)
        # --------------------------------------------------------------------#




        return Block(shard_ID, prevblock, new_txn_log, sent_log, received_log, new_vm_state)

    def make_new_consensus_message(self, shard_ID, mempools, drain_amount, TTL=TTL_CONSTANT):

        assert shard_ID in SHARD_IDS, "expected shard ID"
        assert isinstance(drain_amount, int), "expected int"
        assert isinstance(TTL, int), "expected int"
        assert isinstance(mempools, dict), "expected dict"
        new_block = self.make_block(shard_ID, mempools, drain_amount, TTL)
        new_message = ConsensusMessage(new_block, self.name, copy.copy(self.consensus_messages))
        self.receive_consensus_message(new_message)
        return new_message
