"""
Pools Router module
"""
from flask import Blueprint
from werkzeug.exceptions import HTTPException

from app.rbac import rbac
from app.controllers import pools_controller as controller
from app.lib.request_utils import handle_exception

pools = Blueprint(name="pools", import_name=__name__)
pools.register_error_handler(HTTPException, handle_exception)


@pools.route("", methods=["GET"])
@rbac.allow("pools.list")
def get_pools(*args, **kwargs):
    """
    A function to handle GET requests for pools, with authentication required.
    """
    return controller.get_pools(*args, **kwargs)
