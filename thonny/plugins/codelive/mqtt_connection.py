import json
import os
import random
import string
import sys
import time
import uuid

import paho.mqtt.client as mqtt_client
import paho.mqtt.publish as mqtt_publish
import paho.mqtt.subscribe as mqtt_subscribe

import thonny.plugins.codelive.utils as utils
import thonny.plugins.codelive.client as thonny_client

from thonny import get_workbench

WORKBENCH = get_workbench()

BROKER_URLS = [
    "test.mosquitto.org",
    "mqtt.eclipse.org",
    "broker.hivemq.com",
    "mqtt.fluux.io",
    "broker.emqx.io"
]

USER_COLORS = [
    "blue", 
    "green", 
    "red", 
    "pink", 
    "orange",
    "black",
    "white",
    "purple"
]

def topic_exists(s):
    # TODO: complete
    return False

def generate_topic():
    # TODO: complete
    existing_names = set()

    while True:
        name = "_".join([USER_COLORS[random.randint(0, len(USER_COLORS) - 1)] for _ in range(4)])
        name += ":" + "".join([str(random.randint(0, 9)) for _ in range(4)])

        if name in existing_names:
            continue

        if topic_exists(name):
            print("Topic %s is taken. Trying another random name..." % repr(name))
            existing_names.add(name)
        else:
            return name

def get_sender_id(json_msg):
    return json_msg['id']

def get_instr(json_msg):
    return json_msg['instr']

def get_unique_code(json_msg):
    return json_msg['unique_code']

def get_id_assigned(json_msg):
    return json_msg['id_assigned']

def need_id(my_id):
    min_valid_id = 0
    if isinstance(my_id, int) and my_id < min_valid_id:
        return True
    return False

def test_broker(url):
    client = mqtt_client.Client()
    try:
        #it seems as if keepalive only takes integers
        client.connect(url, 1883, 1)
        return True
    except Exception: 
        return False 
    
def get_default_broker():
    global BROKER_URLS

    for broker in BROKER_URLS:
        if test_broker(broker):
            return broker

    return None

def assign_broker(broker_url = None):
    if test_broker(broker_url):
        return broker_url
    else:
        return get_default_broker()

class MqttConnection(mqtt_client.Client):
    def __init__(self, 
                 session,
                 broker_url, 
                 port = None, 
                 qos = 0, 
                 delay = 1.0, 
                 topic = None,
                 on_message = None,
                 on_publish = None,
                 on_connect = None):

        mqtt_client.Client.__init__(self)
        self.session = session #can access current ID of client
        self.broker = assign_broker(broker_url) #TODO: Handle assign_broker returning none
        self.port = port or self.get_port()
        self.qos = qos
        self.delay = delay
        self.topic = topic
        self.assigned_ids = dict() #for handshake
        
        if topic == None:
            self.topic = generate_topic()
            print("New Topic: %s" % self.topic)
        else:
            print("Existing topic: %s" % self.topic)

    @classmethod
    def handshake(cls, name, topic, broker):

        my_id = random.randint(-1000,-1)
        reply_url = str(uuid.uuid4())

        greeting = {
            "id" : my_id,
            "name" : name,
            "reply" : reply_url
        }

        mqtt_publish.single(topic, payload= json.dumps(greeting), hostname = broker)
        payload = mqtt_subscribe.simple(topic + "/" + reply_url, hostname=broker).payload
        response = json.loads(payload)

        return response

    def get_port(self):
        return 1883

    def on_message(self, client, data, msg):
        json_msg = json.loads(msg.payload)

        sender_id = get_sender_id(json_msg)
        print(sender_id)
        print(self.session.user_id)
        if sender_id == self.session.user_id:
            print("instr ignored")
            return

        if sender_id < 0 and self.session.is_host:
            self.respond_to_handshake(sender_id, json_msg["reply"], json_msg["name"])
            return
        
        instr = get_instr(json_msg)
        if msg.topic == self.topic and instr:
            print(instr)
            WORKBENCH.event_generate("RemoteChange", change=instr)
    
    def publish(self, msg = None, id_assignment = None, unique_code =  None):
        send_msg = {
            "id": self.session.user_id,
            "instr": msg,
            "unique_code": unique_code,
            "id_assigned": id_assignment
        }
        mqtt_client.Client.publish(self, self.topic, payload = json.dumps(send_msg))

    def respond_to_handshake(self, sender_id, reply_url, name):
        
        assigned_id = utils.get_new_id()
        def get_unique_name(_name):
            name_list = [user.name for user in self.session.get_active_users(False)]
            if _name not in name_list:
                return _name
            
            else:
                return "%s (%d)" % (_name, assigned_id)

        message = {
            "id": self.session.user_id,
            "name": get_unique_name(name),
            "id_assigned": assigned_id,
            "docs": self.session.get_docs(),
            "users": self.session.get_active_users()
        }

        mqtt_publish.single(self.topic + "/" + reply_url, payload=json.dumps(message), hostname=self.broker)

    def Connect(self):
        mqtt_client.Client.connect(self, self.broker, self.port, 60)
        mqtt_client.Client.subscribe(self, self.topic, qos=self.qos)
    
    def get_sender(self, msg):
        pass

if __name__ == "__main__":
    import sys
    import pprint

    class Session_temp:
        def __init__(self, name = "John Doe", _id = None, is_host = True):
            self.username = name
            self.user_id = _id or utils.get_new_id()
            self.is_host = is_host

        def get_docs(self):
            return {1: {"title": "doc1",
                        "content": "Hello World 1"},
                    2: {"title": "doc2",
                        "content": "Hello World 2"},
                    3: {"title": "doc3",
                        "content": "Hello World 2"}}
    
        def get_active_users(self, in_json = True):
            return {1: "user1", 2: "user2", 3: "user3"}

    def test_handshake():
        temp_topic = "codelive_handshake_test/" + generate_topic()
        temp_broker = assign_broker()

        x = Session_temp()

        myConnection = MqttConnection(x, temp_broker, topic = temp_topic)
        myConnection.Connect()
        myConnection.loop_start()

        while True:
            x = input("Press enter for handshake...")
            response = MqttConnection.handshake("Jane Doe", temp_topic, temp_broker)
            p = pprint.PrettyPrinter(4)
            p.pprint(response)
            

    if sys.argv[1] == "handshake":
        test_handshake()
