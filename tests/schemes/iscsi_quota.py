from marshmallow import Schema, fields, validate

from tests.schemes.iscsi_config import ConfigSchema
from tests.schemes.pool import PoolSchema
from tests.schemes.shared import AccountSchema


class IscsiLimitsSchema(Schema):
    clients = fields.Integer(required=True)
    data_size_gb = fields.Integer(required=True)
    disks = fields.Integer(required=True)
    snapshots = fields.Integer(required=True)


class IscsiQuotaUsageSchema(Schema):
    clients = fields.Integer(required=True)
    data_size_gb = fields.Integer(required=True)
    disks = fields.Integer(required=True)
    snapshots = fields.Integer(required=True)
    snapshots_size_gb = fields.Integer(required=True)


class IscsiQuotaSchema(Schema):
    account = fields.Nested(AccountSchema)
    account_id = fields.Integer(required=True)
    clients = fields.Integer(required=True)
    configs = fields.List(fields.Nested(ConfigSchema()), required=False)
    data_size_gb = fields.Integer(required=True)
    disks = fields.Integer(required=True)
    id = fields.Integer(required=True)
    limits = fields.Nested(IscsiLimitsSchema())
    pool = fields.Nested(PoolSchema())
    snapshots = fields.Integer(required=True)
    usage = fields.Nested(IscsiQuotaUsageSchema())
