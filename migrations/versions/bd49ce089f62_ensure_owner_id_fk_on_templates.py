"""ensure owner_id FK on templates (safe)"""

from alembic import op
import sqlalchemy as sa

revision = "bd49ce089f62"
down_revision = "e260de4fc7ad"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "templates" not in insp.get_table_names():
        return

    cols = [c["name"] for c in insp.get_columns("templates")]
    if "owner_id" not in cols:
        with op.batch_alter_table("templates") as b:
            b.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))

    fks = insp.get_foreign_keys("templates")
    has_fk = any(
        "owner_id" in fk.get("constrained_columns", []) and fk.get("referred_table") == "users"
        for fk in fks
    )
    if not has_fk:
        with op.batch_alter_table("templates") as b:
            b.create_foreign_key(
                "fk_templates_owner_id_users",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="SET NULL",
            )

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "templates" not in insp.get_table_names():
        return

    for fk in insp.get_foreign_keys("templates"):
        if "owner_id" in fk.get("constrained_columns", []) and fk.get("referred_table") == "users":
            with op.batch_alter_table("templates") as b:
                b.drop_constraint(fk["name"], type_="foreignkey")
            break

    cols = [c["name"] for c in insp.get_columns("templates")]
    if "owner_id" in cols:
        with op.batch_alter_table("templates") as b:
            b.drop_column("owner_id")
