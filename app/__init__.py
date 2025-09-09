from flask import Flask
from flask_cors import CORS

from . import consts
from .database import db, migrate
from .loggers import log
from .routers.account_router import account_management
from .routers.health_check import health_check_bp
from .routers.iscsi_router import iscsi
from .routers.pools_router import pools
from .routers.s3_router import s3
from .seed import seed as seed_data


def create_app():
    """
    Create and configure the Flask application.
    """
    app = Flask(__name__, template_folder="tmp")
    # we can set level only after consts are imported
    log.setLevel(consts.LOG_LEVEL)
    db_conn = (
        f"postgresql://"
        f"{consts.DATABASE_USERNAME}:{consts.DATABASE_PASSWORD}@"
        f"{consts.DATABASE_HOST}:{consts.DATABASE_PORT}/"
        f"{consts.DATABASE_NAME}"
    )

    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = db_conn
    # app.config.from_object(config)

    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    app.register_blueprint(health_check_bp)

    app.register_blueprint(account_management, url_prefix="/api/v2/accounts")
    app.register_blueprint(iscsi, url_prefix="/api/v2/iscsi")
    app.register_blueprint(s3, url_prefix="/api/v2/s3")
    app.register_blueprint(pools, url_prefix="/api/v2/pools")
    CORS(app, resources={r"/*": {"origins": "*"}})

    db.init_app(app)
    migrate.init_app(app, db)

    app.cli.command("seed")(seed_data)

    return app
