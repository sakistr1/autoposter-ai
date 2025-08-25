from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Text

DATABASE_URL = "sqlite:///production_engine/engine.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

metadata = MetaData()

committed_posts_table = Table(
    "committed_posts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("preview_id", String(128), nullable=False),
    Column("urls_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

pe_templates_table = Table(
    "pe_templates",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("type", String(32), nullable=False),
    Column("ratio", String(16), nullable=True),
    Column("spec_json", Text, nullable=True),
    Column("thumb_url", String(512), nullable=True),
    Column("created_at", DateTime, nullable=True),
)

pe_mapping_rules_table = Table(
    "pe_mapping_rules",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("category", String(128), nullable=False),
    Column("post_type", String(32), nullable=False),
    Column("mode", String(64), nullable=False),
    Column("template_id", Integer, nullable=False),
    Column("created_at", DateTime, nullable=True),
)
