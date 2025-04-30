from flask_login import UserMixin
from datetime import datetime

class Account(UserMixin):
    def __init__(self, data):
        self.id = str(data.get('_id'))
        self.Username = data.get('Username')
        self.Password = data.get('Password')
        self.Fullname = data.get('Fullname')
        self.Email = data.get('Email')
        self.PhoneNumber = data.get('PhoneNumber')
        self.Role = data.get('Role')
        self.CreateAt = data.get('CreateAt')
        self.IsActive = data.get('IsActive', True)

    def get_id(self):
        return self.id

class LoginRecords:
    def __init__(self, data):
        self.id = str(data.get('_id'))
        self.account_ref = str(data.get('AccountRef'))  # ObjectId dưới dạng string
        self.login_time = data.get('LoginTime', datetime.utcnow())
        self.ip_address = data.get('IPAddress', None)