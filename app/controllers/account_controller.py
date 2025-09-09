"""
Account controller
"""

import os

from flask import abort, jsonify, request
from marshmallow import ValidationError

from app.controllers.iscsi.quotas_controller import create as create_iscsi_quota
from app.controllers.iscsi_controller import set_config_gateway as set_gateway
from app.controllers.iscsi_controller import set_iscsi_configs as set_config
from app.controllers.s3.quotas_controller import create as create_s3_quota
from app.database import db
from app.lib import paramiko
from app.lib.request_utils import abort_detailed, log, request_json
from app.models.account import Accounts, AccountSchema
from app.models.iscsi_config import IscsiConfigs, IscsiConfigSchema
from app.models.iscsi_gateway import IscsiGateways, IscsiGatewaySchema
from app.models.iscsi_quota import IscsiQuotas, IscsiQuotaSchema
from app.models.s3_quota import S3Quotas, S3QuotaSchema
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
        data = AccountSchema().load(data)
    except ValidationError as e:
        abort_detailed(400, "Invalid account parameters.", e.messages)

    # Attempt to create Account (assuming unique constraint or similar check exists)
    account = Accounts(
        **{k: v for k, v in data.items() if k not in ["services"]}
    )
    account.save()

    # Check if account creation was successful
    if account.id is None:
        log.error("Failed to create account")
        abort(409, "Account already exist.")
    log.debug("Account created successfully")

    # Process S3 Quotas
    for s3_quota in data.get("services", {}).get("s3", {}).get("quotas", []):
        s3_quota["account_name"] = account.name
        create_s3_quota(subject, s3_quota)
    log.debug("S3 Quotas processed successfully")

    # Process iSCSI Quotas
    for iscsi_quota in (data.get("services", {}).get("iscsi", {}).get("quotas", [])):
        iscsi_quota["account_name"] = account.name
        create_iscsi_quota(subject, iscsi_quota)
    log.debug("iSCSI Quotas processed successfully")

    # Process iSCSI Configs and Gateways
    for iscsi_config in (
            data.get("services", {}).get("iscsi", {}).get("configs", [])
    ):
        iscsi_config["account_name"] = account.name
        gateways = iscsi_config.pop("gateways", [])

        iscsi_config = set_config(subject, iscsi_config)
        for gateway in gateways:
            set_gateway(subject, iscsi_config["id"], gateway)

    log.debug("iSCSI Configs and Gateways processed successfully")
    log.debug("Account and associated records created successfully")

    return AccountSchema().dump(account)


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
            s3_quota = S3QuotaSchema(partial=True).load(s3_quota)
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
            iscsi_quota = IscsiQuotaSchema(partial=True).load(iscsi_quota)
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
            iscsi_config = IscsiConfigSchema(partial=True).load(iscsi_config)
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
