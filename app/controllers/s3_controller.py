"""
S3 Controller
"""
from flask import abort, jsonify, request
from marshmallow import ValidationError

from app.lib.s3.exceptions import CephServiceException
from app.lib.s3.service import CephService
from app.lib.request_utils import (
    abort_detailed,
    log,
    no_content,
    parse_jsonapi_filters,
    request_json,
)
from app.models.account import Accounts
from app.models.bucket import BucketSchema
from app.models.pool import Pools
from app.models.s3_quota import S3Quotas
from app.models.s3_user import S3Users, S3UserSchema


def get_s3_limits(subject):
    """
    List account's S3 per-pool limit-sets
    """
    limitsets = S3Quotas.get_default_limitsets().all()
    # NOTE: currently we do not support non-default limitsets
    limitsets = [limitset.to_dict(is_limit=True) for limitset in limitsets]
    return jsonify(limitsets)


def create_s3_user(subject):
    """
    Create S3 User in Ceph and in Postgres
    """
    body = request_json(request)
    account_name = body.get("account_name", subject.account_name)

    account = Accounts.filtered(subject).filter_by(name=account_name).first()
    if not account:
        abort(404, "Account with this name not found.")
    body.pop("account_name", None)

    pool = Pools.query.filter_by(id=body.get("pool_id")).first()
    if not pool:
        abort(404, "Pool with this ID not found.")

    account_quota = S3Quotas.query.filter_by(
        account_id=account.id,
        pool_id=pool.id,
    ).first()
    if not account_quota:
        abort(404, "Account quota not found.")
    
    service = CephService()
    body["name"] = f"{account_name}${body['name']}"
    body |= {"account_id": account.id}

    try:
        validated_body = S3UserSchema(context={"account_quota": account_quota}).load(body)

        log.info(f"Attempt to create S3 user with name {body['name']}")
        service.create_s3_user(
            name=validated_body["name"],
            display_name=validated_body["owner"],
            placement=pool.klass,
            quota_data=validated_body["quota"]
        )
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)
    except CephServiceException as e:
        abort_detailed(400, f"Failed to create S3 user {body['name']}", str(e))

    validated_body.pop("quota", None)

    s3user = S3Users(**validated_body)
    s3user.save()
    service.enrich(s3user)

    return S3UserSchema().dump(s3user)


def get_account_s3_users(subject):
    """
    Get list of S3 User which are assigned to account
    """
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        s3_users = S3Users.filtered(subject, request_filters=parsed_filters).all()
    except ValidationError as e:
        abort_detailed(400, "Invalid query parameters.", e.messages)
    return S3UserSchema(many=True).dump(s3_users)


def get_s3_user(subject, user_id):
    """
    Retrive info, keys, statistice of S3 User from ceph
    """
    s3_user = S3Users.filtered(subject).filter_by(id=user_id).first()

    if not s3_user:
        abort(404, "S3 User with this ID not found or you haven't access for it.")
    return S3UserSchema().dump(s3_user)


def delete_s3_user(subject, user_id):
    """
    Delete S3 User from Ceph and Postgres
    """
    log.info(f"Delete S3User with id {user_id}")

    s3_user = S3Users.filtered(subject).filter_by(id=user_id).first()
    if s3_user is None:
        abort(404, "This account hasn't got the user with this ID or you haven't access for it.")
    s3_user.destroy()
    return jsonify("No content.")


def update_s3_user(subject, user_id):
    """
    Editing S3 user. Modify quotas and so on.
    """
    body = request_json(request)
    s3_user = S3Users.filtered(subject).filter_by(id=user_id).first()
    if not s3_user:
        abort(404, "S3 User not found or you haven't access for it.")

    account = Accounts.query.filter_by(id=s3_user.account_id).first()
    account_quota = S3Quotas.query.filter_by(
        account_id=account.id,
        pool_id=s3_user.pool_id,
    ).first()

    service = CephService()
    try:
        validated_body = S3UserSchema(
            context={
                'account_quota': account_quota,
                'user': s3_user
            }

        ).load(body, partial=True)

        service.update_s3_user(
            s3_user=s3_user,
            owner=validated_body.get("owner"),
            quota=validated_body.get("quota"),
            status=validated_body.get("status")
        )
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)
    except CephServiceException as e:
        abort_detailed(e.code, f"Failed to update S3 user {s3_user.name}", e.message)
    s3_user.update(validated_body)
    return S3UserSchema().dump(s3_user)


