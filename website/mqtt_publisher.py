# mqtt_publisher.py
import paho.mqtt.client as mqtt
import os
from dotenv import load_dotenv

load_dotenv()

broker_address = os.getenv("MQTT_BROKER_ADDRESS")
broker_port = int(os.getenv("MQTT_BROKER_PORT"))
topic = "drowning/alert"

client = mqtt.Client()

def connect_mqtt():
    client.connect(broker_address, broker_port)
    client.loop_start()  # dùng loop_start để chạy song song
    print("Đã kết nối MQTT")

def publish_message(message):
    client.publish(topic, message)
    print(f"{message}")