from marshmallow import Schema, fields, validate


class PoolTestSchema(Schema):
    id = fields.Integer(required=True)
    klass = fields.String(data_key="class", required=True)
    name = fields.String(required=True)
    type = fields.String(required=True)
