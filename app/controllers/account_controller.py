"""
Account controller
"""

import os

from app.database import db
from app.lib import paramiko, request_utils
from app.lib.controller_utils import (
    _get_iscsi_account_usage_billing,
    _get_s3_account_usage_billing,
)

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


def create_account(data):
    """
    Create account instance along with its S3 and iSCSI quotas and iSCSI configs.
    """
    # Validate input data
    valid, message = Accounts.validate_account_data(data)
    if not valid:
        request_utils.log.error(message)
        return request_utils.bad_request(message)

    # Create accountr
    request_utils.log.debug(
        f"Creating account and associated records for: {data['name']}"
    )
    request_utils.log.debug(f"Data: {data}")

    try:
        # Attempt to create Account (assuming unique constraint or similar check exists)
        account_obj = Accounts(
            **{k: v for k, v in data.items() if k not in ["services"]}
        )
        account_obj.save()
        # Check if account creation was successful
        if account_obj.id is None:
            request_utils.log.error("Failed to create account")
            return request_utils.conflict("Account already exists")
        request_utils.log.debug("Account created successfully")

        # Process S3 Quotas
        for s3_quota in data.get("services", {}).get("s3", {}).get("quotas", []):
            s3_quota["account_id"] = account_obj.id
            s3_quota_obj = S3Quotas(**s3_quota)
            s3_quota_obj.save()
        request_utils.log.debug("S3 Quotas processed successfully")

        # Process iSCSI Quotas
        for iscsi_quota in data.get("services", {}).get("iscsi", {}).get("quotas", []):
            iscsi_quota["account_id"] = account_obj.id
            iscsi_quota_obj = IscsiQuotas(**iscsi_quota)
            iscsi_quota_obj.save()
        request_utils.log.debug("iSCSI Quotas processed successfully")

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

        request_utils.log.debug("iSCSI Configs and Gateways processed successfully")

        # Prepare final response
        response_data = account_obj.toDict()

        request_utils.log.debug("Account and associated records created successfully")
        return request_utils.ok(response_data)

    except Exception as e:
        request_utils.log.error(
            f"An error occurred while creating account and associated records: {e}"
        )
        return request_utils.internal_server_error(
            "Failed to create account and associated records"
        )


def get_account_info(account_name):
    """Get account information by name."""
    account = Accounts.query.filter_by(name=account_name).first()

    if account is None:
        return request_utils.not_found("Account does not exist.")

    return request_utils.ok(account.toDict())


def update_account(data):
    # Validate input data
    valid, message = Accounts.validate_account_data(data)
    if not valid:
        request_utils.log.error(message)
        return request_utils.bad_request(message)

    request_utils.log.debug(f"Update account with data: {data}")

    # Search for the existing account by name or another unique identifier
    account_obj = Accounts.query.filter_by(name=data.get("name")).first()

    if not account_obj:
        error_message = f"Account with name {data.get('name')} does not exist."
        request_utils.log.error(error_message)
        return request_utils.not_found(error_message)

    try:
        # Process S3 Quotas
        for s3_quota in data.get("services", {}).get("s3", {}).get("quotas", []):
            s3_quota["account_id"] = account_obj.id
            s3_quota_obj = S3Quotas(**s3_quota)

            existing_s3_quota = S3Quotas.query.filter_by(
                pool_id=s3_quota_obj.pool_id, account_id=s3_quota_obj.account_id
            ).first()

            request_utils.log.debug(existing_s3_quota)
            if existing_s3_quota:
                # Update existing record's attributes as needed
                for key, value in s3_quota.items():
                    setattr(existing_s3_quota, key, value)
                db.session.commit()  # Assuming `db` is your SQLAlchemy database instance
            else:
                # If not found, perhaps you want to add a new record instead
                db.session.add(s3_quota_obj)

            request_utils.log.debug(s3_quota_obj)
            db.session.commit()

        request_utils.log.debug("S3 Quotas processed successfully")

        # Process iSCSI Quotas
        for iscsi_quota in data.get("services", {}).get("iscsi", {}).get("quotas", []):
            iscsi_quota["account_id"] = account_obj.id
            iscsi_quota_obj = IscsiQuotas(**iscsi_quota)

            existing_iscsi_quota = IscsiQuotas.query.filter_by(
                pool_id=iscsi_quota_obj.pool_id, account_id=iscsi_quota_obj.account_id
            ).first()

            request_utils.log.debug(existing_iscsi_quota)
            if existing_iscsi_quota:
                for key, value in iscsi_quota.items():
                    setattr(existing_iscsi_quota, key, value)
            else:
                db.session.add(iscsi_quota_obj)

            request_utils.log.debug(iscsi_quota_obj)
            db.session.commit()  # Commit once after all updates/additions

        request_utils.log.debug("iSCSI Quotas processed successfully")

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
                request_utils.log.debug(iscsi_config_obj)
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

            request_utils.log.debug(iscsi_config_obj_id)

            for gateway in gateways:
                gateway["config_id"] = (
                    iscsi_config_obj_id  # Link each gateway to the correct config
                )
                iscsi_gateway_obj = IscsiGateways(**gateway)

                # Attempt to find an existing gateway with the specified criteria
                existing_gateway = IscsiGateways.query.filter_by(
                    config_id=iscsi_config_obj_id
                ).first()

                request_utils.log.debug(f"Existing gateway: {existing_gateway}")

                if existing_gateway:
                    # If found, update existing gateway's attributes
                    for key, value in gateway.items():
                        setattr(existing_gateway, key, value)
                else:
                    # If not found, add a new gateway record
                    db.session.add(iscsi_gateway_obj)

                request_utils.log.debug(iscsi_gateway_obj)

            # Commit once after all updates/additions
            db.session.commit()

        # Prepare final response
        response_data = Accounts.query.filter_by(name=data["name"]).first().toDict()

        request_utils.log.debug("Account and associated records updated successfully")
        return request_utils.ok(response_data)

    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        request_utils.log.error(
            f"An error occurred while updating account and associated records: {e}"
        )
        return request_utils.internal_server_error(
            "Failed to update account and associated records"
        )


