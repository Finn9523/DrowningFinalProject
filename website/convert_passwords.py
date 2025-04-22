import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from website import create_app, db
from website.models import Account
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    users = Account.query.all()
    count = 0

    for user in users:
        # Kiểm tra xem mật khẩu đã được mã hóa hay chưa (ví dụ mật khẩu thô ngắn hơn 60 ký tự)
        if len(user.password) < 60:
            print(f"🔐 Mã hóa mật khẩu cho user: {user.username}")
            user.password = generate_password_hash(user.password)
            count += 1

    db.session.commit()
    print(f"✅ Đã mã hóa mật khẩu cho {count} tài khoản.")
