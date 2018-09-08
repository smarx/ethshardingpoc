SHARD_IDS = [0, 1, 2]


# Maurelian: please give message data format (for txs)

class Message_Data:


class Message:
    def __init__(self, data, base, TTL):
        self.data = data
        self.base = base
        self.TTL = TTL

class Sent_Log:
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


class Received_Log:
    def __init__(self):
        self.sources = dict.fromkeys(SHARD_IDS)
        self.log = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            self.sources[ID] = None
            self.log[ID] = []

    def add_received_message(self, shard_ID, message):
        self.log[shard_ID].append(message)

    # also adds sources, a map from SHARD IDS to blocks
    def add_received_messages(self, sources, shard_IDs, messages):
        self.sources = sources
        for i in xrange(len(shard_IDs)):
            self.add_sent_message(shard_IDs[i], messages[i])
        return self


# Maurelian: please replace VM_state = None as default for geneis blocks to some initial VM state (balances)
class Block:
    def __init__(self, ID, prevblock=None, data=None, sent_log=Sent_Log(), received_log=Received_Log(), VM_state=None):
        self.shard_ID = ID
        self.prevblock = prevblock
        self.data = data
        self.sent_log = sent_log
        self.received_log = received_log
        self.VM_state = VM_state

        check = self.is_valid()
        assert check[0], check[1]

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
        if not isinstance(self.sent_log, Sent_Log):
            return False, "expected sent log"
        if not isinstance(self.received_log, Received_Log):
            return False, "expected received_log"
        # if not isinstance(self.VM_state, EVM_State):
        #    return False, "expected an EVM State"

        '''
        Type check consistency conditions between the:
        '''

        # check that the prev block is on the same shard as this block
        if self.prevblock is not None:
            if self.shard_ID != self.prevblock.shard_ID:
                return False, "prevblock should be on same shard as this block"

        # bases for shard i are on shard i
        for ID in SHARD_IDS:
            for message in self.sent_log.log[ID]:  # warning, checks for all messages of all time, not just new ones
                if message.base.shard_ID != ID:
                    return False, "message sent to shard i has base on shard j != i"
        for message in self.received_log.log[ID]:  # warning, checks for all messages of all time, not just new ones
            if message.base.shard_ID != self.shard_ID:
                return False, "received message with base on different shard"
        for ID in SHARD_IDS:
            if self.received_log.sources[ID].shard_ID != ID:
                return False, "source for shard i on shard j != i"

        


        return True

# To Do:
# check if messages are received by TTL of bases
# check that prev sent/received are prefixes of current sent/received
# check that bases are monotonically increasing
# check "receive sent from base"
# check "sent forces recieve"
# check "source autheticity, source/base agreement, and only receive sent"

    def newly_sent(self):
        new_sent = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            new = []
            num_sent = len(self.sent_log.log[ID])
            prev_num_sent = len(self.prevblock.sent_log.log[ID])
            num_new_sent = num_sent - prev_num_sent
            assert num_new_sent >= 0, "expected growing sent log"
            for i in xrange(num_new_sent):
                new.append(self.sent_log.log[ID][prev_num_sent + i])
            new_sent[ID] = new

        return new_sent

    def newly_received(self):
        new_received = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            new = []
            num_received = len(self.received_log.log[ID])
            prev_num_received = len(self.prevblock.received_log.log[ID])
            num_new_received = num_received - prev_num_received
            assert num_new_received >= 0, "expected growing received log"
            for i in xrange(num_new_received):
                new.append(self.received_log.log[ID][prev_num_received + i])
            new_received[ID] = new

        return new_received

