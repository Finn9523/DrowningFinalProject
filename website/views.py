import os
import cv2
import torch
import threading
import queue
from flask import Blueprint, render_template, request, url_for, Response, flash, redirect
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from ultralytics import YOLO
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from website.mqtt_publisher import publish_message
from dotenv import load_dotenv

views = Blueprint('views', __name__)

# Load mô hình YOLO11
model_path = "website/static/models/best.pt"
model = YOLO(model_path)

UPLOAD_FOLDER = 'website/static/videos'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_video_paths():
    """Trả về danh sách các video có trong thư mục UPLOAD_FOLDER"""
    return [
        os.path.join(UPLOAD_FOLDER, f)
        for f in os.listdir(UPLOAD_FOLDER)
        if allowed_file(f)
    ]

# Hàm gửi email cảnh báo
def send_alert_email():
    # Load biến môi trường từ file .env
    load_dotenv()
    api_key = os.getenv("BREVO_API_KEY")

    # Cấu hình với API key từ biến môi trường
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    sender = {"name": "Hệ thống giám sát", "email": "huynhtan942003@gmail.com"}
    recipient = [{"email": "tan45385@gmail.com"}]

    subject = "⚠️ Cảnh báo đuối nước!"
    html_content = "<h2>Hệ thống phát hiện đuối nước!</h2><p>Vui lòng kiểm tra ngay!</p>"

    email_data = {
        "sender": sender,
        "to": recipient,
        "subject": subject,
        "htmlContent": html_content
    }

    try:
        api_instance.send_transac_email(email_data)
        print("📩 Email cảnh báo đã gửi thành công!")
    except ApiException as e:
        print(f"❌ Lỗi gửi email: {e}")

def process_video(video_path, frame_queue):
    """Luồng xử lý video và đẩy frame vào queue"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Không thể mở video:", video_path)
        return

    frame_count = 0
    fps = int(cap.get(cv2.CAP_PROP_FPS))  # Lấy FPS của video
    frame_skip = max(1, fps // 10)  # Chỉ lấy khoảng 10 frame/giây để giảm tải CPU

    email_sent = False
    drowning_frame_count = 0
    drowning_duration_sec = 3  # 👈 Số giây liên tục cần phát hiện để cảnh báo
    drowning_threshold = drowning_duration_sec * (10)  # 10 fps (do frame_skip)

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Quay lại đầu video nếu hết frame
            continue

        frame_count += 1
        if frame_count % frame_skip != 0:  # Bỏ qua các frame không cần thiết
            continue

        # Resize để giảm tải CPU
        frame_resized = cv2.resize(frame, (640, 360))
        results = model(frame_resized, verbose=False)

        is_drowning = False
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0]
            conf = box.conf[0].item()
            cls = int(box.cls[0].item())

            # Chuyển về tọa độ gốc của frame
            x1 = int(x1 * frame.shape[1] / 640)
            y1 = int(y1 * frame.shape[0] / 360)
            x2 = int(x2 * frame.shape[1] / 640)
            y2 = int(y2 * frame.shape[0] / 360)

            if model.names[cls] == "drowning" and conf > 0.5:
                label = f"{model.names[cls]} {conf:.2f}"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                is_drowning = True

        # Cập nhật bộ đếm đuối nước
        if is_drowning:
            drowning_frame_count += 1
        else:
            drowning_frame_count = 0

        # Cảnh báo nếu liên tục đủ số frame đuối nước
        if drowning_frame_count >= drowning_threshold and not email_sent:
            send_alert_email()
            publish_message("CẢNH BÁO: Phát hiện đuối nước!")
            email_sent = True

        frame_queue.put((frame, is_drowning))

    cap.release()


def generate_frames(video_index):
    """Luồng phát video từ queue"""
    videos_paths = get_video_paths()
    if video_index < 0 or video_index >= len(videos_paths):
        return

    video_path = videos_paths[video_index]
    frame_queue = queue.Queue(maxsize=10)

    # Tạo luồng xử lý video
    thread = threading.Thread(target=process_video, args=(video_path, frame_queue))
    thread.daemon = True  # Tự động dừng khi Flask tắt
    thread.start()

    while True:
        try:
            frame, is_drowning = frame_queue.get(timeout=5)  # Lấy frame từ queue
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'X-Drowning: ' + (b'1' if is_drowning else b'0') + b'\r\n\r\n' +
                   frame_bytes + b'\r\n')
        except queue.Empty:
            break  # Thoát nếu không có frame

@views.route('/video_feed/<int:video_index>')
def video_feed(video_index):
    videos_paths = get_video_paths()
    if video_index < 0 or video_index >= len(videos_paths):
        return "Video không tồn tại", 404
    return Response(generate_frames(video_index), mimetype='multipart/x-mixed-replace; boundary=frame')

@views.route('/upload_video', methods=['POST'])
@login_required
def upload_video():
    if 'video' not in request.files:
        flash('Không có video nào được chọn!')
        return redirect(url_for('views.home'))

    file = request.files['video']
    if file.filename == '':
        flash('Không có video nào được chọn!')
        return redirect(url_for('views.home'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        flash('Video đã được tải lên thành công!')
        return redirect(url_for('views.home'))
    
    flash('Định dạng video không hợp lệ!')
    return redirect(url_for('views.home'))

@views.route('/')
def home():
    videos_paths = get_video_paths()
    return render_template('home.html', user=current_user, videos_paths=videos_paths)
