from marshmallow import Schema, fields


class IscsiDiskTestSchema(Schema):
    id = fields.Int(required=True)
    owner = fields.String(required=True)
    size_gb = fields.Int(required=True)
    name = fields.String(required=True)


class IscsiDiskResponseTestSchema(IscsiDiskTestSchema):
    clients = fields.List(
        fields.Nested("IscsiClientTestSchema"),
        required=True,
    )
    snapshots = fields.List(
        fields.Nested("SnapshotTestSchema"),
        required=True,
    )
