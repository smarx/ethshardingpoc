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


class SwitchMessage_BecomeAParent(Message):
    def __init__(self, base, TTL, target_shard_ID, new_child_ID, new_child_source):
        super(SwitchMessage_BecomeAParent, self).__init__(base, TTL, target_shard_ID, None)
        self.new_child_ID = new_child_ID
        self.new_child_source = new_child_source


class SwitchMessage_ChangeParent(Message):
    def __init__(self, base, TTL, target_shard_ID, new_parent_ID, new_parent_source):
        super(SwitchMessage_ChangeParent, self).__init__(base, TTL, target_shard_ID, None)
        self.new_parent_ID = new_parent_ID
        self.new_parent_source = new_parent_source


class MessagesLog:
    def __init__(self):
        self.log = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            self.log[ID] = []

    def add_message(self, shard_ID, message):
        assert shard_ID in SHARD_IDS, "expected shard ID"
        assert isinstance(message, Message), "expected message"
        self.log[shard_ID].append(message)

    def add_messages(self, shard_IDs, messages):
        for i in range(len(shard_IDs)):
            self.add_message(shard_IDs[i], messages[i])
        return self

    def append_MessagesLog(self, log):
        assert isinstance(log, MessagesLog), "expected messages log"

        new_log = MessagesLog()

        for ID in SHARD_IDS:
            for l in self.log[ID]:
                new_log.log[ID].append(l)

        for ID in SHARD_IDS:
            for l in log.log[ID]:
                new_log.log[ID].append(l)

        return new_log



