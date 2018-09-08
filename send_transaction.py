import pusher
import sys

pusher_client = pusher.Pusher(
    app_id='595055',
    key='a9afbec4cb2906a41792',
    secret='b678140faccbb6313bba',
    cluster='eu',
    ssl=True
)

pusher_client.trigger('transactions', 'new-transaction', {
    'from': sys.argv[1],
    'to': sys.argv[2],
    'message': sys.argv[3],
    'value': sys.argv[4],
})
