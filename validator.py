from blocks import Block
from blocks import ReceivedLog
from config import SHARD_IDS
from config import VALIDATOR_NAMES
from config import VALIDATOR_WEIGHTS
from config import TTL_CONSTANT

from fork_choice import sharded_fork_choice

class ConsensusMessage:
    def __init__(self, block, name, justification):
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
    def __init__(self, name, starting_blocks):
        assert name in VALIDATOR_NAMES, "expected a validator name"
        self.name = name
        self.consensus_messages = []
        assert isinstance(starting_blocks, dict), "expected dict"
        for ID in SHARD_IDS:
            assert ID in starting_blocks.keys(), "expected to have starting blocks for all shard IDs"
        for b in starting_blocks.values():
            assert isinstance(b, Block), "expected starting blocks to be blocks"

        self.starting_blocks = starting_blocks


    def receive_consensus_messages(self, messages):
        for m in messages:
            self.consensus_messages.append(m)

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
        for b in self.starting_blocks.values():
            blocks.append(b)

        for b in blocks:
            print "b", b

        return sharded_fork_choice(self.starting_blocks, blocks, self.get_weighted_blocks())


    def make_block(self, shard_ID, data, TTL=TTL_CONSTANT):
        # first we execute the fork choice rule
        fork_choice = self.fork_choice()
        prevblock = fork_choice[shard_ID]

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
            if ID == shard_ID:
                continue

            previous_received_log_size = len(prevblock.received_log.log[ID])
            current_received_log_size = len(received_log.log[ID])
            assert current_received_log_size >= previous_received_log_size, "did not expect log size to shrink"

            newly_received_messages[ID] = []
            for i in xrange(current_received_log_size - previous_received_log_size):
                newly_received_messages[ID].append(received_log.log[ID][previous_received_log_size + i])

        # which have the following newly received payloads:
        newly_received_payloads = {}
        for ID in SHARD_IDS:
            if ID == shard_ID:
                continue
            newly_received_payloads[ID] = []
            for m in newly_received_messages[ID]:
                newly_received_payloads[ID].append(m.message_payload)

        '''
        KEY INTEGRATION HERE
        '''

        # this is where we have this function that produces the new vm state and the new outgoing payloads
        # new_vm_state, new_outgoing_payloads = INTEGRATE_HERE(prevblock.vm_state, data, newly_received_payloads)
        # need new_outgoing_payloads is a dict of shard id to new payloads

        new_vm_state = prevblock.vm_state
        new_outgoing_payloads = {}
        for ID in SHARD_IDS:
            new_outgoing_payloads[ID] = []

        # we now package the sent_log with new messages that deliver these payloads
        new_sent_messages = []
        shard_IDs = []
        for ID in SHARD_IDS:
            for payload in new_outgoing_payloads[ID]:
                new_sent_messages.append(Message(fork_choice[ID], TTL, payload))
                shard_IDs.append(ID)
        
        sent_log = prevblock.sent_log.add_sent_messages(shard_IDs, new_sent_messages)


        return Block(shard_ID, prevblock, data, sent_log, received_log, new_vm_state)

    def make_new_consensus_message(self, shard_ID, data, TTL=TTL_CONSTANT):
        new_block = self.make_block(shard_ID, data, TTL)
        new_message = ConsensusMessage(new_block, self.name, self.consensus_messages)
        self.consensus_messages.append(new_message)
        return new_message
