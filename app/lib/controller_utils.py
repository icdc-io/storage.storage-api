"""
Controller uilts module
"""

import os

from app.lib.ceph_utils import ceph_connection as rgwadmin_conn
from app.lib.exceptions import Failed
from app.lib.request_utils import (
    bad_gateway,
    bad_request,
    conflict,
    created,
    forbidden,
    gateway_timeout,
    internal_server_error,
    is_failed,
    log,
    method_not_allowed,
    no_content,
    not_found,
    not_implemented,
    ok,
    unauthorized,
    unprocessable_entity,
)
from app.models.account import Accounts
from app.models.pool import Pools

status_codes = {
    200: ok,
    201: created,
    204: no_content,
    400: bad_request,
    401: unauthorized,
    403: forbidden,
    404: not_found,
    405: method_not_allowed,
    409: conflict,
    422: unprocessable_entity,
    500: internal_server_error,
    501: not_implemented,
    502: bad_gateway,
    504: gateway_timeout,
}


def trytest(func):
    """
    Decprator for raising Exceptions. Depends on statuscode
    """

    def decorate(*args, **kwargs):
        try:
            resp = func(*args, **kwargs)
            if is_failed(resp):
                raise Failed
            return resp
        except Failed:
            return status_codes.get(resp["code"])(str(resp["data"]))

    return decorate


def _get_ceph_s3user_usage(s3_user):
    try:
        user_info = _get_ceph_user_info(s3_user)

        buckets = rgwadmin_conn().request(
            "GET", f"/admin/bucket?format=json&uid={s3_user}"
        )
        user_info["user_quota"]["max_size"] = int(
            user_info["user_quota"]["max_size"] / 1024
        )
        user_info["stats"]["size"] = int(user_info["stats"]["size"] / 1024)
        stat = {
            "storage_size": {"actual": 0, "limit": 0},
            "buckets": {"actual": 0, "limit": 0},
            "objects": {"actual": 0, "limit": 0},
        }
        for bucket in buckets:
            # Start block for v1v2
            if "$" in s3_user:
                bucket_info = rgwadmin_conn().get_bucket(
                    f"{s3_user.split('$')[0]}/{bucket}"
                )
            else:
                bucket_info = rgwadmin_conn().get_bucket(bucket)
            # End block for v1v2

            stat["storage_size"]["actual"] += int(
                bucket_info["bucket_quota"]["max_size_kb"] / 1024
            )
            stat["objects"]["actual"] += bucket_info["bucket_quota"]["max_objects"]
        stat["storage_bucket_limit"], stat["object_bucket_limit"] = (
            int(user_info["bucket_quota"]["max_size_kb"] / 1024),
            user_info["bucket_quota"]["max_objects"],
        )
        stat["buckets"]["limit"], stat["buckets"]["actual"] = (
            user_info["max_buckets"],
            len(buckets),
        )
        stat["storage_size"]["limit"] = int(
            user_info["user_quota"]["max_size_kb"] / 1024
        )
        stat["objects"]["limit"] = user_info["user_quota"]["max_objects"]
        return {
            "stats": stat,
            "is_locked": bool(user_info["suspended"]),
            "tenant": user_info["tenant"],
            "user_id": user_info["user_id"],
        }
    except Exception:
        return internal_server_error()


def _get_ceph_user_info(s3_user: str) -> dict:
    """Get information about a Ceph user.

    Args:
        s3_user (str): The name of the user.

    Returns:
        dict: A dictionary with information about the user.
    """
    url = f"/admin/user?format=json&stats=true&uid={s3_user}"
    return rgwadmin_conn().request("GET", url)


def _create_s3user_ceph(account_name, data):
    try:
        user_name = f"{account_name}${data['name']}"
        rgwadmin_conn().create_user(
            uid=user_name,
            display_name=data["owner"],
            max_buckets=data["limits"]["buckets"],
        )
        rgwadmin_conn().create_subuser(
            user_name,
            subuser="swift",
            key_type="Swift",
            access="full",
            generate_secret=True,
        )
        rgwadmin_conn().set_user_quota(
            user_name,
            "user",
            max_size_kb=data["limits"]["storage_size"] * 1024,
            max_objects=data["limits"]["objects"],
            enabled=True,
        )
        rgwadmin_conn().set_user_quota(
            user_name,
            "bucket",
            max_size_kb=data["limits"]["bucket_storage_size"] * 1024,
            max_objects=data["limits"]["bucket_objects"],
            enabled=True,
        )
        return ok()
    except TypeError as exception:
        return internal_server_error(exception)
    except Exception as exception:
        return conflict(exception)


