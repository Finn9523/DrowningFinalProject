# mqtt_publisher.py
import time
import paho.mqtt.client as mqtt

broker_address = "192.168.1.5"  # IP máy bạn (hoặc localhost nếu chạy cùng máy)
broker_port = 1883
topic = "drowning/alert"

client = mqtt.Client()
client.connect(broker_address, broker_port)

while True:
    message = "CẢNH BÁO: Phát hiện đuối nước!"
    client.publish(topic, message)
    print(f"Đã gửi: {message}")
    time.sleep(10)  # gửi mỗi 10 giây