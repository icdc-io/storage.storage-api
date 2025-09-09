"""remove s3_placement_target from pools table

Revision ID: fe66707b8594
Revises: 950a110b9413
Create Date: 2025-02-18 15:55:16.451176

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'fe66707b8594'
down_revision = '950a110b9413'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Get the list of columns in the pools table
    columns = [col['name'] for col in inspector.get_columns('pools')]
    if "s3_placement_target" in columns:
        with op.batch_alter_table("pools", schema=None) as batch_op:
            batch_op.drop_column("s3_placement_target")
    else:
        print("Column 's3_placement_target' is already removed — skipping the rename steps.")


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Get the list of columns in the pools table
    columns = [col['name'] for col in inspector.get_columns('pools')]
    if "s3_placement_target" not in columns:
        with op.batch_alter_table("pools", schema=None) as batch_op:
            batch_op.add_column(sa.Column("s3_placement_target", sa.String(), nullable=True))
    else:
        print("Column 's3_placement_target' is already added. Skipping downgrade steps.")
