from marshmallow import Schema, fields


class IscsiGatewayTestSchema(Schema):
    id = fields.Int(required=True)
    name = fields.String(required=True)
    portal_ip_address = fields.String(required=True)


class IscsiGatewayResponseTestSchema(IscsiGatewayTestSchema):
    cluster = fields.Nested("IscsiClusterTestSchema", required=True)
