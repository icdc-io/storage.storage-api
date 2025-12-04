from marshmallow import Schema, fields, validate


class PoolTestSchema(Schema):
    id = fields.Integer(required=True)
    klass = fields.String(required=True)
    name = fields.String(required=True)
    type = fields.String(required=True)
