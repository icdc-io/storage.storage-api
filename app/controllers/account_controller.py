"""
Account controller
"""

import os

from flask import request, abort, jsonify

from app.database import db
from app.lib import paramiko
from app.lib.controller_utils import (
    _get_iscsi_account_usage_billing,
    _get_s3_account_usage_billing,
)
from app.lib.request_utils import request_json, log, ok

# Import models
from app.models.account import Accounts

from app.models.iscsi_config import IscsiConfigs
from app.models.iscsi_gateway import IscsiGateways
from app.models.iscsi_quota import IscsiQuotas
from app.models.s3_quota import S3Quotas
from app.models.s3_user import S3Users

#############################################
# Account Controller
#############################################


def create_account(subject):
    """
    Create account instance along with its S3 and iSCSI quotas and iSCSI configs.
    """
    data = request_json(request)
    # Validate input data
    valid, message = Accounts.validate_account_data(data)
    if not valid:
        log.error(message)
        abort(400, message)
    # Create account
    log.debug(
        f"Creating account and associated records for: {data['name']}"
    )
    log.debug(f"Data: {data}")

    try:
        # Attempt to create Account (assuming unique constraint or similar check exists)
        account_obj = Accounts(
            **{k: v for k, v in data.items() if k not in ["services"]}
        )
        account_obj.save()
        # Check if account creation was successful
        if account_obj.id is None:
            log.error("Failed to create account")
            abort(409, "Account already exist.")
        log.debug("Account created successfully")

        # Process S3 Quotas
        for s3_quota in data.get("services", {}).get("s3", {}).get("quotas", []):
            s3_quota["account_id"] = account_obj.id
            s3_quota_obj = S3Quotas(**s3_quota)
            s3_quota_obj.save()
        log.debug("S3 Quotas processed successfully")

        # Process iSCSI Quotas
        for iscsi_quota in data.get("services", {}).get("iscsi", {}).get("quotas", []):
            iscsi_quota["account_id"] = account_obj.id
            iscsi_quota_obj = IscsiQuotas(**iscsi_quota)
            iscsi_quota_obj.save()
        log.debug("iSCSI Quotas processed successfully")

        # Process iSCSI Configs and Gateways
        for iscsi_config in (
                data.get("services", {}).get("iscsi", {}).get("configs", [])
        ):
            iscsi_config["account_id"] = account_obj.id
            gateways = iscsi_config.pop("gateways", [])
            iscsi_config_obj = IscsiConfigs(**iscsi_config)

            iscsi_config_obj.save()

            for gateway in gateways:
                gateway["config_id"] = iscsi_config_obj.id
                gateway_obj = IscsiGateways(**gateway)
                gateway_obj.save()

        log.debug("iSCSI Configs and Gateways processed successfully")

        # Prepare final response
        response_data = account_obj.toDict()

        log.debug("Account and associated records created successfully")
        return response_data

    except Exception as e:
        log.error(
            f"An error occurred while creating account and associated records: {e}"
        )
        abort(500, "Failed to create account and associated records")


def get_account_info(subject, account_name):
    """Get account information by name."""
    account = Accounts.query.filter_by(name=account_name).first()

    if account is None:
        abort(404, "Account does not exist.")

    return account.toDict()


def update_account(subject, account_name):
    data = request_json(request)
    data["name"] = account_name
    # Validate input data
    valid, message = Accounts.validate_account_data(data)
    if not valid:
        log.error(message)
        abort(400, message)

    log.debug(f"Update account with data: {data}")

    # Search for the existing account by name or another unique identifier
    account_obj = Accounts.query.filter_by(name=account_name).first()

    if not account_obj:
        error_message = f"Account with name {data.get('name')} does not exist."
        log.error(error_message)
        abort(404, error_message)

    try:
        # Process S3 Quotas
        for s3_quota in data.get("services", {}).get("s3", {}).get("quotas", []):
            s3_quota["account_id"] = account_obj.id
            s3_quota_obj = S3Quotas(**s3_quota)

            existing_s3_quota = S3Quotas.query.filter_by(
                pool_id=s3_quota_obj.pool_id, account_id=s3_quota_obj.account_id
            ).first()

            log.debug(existing_s3_quota)
            if existing_s3_quota:
                # Update existing record's attributes as needed
                for key, value in s3_quota.items():
                    setattr(existing_s3_quota, key, value)
                db.session.commit()  # Assuming `db` is your SQLAlchemy database instance
            else:
                # If not found, perhaps you want to add a new record instead
                db.session.add(s3_quota_obj)

            log.debug(s3_quota_obj)
            db.session.commit()

        log.debug("S3 Quotas processed successfully")

        # Process iSCSI Quotas
        for iscsi_quota in data.get("services", {}).get("iscsi", {}).get("quotas", []):
            iscsi_quota["account_id"] = account_obj.id
            iscsi_quota_obj = IscsiQuotas(**iscsi_quota)

            existing_iscsi_quota = IscsiQuotas.query.filter_by(
                pool_id=iscsi_quota_obj.pool_id, account_id=iscsi_quota_obj.account_id
            ).first()

            log.debug(existing_iscsi_quota)
            if existing_iscsi_quota:
                for key, value in iscsi_quota.items():
                    setattr(existing_iscsi_quota, key, value)
            else:
                db.session.add(iscsi_quota_obj)

            log.debug(iscsi_quota_obj)
            db.session.commit()  # Commit once after all updates/additions

        log.debug("iSCSI Quotas processed successfully")

        # Process iSCSI Configs and Gateways
        for iscsi_config in (
            data.get("services", {}).get("iscsi", {}).get("configs", [])
        ):
            iscsi_config["account_id"] = account_obj.id
            gateways = iscsi_config.pop("gateways", [])
            iscsi_config_obj = IscsiConfigs(**iscsi_config)

            existing_iscsi_config = IscsiConfigs.query.filter_by(
                pool_id=iscsi_config_obj.pool_id, account_id=iscsi_config_obj.account_id
            ).first()

            if existing_iscsi_config:
                for key, value in iscsi_config.items():
                    setattr(existing_iscsi_config, key, value)
            else:
                db.session.add(iscsi_config_obj)
                log.debug(iscsi_config_obj)
                db.session.commit()

            # Process Gateways
            iscsi_config_obj_id = (
                db.session.query(IscsiConfigs.id)
                .filter_by(
                    pool_id=iscsi_config_obj.pool_id,
                    account_id=iscsi_config_obj.account_id,
                )
                .first()[0]
            )

            log.debug(iscsi_config_obj_id)

            for gateway in gateways:
                gateway["config_id"] = (
                    iscsi_config_obj_id  # Link each gateway to the correct config
                )
                iscsi_gateway_obj = IscsiGateways(**gateway)

                # Attempt to find an existing gateway with the specified criteria
                existing_gateway = IscsiGateways.query.filter_by(
                    config_id=iscsi_config_obj_id
                ).first()

                log.debug(f"Existing gateway: {existing_gateway}")

                if existing_gateway:
                    # If found, update existing gateway's attributes
                    for key, value in gateway.items():
                        setattr(existing_gateway, key, value)
                else:
                    # If not found, add a new gateway record
                    db.session.add(iscsi_gateway_obj)

                log.debug(iscsi_gateway_obj)

            # Commit once after all updates/additions
            db.session.commit()

        # Prepare final response
        response_data = Accounts.query.filter_by(name=data["name"]).first().toDict()

        log.debug("Account and associated records updated successfully")
        return response_data

    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        log.error(
            f"An error occurred while updating account and associated records: {e}"
        )
        abort(500, "Failed to update account and associated records")


