"""
Account Model
"""
from typing import Any, Dict, Union
from app.database import db
from app.loggers import log
from app.models.iscsi_config import IscsiConfigs
from app.models.iscsi_quota import IscsiQuotas, IscsiQuotaSchema
from app.models.iscsi_gateway import IscsiGateways
from app.models.model import AbstractModel
from app.models.pool import Pools
from app.models.s3_quota import S3Quotas, S3QuotaSchema
from sqlalchemy.orm import joinedload


class Accounts(db.Model, AbstractModel):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.String(128))
    s3_quotas = db.relationship("S3Quotas", back_populates="account", cascade="all, delete-orphan")
    iscsi_quotas = db.relationship(
        "IscsiQuotas", backref="account_iscsiquotas", cascade="all, delete-orphan"
    )
    s3_users = db.relationship("S3Users", back_populates="account", cascade="all, delete-orphan")
    iscsi_configs = db.relationship(
        "IscsiConfigs", backref="account-configs", cascade="all, delete-orphan"
    )
    iscsi_clients = db.relationship(
        "IscsiClients", backref="clients", cascade="all, delete-orphan"
    )

    def save(self):
        """
        Save the data using the specified database connection.
        """

        self._commit(db)

    def __repr__(self):
        """
        Return a string representation of the Account object.
        """
        return f"Account('{self.id}', '{self.name}', '{self.description}', {self.s3_quotas}, {self.iscsi_quotas})"

    def __str__(self):
        """
        Return a string representation of the Account object including id, name,
        description, s3_quotas, and iscsi_quotas.
        """
        return f"Account('{self.id}', '{self.name}', \
            '{self.description}', {self.s3_quotas}, {self.iscsi_quotas})"

    def serialize(self, hide_params=None):
        """
        Serialize the object and return a response after filtering the specified fields.

        Args:
            hide_params (dict): A dictionary of parameters to hide.

        Returns:
            dict: A filtered response containing the specified fields.
        """

        super()._serialize()
        fields = {
            "id": "self.id",
            "name": "self.name",
            "description": "self.description",
            "quotas": "self._quotas(self.iscsi_quotas, self.s3_quotas)",
        }
        return self.response_filter(fields, hide_params)

    def _quotas(self):
        """
        Returns a dictionary containing the serialized iscsi and s3 quotas based on the provided iscsi_quotas and s3_quotas.
        """
        return {
            "iscsi": [
                IscsiQuotaSchema(many=True).dump(self.iscsi_quotas)
            ],
            "s3": [
                S3QuotaSchema(many=True).dump(self.s3_quotas)
            ],
        }

    @staticmethod
    def get_all_accounts():
        """
        Get all accounts from the database, excluding accounts with the name 'default'.
        """
        filtered_accounts = Accounts.query.filter(Accounts.name != "default").all()
        return [account.serialize() for account in filtered_accounts]

    @staticmethod
    def validate_account_data(data):
        """
        Validate the input data for account creation or update, omitting the uniqueness check for iSCSI config names.
        """
        # Required fields for account and specific services
        required_fields = ["name"]
        services_required_fields = {"s3": ["quotas"], "iscsi": ["configs", "quotas"]}
        iscsi_config_required_fields = ["name", "target_iqn"]
        gateway_required_fields = [
            "name",
            "portal_ip_address",
            "ip_address",
            "cloudgw_id",
            "api_user",
            "api_password",
        ]

        # Initialize sets for tracking unique values (except iSCSI config names)
        portal_ip_addresses = set()
        ip_addresses = set()
        cloudgw_ids = set()

        # Validate general account fields
        for field in required_fields:
            if not data.get(field):
                return False, f"{field.capitalize()} cannot be empty."

        # Validate service-specific fields
        for service, fields in services_required_fields.items():
            if service in data.get("services", {}):
                for field in fields:
                    if not data["services"][service].get(field):
                        return False, f"{service.capitalize()} {field} cannot be empty."

        # Validate iSCSI configs and skip uniqueness check for iSCSI config names
        if "iscsi" in data.get("services", {}):
            for iscsi_config in data["services"]["iscsi"].get("configs", []):
                for field in iscsi_config_required_fields:
                    if not iscsi_config.get(field):
                        return False, f"iSCSI Config {field} cannot be empty."
                # Previously performed uniqueness checks are removed here

                # Validate gateway details with uniqueness checks
                for gateway in iscsi_config.get("gateways", []):
                    for field in gateway_required_fields:
                        if not gateway.get(field):
                            return False, f"Gateway {field} cannot be empty."
                    # Perform uniqueness checks for gateway details
                    if (
                        gateway["portal_ip_address"] in portal_ip_addresses
                        or gateway["ip_address"] in ip_addresses
                        or gateway["cloudgw_id"] in cloudgw_ids
                    ):
                        return (
                            False,
                            "Gateway 'portal_ip_address', 'ip_address', or 'cloudgw_id' must be unique.",
                        )
                    portal_ip_addresses.add(gateway["portal_ip_address"])
                    ip_addresses.add(gateway["ip_address"])
                    cloudgw_ids.add(gateway["cloudgw_id"])

        # If all validations pass
        return True, "Validation successful."

    def toDict(self):
        """
        Construct a response dictionary for an account, including its associated S3 and iSCSI quotas.
        This method utilizes the toJson method from IscsiQuotas and S3Quotas to serialize quota information.
        """

        # Construct and return the response dictionary
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "quotas": {
                "s3": [quota.toDict() for quota in self.s3_quotas],
                "iscsi": [quota.toDict() for quota in self.iscsi_quotas],
            },
        }


from marshmallow import Schema, fields


class AccountSchema(Schema):
    id = fields.Int()
    name = fields.String()
    description = fields.String()
