"""
Gateway Router module
"""
from flask import Blueprint, request

import app.controllers.auth as auth
from app.controllers import gateway_controller as controller
from app.lib.request_utils import process_response, request_json

gw = Blueprint(name="gateway_management", import_name=__name__)


@gw.route("/<gateway_id>", methods=["GET"])
@auth.account_auth_required
def get_gateway(*args, **kwargs):  # pylint: disable=missing-function-docstring
    data = controller.get_gateway(*args, **kwargs)
    return process_response(data)


gw.route("/", methods=["POST"])


@auth.account_auth_required
def set_gateway(*args, **kwargs):  # pylint: disable=missing-function-docstring
    kwargs["body"] = request_json(request)
    data = controller.set_gateway(*args, **kwargs)
    return process_response(data)
