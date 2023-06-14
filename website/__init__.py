from flask import Flask, redirect, url_for, request, session
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from flask_babel import Babel, gettext as _
from deep_translator import GoogleTranslator

db = SQLAlchemy()
DB_NAME = "db.sqlite3"


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dfsdkhfak dfasjdkfhk'  # secret key for cookies
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['BABEL_SUPPORTED_LANGUAGES'] = ['en', 'vi']
    app.config['BABEL_DEFAULT_LOCALE'] = 'en'

    @app.before_first_request
    def setup_session():
        session['language'] = 'en'

    db.init_app(app)

    from .routes import main
    from .auth import auth

    app.register_blueprint(main, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import User

    with app.app_context():
        db.create_all()

    def get_locale():
        return session.get('language', 'en')
    
    
    babel = Babel(app)
    babel.init_app(app, locale_selector=get_locale)

    def translating(text):
        if session['language'] == 'vi':
            translation = GoogleTranslator(source='en', target='vi').translate(text)
        else:
            translation = text
        
        return translation

    app.jinja_env.globals.update(translate=translating)

    @app.route('/change_language')
    def change_language():
        if session['language'] == 'en':
            session['language']  = 'vi'
        else:
            session['language'] = 'en'
        if request.referrer.endswith('/search'):
            return redirect(url_for('main.search'))
        if request.referrer.endswith('/search_recipe'):
            return redirect(url_for('main.search_recipe'))
        
        return redirect(request.referrer or url_for('main.index'))

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app
