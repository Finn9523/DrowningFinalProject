from datetime import datetime
from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class Account(db.Model, UserMixin):
    __tablename__ = 'Account'

    Id = db.Column(db.Integer, primary_key=True)  # Đúng tên cột SQL Server
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    Fullname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False, unique=True)
    PhoneNumber = db.Column(db.String(15), nullable=True, unique=True)
    Role = db.Column(db.String(20), nullable=False)  # 'Admin', 'Manager', 'Employee'
    CreateAt = db.Column(db.DateTime(timezone=True), server_default=func.now())
    is_active = db.Column(db.Boolean, default=True)  # 1: Active, 0: Inactive   

    # Quan hệ với bảng LoginRecords
    login_records = db.relationship('LoginRecords', backref='account', lazy=True)
     # Thêm phương thức get_id để Flask-Login sử dụng
    def get_id(self):
        return str(self.Id)

# Model lưu lịch sử đăng nhập
class LoginRecords(db.Model):
    __tablename__ = 'LoginRecords'

    RecordId = db.Column(db.Integer, primary_key=True)
    AccountId = db.Column(db.Integer, db.ForeignKey('Account.Id'), nullable=False)  # Đúng với CSDL
    LoginTime = db.Column(db.DateTime, default=datetime.utcnow)  # Thời gian đăng nhập
    IPAddress = db.Column(db.String(50), nullable=True)  # Địa chỉ IP của user

# Model Camera
class Camera(db.Model):
    __tablename__ = 'Cameras'
    
    CameraId = db.Column(db.Integer, primary_key=True)  # Đổi thành CameraId để khớp SQL Server
    Location = db.Column(db.String(255), nullable=False)
    StreamURL = db.Column(db.String(500), nullable=False)
    Status = db.Column(db.String(50), nullable=False, default='Active')


# Model Alert
class Alert(db.Model):
    __tablename__ = 'Alerts'
    
    AlertId = db.Column(db.Integer, primary_key=True)
    CameraId = db.Column(db.Integer, db.ForeignKey('Cameras.CameraId', ondelete="CASCADE"), nullable=False)
    DetectedAt = db.Column(db.DateTime, default=db.func.current_timestamp())
    Status = db.Column(db.String(50), nullable=False, default='Pending')
