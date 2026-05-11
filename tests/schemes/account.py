from marshmallow import Schema, fields, validate

from tests.schemes.iscsi_quota import IscsiQuotaTestSchema
from tests.schemes.s3_quota import S3QuotaTestSchema


class QuotasSchema(Schema):
    iscsi = fields.List(fields.List(fields.Nested(IscsiQuotaTestSchema())))
    s3 = fields.List(fields.List(fields.Nested(S3QuotaTestSchema())))


class AccountTestResponseSchema(Schema):
    description = fields.String(allow_none=True)
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    quotas = fields.Nested(QuotasSchema())