def delete_account(**kwargs):
    """
    The delete_account function deletes an account along with its associated records and returns the ID of the deleted account.
        @param kwargs: keyword arguments containing the account_name
        @return: the ID of the deleted account
    """
    account_name = kwargs["account_name"]
    account_obj = Accounts.query.filter_by(name=account_name).first()

    if account_obj is None:
        request_utils.log.debug("Account not found")
        return request_utils.not_found("Account not found: " + str(account_name))

    if account_obj.id is not None:
        s3_quotas_obj = S3Quotas.get_by("account_id", account_obj.id)
        iscsi_quotas_obj = IscsiQuotas.get_by("account_id", account_obj.id)
        configs_obj = IscsiConfigs.get_by("account_id", account_obj.id)

        getaways_obj = None  # Initialize getaways_obj to None before the if statement
        if configs_obj is not None:
            getaways_obj = IscsiGateways.get_by("config_id", configs_obj.id)

        if getaways_obj is None:
            request_utils.log.debug("iSCSI Gateways not found")
        else:
            resultIscsiGateway, message = IscsiGateways._delete_by(
                "config_id", configs_obj.id
            )
            if resultIscsiGateway:
                request_utils.log.debug(message)

        # If configs_obj is not None, attempt to delete it and its related records
        if configs_obj is not None:
            resultIscsiConfig, message = IscsiConfigs._delete_by(
                "account_id", account_obj.id
            )
            if resultIscsiConfig:
                request_utils.log.debug(message)

        # Check and delete S3 quotas if they exist
        if s3_quotas_obj is None:
            request_utils.log.debug("S3 Quotas not found")
        else:
            resultS3Quotas, message = S3Quotas._delete_by("account_id", account_obj.id)
            if resultS3Quotas:
                request_utils.log.debug(message)

        # Check and delete iSCSI quotas if they exist
        if iscsi_quotas_obj is None:
            request_utils.log.debug("iSCSI Quotas not found")
        else:
            resultIscsiQuotas, message = IscsiQuotas._delete_by(
                "account_id", account_obj.id
            )
            if resultIscsiQuotas:
                request_utils.log.debug(message)

        # Finally, delete the account itself
        result, message = Accounts._delete_by("id", account_obj.id)
        if result:
            request_utils.log.debug(message)

        request_utils.log.debug(
            "Account and associated records deleted successfully: "
            + str(account_obj.id)
        )

        return request_utils.ok(account_obj.id)


def get_accounts_all(**kwargs):
    """
    Retrieve all accounts with optional filter parameters.
    """

    return request_utils.ok(Accounts.get_all_accounts())


def get_account_usage(**kwargs):
    """
    This function retrieves the account usage for the specified account name.
    It takes in keyword arguments and returns a dictionary containing the usage
    for the "s3" and "iscsi" services.
    """
    account_name = kwargs["account_name"]
    account_obj = Accounts.query.filter_by(name=account_name).first()
    usage = {
        "s3": _get_s3_account_usage_billing(account_obj),
        "iscsi": _get_iscsi_account_usage_billing(account_obj),
    }
    return request_utils.ok(usage)


def get_account_snapshots(**kwargs):
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
    return request_utils.ok(snapshots)


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
