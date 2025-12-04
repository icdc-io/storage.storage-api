from marshmallow import Schema, fields


class SnapshotTestSchema(Schema):
    id = fields.Int(required=True)
    name = fields.String(required=True)
    description = fields.String(required=True)
    provisioned = fields.Int(required=True)
    size_gb = fields.Int(required=True)
    creation_time = fields.DateTime(required=True)
    disk_id = fields.Int(required=True)


class SnapshotResponseTestSchema(SnapshotTestSchema):
    disk = fields.Nested("IscsiDiskTestSchema", required=True)
