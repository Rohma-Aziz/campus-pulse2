from dotenv import load_dotenv
import os
import click
from flask import Flask, g, redirect, render_template, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect          

load_dotenv()
db = SQLAlchemy()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)

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
    app.config['ADMIN_ONLY_CATEGORIES'] = {'Notices'}

    db.init_app(app)
    csrf.init_app(app)

    # Models aur Blueprints import karein
    from app.models import CATEGORIES, DEPARTMENTS, User
    from app.auth import auth_bp
    from app.feed import feed_bp
    from app.admin import admin_bp
    from app.feedback import feedback_bp
    from app.routes.analytics_routes import analytics_bp
    
    # Blueprints ko sirf ek baar register karein
    app.register_blueprint(auth_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(analytics_bp)

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
        # Agar user pehle se logged in hai, tabhi role ke hisab se dashboard par bhejo
        if 'user_id' in session:
            # Agar g.user available hai toh role check karo
            if g.get('user') and g.user.is_admin:
                return redirect(url_for('admin.dashboard'))
            elif g.get('user'):
                return redirect(url_for('feedback.dashboard'))
        
        # Agar logged in nahi hai, toh seedha home.html render karo (redirect mat karo!)
        return render_template('home.html')
    # Navigation Diagram ke mutabiq Entry Point & Role Check
    # Seedha real login page par bhej dega # Naya index.html landing page

    @app.cli.command('create-admin')
    @click.argument('email')
    @click.argument('name')
    @click.password_option()
    def create_admin(email, name, password):
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