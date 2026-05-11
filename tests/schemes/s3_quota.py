from marshmallow import Schema, fields


class S3LimitsTestSchema(Schema):
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)
    users = fields.Integer(required=True)


class S3QuotaUsageTestSchema(Schema):
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)
    users = fields.Integer(required=True)


class S3QuotaTestSchema(Schema):
    id = fields.Integer(required=True)
    users = fields.Integer(required=True)
    buckets = fields.Integer(required=True)
    objects = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    endpoints = fields.Dict(keys=fields.String(), values=fields.String())
    limits = fields.Nested(S3LimitsTestSchema)
    usage = fields.Nested(S3QuotaUsageTestSchema)


class S3QuotaResponseTestSchema(S3QuotaTestSchema):
    account = fields.Nested("AccountTestSchema")
    pool = fields.Nested("PoolTestSchema")
