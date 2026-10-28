from dotenv import load_dotenv
import os
import click
from flask import Flask, g, redirect, render_template, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect          

load_dotenv()
db = SQLAlchemy()
csrf = CSRFProtect()
db_url = os.environ.get("DATABASE_URL", "sqlite:///campus_pulse.db")
def create_app():
    app = Flask(__name__)

    # Configuration (settings stay here, no config.py needed)
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": {"ssl": {"ca": os.path.join(base_dir, "ca.pem")}}
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['POSTS_PER_PAGE'] = 10
    # Only admins can post in these categories. Use set() to let students post notices too.
    app.config['ADMIN_ONLY_CATEGORIES'] = {'Notices'}

    db.init_app(app)
    csrf.init_app(app)

    from app.models import CATEGORIES, DEPARTMENTS, User
    from app.auth import auth_bp
    from app.feed import feed_bp
    from app.admin import admin_bp
    from app.feedback import feedback_bp  
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(feedback_bp)

    @app.before_request
    def load_user():
        user_id = session.get('user_id')
        g.user = db.session.get(User, user_id) if user_id else None
        if user_id and g.user is None:
            session.clear()

    @app.context_processor
    def inject_globals():
        return {'current_user': g.get('user'), 'CATEGORIES': CATEGORIES, 'DEPARTMENTS': DEPARTMENTS}

    @app.route('/')
    def home():
        if g.user:
            target = 'admin.moderation' if g.user.is_admin else 'feed.view_feed'
            return redirect(url_for(target))
        return render_template('home.html')

    @app.cli.command('create-admin')
    @click.argument('email')
    @click.argument('name')
    @click.password_option()
    def create_admin(email, name, password):
        """Create an admin: flask --app <your_entry_file> create-admin EMAIL NAME"""
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            click.echo('A user with that email already exists.')
            return
        admin = User(name=name.strip(), email=email, role='admin', department='Admin')
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f'Admin created: {email}')

    with app.app_context():
        db.create_all()

    return app