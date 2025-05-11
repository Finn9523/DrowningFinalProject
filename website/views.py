import os
import cv2
import time
import threading
from flask import Blueprint, render_template, flash, redirect, request, url_for, Response
from flask_login import login_required, current_user
from ultralytics import YOLO
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from website.mqtt_publisher import publish_message
from dotenv import load_dotenv
from website.models import Account
from bson.objectid import ObjectId
from website import mongo

views = Blueprint('views', __name__)

model = YOLO("website/static/models/best.pt")

latest_frame = None

# ---------- GỬI EMAIL CẢNH BÁO ----------
def send_alert_email():
    load_dotenv()
    api_key = os.getenv("BREVO_API_KEY")

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    sender = {"name": "Hệ thống giám sát", "email": "huynhtan942003@gmail.com"}
    recipient = [{"email": "tan45385@gmail.com"}]

    email_data = {
        "sender": sender,
        "to": recipient,
        "subject": "⚠️ Cảnh báo đuối nước!",
        "htmlContent": "<h2>Hệ thống phát hiện đuối nước!</h2><p>Vui lòng kiểm tra ngay!</p>"
    }

    try:
        api_instance.send_transac_email(email_data)
        print("📩 Đã gửi email cảnh báo")
    except ApiException as e:
        print(f"❌ Lỗi gửi email: {e}")


# ---------- XỬ LÝ VIDEO QUA RTSP ----------
@views.route('/video_feed')
def video_feed():
    def generate_frames():
        cap = cv2.VideoCapture("rtsp://192.168.1.13:8554/cam", cv2.CAP_FFMPEG)

        if not cap.isOpened():
            print("❌ Không thể mở RTSP stream.")
            return

        email_sent = False
        drowning_frame_count = 0
        threshold = 30  # số frame liên tục phát hiện đuối nước để gửi cảnh báo

        while True:
            success, frame = cap.read()
            if not success:
                print("⚠️ Không đọc được frame.")
                break

            frame_resized = cv2.resize(frame, (640, 360))

            # ------ YOLO xử lý frame ------
            is_drowning = False
            results = model(frame_resized)  # model đã load trước ở đâu đó

            for r in results:
                for i in range(len(r.boxes.cls)):
                    class_id = int(r.boxes.cls[i])
                    label = model.names[class_id]  # lấy tên nhãn từ model

                    if label == "drowning":
                        is_drowning = True
                        break

            # ------ Cảnh báo nếu phát hiện đuối nước nhiều frame ------
            drowning_frame_count = drowning_frame_count + 1 if is_drowning else 0

            if drowning_frame_count >= threshold and not email_sent:
                send_alert_email()
                publish_message("True")
                email_sent = True
                print("🚨 Gửi cảnh báo! Đuối nước phát hiện.")

            if not is_drowning:
                email_sent = False  # reset lại nếu bình thường

            # ------ Vẽ khung từ YOLO ------
            frame_with_boxes = results[0].plot()

            # ------ Encode & gửi frame ------
            _, buffer = cv2.imencode('.jpg', frame_with_boxes)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ---------- DASHBOARD ADMIN ----------
@views.route('/admin.html', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.Role != 'Admin':
        flash('Bạn không có quyền truy cập!', category='error')
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        action = request.form.get('action')

        if not ObjectId.is_valid(user_id):
            flash('ID không hợp lệ.', 'error')
        else:
            user_doc = mongo.db.accounts.find_one({'_id': ObjectId(user_id)})
            if not user_doc:
                flash('Không tìm thấy người dùng.', 'error')
            else:
                if action == 'toggle_status':
                    if user_doc['Role'] == 'Admin':
                        flash('Không thể vô hiệu hóa tài khoản Admin!', 'error')
                    else:
                        new_status = not user_doc.get('IsActive', True)
                        mongo.db.accounts.update_one({'_id': ObjectId(user_id)}, {'$set': {'IsActive': new_status}})
                        status = 'kích hoạt' if new_status else 'vô hiệu hóa'
                        flash(f"Tài khoản {user_doc['Username']} đã được {status}", 'success')

                elif action == 'update_role':
                    new_role = request.form.get('new_role')
                    if new_role in ['Manager', 'Employee']:
                        mongo.db.accounts.update_one({'_id': ObjectId(user_id)}, {'$set': {'Role': new_role}})
                        flash(f"Đã cập nhật vai trò của {user_doc['Username']} thành {new_role}", 'success')
                    else:
                        flash('Vai trò không hợp lệ!', 'error')

    user_docs = list(mongo.db.accounts.find({'Role': {'$in': ['Manager', 'Employee']}}))
    users = [Account(doc) for doc in user_docs]

    account_map = {str(doc['_id']): doc for doc in user_docs}
    login_docs = list(mongo.db.login_records.find().sort('LoginTime', -1))

    login_records = []
    for record in login_docs:
        acc_id = record.get('AccountRef')
        if acc_id and ObjectId.is_valid(str(acc_id)):
            acc_doc = account_map.get(str(acc_id))
            if acc_doc:
                login_records.append({
                    'Username': acc_doc.get('Username'),
                    'Role': acc_doc.get('Role'),
                    'LoginTime': record.get('LoginTime'),
                    'IPAddress': record.get('IPAddress') or 'Không xác định'
                })

    return render_template("admin.html", user=current_user, login_records=login_records, users=users)


# ---------- DASHBOARD MANAGER ----------
@views.route('/manager.html')
@login_required
def manager_dashboard():
    return render_template('manager.html', user=current_user)


# ---------- TRANG HOME ----------
@views.route('/')
def home():
    return render_template('home.html', user=current_user)