"""
Config Router module
"""
from flask import Blueprint, request

import app.controllers.auth as auth
from app.controllers import config_controller as controller
from app.lib.request_utils import process_response, request_json

config = Blueprint(name="config_management", import_name=__name__)


@config.route("/<config_id>/gateways", methods=["GET"])
@auth.account_auth_required
def get_config_gateways(*args, **kwargs):  # pylint: disable=missing-function-docstring
    data = controller.get_config_gateways(*args, **kwargs)
    return process_response(data)


@config.route("/<config_id>/gateways", methods=["POST"])
@auth.account_auth_required
def set_config_gateways(*args, **kwargs):  # pylint: disable=missing-function-docstring
    kwargs["body"] = request_json(request)
    data = controller.set_config_gateway(*args, **kwargs)
    return process_response(data)