def _check_s3_user_quota(quota, users, actual_usage, request_params) -> bool:
    check = []
    message = []
    log.info("===Check user quota===")
    storage_check = quota["data_size_mb"] >= int(
        request_params["storage_size"] + float(actual_usage["storage_size_mb"])
    )
    check.append(storage_check)
    log.info(
        f"===Check storage quota. Quota size {quota['data_size_mb']}, \
        requested { request_params['storage_size']}, \
        actual {float(actual_usage['storage_size_mb'])}, \
        accepted {storage_check}==="
    )
    if not storage_check:
        message.append(
            f"storage ({int(request_params['storage_size'] + float(actual_usage['storage_size_mb']))}/{quota['data_size_mb'] })"
        )

    objects_check = (
        quota["objects"] >= request_params["objects"] + actual_usage["objects"]
    )
    check.append(objects_check)
    log.info(
        f"===Check objects quota. Quota objects {quota['objects']}, \
        requested {request_params['objects']}, \
        actual {float(actual_usage['objects'])}, \
        accepted {objects_check}==="
    )
    if not objects_check:
        message.append(
            f"objects ({request_params['objects'] + actual_usage['objects']}/{quota['objects']})"
        )

    users_check = quota["users"] >= users + 1
    check.append(users_check)
    log.info(
        f"===Check user quota. Quota users {quota['data_size_mb']}, \
        requested 1, \
        actual {users}, \
        accepted {users_check}==="
    )
    if not users_check:
        message.append(f"users ({users+1}/{quota['users']})")

    buckets_check = (
        quota["buckets"] >= actual_usage["buckets"] + request_params["max_buckets"]
    )
    check.append(buckets_check)
    log.info(
        f"===Check buckets quota. Quota buckets {quota['buckets']}, \
        requested {request_params['max_buckets']},  \
        actual {actual_usage['buckets']}, \
        accepted {buckets_check}==="
    )
    if not buckets_check:
        message.append(
            f"buckets ({actual_usage['buckets'] + request_params['max_buckets']}/{quota['buckets']})"
        )
    if False in check:
        return message
    return True


def _check_s3_user_quota_update(quota, user_info, actual_usage, request_params) -> bool:
    check = []
    message = []
    log.info("===Check user quota===")
    storage_delta = (
        request_params["storage_size"] - user_info["stats"]["storage_size"]["limit"]
    )
    storage_check = quota["data_size_mb"] >= int(
        storage_delta + float(actual_usage["storage_size_mb"])
    )
    check.append(storage_check)
    log.info(
        f"===Check storage quota. Quota size {quota['data_size_mb']}, \
        requested { request_params['storage_size']}, \
        user's {user_info['stats']['storage_size']['limit']},\
        actual account usage {float(actual_usage['storage_size_mb'])}, \
        delta {storage_delta},\
        accepted {storage_check}==="
    )
    if not storage_check:
        message.append(
            f"storage ({int(storage_delta + float(actual_usage['storage_size_mb']))}/{quota['data_size_mb'] })"
        )

    objects_delta = request_params["objects"] - user_info["stats"]["objects"]["limit"]
    objects_check = quota["objects"] >= objects_delta + actual_usage["objects"]
    check.append(objects_check)
    log.info(
        f"===Check objects quota. Quota objects {quota['objects']}, \
        requested {request_params['objects']}, \
        user's {user_info['stats']['objects']['limit']},\
        actual account usage {float(actual_usage['objects'])}, \
        delta {objects_delta},\
        accepted {objects_check}==="
    )
    if not objects_check:
        message.append(
            f"objects ({objects_delta + actual_usage['objects']}/{quota['objects']})"
        )

    buckets_delta = (
        request_params["max_buckets"] - user_info["stats"]["buckets"]["limit"]
    )
    buckets_check = quota["buckets"] >= buckets_delta + actual_usage["buckets"]
    check.append(buckets_check)
    log.info(
        f"===Check buckets quota. Quota buckets {quota['buckets']}, \
        requested {request_params['max_buckets']},  \
        user's {user_info['stats']['buckets']['limit']},\
        actual account usage {actual_usage['buckets']}, \
        delta {buckets_delta},\
        accepted {buckets_check}==="
    )
    if not buckets_check:
        message.append(
            f"buckets ({actual_usage['buckets'] + buckets_delta}/{quota['buckets']})"
        )
    if False in check:
        return message
    return True


