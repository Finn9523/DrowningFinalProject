# mqtt_publisher.py
import paho.mqtt.client as mqtt

broker_address = "192.168.1.7"
broker_port = 1883
topic = "drowning/alert"

client = mqtt.Client()

def connect_mqtt():
    client.connect(broker_address, broker_port)
    client.loop_start()  # dùng loop_start để chạy song song
    print("MQTT client đã kết nối.")

def publish_message(message):
    client.publish(topic, message)
    print(f"Đã gửi: {message}")