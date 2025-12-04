"""rename iscsi_configs -> iscsi_clusters and create new table iscsi targets

Revision ID: a1b2c3d4e5f6
Revises: fe66707b8594
Create Date: 2025-09-23 15:50:12.967121

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'fe66707b8594'
branch_labels = None
depends_on = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def _fk_exists(inspector, table: str, fk_name: str) -> bool:
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table))


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # -- 0) Define starting names of tables
    configs_table_name  = "iscsi_configs"
    clusters_table_name = "iscsi_clusters"
    targets_table_name  = "iscsi_targets"
    disks_table_name    = "iscsi_disks"
    gateways_table_name = "iscsi_gateways"

    # -- 1) Rename iscsi_configs -> iscsi_clusters
    #       If not already renamed
    if _table_exists(inspector, configs_table_name) and not _table_exists(inspector, clusters_table_name):
        op.rename_table(configs_table_name, clusters_table_name)
    else:
        # already renamed or tables are not exists
        if not _table_exists(inspector, clusters_table_name):
            raise RuntimeError(
                "No source table named iscsi_configs and destination table name iscsi_clusters."
            )

    # Update inspector
    inspector = sa.inspect(conn)

    # -- 2) Create iscsi_targets table, if not exist.
    if not _table_exists(inspector, targets_table_name):
        op.create_table(
            targets_table_name,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "pool_id",
                sa.Integer(),
                sa.ForeignKey("pools.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "cluster_id",
                sa.Integer(),
                sa.ForeignKey(f"{clusters_table_name}.id", ondelete="RESTRICT"),
                nullable=False,
            ),
        )
    inspector = sa.inspect(conn)
    uc_name = "uq_iscsi_targets_cluster_pool"
    uc_exists = any(
        uc.get("name") == uc_name
        or set(uc.get("column_names") or []) == {"cluster_id", "pool_id"}
        for uc in inspector.get_unique_constraints(targets_table_name)
    )
    if not uc_exists:
        op.create_unique_constraint(
            uc_name,
            targets_table_name,
            ["cluster_id", "pool_id"],
        )
    # -- 3) Transfer pool_id from cluster.pool_id to target.pool_id,
    #       if not already transferred
    if _column_exists(inspector, clusters_table_name, "pool_id"):
        op.execute(
            f"""
            INSERT INTO {targets_table_name} (pool_id, cluster_id)
            SELECT c.pool_id, c.id
            FROM {clusters_table_name} c
            WHERE c.pool_id IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1 FROM {targets_table_name} t
                    WHERE t.cluster_id = c.id and t.pool_id = c.pool_id
               );
            """
        )
    # --- sync sequence/identity for iscsi_targets.id with current MAX(id)
    op.execute("""
    DO $$
    DECLARE
      seq_name text;
      max_id bigint;
    BEGIN
      SELECT pg_get_serial_sequence('iscsi_targets', 'id') INTO seq_name;
      SELECT COALESCE(MAX(id), 0) INTO max_id FROM iscsi_targets;
      EXECUTE format(
        'SELECT setval(%L, %s, true);',
        seq_name,
        GREATEST(max_id, 1)
      );
    END $$;
    """)

    # -- 4) Change disks.config_id to disks.target_id
    #       Make sure that name of column is not already renamed.
    src_col = "config_id"
    dst_col = "target_id"

    if _column_exists(inspector, disks_table_name, src_col):
        # Delete fkey config_id related to iscsi_cluster
        fks = [
            fk for fk in inspector.get_foreign_keys(disks_table_name)
            if src_col in (fk.get("constrained_columns") or [])
        ]
        for fk in fks:
            name = fk.get("name")
            if name:
                op.drop_constraint(name, disks_table_name, type_="foreignkey")
        # Rename column from config_id to target_id
        with op.batch_alter_table(disks_table_name) as batch:
            batch.alter_column(
                src_col,
                new_column_name=dst_col,
                existing_type=sa.Integer(),
                existing_nullable=True,
            )
    # Update inspector
    inspector = sa.inspect(conn)

    # -- 5) Replace cluster ids with the ids of the corresponding targets
    #       (matched by cluster_id and pool_id). If not replaced
    if _column_exists(inspector, clusters_table_name, "pool_id"):
        op.execute(
            f"""
            UPDATE iscsi_disks d
            SET    target_id = t.id
            FROM   iscsi_clusters c
            JOIN   iscsi_targets  t
                   ON  t.cluster_id = c.id
                   AND t.pool_id    IS NOT DISTINCT FROM c.pool_id
            WHERE  d.{dst_col} = c.id;
            """
        )

    # -- 6) Create new fkey for target_id related to iscsi_targets,
    #       if not already created
    fk_name = "fk_iscsi_disks_target_id"
    name_exists = any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(disks_table_name))
    pair_exists = any(
        set(fk.get("constrained_columns") or []) == {"target_id"} and
        fk.get("referred_table") == targets_table_name and
        set(fk.get("referred_columns") or []) == {"id"}
        for fk in inspector.get_foreign_keys(disks_table_name)
    )

    if not (name_exists or pair_exists):
        with op.batch_alter_table(disks_table_name) as batch:
            batch.create_foreign_key(
                "fk_iscsi_disks_target_id",
                targets_table_name,
                ["target_id"],
                ["id"],
                ondelete="RESTRICT"
            )

    # -- 7) Change config_id in iscsi_gateways to cluster_id, just rename
    if _table_exists(inspector, gateways_table_name) and _column_exists(inspector, gateways_table_name, "config_id"):
        # 7.1) drop any FK that references config_id
        for fk in inspector.get_foreign_keys(gateways_table_name):
            if "config_id" in (fk.get("constrained_columns") or []):
                if fk.get("name"):
                    op.drop_constraint(fk["name"], gateways_table_name, type_="foreignkey")

        # 7.2) simple rename: config_id -> cluster_id
        with op.batch_alter_table(gateways_table_name) as batch:
            batch.alter_column(
                "config_id",
                new_column_name="cluster_id",
                existing_type=sa.Integer(),
                existing_nullable=True,
            )

        # 7.3) recreate FK with canonical name on cluster_id -> iscsi_clusters(id), if missing
        inspector = sa.inspect(conn)
        fk_name = "fk_iscsi_gateways_cluster_id"
        name_exists = any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(gateways_table_name))
        pair_exists = any(
            set(fk.get("constrained_columns") or []) == {"cluster_id"} and
            fk.get("referred_table") == clusters_table_name and
            set(fk.get("referred_columns") or []) == {"id"}
            for fk in inspector.get_foreign_keys(gateways_table_name)
        )
        if not (name_exists or pair_exists):
            with op.batch_alter_table(gateways_table_name) as batch:
                batch.create_foreign_key(
                    fk_name,
                    clusters_table_name,
                    ["cluster_id"], ["id"],
                    ondelete="RESTRICT",
                )

    # -- 8) Delete target_iqn and pool_id from iscsi_clusters
    #       if not already deleted.
    with op.batch_alter_table(clusters_table_name) as batch:
        if _column_exists(inspector, clusters_table_name, "target_iqn"):
            batch.drop_column("target_iqn")
        if _column_exists(inspector, clusters_table_name, "pool_id"):
            batch.drop_column("pool_id")

    # -- 9) Add unique constraint on iscsi_clusters.name if not exists
    uc_name = "uq_iscsi_clusters_name"
    uc_exists = any(
        uc.get("name") == uc_name
        or set(uc.get("column_names") or []) == {"name"}
        for uc in inspector.get_unique_constraints(clusters_table_name)
    )
    if not uc_exists:
        op.create_unique_constraint(
            uc_name,
            clusters_table_name,
            ["name"],
        )

    # -- 10) Clean name: "xxx.conf" -> "xxx"
    op.execute(
        f"""
        UPDATE {clusters_table_name}
        SET name = regexp_replace(name, '\\.conf$', '')
        WHERE name ~ '\\.conf$'
        """
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # -- 0) Define table names (same as in upgrade)
    configs_table_name  = "iscsi_configs"
    clusters_table_name = "iscsi_clusters"
    targets_table_name  = "iscsi_targets"
    disks_table_name    = "iscsi_disks"
    gateways_table_name = "iscsi_gateways"

    # -- 1) iscsi_gateways: change cluster_id -> config_id
    if _table_exists(inspector, gateways_table_name) and _column_exists(inspector, gateways_table_name, "cluster_id"):
        # 1.1) drop any FK that references cluster_id
        for fk in inspector.get_foreign_keys(gateways_table_name):
            if "cluster_id" in (fk.get("constrained_columns") or []):
                if fk.get("name"):
                    op.drop_constraint(fk["name"], gateways_table_name, type_="foreignkey")

        # 1.2) simple rename: cluster_id -> config_id
        with op.batch_alter_table(gateways_table_name) as batch:
            batch.alter_column(
                "cluster_id",
                new_column_name="config_id",
                existing_type=sa.Integer(),
                existing_nullable=True,
            )
        inspector = sa.inspect(conn)

        # 1.3) recreate FK: config_id -> iscsi_clusters(id) (only if missing)
        fk_name = "fk_iscsi_gateways_config_id"  # adjust to your canonical old name
        name_exists = any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(gateways_table_name))
        pair_exists = any(
            set(fk.get("constrained_columns") or []) == {"config_id"} and
            fk.get("referred_table") == clusters_table_name and
            set(fk.get("referred_columns") or []) == {"id"}
            for fk in inspector.get_foreign_keys(gateways_table_name)
        )
        if not (name_exists or pair_exists):
            with op.batch_alter_table(gateways_table_name) as batch:
                batch.create_foreign_key(
                    fk_name,
                    clusters_table_name,
                    ["config_id"], ["id"],
                    ondelete="RESTRICT",
                )

    inspector = sa.inspect(conn)

    # -- 2) iscsi_disks: drop FK to iscsi_targets(id) if present
    for fk in inspector.get_foreign_keys(disks_table_name):
        if set(fk.get("constrained_columns") or []) == {"target_id"} \
           and fk.get("referred_table") == targets_table_name \
           and set(fk.get("referred_columns") or []) == {"id"}:
            if fk.get("name"):
                op.drop_constraint(fk["name"], disks_table_name, type_="foreignkey")
    inspector = sa.inspect(conn)

    # -- 3) iscsi_disks: replace target_id values with cluster_id (reverse of step 5 in upgrade)
    if _column_exists(inspector, disks_table_name, "target_id") and _table_exists(inspector, targets_table_name):
        op.execute(f"""
            UPDATE {disks_table_name} d
            SET    target_id = t.cluster_id
            FROM   {targets_table_name} t
            WHERE  d.target_id = t.id
        """)

    # -- 4) iscsi_disks: rename target_id -> config_id (simple rename)
    if _column_exists(inspector, disks_table_name, "target_id"):
        with op.batch_alter_table(disks_table_name) as batch:
            batch.alter_column(
                "target_id",
                new_column_name="config_id",
                existing_type=sa.Integer(),
                existing_nullable=True,
            )
        inspector = sa.inspect(conn)

    # -- 5) iscsi_disks: recreate FK config_id -> iscsi_clusters(id) if missing
    if _column_exists(inspector, disks_table_name, "config_id") and _table_exists(inspector, clusters_table_name):
        fk_name = "fk_iscsi_disks_config_id_clusters"
        name_exists = any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(disks_table_name))
        pair_exists = any(
            set(fk.get("constrained_columns") or []) == {"config_id"} and
            fk.get("referred_table") == clusters_table_name and
            set(fk.get("referred_columns") or []) == {"id"}
            for fk in inspector.get_foreign_keys(disks_table_name)
        )
        if not (name_exists or pair_exists):
            with op.batch_alter_table(disks_table_name) as batch:
                batch.create_foreign_key(
                    fk_name,
                    clusters_table_name,
                    ["config_id"], ["id"],
                    ondelete="RESTRICT"
                )
        inspector = sa.inspect(conn)

    # -- 6) iscsi_clusters: add pool_id back (+ FK to pools) and restore target_iqn
    if _table_exists(inspector, clusters_table_name):
        # 6.1) add pool_id if missing
        if not _column_exists(inspector, clusters_table_name, "pool_id"):
            with op.batch_alter_table(clusters_table_name) as batch:
                batch.add_column(sa.Column("pool_id", sa.Integer(), nullable=True))
        inspector = sa.inspect(conn)

        # 6.2) create FK (pool_id -> pools.id) if missing
        fk_name = "fk_iscsi_clusters_pool_id_pools"
        name_exists = any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(clusters_table_name))
        pair_exists = any(
            set(fk.get("constrained_columns") or []) == {"pool_id"} and
            fk.get("referred_table") == "pools" and
            set(fk.get("referred_columns") or []) == {"id"}
            for fk in inspector.get_foreign_keys(clusters_table_name)
        )
        if not (name_exists or pair_exists):
            op.create_foreign_key(
                fk_name,
                clusters_table_name, "pools",
                ["pool_id"], ["id"],
                ondelete="RESTRICT"
            )
        inspector = sa.inspect(conn)

        # 6.3) add target_iqn back if missing
        if not _column_exists(inspector, clusters_table_name, "target_iqn"):
            with op.batch_alter_table(clusters_table_name) as batch:
                batch.add_column(sa.Column("target_iqn", sa.String(length=256), nullable=True))
        inspector = sa.inspect(conn)

        # 6.4) refill clusters.pool_id from targets (first target per cluster)
        if _table_exists(inspector, targets_table_name):
            op.execute(f"""
                WITH first_targets AS (
                    SELECT DISTINCT ON (cluster_id) cluster_id, pool_id
                    FROM {targets_table_name}
                    WHERE pool_id IS NOT NULL
                    ORDER BY cluster_id, id
                )
                UPDATE {clusters_table_name} c
                SET pool_id = ft.pool_id
                FROM first_targets ft
                WHERE c.id = ft.cluster_id
            """)

        # 6.5) restore ".conf" suffix where missing
        op.execute(f"""
            UPDATE {clusters_table_name}
            SET name = name || '.conf'
            WHERE name NOT LIKE '%.conf'
        """)

    # -- 7) drop iscsi_targets table (safe if exists)
    if _table_exists(inspector, targets_table_name):
        op.drop_table(targets_table_name)

    # -- 8) rename iscsi_clusters -> iscsi_configs (only if target name is free)
    inspector = sa.inspect(conn)
    if _table_exists(inspector, clusters_table_name) and not _table_exists(inspector, configs_table_name):
        op.rename_table(clusters_table_name, configs_table_name)

