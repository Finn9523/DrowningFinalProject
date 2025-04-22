from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
from .models import Account, LoginRecords
from . import db

auth = Blueprint('auth', __name__)

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

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đăng xuất thành công.', category='success')
    return redirect(url_for('auth.login'))

@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        username = request.form.get('username')
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        phone = request.form.get('phone')
        role = request.form.get('role') or 'Employee'  # Mặc định là 'User' nếu không chọn
        password = request.form.get('password1')
        confirm_password = request.form.get('password2')

        # Kiểm tra thông tin hợp lệ
        user = Account.query.filter_by(username=username).first()
        email_check = Account.query.filter_by(email=email).first()

        if user:
            flash('Tên đăng nhập đã tồn tại.', category='error')
        elif email_check:
            flash('Email đã được sử dụng.', category='error')
        elif len(username) < 4:
            flash('Tên đăng nhập phải có ít nhất 4 ký tự.', category='error')
        elif len(fullname) < 3:
            flash('Họ và tên phải có ít nhất 3 ký tự.', category='error')
        elif len(password) < 7:
            flash('Mật khẩu phải có ít nhất 7 ký tự.', category='error')
        elif password != confirm_password:
            flash("Mật khẩu không khớp.", category='error')
        elif role not in ['Admin', 'Manager', 'User', 'Employee']:
            flash("Vai trò không hợp lệ!", category='error')
        else:
            # Mã hóa mật khẩu và tạo tài khoản mới
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = Account(
                username=username,
                password=hashed_password,
                Fullname=fullname,
                email=email,
                PhoneNumber=phone,
                Role=role
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('Tạo tài khoản thành công!', category='success')

            # Điều hướng theo Role
            if role == 'Admin':
                return redirect(url_for('views.admin_dashboard'))
            elif role == 'Manager':
                return redirect(url_for('views.home'))
            else:
                return redirect(url_for('views.home'))

    return render_template("signup.html", user=current_user)
