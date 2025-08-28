"""
S3 Controller
"""
from json import JSONDecodeError
import re

import rgwadmin.exceptions
from flask import abort, jsonify, request
from marshmallow import ValidationError
from botocore.exceptions import ClientError

from app.lib.ceph_utils import boto3_conn
from app.lib.ceph_utils import ceph_connection as rgwadmin_conn
from app.lib import paramiko
from app.lib.request_utils import (
    abort_detailed,
    log,
    no_content,
    request_json,
    parse_jsonapi_filters,
)
from app.models.account import Accounts
from app.models.pool import Pools
from app.models.s3_user import S3Users, S3UserSchema
from app.models.s3_quota import S3Quotas
from app.models.bucket import Bucket, BucketSchema


def get_s3_limits(subject):
    """
    List account's S3 per-pool limit-sets
    """
    limitsets = S3Quotas.get_default_limitsets().all()
    # NOTE: currently we do not support non-default limitsets
    limitsets = [limitset.toDict() for limitset in limitsets]
    return jsonify(limitsets)


def create_s3_user(subject):
    """
    Create S3 User in Ceph and in Postgres
    """
    body = request_json(request)
    account_name = body["account_name"]
    account = Accounts.filtered(subject).filter_by(name=body["account_name"]).first()
    if not account:
        abort(404, "Account with this name not found.")
    body.pop("account_name", None)
    pool = Pools.query.filter_by(id=body["pool_id"]).first()
    if not pool:
        abort(404, "Pool with this ID not found.")

    account_quota = S3Quotas.query.filter_by(
        account_id=account.id,
        pool_id=pool.id,
    ).first()
    if not account_quota:
        abort(404, "Account quota not found.")

    body["name"] = f"{account_name}${body['name']}"
    try:
        validated_body = S3UserSchema(context={"account_quota": account_quota}).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    try:
        _create_s3user_ceph(account_name, validated_body, pool.klass)
    except rgwadmin.exceptions.UserExists as e:
        abort_detailed(400, f"Failed to create S3 user {validated_body['name']}", str(e))
    except rgwadmin.exceptions.RGWAdminException as e:
        abort_detailed(400, f"Failed to create S3 user {validated_body['name']}", str(e))
    except TypeError as e:
        abort_detailed(400, f"Failed to create S3 user {validated_body['name']}", str(e))
    except JSONDecodeError as e:
        abort_detailed(400, f"Failed to create S3 user {validated_body['name']}", e.msg)
    except ValueError as e:
        abort_detailed(400, f"Failed to create S3 user {validated_body['name']}", str(e))
    except KeyError as e:
        abort_detailed(400, f"Failed to create S3 user {validated_body['name']}", str(e))
    except Exception as e:
        abort_detailed(500, f"Failed to create S3 user {validated_body['name']}", str(e))

    validated_body |= {"account_id": account.id}
    validated_body.pop("quota", None)

    s3user = S3Users(**validated_body)
    s3user.save()

    return S3UserSchema().dump(s3user)


