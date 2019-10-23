import json
from datetime import datetime

import boto3

from app.controllers import (
    account_controller,
    gateway_controller,
    iscsi_controller,
    pools_controller,
)
from app.lib.ceph_utils import ceph_connection as ceph
from app.lib.request_utils import log
from app.models.account import Accounts
from migration_cli import ACCESS_KEY, HOST, S3_DEFAULT_CLASS, SECRET_KEY

client = None


def migrate_iscsi(account_name):
    """
    Migrates the iSCSI configuration and clients for the given account.

    Args:
        account_name (str): The name of the account to migrate.

    Returns:
        None
    """
    global client
    data = client.get_object(Bucket="storage-db", Key=f"iscsi/{account_name}")
    account_config = json.loads(data["Body"].read().decode("utf-8"))
    # create quota
    iscsi_pool = account_config["iscsi_conf"]["ceph_pool"]
    iscsi_pull_id = [
        i
        for i in pools_controller.get_pools(filter={"type": "iscsi"})["data"]
        if i["class"] == iscsi_pool.split("-")[1]
    ][0]["id"]
    default_iscsi_quota = account_controller._default_account_iscsi_quota(iscsi_pull_id)

    account_controller.set_account_iscsi_quota(
        account_name=account_name,
        body={
            "pool_id": iscsi_pull_id,
            "clients": account_config["account_quota"]["number_of_clients"],
            "data_size_gb": account_config["account_quota"]["storage_size_gb"],
            "disks": account_config["account_quota"]["number_of_disks"],
            "snapshots": default_iscsi_quota["snapshots"],
        },
    )

    config = account_controller.set_iscsi_configs(
        account_name=account_name,
        body={
            "pool_id": iscsi_pull_id,
            "target_iqn": account_config["iscsi_conf"]["server_iqn"],
            "name": f"{account_name}_default.conf",
        },
    )

    if len(account_config["iscsi_conf"]["gateways"]):
        for gateway in account_config["iscsi_conf"]["gateways"]:
            gateway_controller.set_gateway(
                body={
                    "api_password": account_config["iscsi_conf"]["password"],
                    "api_user": account_config["iscsi_conf"]["username"],
                    "ip_address": gateway["san_ip_address"],
                    # "name": account_config['iscsi_conf'],
                    "portal_ip_address": gateway["private_ip_address"],
                    "config_id": config["data"]["id"],
                }
            )
    if len(account_config["disks"]):
        for disk in account_config["disks"]:
            created_disk = iscsi_controller._disk_migrate(
                body={
                    "name": disk["name"],
                    "size_gb": disk["size_gb"],
                    "owner": disk["owner"],
                    "config_id": config["data"]["id"],
                }
            )
            if len(disk["snapshots"]):
                for snap in disk["snapshots"]:
                    iscsi_controller._snapshot_migrate(
                        {
                            "creation_time": datetime.strptime(
                                snap["creation_time"], "%Y-%m-%dT%H:%M:%S+00:00"
                            ),
                            "description": snap["description"],
                            "size_gb": snap["snapshot_size_gb"],
                            "name": snap["snapshot_name"],
                            "disk_id": created_disk["id"],
                        }
                    )

    # create iscsi_clients

    if len(account_config["clients"]):
        for client in account_config["clients"]:
            created_client = account_controller.create_iscsi_client(
                account_name=account_name,
                body={
                    "name": client["owner"],
                    "iqn": client["client_name"],
                    "chap_username": client["chap_username"],
                    "chap_password": client["chap_password"],
                    "owner": client["owner"],
                },
            )["data"]
            for assigned_disk in client["assigned_disks"]:
                # disk = []
                iscsi_controller._migrate_assigned_disks(created_client, assigned_disk)


def create_account(account_name):
    """
    Create account with the given account name.

    Args:
        account_name (str): The name of the account to be created.

    Returns:
        None
    """
    # create account
    global account_tmp
    global client
    data = client.get_object(Bucket="storage-db", Key=f"iscsi/{account_name}")
    account_config = json.loads(data["Body"].read().decode("utf-8"))

    account_tmp = account_controller.create_account(
        {
            "name": account_config["account"],
            "description": account_config["account_description"],
        }
    )


def migrate_s3(account_name):
    """
    Migrates data from an S3 bucket to the storage database for a specified account.
    :param account_name: The name of the account for which data is being migrated
    :return: None
    """
    global client
    data = client.get_object(Bucket="storage-db", Key=f"s3/{account_name}")
    account_config = json.loads(data["Body"].read().decode("utf-8"))
    s3_pull_id = [
        i
        for i in pools_controller.get_pools(filter={"type": "s3"})["data"]
        if i["class"] == S3_DEFAULT_CLASS
    ][0]["id"]
    # set quota

    default_s3_quotas = account_controller._default_account_s3_quota(s3_pull_id)
    account_controller.set_account_s3_quota(
        account_name=account_name,
        body={
            "pool_id": s3_pull_id,
            "objects": account_config["account_quota"]["number_of_objects"],
            "data_size_mb": account_config["account_quota"]["data_size_mb"],
            "users": account_config["account_quota"]["number_of_s3users"],
            "buckets": default_s3_quotas["buckets"],
        },
    )
    # create s3 user

    if len(account_config["s3users"]):
        for user in account_config["s3users"]:
            s3_user_info = ceph().get_user(user["s3user"])
            tag = False if len(s3_user_info["placement_tags"]) else True
            # tag = False
            account_controller._migrate_s3user(
                {
                    "account_id": Accounts.get_by("name", account_name).id,
                    "description": user["s3user_description"],
                    "owner": user["owner"],
                    "name": user["s3user"],
                    "default_placement": s3_pull_id,
                },
                S3_DEFAULT_CLASS,
                tag,
            )


def migrate_account(**kwargs):
    """
    Migrates an account to a new system, including creating the account, migrating S3 data, and migrating iSCSI data.

    Args:
        **kwargs: Keyword arguments for the function.

    Returns:
        None
    """
    global client
    client = boto3.client(
        "s3",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        endpoint_url=HOST,
    )
    account = kwargs["account_name"]
    log.debug("-START-------ACCOUNT----------")
    create_account(account)
    log.debug("-END-------ACCOUNT----------")
    log.debug("-START-------S3----------")
    migrate_s3(account)
    log.debug("-END-------S3----------")
    log.debug("-START-------ISCSI----------")
    migrate_iscsi(account)
    log.debug("-END-------ISCSI----------")
