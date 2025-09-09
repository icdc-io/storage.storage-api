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

from app.database import db
from app.models.model import AbstractModel


class IscsiGateways(db.Model, AbstractModel):

    """
    Define columns in database and methods of model
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    portal_ip_address = db.Column(db.String(128))
    ip_address = db.Column(db.String(128))
    cloudgw_id = db.Column(db.String(128))
    api_user = db.Column(db.String(128))
    api_password = db.Column(db.String(128))
    config_id = db.Column(db.Integer, db.ForeignKey("iscsi_configs.id"))

    def save(self):
        """
        INSERT SQL
        """
        return self._commit(db)

    def __repr__(self):
        return f"IscsiGateways({self.id}, {self.name}, {self.portal_ip_address}, \
            {self.ip_address}, {self.cloudgw_id}, {self.api_user}, {self.api_password}, {self.config_id})"

    def serialize(self, hide_params=None):
        """
        Serialize model method
        """
        super()._serialize()
        fields = {
            "id": "self.id",
            "name": "self.name",
            "portal_ip_address": "self.portal_ip_address",
            "ip_address": "self.ip_address",
            "config": "self._config()",
        }
        return self.response_filter(fields, hide_params)

    def _config(self):
        """
        Retrieves and serializes the IscsiConfigs object by "id" and returns a subset of its data containing the "gateways" field.
        """
        from app.models.iscsi_config import IscsiConfigs  # fix circular import

        return IscsiConfigs.get_by("id", self.config_id).serialize(["gateways"])


def validate_ip(value: str):
    try:
        ip_address(value)
    except ValueError:
        raise ValidationError("Invalid IPv4 or IPv6 address.")


class IscsiGatewaySchema(Schema):
    GATEWAY_NAME_PATTERN = r'^[a-z0-9._\-]+$'

    id = fields.Int()
    config_id = fields.Int()

    name = fields.String(
        validate=validate.And(
            validate.Length(min=1, max=64),
            validate.Regexp(regex=GATEWAY_NAME_PATTERN)
        )
    )
    portal_ip_address = fields.String(validate=validate_ip)
    ip_address = fields.String(validate=validate_ip)

    cloudgw_id = fields.String(load_only=True)
    api_user = fields.String(load_only=True)
    api_password = fields.String(load_only=True)
