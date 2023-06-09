import os
from flask import Flask
import logging

from dotenv import dotenv_values
env_values = dotenv_values('.env')

SECRET_KEY = env_values['SECRET_KEY']

def create_app():
    logging.basicConfig(filename='myapp.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

    app = Flask(__name__)

    app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.secret_key = SECRET_KEY

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    from .views import views
    app.register_blueprint(views, url_prefix='/')

    return app