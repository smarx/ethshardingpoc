SHARD_IDS = [0, 1, 2]


class Message:
    def __init__(self, data):
        self.data = data


class Sent_Log:
    def __init__(self):
        self.log = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            self.log[ID] = []

    def add_sent_message(self, shard_ID, message, base, TTL):
        self.log[shard_ID].append(message, base, TTL)

    def add_sent_messages(self, shard_IDs, messages, bases, TTLs):
        for i in xrange(len(shard_IDs)):
            self.add_sent_message(shard_IDs[i], messages[i], bases[i], TTLs[i])
        return self


class Received_Log:
    def __init__(self):
        self.sources = dict.fromkeys(SHARD_IDS)
        self.log = dict.fromkeys(SHARD_IDS)
        for ID in SHARD_IDS:
            self.sources[ID] = None
            self.log[ID] = []

    def add_received_message(self, shard_ID, message, base, TTL):
        self.log[shard_ID].append(message, base, TTL)

    # also adds sources, a map from SHARD IDS to blocks
    def add_received_messages(self, sources, shard_IDs, messages, bases, TTLs):
        self.sources = sources
        for i in xrange(len(shard_IDs)):
            self.add_sent_message(shard_IDs[i], messages[i], bases[i], TTLs[i])
        return self


class Block:
    def __init__(self, ID, prevblock=None, data=None, sent_log=Sent_Log(), received_log=Received_Log(), VM_state=None):
        assert (ID in SHARD_IDS), "expected a shard ID"
        self.shard_ID = ID
        self.prevblock = prevblock
        if self.prevblock is not None:
            assert self.shard_ID == self.prevblock.shard_ID, "prevblock should be on same shard as this block"
            assert isinstance(self.prevblock, Block), "expected prevblock to be a block"
        self.data = data
        assert isinstance(sent_log, Sent_Log), "expected sent log"
        self.sent_log = sent_log
        assert isinstance(received_log, Received_Log), "expected received_log"
        self.received_log = received_log
        self.VM_state = VM_state

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

# To Do:
# check if bases for shard i are on shard i
# check if messages are received by TTL of bases
# check that prev sent/received are prefixes of current sent/received
# check that bases are monotonically increasing
# check "receive sent from base"
# check "sent forces recieve"
# check "source autheticity, source/base agreement, and only receive sent"
# check that VM state is the result of applying txs in data and received messages to VM state of prev block