def _check_s3_account_quota_update_user_overflow(quota, request_params) -> bool:
    check = []
    check.append(quota["data_size_mb"] >= int(request_params["storage_size"]))
    check.append(quota["objects"] >= request_params["objects"])
    if False in check:
        return False
    return True


def _collect_s3_account_usage(data):
    log.info("===Collect account usage===")
    stats = {}
    stats["objects"] = sum(
        record["user_quota"].get("max_objects", 0) for record in data
    )
    stats["storage_size_mb"] = sum(
        float(record["user_quota"].get("max_size", 0) / 1024 / 1024) for record in data
    )
    stats["buckets"] = sum(record["max_buckets"] for record in data)
    log.info(f"===Account usage is {stats}===")
    return stats


def _check_iscsi_account_quota(stats, request, disk_count=1) -> bool:
    check = []
    message = []
    log.info("===Check user quota===")

    storage_check = stats["storage_gb"]["limit"] >= int(
        stats["storage_gb"]["actual"] + request["size_gb"]
    )
    check.append(storage_check)
    log.info(
        f"===Check storage quota. Quota size {stats['storage_gb']['limit']}, \
        requested {request['size_gb']}, \
        actual {stats['storage_gb']['actual']}, \
        accepted {storage_check}==="
    )
    if not storage_check:
        message.append(
            f"storage ({int(stats['storage_gb']['actual'] + request['size_gb'])}/{stats['storage_gb']['limit']})"
        )

    disk_check = stats["disks"]["limit"] >= stats["disks"]["actual"] + disk_count
    check.append(disk_check)
    log.info(
        f"===Check disks quota. Quota size {stats['disks']['limit']}, \
        requested {disk_count}, \
        actual {stats['disks']['actual']}, \
        accepted {disk_check}==="
    )
    if not disk_check:
        message.append(
            f"disk ({int(stats['disks']['actual'] + 1)}/{stats['disks']['limit']})"
        )

    snapshots_check = stats["snapshots"]["limit"] >= stats["snapshots"][
        "actual"
    ] + request.get("snapshots", 0)
    check.append(snapshots_check)
    log.info(
        f"===Check snapshot quota. Quota snapshots {stats['snapshots']['limit']}, \
        requested {request.get('snapshots', 0)},  \
        actual {stats['snapshots']['actual']}, \
        accepted {snapshots_check}==="
    )
    if not snapshots_check:
        message.append(
            f"snapshots ({stats['snapshots']['actual'] + request.get('snapshots', 0)}/{stats['snapshots']['limit']})"
        )

    if False in check:
        return message
    return True


def _check_iscsi_account_quota_disk_update(stats, request, disk_obj) -> bool:
    check = []
    message = []
    log.info("===Check user quota disk update===")

    delta = request["size_gb"] - disk_obj.size_gb
    if delta < 0:
        log.info("Requested params is lower.")
        return False

    storage_check = stats["storage_gb"]["limit"] >= int(
        stats["storage_gb"]["actual"] + delta
    )
    check.append(storage_check)
    log.info(
        f"===Check storage quota. Quota size {stats['storage_gb']['limit']}, \
        requested {delta}, \
        actual {stats['storage_gb']['actual']}, \
        accepted {storage_check}==="
    )
    if not storage_check:
        message.append(
            f"storage ({stats['storage_gb']['actual'] + delta}/{stats['storage_gb']['limit']})"
        )

    if False in check:
        return message
    return True


