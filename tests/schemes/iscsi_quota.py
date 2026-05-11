from marshmallow import Schema, fields


class IscsiLimitsTestSchema(Schema):
    clients = fields.Int(required=True)
    data_size_gb = fields.Int(required=True)
    disks = fields.Int(required=True)
    snapshots = fields.Int(required=True)


class IscsiQuotaUsageTestSchema(Schema):
    clients = fields.Int(required=True)
    data_size_gb = fields.Int(required=True)
    disks = fields.Int(required=True)
    snapshots = fields.Int(required=True)
    snapshots_size_gb = fields.Int(required=True)


class IscsiQuotaTestSchema(Schema):
    id = fields.Int(required=True)
    clients = fields.Int(required=True)
    data_size_gb = fields.Int(required=True)
    disks = fields.Int(required=True)
    snapshots = fields.Int(required=True)


class IscsiQuotaResponseTestSchema(IscsiQuotaTestSchema):
    account = fields.Nested("AccountTestSchema", required=True)
    pool = fields.Nested("PoolTestSchema", required=True)
    limits = fields.Nested(IscsiLimitsTestSchema, required=True)
    usage = fields.Nested(IscsiQuotaUsageTestSchema, required=True)
    target = fields.Dict(required=True)
