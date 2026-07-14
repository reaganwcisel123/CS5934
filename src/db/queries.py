"""Read the atlas back out of Postgres in the dashboard's record shape."""

from __future__ import annotations

from sqlalchemy import text

from src.db.engine import get_engine


def get_atlas() -> dict:
    """Return {records, provenance, county_count} matching clinic_atlas.json."""
    eng = get_engine()
    with eng.connect() as c:
        counties = c.execute(text(
            "select fips,name,region,district,rural,population,model_risk_drivers "
            "from county order by fips")).all()
        metrics = c.execute(text(
            "select county_fips,metric_key,value,status,source_id from county_metric "
            "where as_of=(select max(as_of) from county_metric)")).all()
        patients = c.execute(text(
            "select county_fips,name,age,risk,risk_tier,risk_drivers,attrs from patient "
            "where as_of=(select max(as_of) from patient) order by county_fips,patient_key")).all()

    records = {fips: {"id": fips, "name": name, "region": region, "district": district,
                      "rural": float(rural) if rural is not None else None,
                      "patients": int(population) if population is not None else 0,
                      "dom": {}, "outcomes": {}, "measures": {}, "needIndex": None, "hpsaScore": 0,
                      "modelRisk": None, "modelRiskDrivers": drivers or [], "patientsList": []}
               for fips, name, region, district, rural, population, drivers in counties}

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
        elif key == "model.risk":
            rec["modelRisk"] = v

    for fips, name, age, risk, tier, drivers, attrs in patients:
        rec = records.get(fips)
        if rec is None:
            continue
        pt = dict(attrs or {})  # attrs/drivers come back from jsonb as dict/list
        pt.update({"name": name, "age": int(age) if age is not None else None,
                   "risk": float(risk) if risk is not None else None,
                   "riskTier": tier, "riskDrivers": drivers or []})
        rec["patientsList"].append(pt)

    return {"records": list(records.values()), "provenance": prov, "county_count": len(records)}


def get_sources() -> dict:
    with get_engine().connect() as c:
        rows = c.execute(text(
            "select source_id,name,provider,ingestion_status from data_source order by source_id")).mappings().all()
    return {"sources": [dict(r) for r in rows]}
