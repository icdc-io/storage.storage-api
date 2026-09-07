"""add wwn to iscsi disks

Revision ID: c2d7e9f1a4b3
Revises: a1b2c3d4e5f6
Create Date: 2026-09-03 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision = "c2d7e9f1a4b3"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "iscsi_disks",
        sa.Column("wwn", sa.String(length=128), nullable=True),
    )

    from app.models.iscsi_disk import IscsiDisks

    session = Session(bind=op.get_bind())
    try:
        disks = session.query(IscsiDisks).filter(IscsiDisks.wwn.is_(None)).all()
        for disk in disks:
            msg = f"Skipping disk with name: {disk.name} and id: {disk.id}"
            try:
                response = disk.target.iscsi_service().get_disk(disk.name)
            except ValueError as error:
                print(f"{msg}: cannot access its gateway ({error}).")
                continue

            if response.get("code", 500) >= 400:
                print(f"{msg}: cannot retrieve its WWN.")
                continue

            data = response.get("data")
            wwn = data.get("wwn") if isinstance(data, dict) else None
            if not wwn:
                print(f"{msg}: gateway returned no WWN.")
                continue

            disk.wwn = wwn

        session.flush()
    finally:
        session.close()


def downgrade():
    op.drop_column("iscsi_disks", "wwn")
