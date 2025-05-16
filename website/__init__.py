from flask import Flask
from flask_login import LoginManager
import os
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from website.frame_receiver import receive_frames
import threading

mongo = PyMongo()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['MONGO_URI'] = os.getenv('MONGO_URI')

    mongo.init_app(app)
    login_manager.init_app(app)

    from .models import Account

    @login_manager.user_loader
    def load_user(user_id):
        try:
            obj_id = ObjectId(user_id)
        except InvalidId:
            return None  # Không crash
        user_doc = mongo.db.accounts.find_one({'_id': obj_id})
        return Account(user_doc) if user_doc else None

    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    threading.Thread(target=receive_frames, daemon=True).start()

    return app
