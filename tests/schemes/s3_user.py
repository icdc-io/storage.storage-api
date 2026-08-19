from marshmallow import Schema, fields, validate

from tests.schemes.pool import PoolTestSchema
from tests.schemes.shared import AccountTestSchema


class KeysS3Schema(Schema):
    access_key = fields.String(required=True)
    secret_key = fields.String(required=True)
    user = fields.String(required=True)


class KeysSwiftSchema(Schema):
    secret_key = fields.String(required=True)
    user = fields.String(required=True)


class KeysSchema(Schema):
    s3 = fields.Nested(KeysS3Schema(), required=True)
    swift = fields.Nested(KeysSwiftSchema(), required=True)


class S3UserQuotaSchema(Schema):
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)


class S3UserUsageSchema(Schema):
    buckets = fields.Integer(required=True)
    data_size_mb = fields.Integer(required=True)
    objects = fields.Integer(required=True)


class S3UserTestResponseSchema(Schema):
    account = fields.Nested(AccountTestSchema, required=True)
    description = fields.String(allow_none=True)
    id = fields.Integer(required=True)
    keys = fields.Nested(KeysSchema(), required=True)
    name = fields.String(required=True)
    owner = fields.String(required=True)
    pool = fields.Nested(PoolTestSchema(), required=True)
    status = fields.String(
        required=True,
        validate=validate.OneOf(["active", "locked", "deleted", "unknown"])
    )
    usage = fields.Nested(S3UserUsageSchema(), required=True)
    quota = fields.Nested(S3UserQuotaSchema(), required=True)
