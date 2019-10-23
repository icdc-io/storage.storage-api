from app.lib import request_utils
from app.lib.request_utils import log
from app.lib.request_utils import abort_detailed
from app.models.account import Accounts
from app.models.s3_quota import S3Quotas, S3QuotaSchema
from app.models.pool import Pools
from sqlalchemy.orm import selectinload
from flask import abort, jsonify
from marshmallow import ValidationError


def index(**kwargs):
    account = Accounts.query.filter_by(name=kwargs["account_name"]).first()
    log.debug(kwargs["account_name"])
    if not account:
        abort(404, "Account not found.")
    quotas = S3Quotas.query.options(selectinload(S3Quotas.pool)).filter_by(account_id=account.id).all()

    return jsonify(S3QuotaSchema(many=True).dump(quotas))


# TODO: implement RBAC
def create(**kwargs):
    body = kwargs["body"]
    account = Accounts.query.filter_by(name=body["account_name"]).first()
    if not account:
        abort(404, "Account with this name not found.")
    body.pop("account_name")
    try:
        S3QuotaSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    if S3Quotas.query.filter_by(account_id=account.id, pool_id=body["pool_id"]).first():
        abort(409, "Only one account quota can be configured for specific pool.")
    quota = S3Quotas(**body)
    account.s3_quotas.append(quota)
    account.save()
    
    return S3QuotaSchema().dump(quota)


# TODO: implement RBAC
def update(**kwargs):
    quota = S3Quotas.query.filter_by(id=kwargs["id"]).first()
    usage = quota.compute_usage()
    if not quota:
        abort(404, "Quota with this ID not found.")
    schema = S3QuotaSchema(context={"usage": usage})
    try:
        schema.load(kwargs["body"] | {"pool_id": quota.pool_id})
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    quota.update(kwargs["body"])

    return S3QuotaSchema().dump(quota)


# TODO: implement RBAC
def destroy(**kwargs):
    quota = S3Quotas.query.filter_by(id=kwargs["id"]).first()
    if not quota:
        abort(404, "Quota with this ID not found.")
    quota.destroy()

    return jsonify("No content.")
