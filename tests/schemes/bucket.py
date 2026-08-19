from marshmallow import Schema, fields


class BucketQuotaTestSchema(Schema):
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)


class BucketUsageTestSchema(Schema):
    data_size_mb = fields.Integer(required=True)
    multipart_objects = fields.Integer(required=True)
    objects = fields.Integer(required=True)
    total_objects = fields.Integer(required=True)


class BucketResponseTestSchema(Schema):
    name = fields.String(required=True)
    path = fields.String(required=True)
    quota = fields.Nested(BucketQuotaTestSchema(), required=True)
    usage = fields.Nested(BucketUsageTestSchema(), required=True)
    user_name = fields.String(required=True)
