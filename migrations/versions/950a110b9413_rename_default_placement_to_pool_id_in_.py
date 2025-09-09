"""Rename default_placement to pool_id in S3Users

Revision ID: 950a110b9413
Revises: fc43209701a5
Create Date: 2024-11-05 18:01:57.407229
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '950a110b9413'
down_revision = 'fc43209701a5'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Get the list of columns in the s3_users table
    columns = [col['name'] for col in inspector.get_columns('s3_users')]

    # Check if the default_placement column still exists.
    # If it has already been renamed (or removed), we'll skip these steps.
    if 'default_placement' in columns:
        with op.batch_alter_table('s3_users', schema=None) as batch_op:
            # Make sure to drop the foreign key only if it actually exists,
            # because the name may differ or it may have already been removed.
            fks = inspector.get_foreign_keys('s3_users')
            fk_names = [fk['name'] for fk in fks if fk['name']]

            if 's3_users_default_placement_fkey' in fk_names:
                batch_op.drop_constraint('s3_users_default_placement_fkey', type_='foreignkey')

            # Rename the column
            batch_op.alter_column(
                'default_placement',
                new_column_name='pool_id',
                existing_type=sa.Integer(),
                existing_nullable=True
            )

            # Create the new foreign key
            batch_op.create_foreign_key(
                's3_users_pool_id_fkey',  # we can explicitly set a name here
                'pools',
                ['pool_id'],
                ['id']
            )
    else:
        print("Column 'default_placement' is already renamed or doesn't exist — skipping the rename steps.")


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Get the list of columns in the s3_users table
    columns = [col['name'] for col in inspector.get_columns('s3_users')]

    # Check if the pool_id column exists
    if 'pool_id' in columns:
        with op.batch_alter_table('s3_users', schema=None) as batch_op:
            # Similarly, check if the new foreign key exists
            fks = inspector.get_foreign_keys('s3_users')
            fk_names = [fk['name'] for fk in fks if fk['name']]

            if 's3_users_pool_id_fkey' in fk_names:
                batch_op.drop_constraint('s3_users_pool_id_fkey', type_='foreignkey')

            # Rename the column back to default_placement
            batch_op.alter_column(
                'pool_id',
                new_column_name='default_placement',
                existing_type=sa.Integer(),
                existing_nullable=True
            )

            # Re-create the original foreign key
            batch_op.create_foreign_key(
                's3_users_default_placement_fkey',
                'pools',
                ['default_placement'],
                ['id']
            )
    else:
        print("Column 'pool_id' does not exist — possibly already downgraded. Skipping downgrade steps.")
