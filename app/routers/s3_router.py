"""
S3 Router module
"""
from flask import Blueprint, request, jsonify
from werkzeug.exceptions import HTTPException

from app.lib import auth as auth
from app.controllers import s3_controller as controller
from app.controllers.s3 import quotas_controller
from app.lib.request_utils import process_response, query, request_json, handle_exception

s3 = Blueprint(name="s3", import_name=__name__)
s3.register_error_handler(HTTPException, handle_exception)


@s3.route("/limits", methods=["GET"])
@auth.rbac("s3.limits.list")
def get_s3_limits(subject):
    return controller.get_s3_limits(subject), 200


@s3.route("/users", methods=["POST"])
@auth.rbac("s3.users.create")
def create_s3_user(subject):
    """
    Create an S3 user for the specified account.
    """
    return controller.create_s3_user(subject), 201


@s3.route("/users", methods=["GET"])
@auth.rbac("s3.users.list")
def get_account_s3_users(subject):
    """
    Get account S3 users.
    """
    return jsonify(controller.get_account_s3_users(subject)), 200


@s3.route("/users/<user_id>", methods=["GET"])
@auth.rbac("s3.users.get")
def get_s3_user(subject, user_id):
    return controller.get_s3_user(subject, user_id), 200


@s3.route("/users/<user_id>", methods=["DELETE"])
@auth.rbac("s3.users.delete")
def delete_s3_user(subject, user_id):
    return controller.delete_s3_user(subject, user_id), 204


@s3.route("/users/<user_id>", methods=["PUT"])
@auth.rbac("s3.users.update")
def update_s3_user(subject, user_id):
    return controller.update_s3_user(subject, user_id), 200


@s3.route("/buckets", methods=["POST"])
@auth.rbac("s3.buckets.create")
def create_bucket(subject):
    return controller.create_bucket(subject), 201


@s3.route("/buckets", methods=["GET"])
@auth.rbac("s3.buckets.list")
def list_buckets(subject):
    return controller.list_buckets(subject), 200


@s3.route("/buckets/<path:path>", methods=["PUT"])
@auth.rbac("s3.buckets.update")
def update_bucket(subject, path):
    return controller.update_bucket(subject, path), 200


@s3.route("/buckets/<path:path>", methods=["DELETE"])
@auth.rbac("s3.buckets.delete")
def delete_bucket(subject, path):
    return controller.delete_bucket(subject, path), 204


@s3.route("/users/<user_id>/keys", methods=["POST"])
@auth.rbac("s3.users.regenerate-keys")
def regenerate_keys(subject, user_id):
    return controller.regenerate_keys(subject, user_id), 201


@s3.route("/quotas", methods=["GET"])
@auth.rbac("s3.quotas.list")
def get_account_s3_quota(subject):
    """
    Get the S3 quota for a specific account.
    """
    return quotas_controller.index(subject), 200


@s3.route("/quotas", methods=["POST"])
@auth.rbac("s3.quotas.create")
def set_account_s3_quota(subject):
    """
    Route for setting the S3 quotas for a specific account.
    Takes in parameters *args and **kwargs.
    Returns the processed response data.
    """
    return quotas_controller.create(subject), 201


@s3.route("/quotas/<id>", methods=["PUT"])
@auth.rbac("s3.quotas.update")
def update_s3_quota(subject, id):
    return quotas_controller.update(subject, id), 200


@s3.route("/quotas/<id>", methods=["DELETE"])
@auth.rbac("s3.quotas.delete")
def destroy_s3_quota(subject, id):
    return quotas_controller.destroy(subject, id), 204
