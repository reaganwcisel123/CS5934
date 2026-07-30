"""FastAPI app. Serves the atlas from Postgres when DATABASE_URL is set,
otherwise falls back to the built dashboard/data/clinic_atlas.json (dev)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.atlas import load_atlas as _atlas
from src.db.engine import db_configured

app = FastAPI(title="Clinic Needs Atlas API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])

from src.api.auth import router as auth_router  # noqa: E402
from src.api.chat import router as chat_router  # noqa: E402
from src.api.forecast import router as forecast_router  # noqa: E402
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(forecast_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "db": db_configured()}


@app.get("/api/counties")
def counties() -> dict:
    atlas = _atlas()
    return {"records": atlas["records"], "provenance": atlas.get("provenance"),
            "county_count": len(atlas["records"])}


@app.get("/api/counties/{fips}")
def county(fips: str) -> dict:
    rec = next((r for r in _atlas()["records"] if r["id"] == fips), None)
    if rec is None:
        raise HTTPException(404, f"county {fips} not found")
    return rec


@app.get("/api/sources")
def sources() -> dict:
    if db_configured():
        from src.db import queries
        return queries.get_sources()
    from src.catalog import Catalog
    return {"sources": [{"source_id": s["source_id"], "name": s.get("source_name"),
                         "provider": s.get("provider"), "ingestion_status": s.get("ingestion_status")}
                        for s in Catalog.load().sources]}
