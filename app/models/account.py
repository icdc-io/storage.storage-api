"""
Account Model
"""
from typing import Optional

from flask_rbac_icdc import PermissionException, RbacAccount
from marshmallow import (
    Schema,
    fields,
    validate,
)
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app import consts
from app.lib.auth import is_operator
from app.models.model import AbstractModel


class Accounts(AbstractModel, RbacAccount):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "accounts"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    description = Column(String(128))
    s3_quotas = relationship(
        "S3Quotas", back_populates="account", cascade="all, delete-orphan"
    )
    iscsi_quotas = relationship(
        "IscsiQuotas", back_populates="account", cascade="all, delete-orphan"
    )
    iscsi_clusters = relationship(
        "IscsiClusters", back_populates="account", cascade="all, delete-orphan"
    )
    s3_users = relationship(
        "S3Users", back_populates="account", cascade="all, delete-orphan"
    )
    iscsi_clients = relationship(
        "IscsiClients", backref="clients", cascade="all, delete-orphan"
    )

    def update(self, body):
        """
        Update Account attributes and save changes.
        """
        self.description = body.get("description", self.description)
        self.save()

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

    @classmethod
    def schema(cls):
        """
        Return Marshmallow schema for validation.
        """
        return AccountSchema()

    @staticmethod
    def validate_account_data(data: dict) -> None:
        """
        Validate the input data for account creation.
        """
        from app.models.iscsi_cluster import IscsiClusterSchema
        from app.models.iscsi_gateway import IscsiGatewaySchema
        from app.models.iscsi_quota import IscsiQuotaSchema
        from app.models.iscsi_target import IscsiTargetSchema
        from app.models.s3_quota import S3QuotaSchema

        s3 = data.get("s3", {})
        for quota in s3.get("quotas", []):
            S3QuotaSchema(partial=["account_id"]).load(quota)

        iscsi = data.get("iscsi", {})
        for quota in iscsi.get("quotas", []):
            IscsiQuotaSchema(partial=["account_id"]).load(quota)

        for cluster in iscsi.get("clusters", []):
            for gw in cluster.pop("gateways", []):
                IscsiGatewaySchema(partial=["cluster_id"]).load(gw)
            for target in cluster.pop("targets", []):
                IscsiTargetSchema(partial=["cluster_id"]).load(target)

            IscsiClusterSchema(partial=["account_id"]).load(cluster)

    @staticmethod
    def get_all_accounts():
        """
        Get all accounts from the database, excluding accounts with the name 'default'.
        """
        filtered_accounts = Accounts.query.filter(Accounts.name != consts.ACCOUNT_DEFAULT).all()
        return Accounts.to_dict_many(filtered_accounts)

    @classmethod
    def get_by_name(cls, account_name: str) -> Optional["Accounts"]:
        """Retrive account by name"""
        return cls.query.filter_by(name=account_name).first()

    def _services(self):
        """
        Returns a dictionary containing the serialized iscsi and s3 quotas based on the provided iscsi_quotas and s3_quotas.
        """
        from app.models.iscsi_cluster import IscsiClusterSchema
        from app.models.iscsi_quota import IscsiQuotaSchema
        from app.models.s3_quota import S3QuotaSchema
        return {
            "s3": {
                "quotas": S3QuotaSchema(many=True).dump(self.s3_quotas)
            },
            "iscsi": {
                "quotas": IscsiQuotaSchema(many=True).dump(self.iscsi_quotas),
                "clusters": IscsiClusterSchema(many=True).dump(self.iscsi_clusters)
            },
        }

    def get_role(self, requested_role: str) -> str:
        """
        Determines the effective role of the account based on provided authentication
        information.

        This method validates the requested role and returns the appropriate role value
        for the subject.

        Raises:
            PermissionException: If the provided operator role is invalid.
        """
        operator = is_operator(self.name, requested_role)
        if requested_role == "operator" and not operator:
            raise PermissionException("You are not operator")
        if operator:
            return "operator"
        return requested_role

    @classmethod
    def to_dict_many(cls, accounts):
        """
        Serialize a list of Accounts.
        """
        return AccountResponseSchema(many=True).dump(accounts)

    def to_dict(self):
        """
        Construct a response dictionary for an account, including its associated S3 and iSCSI quotas.
        """
        return AccountResponseSchema().dump(self)


class AccountSchema(Schema):
    ACCOUNT_NAME_PATTERN = r"^[a-z0-9]+$"
    ACCOUNT_DESCRIPTION_PATTERN = r"^[\w ,.:/;\[\]!@^*()_\-+=]*$"

    id = fields.Int()

    name = fields.String(
        required=True,
        validate=validate.And(
            validate.Length(min=1, max=24),
            validate.Regexp(regex=ACCOUNT_NAME_PATTERN)
        ),
    )

    description = fields.String(
        validate=validate.And(
            validate.Length(min=0, max=24),
            validate.Regexp(regex=ACCOUNT_DESCRIPTION_PATTERN)
        )
    )


class AccountResponseSchema(AccountSchema):
    services = fields.Function(lambda account: account._services(), dump_only=True)

