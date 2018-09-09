#from genesis_state import genesis_state

from config import SHARD_IDS

# [DONE] Maurelian: please give message data format (for txs)
class MessagePayload:
    ''' has properties necessary to create tx on the new shard '''
    def __init__(self, fromAddress, toAddress, value, data):
        self.fromAddress = fromAddress
        self.toAddress = toAddress
        self.value = value
        self.data = data
        # the special transaction pusher address will have these values hard coded 
        # self.nonce = nonce 
        # self.gasPrice = gasPrice
        # self.gasLimit = gasLimit


class Message:
    def __init__(self, base, TTL, message_payload ):
        self.base = base
        self.TTL = TTL
        self.message_payload = message_payload 


class SentLog:
    def __init__(self):
        self.log = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            self.log[ID] = []

    def add_sent_message(self, shard_ID, message):
        self.log[shard_ID].append(message)

    def add_sent_messages(self, shard_IDs, messages):
        for i in xrange(len(shard_IDs)):
            self.add_sent_message(shard_IDs[i], messages[i])
        return self


class ReceivedLog:
    def __init__(self):
        self.sources = { ID: None for ID in SHARD_IDS }
        self.log = { ID: [] for ID in SHARD_IDS }

    def add_received_message(self, shard_id, message):
        self.log[shard_id].append(message)

    # also adds sources, a map from SHARD IDS to blocks
    def add_received_messages(self, sources, shard_ids, messages):
        self.sources = sources
        for i in range(len(shard_ids)):
            self.add_sent_message(shard_IDs[i], messages[i])
        return self


# Maurelian: please replace VM_state = None as default for genesis blocks to some initial VM state (balances)
    #  hmmmm... is that necessary?  I can't compile bc I don't have web3, so not for now!
