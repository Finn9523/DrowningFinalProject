import os
import cv2
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
import website.frame_receiver as rf

views = Blueprint('views', __name__)

model = YOLO("website/static/models/best.pt")

print(rf)

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

# --- MJPEG generator ---
def generate_stream():
    while True:
        with rf.frame_condition:
            rf.frame_condition.wait()
            if rf.current_frame is None:
                print("No frame received")
                continue
            frame = rf.current_frame.copy()

        if frame is None:
            continue
        resized_frame = cv2.resize(rf.current_frame, (640, 360))

        # Chạy YOLO
        results = model(resized_frame)

        # Vẽ bounding boxes lên ảnh
        frame_with_boxes = results[0].plot()

        ret, jpeg = cv2.imencode('.jpg', frame_with_boxes)
        if not ret:
            continue

        frame = jpeg.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@views.route("/video_feed")
@login_required
def video_feed():            
    return Response(generate_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ---------- DASHBOARD ADMIN ----------
@views.route("/admin.html", methods=['GET', 'POST'])
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
@views.route("/manager.html")
@login_required
def manager_dashboard():
    if current_user.Role not in ['Admin', 'Manager']:
        flash('Bạn không có quyền truy cập!', category='error')
        return redirect(url_for('views.home'))
    return render_template('home.html', user=current_user)

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

# ---------- TRANG HOME ----------
@views.route('/')
@login_required
def home():
    if current_user.Role in ['Admin', 'Manager']:
        return render_template('home.html', user=current_user)
    else:
        flash('Bạn không có quyền truy cập trang này.', 'error')
        return redirect(url_for('auth.logout'))


