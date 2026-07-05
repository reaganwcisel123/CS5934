"""Read the atlas back out of Postgres in the dashboard's record shape."""

from __future__ import annotations

from sqlalchemy import text

from src.db.engine import get_engine


def get_atlas() -> dict:
    """Return {records, provenance, county_count} matching clinic_atlas.json."""
    eng = get_engine()
    with eng.connect() as c:
        counties = c.execute(text(
            "select fips,name,region,district,rural,population from county order by fips")).all()
        metrics = c.execute(text(
            "select county_fips,metric_key,value,status,source_id from county_metric "
            "where as_of=(select max(as_of) from county_metric)")).all()

    records = {fips: {"id": fips, "name": name, "region": region, "district": district,
                      "rural": float(rural) if rural is not None else None,
                      "patients": int(population) if population is not None else 0,
                      "dom": {}, "outcomes": {}, "measures": {}, "needIndex": None, "hpsaScore": 0}
               for fips, name, region, district, rural, population in counties}

    prov: dict[str, dict] = {}
    for fips, key, value, status, source in metrics:
        rec = records.get(fips)
        if rec is None:
            continue
        v = float(value) if value is not None else None
        if key.startswith("dom."):
            rec["dom"][key[4:]] = v
            prov[key] = {"source_id": source, "status": status}
        elif key.startswith("outcomes."):
            rec["outcomes"][key[9:]] = v
            prov["outcomes"] = {"source_id": source, "status": status}
        elif key.startswith("measures."):
            rec["measures"][key[9:]] = v
            prov["measures"] = {"source_id": source, "status": status}
        elif key == "needIndex":
            rec["needIndex"] = v
        elif key == "hpsaScore":
            rec["hpsaScore"] = int(v) if v is not None else 0
            prov["hpsaScore"] = {"source_id": source, "status": status}
        elif key == "population":
            prov["patients"] = {"source_id": source, "status": status}

    return {"records": list(records.values()), "provenance": prov, "county_count": len(records)}


def get_sources() -> dict:
    with get_engine().connect() as c:
        rows = c.execute(text(
            "select source_id,name,provider,ingestion_status from data_source order by source_id")).mappings().all()
    return {"sources": [dict(r) for r in rows]}
