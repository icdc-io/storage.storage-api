from marshmallow import Schema, fields
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app import log
from app.lib.request_utils import is_failed
from app.models.iscsi_cluster import IscsiClusters
from app.models.model import AbstractModel


class IscsiTargets(AbstractModel):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "iscsi.targets"
    id = Column(Integer, primary_key=True)
    pool_id = Column(Integer, ForeignKey("pools.id"))
    cluster_id = Column(Integer, ForeignKey("iscsi_clusters.id"))

    pool = relationship("Pools", backref="pool")
    cluster = relationship("IscsiClusters", back_populates="targets")
    disks = relationship(
        "IscsiDisks",
        back_populates="target",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"IscsiTargets({self.id}, {self.cluster.name}, {self.pool.name})"

    @property
    def gateway(self):
        """
        Get gateway for the Target.
        Choosing first on one.
        """
        if len(self.cluster.gateways) == 0:
            raise ValueError("There are no gateway for this target.")
        return self.cluster.gateways[0]

    @property
    def account(self):
        """
        Get account of the Target.
        """
        return self.cluster.account

    @property
    def iqn(self):
        """
        Get iqn of the Target.
        """
        return self.pool.get_target_iqn()

    @classmethod
    def schema(cls):
        """
        Return Marshmallow schema for validation.
        """
        return IscsiTargetSchema()

    @classmethod
    def related_objects(cls):
        """
        Define related models for recursive filtering.
        """
        from app.models.iscsi_cluster import IscsiClusters
        from app.models.pool import Pools
        return [
            (Pools, cls.pool_id),
            (IscsiClusters, cls.cluster_id),
        ]

    @classmethod
    def get_target(cls, account_id, pool_id):
        """
        Get target by account_id and pool_id.
        Be careful: this method doesn't check permissions.
        """
        return (
            cls.query
            .join(IscsiClusters, cls.cluster_id == IscsiClusters.id)
            .filter(
                cls.pool_id == pool_id,
                IscsiClusters.account_id == account_id,
            )
            .first()
        )

    @classmethod
    def get_account_targets(cls, account_id):
        """
        Get target by account_id and pool_id.
        Be careful: this method doesn't check permissions.
        """
        return (
            cls.query
            .join(IscsiClusters, cls.cluster_id == IscsiClusters.id)
            .filter(
                IscsiClusters.account_id == account_id,
            )
            .all()
        )

    def iscsi_service(self):
        """
        Access to iSCSI Service.
        For access Target instance required.
        """
        from app.lib.iscsi_utils import Iscsi

        iscsi_service = Iscsi(target=self)

        if is_failed(iscsi_service.get_target()):
            log.warning(f"Target {self.iqn} was deleted.")
            raise ValueError(f"Target {self.iqn} was deleted.")

        return iscsi_service

    def to_dict(self):
        """Serialize model"""
        return IscsiTargetResponseSchema().dump(self)


class IscsiTargetSchema(Schema):
    id = fields.Int(dump_only=True)
    iqn = fields.String(dump_only=True)
    pool_id = fields.Int(load_only=True, required=True)
    cluster_id = fields.Int(load_only=True, required=True)
    pool = fields.Nested("PoolSchema", dump_only=True)


class IscsiTargetResponseSchema(IscsiTargetSchema):
    cluster = fields.Nested("IscsiClusterSchema", exclude=["targets"], dump_only=True)