class Block:
    def __init__(self, ID, prevblock=None, data=None, sent_log=None, received_log=None, vm_state=None):  # genesis_state):
        if sent_log is None:
            sent_log = SentLog()
        if received_log is None:
            received_log = ReceivedLog()

        self.shard_ID = ID
        self.prevblock = prevblock
        self.data = data
        self.sent_log = sent_log
        self.received_log = received_log
        self.vm_state = vm_state

        if prevblock is None:
            self.height = 0
        else:
            self.height = self.prevblock.height + 1

        check = self.is_valid()
        assert check[0], check[1]

    def is_in_chain(self, block):
        assert isinstance(block, Block), "expected block"
        if self == block:
            return True

        if self.prevblock is None:
            return False

        return self.prevblock.is_in_chain(block)

    def in_prev_n(self, block, n):
        assert isinstance(n, int), "expected integer"
        assert n >= -1, "expected n at least -1"
        assert isinstance(block, Block)

        if n == -1:
            return False

        if self == block:
            return True

        if self.prevblock is None:
            return False

        return self.prevblock.in_prev_n(block, n-1)

    def newly_sent(self):
        new_sent = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            new = []
            num_sent = len(self.sent_log.log[ID])
            prev_num_sent = len(self.prevblock.sent_log.log[ID])
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
            prev_num_received = len(self.prevblock.received_log.log[ID])
            num_new_received = num_received - prev_num_received
            assert num_new_received >= 0, "expected growing received log"
            for i in range(num_new_received):
                new.append(self.received_log.log[ID][prev_num_received + i])
            new_received[ID] = new

        return new_received

    def is_valid(self):

        '''
        Type checking each value of the block tuple:
        '''
        if self.shard_ID not in SHARD_IDS:
            return False, "expected a shard ID"
        if self.prevblock is not None:
            if not isinstance(self.prevblock, Block):
                return False, "expected prevblock to be a block"
        # if not isinstance(self.data, BlockData):
        #    return False, "expected block data"
        if not isinstance(self.sent_log, SentLog):
            return False, "expected sent log"
        if not isinstance(self.received_log, ReceivedLog):
            return False, "expected received_log"
        # if not isinstance(self.VM_state, EVM_State):
        #    return False, "expected an EVM State"

        #leaving out the genesis blocks for now..
        if self.prevblock is None:
            return True, "Genesis block taken as valid"

        '''
        Type check consistency conditions between the values of the block
        '''


        # check that the prev block is on the same shard as this block
        if self.shard_ID != self.prevblock.shard_ID:
            return False, "prevblock should be on same shard as this block"

        new_sent_messages = self.newly_sent()
        new_received_messages = self.newly_received()

        for ID in SHARD_IDS:

            '''
            Validity conditions for shard IDs
            '''

            # bases for messages sent to shard i are on shard i
            for message in new_sent_messages[ID]:
                if message.base.shard_ID != ID:
                    return False, "message sent to shard i has base on shard j != i"

            # bases for received messages are on this shard
            for message in new_received_messages[ID]:
                if message.base.shard_ID != self.shard_ID:
                    return False, "received message with base on different shard"

            if self.received_log.sources[ID] is not None:
                # sources of messages received from shard i are on shard i
                if self.received_log.sources[ID].shard_ID != ID:
                    return False, "source for shard i on shard j != i"


            '''
            Monotonicity conditions
            '''

            # previous sent log is a prefix of current sent log
            prev_num_sent = len(self.prevblock.sent_log.log[ID])
            for i in xrange(prev_num_sent):
                if self.prevblock.sent_log.log[ID][i] != self.sent_log.log[ID][i]:
                    return False, "expected current sent log to be an extension of the previous"

            # previous received log is a prefix of current received log
            prev_num_received = len(self.prevblock.received_log.log[ID])
            for i in xrange(prev_num_received):
                if self.prevblock.received_log.log[ID][i] != self.received_log.log[ID][i]:
                    return False, "expected current received log to be an extension of the previous"

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
                        return False, "expected bases to be monotonic"

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
                        return False, "expected bases to be monotonic"

            # sources are montonic
            if self.received_log.sources[ID] is not None:
                if self.prevblock.received_log.sources[ID] is not None:
                    if not self.received_log.sources[ID].is_in_chain(self.prevblock.received_log.sources[ID]):
                        return False, "expected sources to be monotonic"

                # sources after bases
                if len(self.prevblock.sent_log.log[ID]) > 0:
                    source = self.received_log.sources[ID]
                    base = last_old_sent_message.base
                    if not source.is_in_chain(base):
                        return False, "expected bases to be in the chaing of sources"

                if len(new_sent_messages[ID]) > 0:
                    base = new_sent_messages[ID][-1].base
                    if not source.is_in_chain(base):
                        return False, "expected bases to be in the chain of sources"


            '''
            Conditions one message receipt
            '''
            if self.received_log.sources[ID] is not None:

                # check that the received messages are sent by the source
                # warning: inefficient
                for i in range(len(self.received_log.log[ID])):
                    if self.received_log.log[ID][i] != self.received_log.sources[ID].sent_log.log[self.Shard_ID][i]:
                        return False, "expected the received messages were sent by source"

                # newly received messages are received by the TTL
                for message in new_received_messages[ID]:
                    if not self.in_prev_n(message.base, message.TTL):
                        return False, "message not received within TTL of its base"

                # their sent messages are received by the TTL as seen from our sources
                source = self.received_log.sources[ID]
                for m in source.sent_log.log[self.shard_ID]:  # inefficient
                    if m.base.height + m.TTL >= self.height:
                        if m not in self.received_log.log[ID]:
                            return False, "expected all expired messages in source to be recieved"

                # our sent messages are received by the TTL as seen from our sources
                for m in self.sent_log.log[ID]:  # inefficient
                    if m.base.height + m.TTL >= source.height:
                        if m not in source.received_log.log[ID]:
                            return False, "expected all expired sent messages to be received by source"

                # our sent messages are received by the TTL as seen from our bases
                for m1 in self.sent_log.log[ID]:  # super inefficient
                    for m2 in self.sent_log.log[ID]:
                        if m1.base.height + m1.TTL >= m2.base.height:
                            if m1 not in m2.base.received_log.log[self.shard_ID]:
                                return False, "expected sent messages to be received by the TTL"

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
