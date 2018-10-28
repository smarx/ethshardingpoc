from genesis_state import genesis_state

from config import SHARD_IDS
from config import VALIDITY_CHECKS_OFF
from config import VALIDITY_CHECKS_WARNING_OFF
from config import DEADBEEF
import copy
import random as rand


def format_msg(msg):
    return "base: %s, target_shard_ID: %s, payload_hash: %s, random_hash: %s" % (msg.base, msg.target_shard_ID, hash(msg.payload), msg.hash)


class MessagePayload:
    ''' has properties necessary to create tx on the new shard '''
    def __init__(self, fromAddress, toAddress, value, data):#, nonce, gasPrice, gasLimit):
        self.fromAddress = fromAddress
        self.toAddress = DEADBEEF  # Using "toAddress here leads to an error, apparently not an address"
        self.value = value
        self.data = data
        # the special transaction pusher address will have these values hard coded
        # self.nonce = nonce
        # self.gasPrice = gasPrice
        # self.gasLimit = gasLimit
        self.hash = rand.randint(1, 10000000)

    def __hash__(self):
        return self.hash

    def __eq__(self, message):
        return self.hash == message.hash

class Message(object):
    def __init__(self, base, TTL, target_shard_ID, payload):
        super(Message, self).__init__()

        self.hash = rand.randint(1, 10000000)

        assert isinstance(base, Block)
        assert base.is_valid(), "expected block to be valid"
        self.base = base
        assert isinstance(TTL, int), "expected integer time-to-live"
        self.TTL = TTL
        assert target_shard_ID in SHARD_IDS, "expected shard ID"
        self.target_shard_ID = target_shard_ID
        assert isinstance(payload, MessagePayload) or payload is None, "expected messagepayload format"
        self.payload = payload

    def __hash__(self):
        return self.hash

    def __eq__(self, message):
        return self.hash == message.hash


class SwitchMessage_BecomeAParent(Message):
    def __init__(self, base, TTL, target_shard_ID, new_child_ID, new_child_source):
        super(SwitchMessage_BecomeAParent, self).__init__(base, TTL, target_shard_ID, None)
        self.new_child_ID = new_child_ID
        self.new_child_source = new_child_source
        self.hash = rand.randint(1, 1000000)

    def __hash__(self):
        return self.hash

    def __eq__(self, message):
        return self.hash == message.hash


class SwitchMessage_ChangeParent(Message):
    def __init__(self, base, TTL, target_shard_ID, new_parent_ID, new_parent_source):
        super(SwitchMessage_ChangeParent, self).__init__(base, TTL, target_shard_ID, None)
        self.new_parent_ID = new_parent_ID
        self.new_parent_source = new_parent_source
        self.hash = rand.randint(1, 1000000)       

    def __hash__(self):
        return self.hash

    def __eq__(self, message):
        return self.hash == message.hash

