import os
from flask import Flask

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'esports_hub.sqlite'),
        ALLOWED_EMAIL_DOMAINS=['.edu', 'university.edu'],
    )

    if test_config is None:
        app.config.from_pyinstance_file('config.py', silent=True)
    else:
        app.config.update(test_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    from app import db
    db.init_app(app)

    from app import auth
    app.register_blueprint(auth.bp)

    from app import main
    app.register_blueprint(main.bp)

    from app import admin
    app.register_blueprint(admin.bp)

    from app import teams
    app.register_blueprint(teams.bp)

    from app import calendar_bp
    app.register_blueprint(calendar_bp.bp)

    from app import analytics
    app.register_blueprint(analytics.bp)

    @app.route('/')
    def index():
        return main.landing()

    return app
