from flask import Blueprint

from app.controllers.health_check_controller import health_check

health_check_bp = Blueprint("health_check", __name__)


@health_check_bp.route("/api/up", methods=["GET"])
def health_check_route():
    return health_check()