def _create_s3user_ceph(account_name, data, placement):
    user_name = data["name"]
    try:
        log.debug(f"[1/4] Creating blank S3 user [{user_name}]")
        # NOTE: we use raw request instead `rgwadmin_conn().create_user()` because create user function
        # currently can not set default placement
        # default placement is required, so user will create buckets with 's3cmd mb' command and placement_rule is assigned to buckets
        rgwadmin_conn().request(
            "PUT",
            f"/admin/user?format=json&uid={user_name}&default-placement={placement}" +
            f"&user-caps=buckets=*" +
            f"&max-buckets={data['quota']['buckets']}&display-name={data['owner']}"
        )
        # rgwadmin_conn().create_user(
        #    uid=user_name,
        #    display_name=data["owner"],
        #    max_buckets=data["quota"]["buckets"],
        #    user_caps="buckets=*"
        # )
        log.debug(f"[1/4] Blank S3 user [{user_name}] is created")
        log.debug(f"[2/4] Setting quota for S3 user [{user_name}]: {data}")
        rgwadmin_conn().set_user_quota(
            user_name,
            "user",
            max_size_kb=int(data["quota"]["data_size_mb"]) * 1024,
            max_objects=int(data["quota"]["objects"]),
            enabled=True,
        )
        log.debug(f"[2/4] Quota for S3 user [{user_name}] is update")
        # NOTE: currently we can not set placement_tags with RGWAdmin (adminops API).
        # Check documentation for updates: https://docs.ceph.com/en/latest/radosgw/adminops/
        # Tags limits 's3cmd --bucket-location=":hdd"  mb' command from assigning not allowed placements.
        log.debug(f"[3/4] Set placement tag [{placement}] to S3 User [{user_name}] via Paramiko (SSH)")
        paramiko.send(
            f"radosgw-admin user modify --uid '{user_name}' --tags '{placement}'"
        )
        log.debug(f"[3/4] Placement tag to S3 User [{user_name}] via Paramiko is updated")
        log.debug(f"[4/4] Create subuser for swift protocol S3 user [{user_name}]")
        rgwadmin_conn().create_subuser(
            user_name,
            subuser="swift",
            key_type="Swift",
            access="full",
            generate_secret=True,
        )
        log.debug(f"[4/4] Swift subuser for S3 user [{user_name}] is created")
    except rgwadmin.exceptions.UserExists as e:
        log.error(f"User {user_name} already exists! {str(e)}")
        raise e
    except rgwadmin.exceptions.RGWAdminException as e:
        log.error(f"RGWAdmin exception occurred while processing S3 User {user_name}: {str(e)}")
        raise e
    except TypeError as e:
        log.error(f"Type error occurred while processing S3 User {user_name}: {str(e)}")
        raise e
    except JSONDecodeError as e:
        log.error(f"JSON decode error occurred while processing S3 User {user_name}: {str(e)}")
        raise e
    except paramiko.ssh_exception.SSHException as e:
        log.error(f"SSH error occurred while processing S3 User {user_name}: {str(e)}")
        raise e
    except ValueError as e:
        log.error(f"Value error occurred while processing S3 User {user_name}: {str(e)}")
        raise e
    except KeyError as e:
        log.error(f"Missing key in input data while processing S3 User {user_name}: {str(e)}")
        raise e
    except Exception as e:
        log.error(f"An unexpected error occurred while processing S3 User {user_name}: {str(e)}")
        raise e


def get_account_s3_users(subject):
    """
    Get list of S3 User which are assigned to account
    """
    schema = S3UserSchema(partial=True)
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = schema.load(parsed_filters)
    except ValidationError as e:
        abort_detailed(400, "Invalid query parameters.", e.messages)
    s3_users = S3Users.filtered(subject).filter_by(**filters).all()
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
    log.debug(f"Delete S3User with id {user_id}")

    s3_user_obj = S3Users.filtered(subject).filter_by(id=user_id).first()
    if s3_user_obj is None:
        abort(404, "This account hasn't got the user with this ID or you haven't access for it.")
    s3_user_obj.remove()
    return jsonify("No content.")


def update_s3_user(subject, user_id):
    """
    Editing S3 user. Modify quotas and so on.
    """
    body = request_json(request)
    s3_user = S3Users.filtered(subject).filter_by(id=user_id).first()
    if not s3_user:
        abort(404, "S3 User not found or you haven't access for it.")
    if s3_user.is_deleted():
        abort(409, "S3 user was deleted in storage.")
    account = Accounts.query.filter_by(id=s3_user.account_id).first()
    account_quota = S3Quotas.query.filter_by(
        account_id=account.id,
        pool_id=s3_user.pool_id,
    ).first()

    try:
        validated_body = S3UserSchema(
            context={
                'account_quota': account_quota,
                'user': s3_user
            }
        ).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    if body.get("owner", None) and "set-owner" not in subject.policy["s3.users"]["permissions"]:
        del validated_body["owner"]  # pylint: disable=multiple-statements

    if "quota" in validated_body:
        cur_quota = s3_user.get_quota()
        new_quota = {
            key: validated_body["quota"].get(key, cur_quota[key])
            for key in ["data_size_mb", "objects", "buckets"]
        }
        validated_body["quota"] = new_quota
        try:
            _modify_user_ceph(s3_user.name, validated_body)
        except rgwadmin.exceptions.NoSuchUser as e:
            abort_detailed(400, "User not found during quota update.", str(e))
        except rgwadmin.exceptions as e:
            abort_detailed(500, "Failed to retrieve user information.", str(e))

    s3_user.update(validated_body)
    return S3UserSchema().dump(s3_user)


