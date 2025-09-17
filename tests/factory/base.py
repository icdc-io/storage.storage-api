from factory import DictFactory
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy import select

from app.database import db
from app.models.s3_quota import S3Quotas


class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"


class BasePayloadFactory(DictFactory):
    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        data = super()._build(model_class, *args, **kwargs)
        return {k: v for k, v in data.items() if v is not None}


def get_s3_quota():
    stmt = select(S3Quotas)
    result = db.session.scalars(stmt)
    res = {quota.id: quota for quota in result}
    return res


# def check_db():
#     res = {}
#     res["quota"] = get_s3_quota()
#     res["account"] = get_accounts()
#     res["pool"] = get_s3_pools()
#     return res
