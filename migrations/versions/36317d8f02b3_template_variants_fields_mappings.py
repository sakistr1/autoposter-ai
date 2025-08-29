from alembic import op
import sqlalchemy as sa

# Αναπροσάρμοσε αν χρειάζεται
revision = '36317d8f02b3'
down_revision = None
branch_labels = None
depends_on = None

def _insp():
    return sa.inspect(op.get_bind())

def add_col_if_missing(table, col_name, type_, nullable=True):
    insp = _insp()
    cols = {c['name'] for c in insp.get_columns(table)}
    if col_name not in cols:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(col_name, type_, nullable=nullable))

def create_table_if_missing(name, *columns, **kw):
    insp = _insp()
    if not insp.has_table(name):
        op.create_table(name, *columns, **kw)

def upgrade():
    # ---- Παραδείγματα: προσαρμόζεις ό,τι χρειάζεται το δικό σου migration ----
    # 1) users: πρόσθεσε στήλες μόνο αν δεν υπάρχουν
    add_col_if_missing("users", "sync_url", sa.String())
    add_col_if_missing("users", "consumer_key", sa.String())
    add_col_if_missing("users", "consumer_secret", sa.String())

    # 2) Δημιούργησε πίνακες μόνο αν δεν υπάρχουν ήδη
    create_table_if_missing(
        "template_variants",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("template_id", sa.String, nullable=False, index=True),
        sa.Column("ratio", sa.String, nullable=False, index=True),
        sa.Column("meta", sa.JSON, nullable=True),
        sa.UniqueConstraint("template_id", "ratio", name="uq_template_variant")
    )

    create_table_if_missing(
        "template_fields",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("meta", sa.JSON, nullable=True),
    )

    create_table_if_missing(
        "template_field_mappings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("variant_id", sa.Integer, sa.ForeignKey("template_variants.id"), nullable=False),
        sa.Column("field_id", sa.Integer, sa.ForeignKey("template_fields.id"), nullable=False),
        sa.Column("mapping", sa.JSON, nullable=True),
        sa.UniqueConstraint("variant_id", "field_id", name="uq_variant_field")
    )

def downgrade():
    # Προαιρετικά, με guards για να μη «σκάει» αν ήδη λείπουν
    insp = _insp()
    for tbl in ["template_field_mappings", "template_fields", "template_variants"]:
        if insp.has_table(tbl):
            op.drop_table(tbl)

    # Δεν αφαιρούμε στήλες σε SQLite (δύσκολο με ALTER TABLE). Αν χρειάζεται,
    # μπορείς να το αφήσεις κενό ή να κάνεις reconstruct table.
