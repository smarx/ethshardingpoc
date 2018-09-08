import json
import time

import pusher
import pusherclient

app_key = 'a9afbec4cb2906a41792'

def transaction_handler(data):
    tx = json.loads(data)
    print('Received transaction:')
    print('\tSend {} from {} to {} with payload {}.'.format(tx['value'], tx['from'], tx['to'], tx['message']))

def connect_handler(data):
    channel = listener.subscribe('transactions')
    channel.bind('new-transaction', transaction_handler)

# HACK around library's lack of cluster support
pusherclient.Pusher.host = "ws-eu.pusher.com"

listener = pusherclient.Pusher(app_key)
listener.connection.bind('pusher:connection_established', connect_handler)
listener.connect()

while True:
    time.sleep(1)
