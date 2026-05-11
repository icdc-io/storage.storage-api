"""
Account controller
"""

import os
from copy import deepcopy

from flask import abort, jsonify, request
from marshmallow import ValidationError

from app.controllers.iscsi.quotas_controller import create as create_iscsi_quota
from app.controllers.iscsi.quotas_controller import update as update_iscsi_quota
from app.controllers.iscsi_controller import (
    create_cluster,
    create_gateway,
)
from app.controllers.s3.quotas_controller import create as create_s3_quota
from app.controllers.s3.quotas_controller import update as update_s3_quota
from app.lib.request_utils import abort_detailed, log, request_json
from app.lib.s3 import paramiko
from app.models.account import Accounts, AccountSchema
from app.models.iscsi_quota import IscsiQuotas
from app.models.s3_quota import S3Quotas
from app.models.s3_user import S3Users

#############################################
# Account Controller
#############################################


def create_account(subject):
    """
    Create account instance along with its S3 and iSCSI quotas and iSCSI clusters.
    """
    body = request_json(request)
    data = body.pop("services", {})
    try:
        validated_body = AccountSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid account parameters.", e.messages)

    # Validate input data
    try:
        Accounts.validate_account_data(deepcopy(data))
    except ValidationError as e:
        abort_detailed(400, "Invalid data provided.", e.messages)

    # Create account
    log.debug(
        f"Creating account and associated records for: {body['name']}"
    )
    log.debug(f"Data: {data}")

    # Attempt to create Account (assuming unique constraint or similar check exists)
    account = Accounts(**validated_body)
    account.save()
    # Check if account creation was successful
    if account.id is None:
        log.error("Failed to create account")
        abort(409, "Account already exist.")
    log.debug("Account created successfully")

    # Process S3 Quotas
    log.debug("Start creating S3 Quotas")
    for s3_quota in data.get("s3", {}).get("quotas", []):
        s3_quota["account_name"] = account.name
        create_s3_quota(subject, s3_quota)
    log.debug("S3 Quotas processed successfully")

    # Process iSCSI Clusters and Gateways
    for iscsi_cluster in (
            data.get("iscsi", {}).get("clusters", [])
    ):
        log.debug(f"Start creating iSCSI Cluster with name: {iscsi_cluster['name']}")

        iscsi_cluster["account_name"] = account.name
        iscsi_gateways = iscsi_cluster.pop("gateways", [])

        iscsi_cluster = create_cluster(subject, iscsi_cluster)
        for gateway in iscsi_gateways:
            log.debug(f"Start creating iSCSI Gateway with name: {gateway['name']}")
            gateway["cluster_id"] = iscsi_cluster["id"]
            create_gateway(subject, gateway)
    log.debug("Clusters and gateways processed successfully")

    # Process iSCSI Quotas
    log.debug("Start creating iSCSI Quotas")
    for iscsi_quota in (data.get("iscsi", {}).get("quotas", [])):
        iscsi_quota["account_name"] = account.name
        create_iscsi_quota(subject, iscsi_quota)
    log.debug("iSCSI Quotas and targets processed successfully")

    log.debug("Account and associated records created successfully")

    return account.to_dict()


def get_account_info(subject, account_name):
    """Get account information by name."""
    account = Accounts.query.filter_by(name=account_name).first()

    if account is None:
        abort(404, "Account does not exist or you haven't permission.")

    return account.to_dict()


