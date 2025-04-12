from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from .models import Account
from . import db

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = Account.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            flash('Đăng nhập thành công!', category='success')
            login_user(user, remember=True)
            return redirect(url_for('views.home'))
        else:
            flash('Email hoặc mật khẩu không chính xác.', category='error')

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
        email = request.form.get('email')
        first_name = request.form.get('FirstName')
        last_name = request.form.get('LastName')
        password = request.form.get('password1')
        confirm_password = request.form.get('password2')

        user = Account.query.filter_by(email=email).first()
        if user:
            flash('Email đã tồn tại.', category='error')
        elif len(email) < 4:
            flash('Email phải có ít nhất 4 ký tự.', category='error')
        elif len(first_name) < 2:
            flash('Tên phải có ít nhất 2 ký tự.', category='error')
        elif len(last_name) < 2:
            flash('Tên phải có ít nhất 2 ký tự.', category='error')
        elif password != confirm_password:
            flash("Mật khẩu không khớp.", category='error')
        elif len(password) < 7:
            flash('Mật khẩu phải có ít nhất 7 ký tự.', category='error')
        else:
            # Thêm user vào database
            new_user = Account(
                email=email,
                firstname=first_name,
                lastname=last_name,
                password=generate_password_hash(password, method='pbkdf2:sha256')
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('Tạo tài khoản thành công!', category='success')
            return redirect(url_for('views.home'))

    return render_template("signup.html", user=current_user)
