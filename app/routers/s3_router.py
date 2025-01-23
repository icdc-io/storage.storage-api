"""
S3 Router module
"""
from flask import Blueprint, request, jsonify
from werkzeug.exceptions import HTTPException

import app.controllers.auth as auth
from app.lib import auth as au
from app.controllers import s3_controller as controller
from app.controllers.s3 import quotas_controller
from app.lib.request_utils import process_response, query, request_json, handle_exception

s3 = Blueprint(name="s3", import_name=__name__)
s3.register_error_handler(HTTPException, handle_exception)


@s3.route("/limits", methods=["GET"])
@au.rbac("s3.limits.list")
def get_s3_limits(*args, **kwargs):
    return controller.get_s3_limits(*args, **kwargs), 200


@s3.route("/users", methods=["POST"])
@auth.account_auth_required
def create_s3_user(*args, **kwargs):
    """
    Create an S3 user for the specified account.

    :param args: additional positional arguments
    :param kwargs: additional keyword arguments
    :return: the processed response data
    """
    kwargs["body"] = request_json(request)
    return controller.create_s3_user(*args, **kwargs), 201


@s3.route("/users", methods=["GET"])
@auth.account_auth_required
def get_account_s3_users(*args, **kwargs):
    """
    Get account S3 users.

    Args:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        The processed response data.
    """
    return jsonify(controller.get_account_s3_users(*args, **kwargs)), 200


@s3.route("/users/<id>", methods=["GET"])
@auth.account_auth_required
def get_s3_user(*args, **kwargs):
    return controller.get_s3_user(*args, **kwargs), 200


@s3.route("/users/<id>", methods=["DELETE"])
@auth.account_auth_required
def delete_s3_user(*args, **kwargs):
    return controller.delete_s3_user(*args, **kwargs), 204


@s3.route("/users/<id>", methods=["PUT"])
@auth.account_auth_required
def update_s3_user(*args, **kwargs):
    kwargs["body"] = request_json(request)
    return controller.update_s3_user(*args, **kwargs), 200


@s3.route("/buckets", methods=["POST"])
@auth.account_auth_required
def create_bucket(*args, **kwargs):
    kwargs["body"] = request_json(request)

    return controller.create_bucket(*args, **kwargs), 201


@s3.route("/buckets", methods=["GET"])
@auth.account_auth_required
def get_bucket_info(*args, **kwargs):
    kwargs["user_name"] = query(request).get("user_name")
    return controller.get_buckets_info(*args, **kwargs), 200


@s3.route("/buckets/<path:path>", methods=["PUT"])
@auth.account_auth_required
def update_bucket(*args, **kwargs):
    kwargs["body"] = request_json(request)
    return controller.update_bucket(*args, **kwargs), 200


@s3.route("/buckets/<path:path>", methods=["DELETE"])
@auth.account_auth_required
def delete_bucket(*args, **kwargs):
    return controller.delete_bucket(*args, **kwargs), 204


@s3.route("/users/<user_id>/keys", methods=["POST"])
@auth.account_auth_required
def regenerate_keys(*args, **kwargs):
    return controller.regenerate_keys(*args, **kwargs), 201


@s3.route("/quotas", methods=["GET"])
@au.rbac("s3.quotas.list")
def get_account_s3_quota(subject):
    """
    Get the S3 quota for a specific account.

    Parameters:
    *args: Variable length argument list.
    **kwargs: Arbitrary keyword arguments.

    Returns:
    The response data after processing.
    """
    return quotas_controller.index(subject), 200


@s3.route("/quotas", methods=["POST"])
@auth.account_admin_required
def set_account_s3_quota(*args, **kwargs):
    """
    Route for setting the S3 quotas for a specific account.
    Takes in parameters *args and **kwargs.
    Returns the processed response data.
    """
    kwargs["body"] = request_json(request)
    return quotas_controller.create(*args, **kwargs), 201


@s3.route("/quotas/<id>", methods=["PUT"])
@auth.account_auth_required
def update_s3_quota(*args, **kwargs):
    kwargs["body"] = request_json(request)
    return quotas_controller.update(*args, **kwargs), 200


@s3.route("/quotas/<id>", methods=["DELETE"])
@auth.account_auth_required
def destroy_s3_quota(*args, **kwargs):
    return quotas_controller.destroy(*args, **kwargs), 204