def create_bucket(subject):
    """
    Create bucket for s3 user.
    """
    body = request_json(request)
    user_name = body.get("user_name")

    s3_user = S3Users.filtered(subject).filter_by(name=user_name).first()
    if s3_user is None:
        abort(404, "User with this name not found or you haven't permission for it.")
    if s3_user.is_deleted():
        abort(409, "User was deleted in storage.")

    try:
        validated_body = BucketSchema(context={"user": s3_user}).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    service = CephService()
    try:
        bucket = service.create_bucket(
            s3_user=s3_user,
            bucket_name=validated_body.get("name"),
            quota=validated_body.get("quota")
        )
    except CephServiceException as e:
        abort_detailed(e.code, f"Failed to update S3 user {validated_body.get('name')}", e.message)

    return bucket.to_dict()


def list_buckets(subject):
    """
    Get buckets for s3 users.
    """
    api_filters = parse_jsonapi_filters(request.args)
    bucket_filters = api_filters.pop("base", {})

    try:
        s3_users = S3Users.filtered(subject, request_filters=api_filters).all()
    except ValidationError as e:
        abort_detailed(400, "Invalid query parameters.", e.messages)

    if not s3_users:
        abort(404, "User not found or you haven't permission.")

    service = CephService()
    try:
        buckets = service.list_s3_buckets(s3_users=s3_users, filters=bucket_filters)
    except CephServiceException as e:
        abort_detailed(e.code, f"Failed to retrieve buckets from the ceph.", e.message)

    return jsonify(BucketSchema(many=True).dump(buckets))


def update_bucket(subject, path):
    """
    Update the bucket of an S3 user.
    """
    body = request_json(request)
    if not body.get("quota"):
        abort(404, "Missed parameter 'quota'.")

    service = CephService()

    try:
        bucket = service.get_bucket_by_path(path)
    except CephServiceException as e:
        abort_detailed(404, "Bucket with this name not found.", e.message)

    s3_user = S3Users.filtered(subject).filter_by(name=bucket.user_name).first()
    if not s3_user:
        abort(401, "You haven't permission for this bucket.")

    try:
        validated_body = BucketSchema(
            context={
                "user": s3_user,
                "bucket": bucket
            },
            partial=True
        ).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters!", e.messages)

    try:
        updated_bucket = service.update_bucket(
            bucket=bucket,
            quota_update=validated_body.get("quota", {})
        )
        return jsonify(updated_bucket.to_dict())
    except CephServiceException as e:
        abort_detailed(e.code, "Failed to update bucket", e.message)

    return updated_bucket.to_dict()


def delete_bucket(subject, path):
    """
    Delete bucket
    """
    service = CephService()
    try:
        bucket = service.get_bucket_by_path(path)
    except CephServiceException:
        abort(404, "Bucket with this name not found.")

    s3_user = S3Users.filtered(subject).filter_by(name=bucket.user_name).first()
    if not s3_user:
        abort(401, "You haven't permission for this bucket.")

    try:
        service.delete_s3_bucket(bucket, force=True)
        return no_content()
    except CephServiceException as e:
        abort_detailed(e.code, "Failed to delete bucket", e.message)


def regenerate_keys(subject, user_id):
    """
    Regenerate S3 keys
    """
    log.debug(f"Regenerate keys for S3User {user_id}")
    s3_user = S3Users.filtered(subject).filter_by(id=user_id).first()
    if not s3_user:
        abort(404, "User with this ID not found or you haven't permission for it.")
    if s3_user.is_deleted():
        abort(409, "User is deleted in storage.")

    service = CephService()
    try:
        service.regenerate_user_keys(s3_user)
    except CephServiceException as e:
        abort_detailed(e.code, "Failed to update bucket", e.message)

    return S3UserSchema().dump(s3_user)
