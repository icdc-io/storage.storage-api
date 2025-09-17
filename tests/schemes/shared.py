from marshmallow import Schema, fields, validate

class AccountSchema(Schema):
    description = fields.String(allow_none=True)
    id = fields.Integer(required=True)
    name = fields.String(required=True)
