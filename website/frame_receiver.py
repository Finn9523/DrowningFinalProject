from threading import Condition
import socket
import struct
import numpy as np
import cv2

current_frame = None
frame_condition = Condition()

def receive_frames():
    global current_frame
    HOST = ''
    PORT = 5000

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(1)
    print(f"[SERVER] Đang lắng nghe tại cổng {PORT}...")

    conn, addr = server_sock.accept()
    print(f"[SERVER] Client đã kết nối: {addr}")

    data_buffer = b''
    payload_size = struct.calcsize('>L')  # 4 byte

    try:
        while True:
            while len(data_buffer) < payload_size:
                packet = conn.recv(4096)
                if not packet:
                    break
                data_buffer += packet
            if len(data_buffer) < payload_size:
                break

            packed_len = data_buffer[:payload_size]
            data_buffer = data_buffer[payload_size:]
            msg_size = struct.unpack('>L', packed_len)[0]

            while len(data_buffer) < msg_size:
                packet = conn.recv(4096)
                if not packet:
                    break
                data_buffer += packet
            if len(data_buffer) < msg_size:
                break

            frame_data = data_buffer[:msg_size]
            data_buffer = data_buffer[msg_size:]

            frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                with frame_condition:
                    current_frame = frame
                    frame_condition.notify_all()


    except Exception as e:
        print(f"[SERVER] Lỗi: {e}")
    finally:
        conn.close()
        server_sock.close()