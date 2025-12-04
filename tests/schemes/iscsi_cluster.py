from marshmallow import Schema, fields


class IscsiClusterTestSchema(Schema):
    id = fields.Int(required=True)
    name = fields.String(required=True)


class IscsiClusterResponseTestSchema(IscsiClusterTestSchema):
    account = fields.Nested("AccountTestSchema", required=True)
    gateways = fields.List(
        fields.Nested("IscsiGatewayTestSchema"),
        required=True,
    )
    targets = fields.List(
        fields.Nested("IscsiTargetTestSchema"),
        required=True,
    )
