"""
Config Router module
"""
from flask import Blueprint
from werkzeug.exceptions import HTTPException

from app.lib import auth
from app.controllers import config_controller as controller
from app.lib.request_utils import handle_exception

config = Blueprint(name="config_management", import_name=__name__)
config.register_error_handler(HTTPException, handle_exception)


@config.route("/<config_id>/gateways", methods=["GET"])
@auth.rbac("iscsi.gateways.list")
def get_config_gateways(subject, config_id):
    return controller.get_config_gateways(subject, config_id)


@config.route("/<config_id>/gateways", methods=["POST"])
@auth.rbac("iscsi.gateways.create")
def set_config_gateways(subject, config_id):
    return controller.set_config_gateway(subject, config_id)
