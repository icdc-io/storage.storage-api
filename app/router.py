"""
Main Router module
"""

from flask_cors import CORS


# Routers import
from app.routers.account_router import account_management
from app.routers.health_check import health_check_bp
from app.routers.iscsi_router import iscsi
from app.routers.pools_router import pools
from app.routers.s3_router import s3
from main import flask_app

# Enable CORS for all routes
CORS(flask_app, resources={r"/*": {"origins": "*"}})

flask_app.register_blueprint(health_check_bp)

flask_app.register_blueprint(account_management, url_prefix="/api/v2/accounts")
flask_app.register_blueprint(iscsi, url_prefix="/api/v2/iscsi")
flask_app.register_blueprint(s3, url_prefix="/api/v2/s3")
flask_app.register_blueprint(pools, url_prefix="/api/v2/pools")
