from marshmallow import Schema, fields, validate
from tests.schemes.iscsi_quota import IscsiQuotaSchema
from tests.schemes.s3_quota import S3QuotaSchema


class QuotasSchema(Schema):
    iscsi = fields.List(fields.List(fields.Nested(IscsiQuotaSchema())))
    s3 = fields.List(fields.List(fields.Nested(S3QuotaSchema())))


class AccountResponseSchema(Schema):
    description = fields.String(allow_none=True)
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    quotas = fields.Nested(QuotasSchema())
