from marshmallow import Schema, fields


class IscsiTargetTestSchema(Schema):
    id = fields.Int(required=True)
    pool = fields.Nested("PoolTestSchema", required=True)
    iqn = fields.String(required=True)


class IscsiTargetResponseTestSchema(IscsiTargetTestSchema):
    cluster = fields.Nested("IscsiClusterTestSchema", required=True)
