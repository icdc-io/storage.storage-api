from marshmallow import Schema, fields, validate


class ConfigSchema(Schema):
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    target_iqn = fields.String(required=True)

