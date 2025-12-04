"""
iSCSI Cluster model
"""
from marshmallow import Schema, fields, validate
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.model import AbstractModel


class IscsiClusters(AbstractModel):
    """
    iSCSI Cluster model.
    """
    RESOURCE_NAME = "iscsi.clusters"
    id = Column(Integer, primary_key=True)
    name = Column(String(128))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    account = relationship(
        "Accounts", back_populates="iscsi_clusters"
    )
    targets = relationship(
        "IscsiTargets", back_populates="cluster", cascade="all, delete-orphan"
    )
    gateways = relationship(
        "IscsiGateways", back_populates="cluster", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"IscsiClusters({self.id}, {self.name}, {self.account_id})"

    def update(self, body: dict) -> None:
        """
        Update cluster attributes and save changes.
        """
        self.name = body.get("name", self.name)
        self.save()

    @classmethod
    def schema(cls):
        """
        Return Marshmallow schema for validation.
        """
        return IscsiClusterSchema()

    @classmethod
    def related_objects(cls) -> list:
        """
        Define related models for recursive filtering.
        """
        from app.models.account import Accounts
        return [(Accounts, cls.account_id)]

    @classmethod
    def to_dict_many(cls, clusters):
        """
        Serialize a list of clusters.
        """
        return IscsiClusterResponseSchema(many=True).dump(clusters)

    def to_dict(self) -> dict:
        """
        Serialize a single cluster.
        """
        return IscsiClusterResponseSchema().dump(self)


class IscsiClusterSchema(Schema):
    CLUSTER_NAME_PATTERN = r"^cluster-[0-9a-f]{8}$"

    id = fields.Int(dump_only=True)
    account_id = fields.Int(load_only=True, required=True)

    gateways = fields.Nested("IscsiGatewaySchema", dump_only=True, many=True)
    targets = fields.Nested("IscsiTargetSchema", dump_only=True, many=True)

    name = fields.String(
        required=True,
        validate=validate.And(
            validate.Length(min=1, max=64),
            validate.Regexp(regex=CLUSTER_NAME_PATTERN)
        ),
    )


class IscsiClusterResponseSchema(IscsiClusterSchema):
    account = fields.Nested("AccountSchema", dump_only=True)
