from website import create_app
from website.mqtt_publisher import connect_mqtt

app = create_app()

if __name__ == '__main__':
    connect_mqtt()  # Kết nối MQTT khi web start
    app.run(host='0.0.0.0', port=5000, debug=True)  