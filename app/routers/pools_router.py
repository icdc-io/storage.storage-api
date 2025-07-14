"""
Pools Router module
"""
from flask import Blueprint, request
from werkzeug.exceptions import HTTPException

from app.lib import auth
from app.controllers import pools_controller as controller
from app.lib.request_utils import handle_exception

pools = Blueprint(name="pools", import_name=__name__)
pools.register_error_handler(HTTPException, handle_exception)


@pools.route("", methods=["GET"])
@auth.rbac("pools.list")
def get_pools(*args, **kwargs):
    """
    A function to handle GET requests for pools, with authentication required.
    """
    return controller.get_pools(*args, **kwargs)
