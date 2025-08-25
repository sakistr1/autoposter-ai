# production_engine/routers/templates_engine.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime
import os, json

# Χρησιμοποιούμε SQLAlchemy Core (όχι ORM) για να ΜΗΝ μπλέκουμε με άλλα models
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, DateTime, select, insert, update

router = APIRouter()

# ---- DB/paths ----
PE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PE_DIR, "engine.db")
ENGINE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(ENGINE_URL, connect_args={"check_same_thread": False})
metadata = MetaData()

# ---- Πίνακες (Core) ----
pe_templates = Table(
    "pe_templates", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("type", String, nullable=False),   # image|carousel|video
    Column("ratio", String, nullable=True),   # e.g. "4:5", "1:1", "9:16"
    Column("spec_json", Text, nullable=False),
    Column("thumb_url", String, nullable=True),
    Column("created_at", DateTime, default=datetime.utcnow),
)

pe_mapping_rules = Table(
    "pe_mapping_rules", metadata,
    Column("id", Integer, primary_key=True),
    Column("category", String, nullable=False),
    Column("post_type", String, nullable=False),  # image|carousel|video
    Column("mode", String, nullable=False),       # Κανονικό, κ.λπ.
    Column("template_id", Integer, nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow),
)

with engine.begin() as conn:
    metadata.create_all(conn)

# ---- Pydantic σχήματα (Pydantic v1) ----
class Slot(BaseModel):
    id: str
    kind: Literal["image","text","logo"]
    x: int; y: int; w: int; h: int
    z: int = 0
    fit: Literal["cover","contain","stretch"] = "cover"
    # text
    text_key: Optional[Literal["title","subtitle","price","cta","description"]] = None
    font_size: Optional[int] = 48
    color: Optional[str] = "#ffffff"
    align: Optional[Literal["left","center","right"]] = "left"
    bold: Optional[bool] = False
    # image
    source: Optional[Literal["product","extra1","extra2","background"]] = None
    opacity: Optional[float] = 1.0

class TemplateSpec(BaseModel):
    canvas_w: int = 1080
    canvas_h: int = 1350
    background: Optional[str] = None  # π.χ. "/static/..." ή "#0A0F20"
    slots: List[Slot]

class RegisterTemplateBody(BaseModel):
    name: str
    type: Literal["image","carousel","video"]
    ratio: Optional[str] = None
    spec: TemplateSpec
    thumb_url: Optional[str] = None
    template_id: Optional[int] = None  # αν δώσεις id -> update

class MappingRuleBody(BaseModel):
    category: str
    post_type: Literal["image","carousel","video"]
    mode: str
    template_id: int

class ResolveBody(BaseModel):
    category: str
    post_type: Literal["image","carousel","video"]
    mode: str

# ---- Endpoints ----
@router.post("/tengine/templates/register")
def register_template(body: RegisterTemplateBody):
    # Pydantic v1: .json()
    spec_json = body.spec.json()
    with engine.begin() as conn:
        if body.template_id:
            stmt = update(pe_templates).where(pe_templates.c.id == body.template_id).values(
                name=body.name, type=body.type, ratio=body.ratio,
                spec_json=spec_json, thumb_url=body.thumb_url
            )
            res = conn.execute(stmt)
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="template_id not found")
            tid = body.template_id
        else:
            stmt = insert(pe_templates).values(
                name=body.name, type=body.type, ratio=body.ratio,
                spec_json=spec_json, thumb_url=body.thumb_url,
                created_at=datetime.utcnow(),
            )
            tid = conn.execute(stmt).inserted_primary_key[0]
    return {"template_id": tid}

@router.get("/tengine/templates")
def list_templates():
    with engine.begin() as conn:
        rows = conn.execute(select(
            pe_templates.c.id, pe_templates.c.name, pe_templates.c.type,
            pe_templates.c.ratio, pe_templates.c.thumb_url
        )).fetchall()
    return [{"id": r.id, "name": r.name, "type": r.type, "ratio": r.ratio, "thumb_url": r.thumb_url} for r in rows]

@router.get("/tengine/templates/{tid}")
def get_template(tid: int):
    with engine.begin() as conn:
        row = conn.execute(select(pe_templates).where(pe_templates.c.id == tid)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="template not found")
    data = dict(row._mapping)
    data["spec"] = json.loads(data.pop("spec_json"))
    return data

@router.post("/tengine/mapping/rules")
def add_rule(body: MappingRuleBody):
    with engine.begin() as conn:
        # check ότι υπάρχει template
        t = conn.execute(select(pe_templates.c.id).where(pe_templates.c.id == body.template_id)).fetchone()
        if not t:
            raise HTTPException(status_code=400, detail="template_id invalid")
        rid = conn.execute(insert(pe_mapping_rules).values(
            category=body.category, post_type=body.post_type, mode=body.mode,
            template_id=body.template_id, created_at=datetime.utcnow()
        )).inserted_primary_key[0]
    return {"rule_id": rid}

@router.post("/tengine/mapping/resolve")
def resolve_rule(body: ResolveBody):
    with engine.begin() as conn:
        row = conn.execute(
            select(pe_mapping_rules.c.template_id)
            .where(pe_mapping_rules.c.category == body.category)
            .where(pe_mapping_rules.c.post_type == body.post_type)
            .where(pe_mapping_rules.c.mode == body.mode)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="no mapping")
    return {"template_id": row.template_id}
