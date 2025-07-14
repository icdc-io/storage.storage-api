"""
Account Router module
"""

from flask import Blueprint, request, jsonify
from werkzeug.exceptions import HTTPException

import app.lib.auth as auth
from app.controllers import account_controller as controller
from app.lib.request_utils import process_response, request_json, handle_exception

account_management = Blueprint(name="account_management", import_name=__name__)
account_management.register_error_handler(HTTPException, handle_exception)


@account_management.route("", methods=["GET"])
@auth.rbac("accounts.list")
def get_accounts(subject):
    """
    Get all accounts for the authenticated operator.
    """
    return controller.get_accounts_all(subject), 200


@account_management.route("", methods=["POST"])
@auth.rbac("accounts.create")
def create_account(subject):
    """
    Create a new account using the provided data.
    """
    return controller.create_account(subject), 201


@account_management.route("/<account_name>", methods=["GET"])
@auth.rbac("accounts.get")
def get_account(subject, account_name):
    """
    Retrieve information for a specific account.
    """
    return controller.get_account_info(subject, account_name), 200


@account_management.route("/<account_name>", methods=["PUT"])
@auth.rbac("accounts.update")
def update_account(subject, account_name):
    """
    Create a new account using the provided data.
    """

    return controller.update_account(subject, account_name), 200


@account_management.route("/<account_name>", methods=["DELETE"])
@auth.rbac("accounts.delete")
def delete_account(subject, account_name):
    """
    Delete an account. Validates that the request method is DELETE and ensures that
    only authorized users can delete their account.

    Returns:
        A tuple of the response message and HTTP status code.
    """
    return controller.delete_account(subject, account_name), 204


@account_management.route("/<account_name>/usage", methods=["GET"])
@auth.rbac("accounts.usage")
def get_account_usage(subject, account_name):
    """
    Retrieves the usage data for the specified account.
    """
    return controller.get_account_usage(subject, account_name), 200
