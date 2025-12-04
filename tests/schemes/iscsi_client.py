from marshmallow import Schema, fields


class IscsiClientTestSchema(Schema):
    id = fields.Int(required=True)
    name = fields.String(required=True)
    chap_username = fields.String(required=True)
    chap_password = fields.String(required=True)
    iqn = fields.String(required=True)
    owner = fields.String(required=True)


class IscsiClientResponseTestSchema(IscsiClientTestSchema):
    account = fields.Nested("AccountTestSchema", required=True)
    disks = fields.List(
        fields.Nested("IscsiDiskTestSchema"),
        required=True,
    )
