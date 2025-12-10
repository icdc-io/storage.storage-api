"""
iSCSI Gateway model
"""
from ipaddress import ip_address

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    validate,
)
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.model import AbstractModel


class IscsiGateways(AbstractModel):

    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "iscsi.gateways"
    id = Column(Integer, primary_key=True)
    name = Column(String(128))
    portal_ip_address = Column(String(128))
    ip_address = Column(String(128))
    cloudgw_id = Column(String(128))
    api_user = Column(String(128))
    api_password = Column(String(128))
    cluster_id = Column(Integer, ForeignKey("iscsi_clusters.id"))
    cluster = relationship("IscsiClusters", back_populates="gateways")

    def __repr__(self):
        return f"IscsiGateways({self.id}, {self.name}, {self.portal_ip_address}, \
            {self.ip_address}, {self.cloudgw_id}, {self.api_user}, {self.api_password}, {self.cluster_id})"

    @classmethod
    def schema(cls):
        """
        Return Marshmallow schema for validation.
        """
        return IscsiGatewaySchema()

    @classmethod
    def related_objects(cls) -> list:
        """
        Define related models for recursive filtering.
        """
        from app.models.iscsi_target import IscsiClusters
        return [
            (IscsiClusters, cls.cluster_id)
        ]

    def to_dict(self):
        """
        Serialize the current gateway to a dictionary.
        """
        return IscsiGatewaySchema().dump(self)


def validate_ip(value: str):
    try:
        ip_address(value)
    except ValueError:
        raise ValidationError("Invalid IPv4 or IPv6 address.")


class IscsiGatewaySchema(Schema):
    GATEWAY_NAME_PATTERN = r'^[a-z0-9._\-]+$'

    id = fields.Int()
    cluster_id = fields.Int(load_only=True, required=True)

    name = fields.String(
        required=True,
        validate=validate.And(
            validate.Length(
                min=1,
                max=64,
                error="Gateway name length must be between 1 and 64 characters."
            ),
            validate.Regexp(
                regex=GATEWAY_NAME_PATTERN,
                error="Gateway.name: String does not match expected pattern."
            )
        )
    )
    portal_ip_address = fields.String(validate=validate_ip, required=True)
    ip_address = fields.String(validate=validate_ip, required=True)

    cloudgw_id = fields.String(load_only=True, required=True)
    api_user = fields.String(load_only=True, required=True)
    api_password = fields.String(load_only=True, required=True)


class IscsiGatewayResponseSchema(IscsiGatewaySchema):
    cluster = fields.Nested("IscsiClusterSchema", dump_only=True)
