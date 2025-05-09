from flask import Flask, render_template, request
import threading
from time import sleep

import amqpstorm
from amqpstorm import Message

app = Flask(__name__)

class RpcClient:
    def __init__(self, host, username, password, virtualhost, rpc_queue):
        self.queue = {}
        self.responses = []
        self.rpc_queue = rpc_queue
        self.connection = amqpstorm.Connection(
            hostname=host,
            username=username,
            password=password,
            virtual_host=virtualhost
        )
        self.channel = self.connection.channel()
        result = self.channel.queue.declare(exclusive=True)
        self.callback_queue = result['queue']
        self.channel.basic.consume(self._on_response,
                                   no_ack=True,
                                   queue=self.callback_queue)
        thread = threading.Thread(target=self._consume_responses)
        thread.daemon = True
        thread.start()


    def _consume_responses(self):
        self.channel.start_consuming(to_tuple=False)

    def _on_response(self, message):
        self.queue[message.correlation_id] = message.body  # Ya es str
        self.responses.append(message.body) 

    def send_request(self, payload):
        message = Message.create(self.channel, payload)
        message.reply_to = self.callback_queue
        self.queue[message.correlation_id] = None
        message.publish(routing_key=self.rpc_queue)
        return message.correlation_id

# Usa los datos correctos según tu URL AMQP de CloudAMQP
rpc_client = RpcClient(
    host='woodpecker-01.rmq.cloudamqp.com',
    username='nvoalptz',
    password='Dz-R0OIoGpp3-EhJaA4g8gkxSfk5wzC5',
    virtualhost='nvoalptz',  # <- MUY IMPORTANTE
    rpc_queue='rpc_queue'
)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        message = request.form['message']
        corr_id = rpc_client.send_request(message)

        timeout = 20
        elapsed = 0
        while rpc_client.queue[corr_id] is None and elapsed < timeout:
            sleep(0.1)
            elapsed += 0.1

        if rpc_client.queue[corr_id] is None:
            response = "Error: Timeout esperando respuesta"
        else:
            response = rpc_client.queue.pop(corr_id)

        return render_template('index.html', response=response, all_responses=rpc_client.responses)

    return render_template('index.html', response=None, all_responses=rpc_client.responses)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
