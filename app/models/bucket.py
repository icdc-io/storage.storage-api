"""
S3 Bucket Model
"""

from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class Bucket:
    def __init__(self, name, path, user_name, quota, usage=None):
        self.path = path
        self.name = name
        self.user_name = user_name
        self.quota = quota
        self.usage = usage

    def __repr__(self):
        return f"<Buckets(name={self.name}, user={self.user_name}, quota={self.quota})>"

    def to_dict(self):
        return BucketSchema().dump(self)


class BucketQuotaSchema(Schema):
    data_size_mb = fields.Int(min=0)
    objects = fields.Int(min=0)


class BucketSchema(Schema):
    BUCKET_NAME_PATTERN = (
        r'^(?!xn--)'
        r'^(?!(\d{1,3}\.){3}\d{1,3}$)'
        r'(?!.*\.\.)'
        r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$'
    )

    path = fields.String(dump_only=True)
    name = fields.String(
        validate=validate.And(
            validate.Length(min=3, max=63),
            validate.Regexp(regex=BUCKET_NAME_PATTERN)
        ),
        required=True
    )
    user_name = fields.String(required=True)

    quota = fields.Nested(BucketQuotaSchema())
    usage = fields.Dict(dump_only=True)

    @validates_schema
    def validate_bucket_schema(self, data, **kwargs):
        s3_user = self.context.get("user")
        bucket = self.context.get("bucket")

        if not s3_user and not bucket:
            return

        errors = {}
        new_quota = data.get("quota", {})

        if data.get("name") and "/" in data.get("name"):
            errors["Name"] = "Bucket name should not contain slashes '/'"

        # Determine current quota
        if bucket:
            cur_quota = bucket.quota
        else:
            cur_quota = {"data_size_mb": -1, "objects": -1}

        for key in ["data_size_mb", "objects"]:
            new_quota[key] = new_quota.get(key, cur_quota.get(key))

        user_quota = s3_user.quota
        for key in ["data_size_mb", "objects"]:
            if user_quota[key] < new_quota[key]:
                errors[key] = f"Bucket quota '{key}' must not exceed user quota."

        if errors:
            raise ValidationError(errors)