def _modify_user_ceph(s3_user_name, body):
    """
    Update S3 User quota on Ceph side
    """
    try:
        rgwadmin_conn().modify_user(
            s3_user_name,
            display_name=body["owner"],
            max_buckets=int(body["quota"]["buckets"]),
        )
        rgwadmin_conn().set_user_quota(
            s3_user_name,
            "user",
            max_size_kb=int(body["quota"]["data_size_mb"]) * 1024,
            max_objects=int(body["quota"]["objects"]),
            enabled=True,
        )
    except rgwadmin.exceptions.NoSuchUser:
        raise rgwadmin.exceptions.NoSuchUser("User not found during quota update.")
    except rgwadmin.exceptions:
        raise rgwadmin.exceptions.InternalError("Failed to retrieve user information.")


def delete_bucket(subject, path):
    """
    Delete bucket
    """
    log.debug(f"Delete bucket with path {path}")
    try:
        bucket = Bucket.from_bucket_path(path)
    except Exception:
        abort(404, "Bucket with this name not found.")

    s3_user = S3Users.filtered(subject).filter_by(name=bucket.user_name).first()
    if not s3_user:
        abort(401, "You haven't permission for this bucket.")
    rgwadmin_conn().remove_bucket(path, purge_objects=True)
    return jsonify("No content.")


def create_bucket(subject):
    """
    Create bucket for s3 user.
    """
    body = request_json(request)
    user_name = body["user_name"]

    s3_user = S3Users.filtered(subject).filter_by(name=user_name).first()
    if s3_user is None:
        abort(404, "User with this name not found or you haven't permission for it.")

    if s3_user.is_deleted():
        abort(409, "User was deleted in storage.")
    try:
        validated_body = BucketSchema(context={"user": s3_user}).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    pool = Pools.get_by("id", s3_user.pool_id)
    keys = s3_user.get_keys()

    if not validated_body.get("quota"):
        validated_body["quota"] = {}

    validated_body["quota"] = {
        "data_size_mb": validated_body["quota"].get("data_size_mb", -1),
        "objects": validated_body["quota"].get("objects", -1)
    }

    try:
        _create_bucket(
            access_key=keys["s3"].get("access_key"),
            secret_key=keys["s3"].get("secret_key"),
            body=validated_body,
            pool=pool
        )
    except ClientError as e:
        abort(400, f"Client error occurred: {str(e)}")
    except Exception as e:
        abort(500, f"Unexpected error: {str(e)}")

    bucket = Bucket.from_user_and_bucket_name(user_name, validated_body["name"])
    return bucket.to_dict()


def _create_bucket(access_key, secret_key, body, pool):
    """
    Create Bucket in ceph.
    """
    body['name'] = body['name'].replace("_", "-")

    # Establish connections
    s3_client = boto3_conn(access_key, secret_key)
    log.debug(f"Logged in s3_client: {s3_client}")

    try:
        # Create bucket
        # Start block for v1v2
        if "$" in body['user_name']:
            s3_client.create_bucket(
                Bucket=body['name'],
                CreateBucketConfiguration={
                    "LocationConstraint": pool.location_constraint()
                },
            )
        else:
            s3_client.create_bucket(Bucket=body['name'])
        # end block for v1v2
        log.info(f"Bucket {body['name']} created successfully")
        update_bucket_quota(bucket_name=body["name"], user_name=body["user_name"], quota=body["quota"])
    except ClientError as e:
        log.error(f"Error creating bucket {body['name']}: {str(e)}")
        if e.response["Error"]["Code"] == "SignatureDoesNotMatch":
            log.error("Check your AWS secret/access key and the signature version.")
        raise e
    except s3_client.exceptions.BucketAlreadyExists as e:
        log.error(f"Bucket {body['name']} already exists: {str(e)}")
        raise e
    except s3_client.exceptions.BucketAlreadyOwnedByYou as e:
        log.error(f"Bucket {body['name']} already owned by you: {str(e)}")
        raise e
    except Exception as e:
        log.error(f"Error creating bucket {body['name']}: {str(e)}")
        log.debug("Debug info: An unexpected exception occurred.")
        raise e


