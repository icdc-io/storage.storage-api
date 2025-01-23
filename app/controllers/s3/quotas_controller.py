from app.lib import request_utils
from app.lib.request_utils import log, abort_detailed, parse_jsonapi_filters
from app.models.account import Accounts
from app.models.s3_quota import S3Quotas, S3QuotaSchema
from app.models.pool import Pools
from sqlalchemy.orm import selectinload
from flask import abort, jsonify, request
from marshmallow import ValidationError

schema = S3QuotaSchema(partial=True)


def index(subject):
    parsed_filters = parse_jsonapi_filters(request.args)
    filters = schema.load(parsed_filters)
    # quotas = S3Quotas.query.options(selectinload(S3Quotas.pool)).filter_by(account_id=account.id).all()
    quotas = S3Quotas.filtered(subject.filters).options(selectinload(S3Quotas.pool)).filter_by(**filters).all()
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
