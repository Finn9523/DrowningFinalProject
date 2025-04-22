from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()

# 🔹 Cấu hình kết nối SQL Server (Thay đổi theo thông tin của bạn)
SERVER = 'HUYNH-TAN'
DATABASE = 'Iot'

DB_URI = f"mssql+pyodbc:///?odbc_connect=" + \
         f"DRIVER=ODBC+Driver+17+for+SQL+Server;SERVER={SERVER};DATABASE={DATABASE};Trusted_Connection=yes;"

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'thienngocluong'
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from .models import Account  # Import sau khi db.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Account.query.get(int(user_id))  # Load user từ database

    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    with app.app_context():
        db.create_all()

    return app
