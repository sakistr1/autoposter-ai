from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import insert, select, desc
import json

from production_engine.engine_database import engine, pe_templates_table

router = APIRouter()

class TemplateIn(BaseModel):
    name: str
    spec_json: dict  # το spec σε JSON

class TemplateOut(BaseModel):
    id: int
    name: str
    spec_json: dict

@router.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateIn):
    with engine.begin() as conn:
        res = conn.execute(
            insert(pe_templates_table).values(
                name=payload.name,
                spec_json=json.dumps(payload.spec_json)
            )
        )
        new_id = int(res.inserted_primary_key[0])
        return {"id": new_id, "name": payload.name, "spec_json": payload.spec_json}

@router.get("/templates", response_model=List[TemplateOut])
def list_templates(limit: int = Query(20, ge=1, le=100)):
    with engine.connect() as conn:
        rows = conn.execute(
            select(pe_templates_table.c.id, pe_templates_table.c.name, pe_templates_table.c.spec_json)
            .order_by(desc(pe_templates_table.c.id)).limit(limit)
        ).all()
    out=[]
    for r in rows:
        try:
            spec = json.loads(r.spec_json) if r.spec_json else {}
        except Exception:
            spec = {}
        out.append({"id": int(r.id), "name": r.name, "spec_json": spec})
    return out

@router.get("/templates/{tpl_id}", response_model=TemplateOut)
def get_template(tpl_id: int):
    with engine.connect() as conn:
        row = conn.execute(
            select(pe_templates_table.c.id, pe_templates_table.c.name, pe_templates_table.c.spec_json)
            .where(pe_templates_table.c.id == tpl_id)
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        spec = json.loads(row["spec_json"]) if row["spec_json"] else {}
    except Exception:
        spec = {}
    return {"id": int(row["id"]), "name": row["name"], "spec_json": spec}
