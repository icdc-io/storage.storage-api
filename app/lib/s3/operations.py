"""
S3 User Query Customization.
Overwrites standard SQLAlchemy Query methods to automatically 'enrich' S3User models
with real-time metadata and usage statistics from Ceph (RGW) during data retrieval.
"""
from sqlalchemy.orm import Query


class S3UserQuery(Query):
    def _enrich(self, results):
        if not results:
            return

        from app.lib.s3.service import CephService
        CephService().enrich(results)

    def all(self):
        results = super().all()
        self._enrich(results)
        return results

    def first(self):
        result = super().first()
        if result:
            self._enrich(result)
        return result

    def __iter__(self):
        results = list(super().__iter__())
        self._enrich(results)
        return iter(results)