def delete_account(subject, account_name):
    """
    The delete_account function deletes an account along with its associated records and returns the ID of the deleted account.
    """
    account_obj = Accounts.query.filter_by(name=account_name).first()

    if account_obj is None:
        log.debug("Account not found")
        abort(404, "Account not found: " + str(account_name))

    if account_obj.id is not None:
        s3_quotas_obj = S3Quotas.get_by("account_id", account_obj.id)
        iscsi_quotas_obj = IscsiQuotas.get_by("account_id", account_obj.id)
        configs_obj = IscsiConfigs.get_by("account_id", account_obj.id)

        getaways_obj = None  # Initialize getaways_obj to None before the if statement
        if configs_obj is not None:
            getaways_obj = IscsiGateways.get_by("config_id", configs_obj.id)

        if getaways_obj is None:
            log.debug("iSCSI Gateways not found")
        else:
            resultIscsiGateway, message = IscsiGateways._delete_by(
                "config_id", configs_obj.id
            )
            if resultIscsiGateway:
                log.debug(message)

        # If configs_obj is not None, attempt to delete it and its related records
        if configs_obj is not None:
            resultIscsiConfig, message = IscsiConfigs._delete_by(
                "account_id", account_obj.id
            )
            if resultIscsiConfig:
                log.debug(message)

        # Check and delete S3 quotas if they exist
        if s3_quotas_obj is None:
            log.debug("S3 Quotas not found")
        else:
            resultS3Quotas, message = S3Quotas._delete_by("account_id", account_obj.id)
            if resultS3Quotas:
                log.debug(message)

        # Check and delete iSCSI quotas if they exist
        if iscsi_quotas_obj is None:
            log.debug("iSCSI Quotas not found")
        else:
            resultIscsiQuotas, message = IscsiQuotas._delete_by(
                "account_id", account_obj.id
            )
            if resultIscsiQuotas:
                log.debug(message)

        # Finally, delete the account itself
        result, message = Accounts._delete_by("id", account_obj.id)
        if result:
            log.debug(message)

        log.debug(
            "Account and associated records deleted successfully: "
            + str(account_obj.id)
        )

        return jsonify("No content")


def get_accounts_all(subject):
    """
    Retrieve all accounts with optional filter parameters.
    """

    return jsonify(Accounts.get_all_accounts())


def get_account_usage(subject, account_name):
    """
    This function retrieves the account usage for the specified account name.
    It takes in keyword arguments and returns a dictionary containing the usage
    for the "s3" and "iscsi" services.
    """
    account_obj = Accounts.query.filter_by(name=account_name).first()
    usage = {
        "s3": _get_s3_account_usage_billing(account_obj),
        "iscsi": _get_iscsi_account_usage_billing(account_obj),
    }
    return jsonify(usage)


def get_account_snapshots(kwargs):
    """
    Get list of Snapshots
    """
    account_name, role, requester_id = (
        kwargs["account_name"],
        kwargs["role"],
        kwargs["requester_id"],
    )
    account_obj = Accounts.query.filter_by(name=account_name).first()
    snapshots = []
    if role == "member":
        iscsi_clients = [
            client
            for client in account_obj.iscsi_clients
            if client.owner == requester_id
        ]
    elif role in ["admin", "cloud"]:
        iscsi_clients = account_obj.iscsi_clients
    for client in iscsi_clients:
        for disk in client.disks:
            _ = [snapshots.append(snapshot.serialize()) for snapshot in disk.snapshots]
    return ok(snapshots)


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
