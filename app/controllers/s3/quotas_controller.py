from app.lib import request_utils
from app.lib.request_utils import log, abort_detailed, parse_jsonapi_filters, request_json
from app.models.account import Accounts
from app.models.s3_quota import S3Quotas, S3QuotaSchema
from app.models.pool import Pools
from sqlalchemy.orm import selectinload
from flask import abort, jsonify, request
from marshmallow import ValidationError


def index(subject):
    schema = S3QuotaSchema(partial=True)
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = schema.load(parsed_filters)
    except TypeError as e:
        abort(400, "Invalid query parameters.")
    quotas = S3Quotas.filtered(subject).options(selectinload(S3Quotas.pool)) \
             .filter_by(**filters).except_(S3Quotas.get_default_limitsets()).all()
    return jsonify(S3QuotaSchema(many=True).dump(quotas))


def create(subject):
    body = request_json(request)
    account = Accounts.filtered(subject).filter_by(name=body["account_name"]).first()
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


def update(subject, quota_id):
    body = request_json(request)
    quota = S3Quotas.filtered(subject).filter_by(id=quota_id).first()
    if not quota:
        abort(404, "Quota with this ID not found or you haven't access for it.")
    usage = quota.compute_usage()
    schema = S3QuotaSchema(context={"usage": usage})
    try:
        schema.load(body | {"pool_id": quota.pool_id})
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    quota.update(body)

    return S3QuotaSchema().dump(quota)


def destroy(subject, quota_id):
    quota = S3Quotas.filtered(subject).filter_by(id=quota_id).first()
    if not quota:
        abort(404, "Quota with this ID not found or you haven't access for it.")
    quota.destroy()

    return jsonify("No content.")
