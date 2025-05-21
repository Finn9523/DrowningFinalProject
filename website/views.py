import os, random, string, datetime
import cv2
from flask import Blueprint, render_template, flash, redirect, request, url_for, Response, jsonify
from flask_login import login_required, current_user
from ultralytics import YOLO
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from website.mqtt_publisher import publish_message
from dotenv import load_dotenv
from website.models import Account
from bson.objectid import ObjectId
from website import mongo
import website.frame_receiver as rf
import hashlib
import base64
from werkzeug.security import check_password_hash
import json

views = Blueprint('views', __name__)

model = YOLO("website/static/models/best.pt")


# ---------------------- GỬI EMAIL CẢNH BÁO ----------------------
def send_alert_email():
    load_dotenv()
    api_key = os.getenv("BREVO_API_KEY")

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    sender = {"name": "Hệ thống giám sát", "email": "huynhtan942003@gmail.com"}
    recipient_email = "tan45385@gmail.com"
    recipient = [{"email": recipient_email}]

    email_content = "Hệ thống phát hiện đuối nước! Vui lòng kiểm tra ngay!"

    email_data = {
        "sender": sender,
        "to": recipient,
        "subject": "⚠️ Cảnh báo đuối nước!",
        "htmlContent": email_content
    }

    try:
        api_instance.send_transac_email(email_data)
        print("📩 Đã gửi email cảnh báo")
        mongo.db.email_logs.insert_one({
            "email": recipient_email,
            "content": email_content,
            "date": datetime.datetime.utcnow()
        })
    except ApiException as e:
        print(f"❌ Lỗi gửi email: {e}")

# ---------------------- STREAM VIDEO ----------------------
rf.is_drowning = False
email_sent = False
frame_counter = 0
threshold = 5

def get_next_alert_id():
    latest = mongo.db.alert.find_one(sort=[("AlertId", -1)])
    return (latest["AlertId"] + 1) if latest else 1


def generate_stream():
    global email_sent, frame_counter

    while True:
        with rf.frame_condition:
            rf.frame_condition.wait()
            if rf.current_frame is None:
                continue
            frame = rf.current_frame.copy()

        try:
            resized = cv2.resize(frame, (640, 360))
            results = model(resized, verbose=False)

            boxes = results[0].boxes
            drowning_detected = False
            for box in boxes:
                cls_id = int(box.cls[0])
                if model.names[cls_id] == "drowning" and box.conf[0].item() > 0.5:
                    drowning_detected = True
                    break


            if drowning_detected:
                frame_counter += 1
            else:
                frame_counter = 0

            rf.is_drowning = drowning_detected

            if frame_counter >= threshold and not email_sent:
                alert_doc = {
                    "AlertId": get_next_alert_id(),  # Hàm lấy AlertId kế tiếp
                    "DetectedAt": datetime.datetime.utcnow(),
                    "Status": "Pending"
                }
                inserted = mongo.db.alert.insert_one(alert_doc)
                alert_id = str(inserted.inserted_id)  # Chính là _id trong MongoDB

                # --- Gửi MQTT JSON ---
                mqtt_payload = {
                    "alert": True,
                    "alert_id": alert_id
                }
                send_alert_email()
                publish_message(json.dumps(mqtt_payload))
                email_sent = True

            if not drowning_detected:
                email_sent = False

            output = results[0].plot()
            ret, jpeg = cv2.imencode('.jpg', output)
            if not ret:
                continue

            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

        except Exception as e:
            print(f"❌ Lỗi xử lý ảnh: {e}")

