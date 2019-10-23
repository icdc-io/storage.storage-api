"""
Pools Router module
"""
from flask import Blueprint, request

import app.controllers.auth as auth
from app.controllers import pools_controller as controller
from app.lib.request_utils import process_response, query

pools = Blueprint(name="pools", import_name=__name__)


@pools.route("", methods=["GET"])
@auth.account_auth_required
def get_pools(*args, **kwargs):
    """
    A function to handle GET requests for pools, with authentication required.
    """
    kwargs["filter"] = query(request)
    data = controller.get_pools(*args, **kwargs)
    return process_response(data)