def _get_iscsi_account_usage(account):
    response = []

    default_account = Accounts.query.filter_by(
        name=os.environ.get("DEFAULT_ACCOUNT")
    ).first()
    for quota in account.iscsi_quotas:
        pool_obj = Pools.query.filter_by(id=quota.pool_id).first()
        max_quota = [
            i for i in default_account.iscsi_quotas if i.pool_id == pool_obj.id
        ][0].serialize()
        usage = {
            "clients": {"actual": 0, "limit": 0},
            "storage_gb": {"actual": 0, "limit": 0},
            "snapshots": {"actual": 0, "limit": 0},
            "disks": {"actual": 0, "limit": 0},
        }

        usage["clients"]["limit"] = quota.clients
        usage["storage_gb"]["limit"] = quota.data_size_gb
        usage["disks"]["limit"] = quota.disks
        usage["snapshots"]["limit"] = quota.snapshots

        for config in [
            config for config in pool_obj.config if config.account_id == account.id
        ]:
            clients = []
            for disk in config.disks:
                usage["storage_gb"]["actual"] += disk.size_gb
                usage["disks"]["actual"] += 1
                for client in disk.clients:
                    clients.append(client.id)
                snapshots = disk.snapshots
                if len(snapshots) == 0:
                    continue
                for snapshot in snapshots:
                    # usage["storage_gb"]["actual"] += snapshot.size_mb / 1024
                    usage["snapshots"]["actual"] += 1
            usage["clients"]["actual"] = len(set(clients))
        quota = quota.serialize()
        quota["stats"] = usage
        quota["max_quota"] = max_quota
        response.append(quota)
        _ = [quota.pop(key, None) for key in ["data_size_gb", "clients", "disks"]]
    return response


def _get_iscsi_account_usage_billing(account):
    response = []
    for quota in account.iscsi_quotas:
        # pool_obj = Pools.get_by("id", quota.pool_id)
        pool_obj = Pools.query.filter_by(id=quota.pool_id).first()
        usage = {
            "clients": {"actual": 0, "limit": 0},
            "storage_gb": {"actual": 0, "limit": 0},
            "snapshots": {"actual": 0, "limit": 0},
            "disks": {"actual": 0, "limit": 0},
            "snapshots_size": {"actual": 0},
        }
        usage["clients"]["limit"] = quota.clients
        usage["storage_gb"]["limit"] = quota.data_size_gb
        usage["disks"]["limit"] = quota.disks
        usage["snapshots"]["limit"] = quota.snapshots
        for config in [
            config for config in pool_obj.config if config.account_id == account.id
        ]:
            clients = []
            for disk in config.disks:
                usage["storage_gb"]["actual"] += disk.size_gb
                usage["disks"]["actual"] += 1
                for client in disk.clients:
                    clients.append(client.id)
                snapshots = disk.snapshots
                if len(snapshots) == 0:
                    continue
                for snapshot in snapshots:
                    usage["snapshots_size"]["actual"] += snapshot.size_gb  # / 1024
                    usage["snapshots"]["actual"] += 1
            usage["clients"]["actual"] = len(set(clients))
        quota = quota.serialize()
        quota["stats"] = usage
        response.append(quota)
        _ = [quota.pop(key, None) for key in ["data_size_gb", "clients", "disks"]]
    return response


def get_user_usage(user_name):
    """
    Fetches S3 user usage details.
    """
    user_quota = rgwadmin_conn().get_user(user_name)["user_quota"]
    return {
        "objects": user_quota["max_objects"],
        "storage_mb": user_quota["max_size_kb"] // 1024,
        "buckets": rgwadmin_conn().get_user(user_name)["max_buckets"],
    }


def calculate_quota_stats(account_usage, quota):
    """
    Calculates and updates the stats for a quota.
    """
    quota_stats = {
        "objects": {"actual": 0, "limit": quota["objects"]},
        "storage_mb": {"actual": 0, "limit": quota["data_size_mb"]},
        "users": {
            "actual": len(
                [i for i in account_usage if i["pool_id"] == quota["pool"]["id"]]
            ),
            "limit": quota["users"],
        },
        "buckets": {
            "actual": sum(
                i["buckets"]
                for i in account_usage
                if i["pool_id"] == quota["pool"]["id"]
            ),
            "limit": quota["buckets"],
        },
    }
    quota_stats["objects"]["actual"] = sum(
        i["objects"] for i in account_usage if i["pool_id"] == quota["pool"]["id"]
    )
    quota_stats["storage_mb"]["actual"] = round(
        sum(
            i["storage_mb"]
            for i in account_usage
            if i["pool_id"] == quota["pool"]["id"]
        ),
        2,
    )

    return quota_stats


def generate_quota_endpoints(account, location_domain):
    """
    Generates public and private endpoints for the quota.
    """
    name = account.name
    endpoints = {
        "public": f"https://s3.{location_domain}/{name}",
        "private": f"http://s3.local.{location_domain}/{name}"
    }
    return endpoints


def serialize_quota_and_cleanup(quota):
    """
    Serializes the quota information and removes unwanted keys.
    """
    keys_to_remove = ["data_size_mb", "objects", "users"]
    for key in keys_to_remove:
        quota.pop(key, None)
    return quota