@views.route('/video_feed')
@login_required
def video_feed():
    return Response(generate_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@views.route('/status')
def status():
    return jsonify({'is_drowning': getattr(rf, 'is_drowning', False)})

def hash_password_scrypt(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=16384,   # giảm xuống 16384
        r=8,
        p=1,
        dklen=32
    )
    return base64.b64encode(salt).decode() + '$' + base64.b64encode(key).decode()

# ---------- DASHBOARD ADMIN ----------
@views.route("/admin.html", methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.Role != 'Admin':
        flash('Bạn không có quyền truy cập!', category='error')
        return redirect(url_for('views.home'))

    # --- POST xử lý cập nhật trạng thái, vai trò, hoặc đặt lại mật khẩu ---
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
                # Vô hiệu hóa hoặc kích hoạt tài khoản
                if action == 'toggle_status':
                    if user_doc['Role'] == 'Admin':
                        flash('Không thể vô hiệu hóa tài khoản Admin!', 'error')
                    else:
                        new_status = not user_doc.get('IsActive', True)
                        mongo.db.accounts.update_one({'_id': ObjectId(user_id)}, {'$set': {'IsActive': new_status}})
                        status = 'kích hoạt' if new_status else 'vô hiệu hóa'
                        flash(f"Tài khoản {user_doc['Username']} đã được {status}", 'success')

                # Cập nhật vai trò
                elif action == 'update_role':
                    new_role = request.form.get('new_role')
                    if new_role in ['Manager', 'Employee']:
                        mongo.db.accounts.update_one({'_id': ObjectId(user_id)}, {'$set': {'Role': new_role}})
                        flash(f"Đã cập nhật vai trò của {user_doc['Username']} thành {new_role}", 'success')
                    else:
                        flash('Vai trò không hợp lệ!', 'error')

                # Đặt lại mật khẩu với scrypt
                elif action == 'reset_password':
                    if user_doc['Role'] == 'Admin':
                        flash('Không thể đặt lại mật khẩu cho tài khoản Admin!', 'error')
                    else:
                        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                        hashed_password = hash_password_scrypt(new_password)
                        mongo.db.accounts.update_one(
                            {'_id': ObjectId(user_id)},
                            {'$set': {'Password': hashed_password, 'LastPasswordReset': datetime.utcnow()}}
                        )
                        flash(f"Mật khẩu mới của {user_doc['Username']}: {new_password}", 'success')
                        flash(f"Mật khẩu đã mã hóa (hash): {hashed_password}", 'info')


    # --- GET xử lý tìm kiếm ---
    keyword = request.args.get('keyword', '').strip()
    query = {'Role': {'$in': ['Manager', 'Employee']}}

    if keyword:
        query['Username'] = {'$regex': keyword, '$options': 'i'}

    user_docs = list(mongo.db.accounts.find(query))
    users = [Account(doc) for doc in user_docs]

    # Lấy bản ghi đăng nhập để hiển thị lịch sử
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


# ---------------------- DASHBOARD MANAGER ----------------------
@views.route("/manager.html")
@login_required
def manager_dashboard():
    if current_user.Role not in ['Admin', 'Manager']:
        flash('Bạn không có quyền truy cập!', 'error')
        return redirect(url_for('views.home'))

    return render_template('home.html', user=current_user, email_stats_url=url_for('views.manager_email_stats'))

@views.route("/email-stats")
@login_required
def manager_email_stats():
    if current_user.Role not in ['Admin', 'Manager']:
        return jsonify({"email": "Không có quyền truy cập", "content": "Bạn không được phép xem thống kê này", "date": ""}), 403

    email_doc = mongo.db.email_logs.find_one(sort=[("date", -1)])
    if not email_doc:
        return jsonify({"email": "Không có dữ liệu", "content": "Không có nội dung", "date": "Không rõ thời gian"})

    date = email_doc.get("date", "")
    if isinstance(date, datetime.datetime):
        date_str = date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        date_str = str(date)[:19].replace("T", " ")

    return jsonify({
        "email": email_doc.get("email", "Không xác định"),
        "content": email_doc.get("content", "Không có nội dung"),
        "date": date_str
    })

# ---------- EMPLOYEE ----------
@views.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = mongo.db.accounts.find_one({'Username': username})
    if not user or not check_password_hash(user['Password'], password):
        return jsonify({'status': 'fail', 'message': 'Sai tài khoản hoặc mật khẩu'}), 401

    if user['Role'] != 'Employee':
        return jsonify({'status': 'fail', 'message': 'Không phải tài khoản nhân viên'}), 403

    # Có thể trả JWT hoặc dữ liệu người dùng
    return jsonify({
        'status': 'success',
        'message': 'Đăng nhập thành công',
        'user': {
            'username': user['Username'],
            'role': user['Role'],
            'id': str(user['_id'])
        }
    })

@views.route("/api/update_alert_status", methods=["POST"])
def update_alert_status():
    data = request.get_json()
    alert_id = data.get("alert_id")
    status = data.get("status")

    if status not in ["Confirmed", "False Alarm"]:
        return jsonify({"success": False, "message": "Invalid status"}), 400

    result = mongo.db.alert.update_one(
        {"_id": ObjectId(alert_id)},
        {"$set": {"Status": status}}
    )

    if result.matched_count == 0:
        return jsonify({"success": False, "message": "Alert not found"}), 404

    return jsonify({"success": True, "message": "Alert updated"})


# ---------- TRANG HOME ----------
@views.route('/')
@login_required
def home():
    if current_user.Role in ['Admin', 'Manager']:
        return render_template('home.html', user=current_user)
    else:
        flash('Bạn không có quyền truy cập trang này.', 'error')
        return redirect(url_for('auth.logout'))