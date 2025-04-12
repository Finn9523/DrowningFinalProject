from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class Account(db.Model, UserMixin):
    __tablename__ = 'Account'

    id = db.Column('Id', db.Integer, primary_key=True)  # Tên cột đúng với SQL Server
    email = db.Column('email', db.String(50), nullable=False)
    password = db.Column('password', db.String(255), nullable=False)  # Lưu hash mật khẩu
    firstname = db.Column('firstname', db.String(20), nullable=False)
    lastname = db.Column('lastname', db.String(20), nullable=False)