def _get_s3_account_usage_billing(account):
    from app import consts

    account_usage = []
    quotas_result = []

    location_domain = consts.LOCATION_DOMAIN

    default_account = Accounts.query.filter_by(name="default").first()

    for quota in account.s3_quotas:
        pool_obj = Pools.query.filter_by(id=quota.pool_id).first()
        max_quota = [i for i in default_account.s3_quotas if i.pool_id == pool_obj.id][
            0
        ].serialize()

        users = [i for i in account.s3_users if i.pool_id == quota.pool_id]
        for user in users:
            user_usage = get_user_usage(user.name)
            user_usage["pool_id"] = pool_obj.id
            account_usage.append(user_usage)

        quota = quota.serialize()

        quota["stats"] = calculate_quota_stats(account_usage, quota)
        quota["endpoints"] = generate_quota_endpoints(account, location_domain)
        quota["max_quota"] = max_quota

        quotas_result.append(serialize_quota_and_cleanup(quota))

    return quotas_result


def _max_quota_iscsi_overflow(request, max_quota) -> bool:
    check = []
    message = []
    log.info("===Check account max quota===")
    storage_check = request["data_size_gb"] <= max_quota.data_size_gb
    check.append(storage_check)
    log.info(
        f"===Check storage max quota. Requested {request['data_size_gb']}, \
        maximum {max_quota.data_size_gb}, \
        accepted {storage_check}==="
    )
    if not storage_check:
        message.append(f"storage ({request['data_size_gb']}/{max_quota.data_size_gb})")

    clients_check = request["clients"] <= max_quota.clients
    check.append(clients_check)
    log.info(
        f"===Check clients max quota. Requested {request['clients']}, \
        maximum {max_quota.clients}, \
        accepted {clients_check}==="
    )
    if not clients_check:
        message.append(f"clients ({request['clients']}/{max_quota.clients})")

    disks_check = request["disks"] <= max_quota.disks
    check.append(disks_check)
    log.info(
        f"===Check disks max quota. Requested {request['disks']}, \
        maximum {max_quota.disks}, \
        accepted {disks_check}==="
    )
    if not disks_check:
        message.append(f"disks ({request['disks']}/{max_quota.disks})")

    snapshots_check = request["snapshots"] <= max_quota.snapshots
    check.append(snapshots_check)
    log.info(
        f"===Check snapshots max quota. Requested {request['snapshots']}, \
        maximum {max_quota.snapshots}, \
        accepted {snapshots_check}==="
    )
    if not snapshots_check:
        message.append(f"snapshots ({request['snapshots']}/{max_quota.snapshots})")

    if False in check:
        return message
    return True


def _max_quota_s3_overflow(request, max_quota) -> bool:
    check = []
    message = []
    log.info("===Check account max quota===")
    objects_check = request["objects"] <= max_quota.objects
    check.append(objects_check)
    log.info(
        f"===Check objects max quota. Requested {request['objects']}, \
        maximum {max_quota.objects}, \
        accepted {objects_check}==="
    )
    if not objects_check:
        message.append(f"objects ({request['objects']}/{max_quota.objects})")

    data_size_mb_check = request["data_size_mb"] <= max_quota.data_size_mb
    check.append(data_size_mb_check)
    log.info(
        f"===Check data_size_mb max quota. Requested {request['data_size_mb']}, \
        maximum {max_quota.data_size_mb}, \
        accepted {data_size_mb_check}==="
    )
    if not data_size_mb_check:
        message.append(
            f"data size ({request['data_size_mb']}/{max_quota.data_size_mb})"
        )

    users_check = request["users"] <= max_quota.users
    check.append(users_check)
    log.info(
        f"===Check users max quota. Requested {request['users']}, \
        maximum {max_quota.users}, \
        accepted {users_check}==="
    )
    if not users_check:
        message.append(f"users ({request['users']}/{max_quota.users})")

    buckets_check = request["buckets"] <= max_quota.buckets
    check.append(buckets_check)
    log.info(
        f"===Check buckets max quota. Requested {request['buckets']}, \
        maximum {max_quota.buckets}, \
        accepted {buckets_check}==="
    )
    if not buckets_check:
        message.append(f"buckets ({request['buckets']}/{max_quota.buckets})")

    if False in check:
        return message
    return True