class Block:
    def __init__(self, ID, prevblock=None, switch_block=False, txn_log=[], sent_log={}, received_log={}, sources={}, parent_ID=None, child_IDs=None, routing_table=None, vm_state=genesis_state):

        if sent_log == {}:
            for i in SHARD_IDS:
                sent_log[i] = []

        if received_log == {}:
            for i in SHARD_IDS:
                received_log[i] = []

        assert ID in SHARD_IDS, "expected shard ID"
        self.shard_ID = ID
        self.prevblock = prevblock
        self.switch_block = switch_block
        self.txn_log = txn_log
        self.sent_log = sent_log
        for i in SHARD_IDS:
            if i not in self.sent_log.keys():
                sent_log[i] = []
        self.received_log = received_log
        for i in SHARD_IDS:
            if i not in self.received_log.keys():
                received_log[i] = []
        self.sources = sources
        self.vm_state = vm_state
        self.parent_ID = parent_ID
        self.child_IDs = child_IDs
        self.routing_table = routing_table
        self.hash = rand.randint(1, 10000000)

        if prevblock is None:  # genesis block
            self.height = 0
        else:
            self.height = self.prevblock.height + 1



    def __str__(self):
        return "Block(%d): shard_ID:%d height:%d" % (self.hash, self.shard_ID, self.height)

    def __eq__(self, block):
        return self.hash == block.hash

    def __hash__(self):
        return self.hash

    def is_changing_neighbors(self):
        # Genesis block isn't changing neighbors
        if self.prevblock is None:
            return False

        # if the parent shard changes then it's changing neighbors
        if self.parent_ID != self.prevblock.parent_ID:
            return True

        # or if the child shards change then it's changing neighbors
        if self.child_IDs != self.prevblock.child_IDs:
            return True

        # otherwise it's not changing neighbors
        return False

    def is_in_chain(self, block):
        assert isinstance(block, Block), "expected block"
        #assert block.is_valid(), "expected block to be valid"
        if self.shard_ID != block.shard_ID:
            return False

        if self == block:
            return True

        if block.height >= self.height:
            return False

        if self.prevblock is None:
            return False

        return self.prevblock.is_in_chain(block)

    def agrees(self, block):
        assert isinstance(block, Block), "expected block"
        assert self.shard_ID == block.shard_ID, "expected to check agreement between blocks on same shard"
        return self.is_in_chain(block) or block.is_in_chain(self)

    def get_neighbors(self):
        neighbors = []
        if self.parent_ID is not None:
            neighbors.append(self.parent_ID)
        for c in self.child_IDs:
            neighbors.append(c)
        return neighbors

    def first_block_with_message_in_sent_log(self, ID, message):
        assert message in self.sent_log[ID]
        if self.prevblock is None:
            return self
        if message not in self.prevblock.sent_log[ID]:
            return self
        else:
            return self.prevblock.first_block_with_message_in_sent_log(ID, message)

    def next_hop(self, target_shard_ID):
        assert self.shard_ID != target_shard_ID
        if target_shard_ID in self.routing_table:
            return self.routing_table[target_shard_ID]
        else:
            return self.parent_ID

    def newly_sent(self):
        new_sent = dict.fromkeys(SHARD_IDS)
        for ID in self.get_neighbors():
            new = []
            num_sent = len(self.sent_log[ID])
            if self.prevblock is not None:
                prev_num_sent = len(self.prevblock.sent_log[ID])
            else:
                prev_num_sent = 0
            num_new_sent = num_sent - prev_num_sent
            assert num_new_sent >= 0, "expected growing sent log"
            for i in range(num_new_sent):
                new.append(self.sent_log[ID][prev_num_sent + i])
            new_sent[ID] = new

        return new_sent

    def newly_received(self):
        new_received = {}
        for ID in self.get_neighbors():
            new_received[ID] = []
            num_received = len(self.received_log[ID])
            if self.prevblock is not None:
                prev_num_received = len(self.prevblock.received_log[ID])
            else:
                prev_num_received = 0
            num_new_received = num_received - prev_num_received
            assert num_new_received >= 0, "expected growing received log, shard_ID: %s, ID: %s, was: %s, now: %s" % (self.shard_ID, ID, prev_num_received, num_received)
            for i in range(num_new_received):
                new_received[ID].append(self.received_log[ID][prev_num_received + i])

        return new_received

    def compute_routing_table(self):
        self.routing_table = {self.shard_ID: self.shard_ID}
        q = [(x, x, self.sources[x]) for x in self.child_IDs]
        for target, hop, source_block in q:
            self.routing_table[target] = hop
            for child in source_block.child_IDs:
                q.append((child, hop, source_block.sources[child]))

    # Goal: make this constant time
    def is_valid(self):

        # THE VALIDITY SWITCH
        if VALIDITY_CHECKS_OFF:
            if not VALIDITY_CHECKS_WARNING_OFF:
                print("Warning: Validity checks off")
            return True, "VALIDITY_CHECKS_OFF"

        # CHECKING INDIVIDUAL TYPES OF INDIVIDUAL DATA FIELDS
        if self.shard_ID not in SHARD_IDS:
            return False, "expected a shard ID"
        if self.prevblock is not None:
            if not isinstance(self.prevblock, Block):
                return False, "expected prevblock to be a block"
        if not isinstance(self.sent_log, dict):
            return False, "expected sent log"
        if not isinstance(self.received_log, dict):
            return False, "expected received_log"
        # if not isinstance(self.VM_state, EVM_State):
        #    return False, "expected an EVM State"

        #leaving out the genesis blocks for now..
        if self.prevblock is None:
            return True, "Genesis block taken as valid"
        # --------------------------------------------------------------------#


        # we're going to need these over and over again:
        new_sent_messages = self.newly_sent()
        new_received_messages = self.newly_received()

        saw_switch_messages = False
        for msg in new_sent_messages.items():
            if isinstance(msg, (SwitchMessage_BecomeAParent, SwitchMessage_ChangeParent)):
                # TODO: validate the correctness of the switch
                saw_switch_messages = True

        if not saw_switch_messages:
            for key, value in list(new_sent_messages.items()) + list(new_received_messages.items()):
                if value is not None:
                    if len(value) and key not in [self.parent_ID, self.shard_ID] + self.child_IDs:
                        return False, "Block on shard %s has sent or received message to shard %s which is not its neighbor or itself (%s messages)" % (self.shard_ID, key, new_sent_messages)

        # SHARD ID VALIDITY CONDITIONS

        # check that the prev block is on the same shard as this block
        if self.shard_ID != self.prevblock.shard_ID:
            return False, "prevblock should be on same shard as this block"

        for ID in self.get_neighbors():

            # bases for messages sent to shard i are on shard i
            for message in new_sent_messages[ID]:
                if message.base.shard_ID != ID:
                    return False, "message sent to shard i has base on shard j != i"

            # bases for received messages are on this shard
            for message in new_received_messages[ID]:
                if message.base.shard_ID != self.shard_ID:
                    return False, "received message with base on different shard"

            # sources of messages received from shard i are on shard i
            if self.sources[ID] is not None:
                if self.sources[ID].shard_ID != ID:
                    return False, "source for shard i on shard j != i"
        # --------------------------------------------------------------------#


        # MONOTONICITY/AGREEMENT CONDITIONS
        for ID in self.get_neighbors():

            # sources are montonic
            if self.prevblock.sources[ID] is not None and ID in [self.parent_ID] + self.child_IDs:
                if not self.sources[ID].is_in_chain(self.prevblock.sources[ID]):
                    return False, "expected sources to be monotonic, shard_ID: %s, source shard id: %s, old height: %s, new height: %s, %s, %s" % (self.shard_ID, ID, self.prevblock.sources[ID].height, self.sources[ID].height, self.sources[ID], self.prevblock.sources[ID])


            # previous tx list is a prefix of this txn list
            prev_num_txs = len(self.prevblock.txn_log)
            new_num_txs = len(self.txn_log)
            if new_num_txs < prev_num_txs:
                return False, "expected current txn log to be an extension of the previous -- error 1"
            for i in range(prev_num_txs):
                if self.txn_log == []:
                    return False, "expected current txn log to be an extension of the previous -- error 2, shard_id: %s, old_txn_num: %s, new_txn_num: %s" % (self.shard_ID, prev_num_txs, len(self.txn_log))
                if self.prevblock.txn_log[i] != self.txn_log[i]:
                    return False, "expected current txn log to be an extension of the previous -- error 3"

            # previous sent log is a prefix of current sent log
            prev_num_sent = len(self.prevblock.sent_log[ID])
            new_num_sent = len(self.sent_log[ID])
            if new_num_sent < prev_num_sent:
                return False, "expected current sent log to be an extension of the previous -- error 1"
            for i in range(prev_num_sent):
                if self.prevblock.sent_log[ID][i] != self.sent_log[ID][i]:
                    return False, "expected current sent log to be an extension of the previous -- error 2"

            # previous received log is a prefix of current received log
            prev_num_received = len(self.prevblock.received_log[ID])
            new_num_received = len(self.received_log[ID])
            if new_num_received < prev_num_received:
                return False,  "expected current received log to be an extension of the previous -- error 1"
            for i in range(prev_num_received):
                if self.prevblock.received_log[ID][i] != self.received_log[ID][i]:
                    return False, "expected current received log to be an extension of the previous -- error 2, shard_ID: %s, log shard ID: %s, old length: %s, new_length: %s, items: %s <> %s, pos: %s" % (self.shard_ID, ID, len(self.prevblock.received_log[ID]), len(self.received_log[ID]), format_msg(self.prevblock.received_log
                        [ID][i]), format_msg(self.received_log[ID][i]), i)

            # bases of sent messages are monotonic
            if len(self.prevblock.sent_log[ID]) > 0:
                last_old_sent_message = self.prevblock.sent_log[ID][-1]
                first_time = True
                for message in new_sent_messages[ID]:
                    if first_time:
                        m1 = last_old_sent_message
                        m2 = message
                        first_time = False
                    if not first_time:
                        m1 = m2
                        m2 = message

                    if not m2.base.is_in_chain(m1.base):
                        return False, "expected bases to be monotonic -- error 1"

            # bases of received messages are monotonic
            if len(self.prevblock.received_log[ID]) > 0:
                last_old_received_message = self.prevblock.received_log[ID][-1]
                first_time = True
                for message in new_received_messages[ID]:
                    if first_time:
                        m1 = last_old_received_message
                        m2 = message
                        first_time = False
                    if not first_time:
                        m1 = m2
                        m2 = message


                    if not m2.base.is_in_chain(m1.base):
                        return False, "expected bases to be monotonic -- error 2"

            if self.prevblock.sources[ID] is not None and ID in [self.parent_ID] + self.child_IDs:
                # sources after bases
                # ... easier to check than agreement between bases and sources,
                # ... also easy for a block producer to enforce
                source = self.sources[ID]
                if len(self.prevblock.sent_log[ID]) > 0:
                    base = last_old_sent_message.base  # most recent base from prev block
                    if not source.agrees(base):  # source is after ^^
                        return False, "expected bases to be in the chain of sources -- error 1"

                if len(new_sent_messages[ID]) > 0:
                    base = new_sent_messages[ID][-1].base  # most recent base from this block
                    if not source.agrees(base):  # source is also after ^^
                        return False, "expected bases to be in the chain of sources -- error 2 (sid: %s, id: %s)" % (self.shard_ID, ID)


        # --------------------------------------------------------------------#
        # SOURCE SYNCHRONICITY CONDITIONS
        for ID in [self.parent_ID] + self.child_IDs:
            if ID is None:
                continue

            if self.sources[ID] is not None:

                source = self.sources[ID]

                # check that the received messages are sent by the source
                for i in range(len(self.received_log[ID])):  # warning: inefficient
                    if self.received_log[ID][i] != source.sent_log[self.shard_ID][i]:
                        return False, "expected the received messages to be sent by source"

                # their sent messages are received by the TTL as seen from the sources
                for m in source.sent_log[self.shard_ID]:  # inefficient
                    if m in self.received_log[ID]:
                        continue
                    # a message incoming (but not yet received) to this shard is expired if...
                    if m.base.height + m.TTL <= self.height:
                        return False, "expected all expired messages in source to be recieved"

                # our sent messages are received by the TTL as seen from our sources
                for m in self.sent_log[ID]:  # inefficient
                    if m in source.received_log[self.shard_ID]:
                        continue
                    # a message outgoing from this shard that hasn't been received is expired if...
                    # print(m.base.height + m.TTL, source.height)
                    if m.base.height + m.TTL <= source.height:
                        return False, "expected all expired sent messages to be received by source"

        # --------------------------------------------------------------------#
        # BASE SYNCHRONICITY CONDITIONS
        for ID in self.get_neighbors():
            # newly received messages are received by the TTL of the base
            for message in new_received_messages[ID]:
                if not self.is_in_chain(message.base):
                    return False, "expected only to receive messages with base in chain, my shard id: %s, their shard id: %s" % (self.shard_ID, ID)
                # Message on received this block are expired if...
                if message.base.height + message.TTL < self.height:
                    return False, "message not received within TTL of its base"

            # questionable validity condition
            # our sent messages are received by the TTL as seen from our bases
            for m1 in self.sent_log[ID]:  # super inefficient
                for m2 in self.sent_log[ID]:
                    if m1 in m2.base.received_log[self.shard_ID]:
                        continue
                    # m1 from this shard that hasn't been received by m2.base, and is expired if...
                    if m1.base.height + m1.TTL <= m2.base.height:
                            return False, "expected sent messages to be received by the TTL"

        # --------------------------------------------------------------------#
        # ALL RECEIVED MESSAGES THAT DO NOT TARGET THIS SHARD MUST BE REROUTED
        payloads_to_reroute = []
        payloads = []
        for ID in self.get_neighbors():
            for message in new_received_messages[ID]:
                if message.target_shard_ID != self.shard_ID:
                    assert message.payload not in payloads
                    payloads.append(message.payload)
                    payloads_to_reroute.append((message.target_shard_ID, message.TTL, message.payload))

        for ID in self.get_neighbors():
            for message in new_sent_messages[ID]:
                key = (message.target_shard_ID, message.TTL, message.payload)
                if key in payloads_to_reroute:
                    payloads_to_reroute.remove(key)

        if len(payloads_to_reroute):
            return False, "%s messages were not rerouted" % len(payloads_to_reroute)

        # --------------------------------------------------------------------#

        # made it!
        return True, "Valid block"


'''
as a general thought, our goal is to make "the world" seem valid from the point of view of every block

"valid" in our case means:

logs hold messages with bases and sources from the expected shards
logs grow monotonically
sources and bases are monotonic
sources and bases agree
receives happen from sources

And also these more difficult ones:

local receives happen before the TTL (is the received message's base not more than TTL prevblocks away)
sents are received before the TTL (as seen from bases)

We need to look at our receives and see them be received by the TTL

And look at the bases and sources and:

see our sent messages be received by the TTL

see their sent messages be received by the TTL
'''
