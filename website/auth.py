from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from .models import Account, LoginRecords
import pytz
from datetime import datetime
from . import db

auth = Blueprint('auth', __name__)

#login bên web
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = Account.query.filter_by(username=username).first()

        if user:
            if not user.is_active:
                flash('Tài khoản đã bị vô hiệu hóa. Vui lòng liên hệ quản trị viên.', 'error')
                return redirect(url_for('auth.login'))

            if check_password_hash(user.password, password):
                flash('Đăng nhập thành công!', category='success')
                login_user(user, remember=True)

                vietnam_tz = pytz.timezone("Asia/Ho_Chi_Minh")
                login_time = datetime.now(vietnam_tz)

                login_record = LoginRecords(AccountId=user.Id, LoginTime=login_time)
                db.session.add(login_record)
                db.session.commit()

                # Điều hướng theo Role
                if user.Role == 'Admin':
                    return redirect(url_for('views.admin_dashboard'))
                elif user.Role == 'Manager':
                    return redirect(url_for('views.home'))
                else:
                    return redirect(url_for('views.home'))
            else:
                flash('Mật khẩu không đúng.', category='error')
        else:
            flash('Tài khoản không tồn tại.', category='error')

    return render_template("login.html", user=current_user)


#login bên api mobile
@auth.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = Account.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        return jsonify({
            'success': True,
            'message': 'Đăng nhập thành công',
            'user': {
                'id': user.Id,
                'email': user.email,
                'fullname': user.fullname,
            }
        }), 200
    else:
        return jsonify({'success': False, 'message': 'Sai email hoặc mật khẩu'}), 401

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đăng xuất thành công.', category='success')
    return redirect(url_for('auth.login'))

# @auth.route('/sign-up', methods=['GET', 'POST'])
# def sign_up():
#     if request.method == 'POST':
#         username = request.form.get('username')
#         email = request.form.get('email')
#         fullname = request.form.get('fullname')
#         password = request.form.get('password1')
#         confirm_password = request.form.get('password2')

#         user = Account.query.filter_by(username=username).first()
#         if user:
#             flash('Tên đăng nhập đã tồn tại.', category='error')
#         elif len(email) < 4:
#             flash('Email phải có ít nhất 4 ký tự.', category='error')
#         elif len(fullname) < 2:
#             flash('Tên phải có ít nhất 2 ký tự.', category='error')
#         elif password != confirm_password:
#             flash("Mật khẩu không khớp.", category='error')
#         elif len(password) < 7:
#             flash('Mật khẩu phải có ít nhất 7 ký tự.', category='error')
#         else:
#             # Thêm user vào database
#             new_user = Account(
#                 username = username,
#                 email=email,
#                 fullname = fullname,
#                 password=generate_password_hash(password, method='pbkdf2:sha256')
#             )
#             db.session.add(new_user)
#             db.session.commit()
#             login_user(new_user, remember=True)
#             flash('Tạo tài khoản thành công!', category='success')
#             return redirect(url_for('views.home'))

#     return render_template("signup.html", user=current_user)

@auth.route('/create-user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.Role != 'Admin':
        flash('Bạn không có quyền truy cập trang này.', category='error')
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        fullname = request.form.get('fullname')
        password = request.form.get('password')
        email = request.form.get('email')
        role = request.form.get('role')  # 'Employee' hoặc 'Manager'
        phone = request.form.get('phone')
        confirmpassword = request.form.get('confirmpassword')

        existing = Account.query.filter_by(username=username).first()
        email_check = Account.query.filter_by(email=email).first()

        if existing:
            flash('Tài khoản đã tồn tại.', category='error')
        elif email_check:
            flash('Email đã được sử dụng.', category='error')
        elif len(username) < 4:
            flash('Tên đăng nhập phải có ít nhất 4 ký tự.', category='error')
        elif len(fullname) < 3:
            flash('Họ và tên phải có ít nhất 3 ký tự.', category='error')
        elif len(password) < 7:
            flash('Mật khẩu phải có ít nhất 7 ký tự.', category='error')
        elif password != confirmpassword:
            flash("Mật khẩu không khớp.", category='error')
        elif role not in ['Admin', 'Manager', 'User', 'Employee']:
            flash("Vai trò không hợp lệ!", category='error')
        else:
            new_user = Account(
                email=email,
                username=username,
                fullname=fullname,
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                Role=role,
                phonenumber=phone,
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Tạo tài khoản thành công!', category='success')

            # Điều hướng theo Role
            if role == 'Admin':
                return redirect(url_for('views.admin_dashboard'))
            elif role == 'Manager':
                return redirect(url_for('views.home'))
            else:
                return redirect(url_for('views.home'))

    return render_template("create_user.html", user=current_user)
