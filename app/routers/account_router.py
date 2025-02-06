"""
Account Router module
"""

from flask import Blueprint, request, jsonify
from werkzeug.exceptions import HTTPException

import app.controllers.auth as auth
import app.lib.auth as au
from app.controllers import account_controller as controller
from app.lib.request_utils import process_response, request_json, handle_exception

account_management = Blueprint(name="account_management", import_name=__name__)
account_management.register_error_handler(HTTPException, handle_exception)


@account_management.route("/<account_name>", methods=["GET"])
@au.rbac("accounts.get")
def get_account(subject, account_name):
    """
    Retrieve information for a specific account.
    """
    return controller.get_account_info(account_name)


@account_management.route("", methods=["GET"])
@au.rbac("accounts.list")
def get_accounts(subject):
    """
    Get all accounts for the authenticated operator.
    """
    return controller.get_accounts_all(subject), 200


@account_management.route("", methods=["POST"])
@au.rbac("accounts.create")
def create_account(subject):
    """
    Create a new account using the provided data.
    """
    return controller.create_account(subject), 201


@account_management.route("", methods=["PUT"])
@au.rbac("accounts.update")
def update_account(*args, **kwargs):
    """
    Create a new account using the provided data.

    Args:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        The response from the account creation process.
    """

    return process_response(controller.update_account(request_json(request)))


@account_management.route("/<account_name>", methods=["DELETE"])
@au.rbac("accounts.delete")
def delete_account(*args, **kwargs):
    """
    Delete an account. Validates that the request method is DELETE and ensures that
    only authorized users can delete their account.

    Returns:
        A tuple of the response message and HTTP status code.
    """
    return process_response(controller.delete_account(*args, **kwargs))


@account_management.route("/<account_name>/iscsi/snapshots", methods=["GET"])
@auth.account_auth_required
def get_account_snapshots(*args, **kwargs):
    """
    Get account snapshots for a given account name using the iSCSI protocol.
    """
    return process_response(controller.get_account_snapshots(*args, **kwargs))


@account_management.route("/<account_name>/usage", methods=["GET"])
@auth.account_auth_required
def get_account_usage(*args, **kwargs):
    """
    Retrieves the usage data for the specified account.

    Args:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        The processed response data.
    """
    return process_response(controller.get_account_usage(*args, **kwargs))
