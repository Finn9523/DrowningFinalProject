from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class Account(db.Model, UserMixin):
    __tablename__ = 'Account'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    fullname = db.Column(db.String(50), nullable=False)
    phonenumber = db.Column(db.String(20), nullable=True, unique=True)
    role = db.Column(db.String(20), nullable=False, default='Employee')  # Các giá trị: Admin, Manager, Employee
    # create_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def is_admin(self):
        return self.role == 'Admin'

    def is_manager(self):
        return self.role == 'Manager'

    def is_employee(self):
        return self.role == 'Employee'