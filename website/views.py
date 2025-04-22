import os
import time
import cv2
import torch
import threading
import queue
from flask import Blueprint, render_template, request, url_for, Response, flash, redirect
from website.models import Account, LoginRecords  # Import the Account model
from website import db  # Import the db object
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from ultralytics import YOLO

views = Blueprint('views', __name__)

# Load mô hình YOLOv8
model_path = "website/static/models/best.pt"
if os.path.exists(model_path):
    model = YOLO(model_path)
else:
    model = None
    print(f"LỖI: Không tìm thấy model tại {model_path}")

UPLOAD_FOLDER = 'website/static/videos'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# Hàm gửi email cảnh báo
def send_alert_email():
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = "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"  # Thay bằng API Key của bạn

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    sender = {"name": "Hệ thống giám sát", "email": "huynhtan942003@gmail.com"}  # Email gửi đi
    recipient = [{"email": "tan45385@gmail.com"}]  # Email nhận cảnh báo

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_video_paths():
    """Trả về danh sách các video có trong thư mục UPLOAD_FOLDER"""
    return [
        os.path.join(UPLOAD_FOLDER, f)
        for f in os.listdir(UPLOAD_FOLDER)
        if allowed_file(f)
    ]

def process_video(video_path, frame_queue, stop_event):
    """Luồng xử lý video và đẩy frame vào queue"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Không thể mở video:", video_path)
        return

    frame_count = 0
    fps = int(cap.get(cv2.CAP_PROP_FPS))  # Lấy FPS của video
    frame_skip = max(1, fps // 10)  # Chỉ lấy khoảng 10 frame/giây để giảm tải CPU

    last_alert_time = 0  # Lưu thời gian gửi email gần nhất
    alert_interval = 30  # Chỉ gửi email tối đa 1 lần mỗi 30 giây

    while cap.isOpened() and not stop_event.is_set():
        success, frame = cap.read()
        if not success:
            break  # Dừng vòng lặp nếu không thể đọc frame

        frame_count += 1
        if frame_count % frame_skip != 0:
            continue  # Bỏ qua các frame không cần thiết

        # Resize để giảm tải CPU
        frame_resized = cv2.resize(frame, (640, 360))
        results = model(frame_resized, verbose=False) if model else []

        is_drowning = False
        for box in results[0].boxes if results else []:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = box.conf[0].item()
            cls = int(box.cls[0].item())

            if model and model.names[cls] == "drowning" and conf > 0.5:
                label = f"{model.names[cls]} {conf:.2f}"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                is_drowning = True

        # Nếu phát hiện đuối nước và chưa gửi email gần đây, thì gửi cảnh báo
        if is_drowning and (time.time() - last_alert_time > alert_interval):
            print("⚠️ Phát hiện đuối nước! Gửi email cảnh báo...")
            send_alert_email()
            last_alert_time = time.time()  # Cập nhật thời gian gửi email

        frame_queue.put((frame, is_drowning))

    cap.release()


def generate_frames(video_index):
    """Luồng phát video từ queue"""
    videos_paths = get_video_paths()
    if video_index < 0 or video_index >= len(videos_paths):
        return

    video_path = videos_paths[video_index]
    frame_queue = queue.Queue(maxsize=10)
    stop_event = threading.Event()

    # Tạo luồng xử lý video
    thread = threading.Thread(target=process_video, args=(video_path, frame_queue, stop_event))
    thread.daemon = True  # Tự động dừng khi Flask tắt
    thread.start()

    try:
        while thread.is_alive():
            try:
                frame, is_drowning = frame_queue.get(timeout=5)
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n'
                       b'X-Drowning: ' + (b'1' if is_drowning else b'0') + b'\r\n\r\n' +
                       frame_bytes + b'\r\n')
            except queue.Empty:
                break
    finally:
        stop_event.set()  # Dừng thread khi không còn frame mới

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
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        if os.path.exists(file_path):
            flash('Video đã tồn tại!')
        else:
            file.save(file_path)
            flash('Video đã được tải lên thành công!')

        return redirect(url_for('views.home'))
    
    flash('Định dạng video không hợp lệ!')
    return redirect(url_for('views.home'))

@views.route('/admin.html', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.Role != 'Admin':
        flash('Bạn không có quyền truy cập!', category='error')
        return redirect(url_for('views.home'))

    user = None  # ✅ Khởi tạo sớm để tránh lỗi
    action = None

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        action = request.form.get('action')
        user = Account.query.get(user_id)

        if not user:
            flash('Không tìm thấy người dùng.', 'error')
        else:
            if action == 'toggle_status':
                if user.Role == 'Admin':
                    flash('Không thể vô hiệu hóa tài khoản Admin!', 'error')
                else:
                    user.is_active = not user.is_active
                    db.session.commit()
                    status = 'kích hoạt' if user.is_active else 'vô hiệu hóa'
                    flash(f'Tài khoản {user.username} đã được {status}', 'success')

            elif action == 'update_role':
                new_role = request.form.get('new_role')
                if new_role in ['Manager', 'Employee']:
                    user.Role = new_role
                    db.session.commit()
                    flash(f'Đã cập nhật vai trò của {user.username} thành {new_role}', 'success')
                else:
                    flash('Vai trò không hợp lệ!', 'error')

    # Lấy danh sách tài khoản 
    users = Account.query.filter(Account.Role.in_(['Manager', 'Employee'])).order_by(Account.username).all()

    # Lấy lịch sử đăng nhập,
    login_records = db.session.query(
        Account.username, Account.Role, LoginRecords.LoginTime, LoginRecords.IPAddress
    ).join(
        LoginRecords, Account.Id == LoginRecords.AccountId
    ).filter(
        Account.Role.in_(['Manager', 'Employee'])
    ).order_by(LoginRecords.LoginTime.desc()).all()

    return render_template("admin.html", users=users, login_records=login_records)

@views.route('/manager.html')
@login_required
def manager_dashboard():
    return render_template('manager.html', user=current_user)


@views.route('/')
def home():
    videos_paths = get_video_paths()
    return render_template('home.html', user=current_user, videos_paths=videos_paths)