class Block:
    def __init__(self, ID, prevblock=None, txn_log=[], sent_log=None, received_log=None, sources=None, vm_state=genesis_state):
        if sent_log is None:
            sent_log = MessagesLog()
        if received_log is None:
            received_log = MessagesLog()
        assert sources is not None

        assert ID in SHARD_IDS, "expected shard ID"
        self.shard_ID = ID
        self.prevblock = prevblock
        self.txn_log = txn_log
        self.sent_log = sent_log
        self.received_log = received_log
        self.sources = sources
        self.vm_state = vm_state
        self.hash = rand.randint(1, 10000000)

        if prevblock is None:
            self.height = 0
            # this is a genesis block, the topology will be set immidiately after the creation
        else:
            self.height = self.prevblock.height + 1
            self.parent_ID = self.prevblock.parent_ID
            self.child_IDs = self.prevblock.child_IDs
            self.routing_table = copy.copy(self.prevblock.routing_table)

        check = self.is_valid()
        if not check[0]:
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("shard_ID", self.prevblock.shard_ID)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("txn_log", self.prevblock.txn_log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("self.sent_log.log", self.prevblock.sent_log.log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("self.received_log.log", self.prevblock.received_log.log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("shard_ID", self.shard_ID)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("txn_log", self.txn_log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("self.sent_log.log", self.sent_log.log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
            print("self.received_log.log", self.received_log.log)
            print("---------------------------------------------------------")
            print("---------------------------------------------------------")
        assert check[0], check[1]

    def __str__(self):
        return "Block(%d): shard_ID:%d height:%d" % (self.hash, self.shard_ID, self.height)

    def __eq__(self, block):
        return self.hash == block.hash

    def __hash__(self):
        return self.hash

    def is_in_chain(self, block):
        assert isinstance(block, Block), "expected block"
        #assert block.is_valid(), "expected block to be valid"
        if self == block:
            return True

        if self.prevblock is None:
            return False

        return self.prevblock.is_in_chain(block)

    def newly_sent(self):
        new_sent = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            new = []
            num_sent = len(self.sent_log.log[ID])
            if self.prevblock is not None:
                prev_num_sent = len(self.prevblock.sent_log.log[ID])
            else:
                prev_num_sent = 0
            num_new_sent = num_sent - prev_num_sent
            assert num_new_sent >= 0, "expected growing sent log"
            for i in range(num_new_sent):
                new.append(self.sent_log.log[ID][prev_num_sent + i])
            new_sent[ID] = new

        return new_sent

    def newly_received(self):
        new_received = {}
        for ID in SHARD_IDS:
            new = []
            num_received = len(self.received_log.log[ID])
            if self.prevblock is not None:
                prev_num_received = len(self.prevblock.received_log.log[ID])
            else:
                prev_num_received = 0
            num_new_received = num_received - prev_num_received
            assert num_new_received >= 0, "expected growing received log, shard_ID: %s, ID: %s, was: %s, now: %s" % (self.shard_ID, ID, prev_num_received, num_received)
            for i in range(num_new_received):
                new.append(self.received_log.log[ID][prev_num_received + i])
            new_received[ID] = new

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
        if not isinstance(self.sent_log, MessagesLog):
            return False, "expected sent log"
        if not isinstance(self.received_log, MessagesLog):
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
                if len(value) and key not in [self.parent_ID, self.shard_ID] + self.child_IDs:
                    return False, "Block on shard %s has sent or received message to shard %s which is not its neighbor or itself (%s messages)" % (self.shard_ID, key, new_sent_messages)

        # SHARD ID VALIDITY CONDITIONS

        # check that the prev block is on the same shard as this block
        if self.shard_ID != self.prevblock.shard_ID:
            return False, "prevblock should be on same shard as this block"

        for ID in SHARD_IDS:

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
        for ID in SHARD_IDS:

            # sources are montonic
<<<<<<< Updated upstream
            if self.prevblock.sources[ID] is not None:
                if not self.sources[ID].is_in_chain(self.prevblock.sources[ID]):
                    return False, "expected sources to be monotonic, shard_ID: %s, source shard id: %s, old height: %s, new height: %s" % (self.shard_ID, ID, self.prevblock.sources[ID].height, self.sources[ID].height)

=======
            if self.sources[ID] is not None:
                if self.prevblock.sources[ID] is not None:
                    if not self.sources[ID].is_in_chain(self.prevblock.sources[ID]):
                        return False, "expected sources to be monotonic"
>>>>>>> Stashed changes

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
            prev_num_sent = len(self.prevblock.sent_log.log[ID])
            new_num_sent = len(self.sent_log.log[ID])
            if new_num_sent < prev_num_sent:
                return False, "expected current sent log to be an extension of the previous -- error 1"
            for i in range(prev_num_sent):
                if self.prevblock.sent_log.log[ID][i] != self.sent_log.log[ID][i]:
                    return False, "expected current sent log to be an extension of the previous -- error 2"

            # previous received log is a prefix of current received log
            prev_num_received = len(self.prevblock.received_log.log[ID])
            new_num_received = len(self.received_log.log[ID])
            if new_num_received < prev_num_received:
                return False,  "expected current received log to be an extension of the previous -- error 1"
            for i in range(prev_num_received):
                if self.prevblock.received_log.log[ID][i] != self.received_log.log[ID][i]:
                    return False, "expected current received log to be an extension of the previous -- error 2, shard_ID: %s, log shard ID: %s, old length: %s, new_length: %s, items: %s <> %s, pos: %s" % (self.shard_ID, ID, len(self.prevblock.received_log.log[ID]), len(self.received_log.log[ID]), format_msg(self.prevblock.received_log.log[ID][i]), format_msg(self.received_log.log[ID][i]), i)

            # bases of sent messages are monotonic
            if len(self.prevblock.sent_log.log[ID]) > 0:
                last_old_sent_message = self.prevblock.sent_log.log[ID][-1]
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
            if len(self.prevblock.received_log.log[ID]) > 0:
                last_old_received_message = self.prevblock.received_log.log[ID][-1]
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

<<<<<<< Updated upstream
            # sources after bases
            # ... easier to check than agreement between bases and sources,
            # ... also easy for a block producer to enforce
            source = self.sources[ID]
            if len(self.prevblock.sent_log.log[ID]) > 0:
                base = last_old_sent_message.base  # most recent base from prev block
                if not source.is_in_chain(base):  # source is after ^^
                    return False, "expected bases to be in the chaing of sources -- error 1"

            if len(new_sent_messages[ID]) > 0:
                base = new_sent_messages[ID][-1].base  # most recent base from this block
                if not source.is_in_chain(base): # source is also after ^^
                    return False, "expected bases to be in the chain of sources -- error 2 (sid: %s, id: %s)" % (self.shard_ID, ID)
=======


            # sources after bases
            # ... easier to check than agreement between bases and sources,
            # ... also easy for a block producer to enforce
            source = self.sources[ID]
            if len(self.prevblock.sent_log.log[ID]) > 0:
                base = last_old_sent_message.base  # most recent base from prev block
                if not source.is_in_chain(base):  # source is after ^^
                    return False, "expected bases to be in the chaing of sources -- error 1"

            if len(new_sent_messages[ID]) > 0:
                base = new_sent_messages[ID][-1].base  # most recent base from this block
                if not source.is_in_chain(base): # source is also after ^^
                    return False, "expected bases to be in the chain of sources -- error 2"
>>>>>>> Stashed changes

        # --------------------------------------------------------------------#


        # SOURCE SYNCHRONICITY CONDITIONS
        for ID in SHARD_IDS:

            if self.sources[ID] is not None:

                source = self.sources[ID]

                # check that the received messages are sent by the source
                for i in range(len(self.received_log.log[ID])):  # warning: inefficient
                    if self.received_log.log[ID][i] != source.sent_log.log[self.shard_ID][i]:
                        return False, "expected the received messages were sent by source"

                # their sent messages are received by the TTL as seen from the sources
                for m in source.sent_log.log[self.shard_ID]:  # inefficient
                    if m in self.received_log.log[ID]:
                        continue
                    # a message incoming (but not yet received) to this shard is expired if...
                    if m.base.height + m.TTL <= self.height:
                        return False, "expected all expired messages in source to be recieved"

                # our sent messages are received by the TTL as seen from our sources
                for m in self.sent_log.log[ID]:  # inefficient
                    if m in source.received_log.log[self.shard_ID]:
                        continue
                    # a message outgoing from this shard that hasn't been received is expired if...
                    if m.base.height + m.TTL <= source.height:
                        return False, "expected all expired sent messages to be received by source"
        # --------------------------------------------------------------------#


        # BASE SYNCHRONICITY CONDITIONS
        for ID in SHARD_IDS:
            # newly received messages are received by the TTL of the base
            for message in new_received_messages[ID]:
                if not self.is_in_chain(message.base):
                    return False, "expected only to receive messages with base in chain, my shard id: %s, their shard id: %s" % (self.shard_ID, ID)
                # Message on received this block are expired if...
                if message.base.height + message.TTL < self.height:
                    return False, "message not received within TTL of its base"

            # our sent messages are received by the TTL as seen from our bases
            for m1 in self.sent_log.log[ID]:  # super inefficient
                for m2 in self.sent_log.log[ID]:
                    if m1 in m2.base.received_log.log[self.shard_ID]:
                        continue
                    # m1 from this shard that hasn't been received by m2.base, and is expired if...
                    if m1.base.height + m1.TTL <= m2.base.height:
                            return False, "expected sent messages to be received by the TTL"
        # --------------------------------------------------------------------#


        # ALL RECEIVED MESSASGES THAT DO NOT TARGET THIS SHARD MUST BE REROUTED
        payloads_to_reroute = []
        for ID in SHARD_IDS:
            for message in new_received_messages[ID]:
                if message.target_shard_ID != self.shard_ID:
                    assert message.payload not in payloads_to_reroute
                    payloads_to_reroute.append((message.target_shard_ID, message.TTL, message.payload))

        for ID in SHARD_IDS:
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
