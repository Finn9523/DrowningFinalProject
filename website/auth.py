from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from datetime import datetime
import pytz
from bson import ObjectId

from .models import Account
from . import mongo  # Mongo client from __init__.py

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user_doc = mongo.db.accounts.find_one({'Username': username})

        if user_doc:
            if not user_doc.get('IsActive', True):
                flash('Tài khoản đã bị vô hiệu hóa.', 'error')
                return redirect(url_for('auth.login'))

            if check_password_hash(user_doc['Password'], password):
                flash('Đăng nhập thành công!', category='success')
                user = Account(user_doc)
                login_user(user, remember=True)

                login_time = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
                mongo.db.login_records.insert_one({
                    'AccountRef': ObjectId(user.id),
                    'LoginTime': login_time
                })

                if user.Role == 'Admin':
                    return redirect(url_for('views.admin_dashboard'))
                elif user.Role == 'Manager':
                    return redirect(url_for('views.home'))  # vì home là dành cho manager
                else:
                    flash('Bạn không có quyền truy cập.', 'error')
                    return redirect(url_for('auth.logout'))
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
        role = request.form.get('role')
        phone = request.form.get('phone')
        confirmpassword = request.form.get('confirmpassword')

        if mongo.db.accounts.find_one({'Username': username}):
            flash('Tài khoản đã tồn tại.', category='error')
        elif mongo.db.accounts.find_one({'Email': email}):
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
            mongo.db.accounts.insert_one({
                'Username': username,
                'Fullname': fullname,
                'Email': email,
                'Role': role,
                'PhoneNumber': phone,
                'Password': generate_password_hash(password, method='pbkdf2:sha256'),
                'IsActive': True,
                'CreateAt': datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
            })
            flash('Tạo tài khoản thành công!', category='success')

            if role == 'Admin':
                return redirect(url_for('views.admin_dashboard'))
            else:
                return redirect(url_for('views.home'))

    return render_template("create_user.html", user=current_user)
