from blocks import Block, Message
from blocks import ReceivedLog
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
        assert self.sender in VALIDATOR_NAMES

        if len(self.justification) == 0:
            self.height = 0

        for m in self.justification:
            assert isinstance(m, ConsensusMessage), "expected justification to contain consensus messages"
            self.height = 0
            if m.sender == self.sender:
                self.height += 1

class Validator:
    def __init__(self, name):
        assert name in VALIDATOR_NAMES, "expected a validator name"
        self.name = name
        self.consensus_messages = []
        self.I=0

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
        self.I += 1
        # first we execute the fork choice rule
        fork_choice = self.fork_choice()
        prevblock = fork_choice[shard_ID]

        prev_txn_log = prevblock.txn_log

        new_txn_log = copy.copy(prev_txn_log)
        data = []
        num_prev_txs = len(prev_txn_log)
        print("num_prev_txs",num_prev_txs)
        print("mempools[shard_ID] == prev_txn_log", mempools[shard_ID] == prev_txn_log)
        for i in range(drain_amount):
            if num_prev_txs + i < len(mempools[shard_ID]):
                new_tx = mempools[shard_ID][num_prev_txs + i]
                new_txn_log.append(new_tx)
                data.append(new_tx)

        # then put together the new received log
        received_log = ReceivedLog()
        for ID in SHARD_IDS:
            if ID == shard_ID:
                continue

            # we're just going to receive every send that we see from the fork choice (which filtered blocks who don't recieve things before their TTLs)
            received_log.sources[ID] = fork_choice[ID]
            received_log.log[ID] = fork_choice[ID].sent_log.log[shard_ID]

        # which has the following newly received messages:
        newly_received_messages = {}
        for ID in SHARD_IDS:

            previous_received_log_size = len(prevblock.received_log.log[ID])
            current_received_log_size = len(received_log.log[ID])
            assert current_received_log_size >= previous_received_log_size, "did not expect log size to shrink"

            if current_received_log_size > previous_received_log_size:
                print("RECEIVED LOG IS GROWING!!")


            newly_received_messages[ID] = received_log.log[ID][previous_received_log_size:]

        # which have the following newly received payloads:
        newly_received_payloads = {}
        for ID in SHARD_IDS:
            newly_received_payloads[ID] = [m.message_payload for m in newly_received_messages[ID]]

        '''
        KEY INTEGRATION HERE
        '''

        # this is where we have this function that produces the new vm state and the new outgoing payloads
        # new_vm_state, new_outgoing_payloads = INTEGRATE_HERE(prevblock.vm_state, data, newly_received_payloads)
        
        old_state = copy.copy(prevblock.vm_state)

        new_vm_state, new_outgoing_payloads = apply_to_state(prevblock.vm_state, data, newly_received_payloads)

        print("new_outgoing_payloads",new_outgoing_payloads)
        #if data != []:
        #    print("data", data)
        # print("--------------------------------------------------------------------")
        for ID in SHARD_IDS:
            if new_outgoing_payloads[ID] != []:
                print("NEW OUTGOING PAYLOADS[",ID,"]", new_outgoing_payloads[ID])

        # print("--------------------------------------------------------------------")
        # print("new_vm_state", new_vm_state)
        # print("old_state == new_vm_state", old_state == new_vm_state)
        if old_state != new_vm_state:
            print("data:", data)
        # print("\n\n\n\n")
        # print(self.I, "--------------------------------------------------------------------")

        # we now package the sent_log with new messages that deliver these payloads
        new_sent_messages = []
        shard_IDs = []
        for ID in SHARD_IDS:
            if ID != shard_ID:
                for payload in new_outgoing_payloads[ID]:
                    print("NEW OUTGOING PAYLOAD", payload)
                    new_sent_messages.append(Message(fork_choice[ID], TTL, payload))
                    shard_IDs.append(ID)

        sent_log = prevblock.sent_log.add_sent_messages(shard_IDs, new_sent_messages)
        return Block(shard_ID, prevblock, new_txn_log, sent_log, received_log, new_vm_state)

    def make_new_consensus_message(self, shard_ID, mempools, drain_amount, TTL=TTL_CONSTANT):
        new_block = self.make_block(shard_ID, mempools, drain_amount, TTL)
        new_message = ConsensusMessage(new_block, self.name, copy.copy(self.consensus_messages))
        self.receive_consensus_message(new_message)
        return new_message