def list_buckets(subject):
    """
    Get buckets for s3 users.
    """
    api_filters = parse_jsonapi_filters(request.args)
    s3user_filters = api_filters.pop("user", {})

    try:
        filters = S3UserSchema(partial=True).load(s3user_filters)
    except ValidationError as e:
        abort_detailed(400, "Invalid filter key for related user.", e.messages)

    s3_users = S3Users.filtered(subject).filter_by(**filters).all()
    if not s3_users:
        abort(404, "User not found or you haven't permission.")

    buckets = []
    s3_user_names = [s3_user.name for s3_user in s3_users]

    if len(s3_users) == 1:
        buckets_info = s3_users[0].get_buckets_info()
    else:
        buckets_info = Bucket.get_all_buckets_info()

    for bucket_info in buckets_info:
        bucket = Bucket.from_bucket_info(bucket_info)
        # Buckets are not stored in database, so we have to filter them iterating by fields
        try:
            if bucket.user_name in s3_user_names and bucket.filter(api_filters):
                buckets.append(bucket)
        except AttributeError as e:
            abort(400, e.args[0])
    return jsonify(BucketSchema(many=True).dump(buckets))


def update_bucket(subject, path):
    """
    Update the bucket of an S3 user.
    """
    body = request_json(request)

    if not body.get("quota"):
        abort(404, "Missed parameter 'quota'.")
    try:
        bucket = Bucket.from_bucket_path(path)
    except Exception:
        abort(404, "Bucket with this name not found.")

    s3_user = S3Users.filtered(subject).filter_by(name=bucket.user_name).first()
    if not s3_user:
        abort(401, "You haven't permission for this bucket.")

    try:
        validated_body = BucketSchema(
            context={
                "user": s3_user,
                "bucket": bucket
            }
        ).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters!", e.messages)

    quota = bucket.quota.to_dict()
    validated_body["quota"] = {
        "data_size_mb": validated_body["quota"].get("data_size_mb", quota["data_size_mb"]),
        "objects": validated_body["quota"].get("objects", quota["objects"])
    }
    if '$' in s3_user.name:
        bucket_name = path.split('/')[1]
    else:
        bucket_name = path.lstrip('/')

    update_bucket_quota(
        bucket_name=bucket_name,
        user_name=bucket.user_name,
        quota=validated_body["quota"]
    )
    bucket = Bucket.from_bucket_path(path)
    return bucket.to_dict()


def update_bucket_quota(bucket_name, user_name, quota):
    """
    Update bucket quota in Ceph
    """
    log.debug(f"Updating bucket quota for bucket {bucket_name}")
    quota["data_size_mb"] = -1 if quota["data_size_mb"] < 0 else quota["data_size_mb"] * 1024
    rgwadmin_conn().set_bucket_quota(
        uid=user_name,
        bucket=bucket_name,
        max_size_kb=quota["data_size_mb"],
        max_objects=quota["objects"],
        enabled=True,
    )

    return no_content()


def regenerate_keys(subject, user_id):
    """
    Regenerate S3 keys
    """
    log.debug(f"Regenerate keys for S3User {user_id}")
    s3_user_obj = S3Users.filtered(subject).filter_by(id=user_id).first()
    if not s3_user_obj:
        abort(404, "User with this ID not found or you haven't permission for it.")
    if s3_user_obj.is_deleted():
        abort(409, "User is deleted in storage.")
    s3_user_name = s3_user_obj.full_name()
    user_info = rgwadmin_conn().request(
        "GET", f"/admin/user?format=json&stats=true&uid={s3_user_name}"
    )
    rgwadmin_conn().modify_user(s3_user_name, generate_key="True")
    rgwadmin_conn().modify_subuser(
        s3_user_name,
        user_info["subusers"][0]["id"],
        access="full",
        generate_secret="True",
    )
    for key in user_info["keys"]:
        rgwadmin_conn().request(
            "DELETE",
            f"/admin/user?format=json&key&uid={s3_user_name}&access-key={key['access_key']}",
        )
    s3_user_obj._user_info_cache = None
    s3_user_obj = S3Users.filtered(subject).filter_by(id=user_id).first()
    return S3UserSchema().dump(s3_user_obj)
