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
@auth.operator_required
def get_account(*args, **kwargs):
    """
    Retrieve information for a specific account.

    This function is decorated with `@auth.operator_required` to ensure
    that only authenticated operators can access this route.

    Args:
        args (tuple): Variable length argument list.
        kwargs (dict): Arbitrary keyword arguments.

    Returns:
        The account data after processing.
    """
    # Extract the account name from the keyword arguments
    account_name = kwargs.get("account_name")

    # Retrieve the account information using the `get_account_info` function
    # from the `account_controller` module. Pass the `account_name` as an argument.
    account_data = controller.get_account_info(account_name)

    # Process the account data and return the processed response.
    # The `process_response` function is expected to be defined in the codebase.
    # It is not provided in this snippet.
    return process_response(account_data)


@account_management.route("", methods=["GET"])
@au.rbac("accounts.list")
def get_accounts(*args, **kwargs):
    """
    Get all accounts for the authenticated operator.

    This function is decorated with `@auth.operator_required` to ensure
    that only authenticated operators can access this route.

    Args:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        The accounts data after processing.
    """
    # Call the `get_accounts_all` function from the `account_controller` module.
    # Pass the `*args` and `**kwargs` to the function.
    # Return the processed response.
    return process_response(controller.get_accounts_all(*args, **kwargs))


@account_management.route("", methods=["POST"])
@auth.operator_required
def create_account(*args, **kwargs):
    """
    Create a new account using the provided data.

    Args:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        The response from the account creation process.
    """

    return process_response(controller.create_account(request_json(request)))


@account_management.route("", methods=["PUT"])
@auth.operator_required
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
@auth.operator_required
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
