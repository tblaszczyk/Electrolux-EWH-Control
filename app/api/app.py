"""
api/app.py
Flask app factory — tylko routing.
Zero logiki sterującej.
"""

from flask import Flask
from flask_cors import CORS


def create_app(config: dict) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.get("secret_key", "dev-secret")
    CORS(app, supports_credentials=True)

    # Zarejestruj blueprinty
    from api.routes.auth_routes import bp as auth_bp
    from api.routes.users      import bp as users_bp
    from api.routes.status      import bp as status_bp
    from api.routes.control     import bp as control_bp
    from api.routes.schedule    import bp as schedule_bp
    from api.routes.config      import bp as config_bp, set_config_ref
    from api.routes.usage       import bp as usage_bp
    from api.routes.pump        import bp as pump_bp
    from api.routes.energy      import bp as energy_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(control_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(usage_bp)
    app.register_blueprint(pump_bp)
    app.register_blueprint(energy_bp)

    # Przekaż referencję do configu (do GET/PATCH /api/config)
    set_config_ref(config)

    return app