def update_account(subject, account_name):
    """
    Update account attributes and add new S3 and iSCSI quotas and iSCSI clusters.
    Can update S3 and iSCSI quotas but need provide all info of created quotas.
    """
    body = request_json(request)
    data = body.pop("services", {})
    # Search for the existing account by name or another unique identifier
    account = Accounts.query.filter_by(name=account_name).first()

    if not account:
        error_message = f"Account with name {data.get('name')} does not exist."
        log.error(error_message)
        abort(404, error_message)

    try:
        validated_body = AccountSchema(partial=True).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid account parameters.", e.messages)

    # Validate input data
    try:
        Accounts.validate_account_data(deepcopy(data))
    except ValidationError as e:
        abort_detailed(400, "Invalid data provided.", e.messages)
    account.update(validated_body)
    # Process S3 Quotas
    for s3_quota in data.get("s3", {}).get("quotas", []):
        s3_quota_obj = S3Quotas.query.filter_by(
            pool_id=s3_quota.get("pool_id", None), account_id=account.id
        ).first()

        log.debug(s3_quota_obj)
        if s3_quota_obj is not None:
            # Update existing record's attributes as needed
            update_s3_quota(subject, s3_quota_obj.id, s3_quota)
        else:
            # If not found, perhaps you want to add a new record instead
            s3_quota["account_name"] = account.name
            create_s3_quota(subject, s3_quota)
        log.debug(s3_quota_obj)

    log.debug("S3 Quotas processed successfully")

    # Process iSCSI Quotas
    for iscsi_quota in data.get("iscsi", {}).get("quotas", []):
        iscsi_quota_obj = IscsiQuotas.query.filter_by(
            pool_id=iscsi_quota.get("pool_id", None), account_id=account.id
        ).first()
        log.debug(iscsi_quota_obj)
        if iscsi_quota_obj is not None:
            update_iscsi_quota(subject, iscsi_quota_obj.id, iscsi_quota)
        else:
            iscsi_quota["account_name"] = account.name
            create_iscsi_quota(subject, iscsi_quota)

        log.debug(iscsi_quota_obj)

    log.debug("iSCSI Quotas processed successfully")

    # Process iSCSI Clusters and Gateways
    for iscsi_cluster in (
            data.get("iscsi", {}).get("clusters", [])
    ):
        log.debug(f"Start creating iSCSI Cluster with name: {iscsi_cluster['name']}")
        iscsi_cluster["account_name"] = account.name
        iscsi_gateways = iscsi_cluster.pop("gateways", [])
        iscsi_cluster = create_cluster(subject, iscsi_cluster)
        for gateway in iscsi_gateways:
            log.debug(f"Start creating iSCSI Gateway with name: {gateway['name']}")
            gateway["cluster_id"] = iscsi_cluster["id"]
            create_gateway(subject, gateway)

    log.debug("Account and associated records updated successfully")
    return account.to_dict()


def delete_account(subject, account_name):
    """
    The delete_account function deletes an account along with its associated records and returns the ID of the deleted account.
        @param kwargs: keyword arguments containing the account_name
        @return: the ID of the deleted account
    """

    account_obj = Accounts.query.filter_by(name=account_name).first()
    if not account_obj:
        abort(404, "Account not found.")
    account_obj.destroy()

    return jsonify("No content")


def get_accounts_all(subject):
    """
    Retrieve all accounts with optional filter parameters.
    """
    return jsonify(Accounts.get_all_accounts())


#############################################
# Default Account S3 and iSCSI Controller
#############################################


def _default_account_s3_quota(pool_id):
    # Get the default account object
    default_account_obj = Accounts.query.filter_by(
        name=os.environ.get("DEFAULT_ACCOUNT")
    ).first()

    max_quota_obj = [
        quota for quota in default_account_obj.s3_quotas if quota.pool_id == pool_id
    ][0]
    return max_quota_obj.serialize()


def _default_account_iscsi_quota(pool_id):
    # Get the default account object
    default_account_obj = Accounts.query.filter_by(
        name=os.environ.get("DEFAULT_ACCOUNT")
    ).first()

    max_quota_obj = [
        quota for quota in default_account_obj.iscsi_quotas if quota.pool_id == pool_id
    ][0]
    return max_quota_obj.serialize()


def _migrate_s3user(body, placement, tag):
    if tag:
        paramiko.send(
            f"radosgw-admin user modify --uid {body['name']}  --tags {placement}"
        )
    s3_user = S3Users(**body)
    s3_user.save()
