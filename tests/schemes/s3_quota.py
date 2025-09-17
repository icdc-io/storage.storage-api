from marshmallow import Schema, fields, validate
from tests.schemes.pool import PoolSchema
from tests.schemes.shared import AccountSchema

class S3LimitsSchema(Schema):
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)
    users = fields.Integer(required=True)


class S3QuotaUsageSchema(Schema):
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)
    users = fields.Integer(required=True)


class S3QuotaSchema(Schema):
    account = fields.Nested(AccountSchema)
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    endpoints = fields.Dict(keys=fields.String(), values=fields.String())
    id = fields.Integer(required=True)
    limits = fields.Nested(S3LimitsSchema())
    objects = fields.Integer(required=True)
    pool = fields.Nested(PoolSchema())
    usage = fields.Nested(S3QuotaUsageSchema())
    users = fields.Integer(required=True)
