from marshmallow import Schema, fields


class AccountSchema(Schema):
    description = fields.String(allow_none=True)
    id = fields.Integer(required=True)
    name = fields.String(required=True)


class ISCSILimitsSchema(Schema):
    clients = fields.Integer(required=True)
    data_size_gb = fields.Integer(required=True)
    disks = fields.Integer(required=True)
    snapshots = fields.Integer(required=True)


class S3LimitsSchema(Schema):
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)
    users = fields.Integer(required=True)


class PoolSchema(Schema):
    id = fields.Integer(required=True)
    klass = fields.String(required=True)
    name = fields.String(required=True)
    type = fields.String(required=True)


class S3UsageSchema(Schema):
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)
    users = fields.Integer(required=True)


class ISCSIUsageSchema(Schema):
    clients = fields.Integer(required=True)
    data_size_gb = fields.Integer(required=True)
    disks = fields.Integer(required=True)
    snapshots = fields.Integer(required=True)
    snapshots_size_gb = fields.Integer(required=True)


class ConfigSchema(Schema):
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    target_iqn = fields.String(required=True)


class QuotaISCSISchema(Schema):
    account = fields.Nested(AccountSchema)
    account_id = fields.Integer(required=True)
    clients = fields.Integer(required=True)
    configs = fields.List(fields.Nested(ConfigSchema), required=False)
    data_size_gb = fields.Integer(required=True)
    disks = fields.Integer(required=True)
    id = fields.Integer(required=True)
    limits = fields.Nested(ISCSILimitsSchema)
    pool = fields.Nested(PoolSchema)
    snapshots = fields.Integer(required=True)
    usage = fields.Nested(ISCSIUsageSchema)


class QuotaS3Schema(Schema):
    account = fields.Nested(AccountSchema)
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    endpoints = fields.Dict(keys=fields.String(), values=fields.String())
    id = fields.Integer(required=True)
    limits = fields.Nested(S3LimitsSchema)
    objects = fields.Integer(required=True)
    pool = fields.Nested(PoolSchema)
    usage = fields.Nested(S3UsageSchema)
    users = fields.Integer(required=True)


class QuotasSchema(Schema):
    iscsi = fields.List(fields.List(fields.Nested(QuotaISCSISchema)))
    s3 = fields.List(fields.List(fields.Nested(QuotaS3Schema)))


class AccountResponseSchema(Schema):
    description = fields.String(allow_none=True)
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    quotas = fields.Nested(QuotasSchema)
