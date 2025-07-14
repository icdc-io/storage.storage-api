"""
Gateway Router module
"""
from flask import Blueprint, request, abort

from app.lib import auth
from app.controllers import gateway_controller as controller
from app.lib.request_utils import process_response, request_json

gw = Blueprint(name="gateway_management", import_name=__name__)


@gw.route("/<gateway_id>", methods=["GET"])
@auth.rbac("iscsi.gateways.get")
def get_gateway(subject, gateway_id):  # pylint: disable=missing-function-docstring
    return controller.get_gateway(subject, gateway_id)


@gw.route("/", methods=["POST"])
@auth.rbac("iscsi.gateways.create")
def set_gateway(subject):  # pylint: disable=missing-function-docstring
    return controller.set_gateway(subject)
