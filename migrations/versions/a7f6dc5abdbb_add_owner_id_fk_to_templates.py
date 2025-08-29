"""add owner_id FK to templates (safe if table missing)"""

from alembic import op
import sqlalchemy as sa

revision = "a7f6dc5abdbb"
down_revision = "e260de4fc7ad"
branch_labels = None
depends_on = None

def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()

def _has_column(insp, table: str, col: str) -> bool:
    try:
        return any(c["name"] == col for c in insp.get_columns(table))
    except Exception:
        return False

def _fk_info(insp, table: str, col: str, ref_table: str):
    for fk in insp.get_foreign_keys(table):
        if col in fk.get("constrained_columns", []) and fk.get("referred_table") == ref_table:
            return True, fk.get("name")
    return False, None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _has_table(insp, "templates"):
        return

    # add column if missing
    if not _has_column(insp, "templates", "owner_id"):
        with op.batch_alter_table("templates") as b:
            b.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))

    # add FK if missing
    has_fk, fk_name = _fk_info(insp, "templates", "owner_id", "users")
    if not has_fk:
        with op.batch_alter_table("templates") as b:
            b.create_foreign_key(
                fk_name or "fk_templates_owner_id_users_id",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="SET NULL",
            )

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _has_table(insp, "templates"):
        return

    has_fk, fk_name = _fk_info(insp, "templates", "owner_id", "users")
    if has_fk and fk_name:
        with op.batch_alter_table("templates") as b:
            b.drop_constraint(fk_name, type_="foreignkey")

    if _has_column(insp, "templates", "owner_id"):
        with op.batch_alter_table("templates") as b:
            b.drop_column("owner_id")
