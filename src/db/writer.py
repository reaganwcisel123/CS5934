"""Write the built dataset and catalog into Postgres (idempotent upserts)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import text

from src.db.engine import get_engine

_UPSERT_COUNTY = text(
    "insert into county(fips,name,region,district,rural,population,updated_at) "
    "values(:fips,:name,:region,:district,:rural,:pop,now()) "
    "on conflict(fips) do update set name=excluded.name,region=excluded.region,"
    "district=excluded.district,rural=excluded.rural,population=excluded.population,updated_at=now()"
)
_UPSERT_METRIC = text(
    "insert into county_metric(county_fips,metric_key,value,status,source_id,as_of) "
    "values(:fips,:key,:val,:status,:source,current_date) "
    "on conflict(county_fips,metric_key,as_of) do update set "
    "value=excluded.value,status=excluded.status,source_id=excluded.source_id"
)


def _metrics(rec: dict) -> Iterator[tuple[str, object]]:
    for k, v in rec.get("dom", {}).items():
        yield f"dom.{k}", v
    for k, v in rec.get("outcomes", {}).items():
        yield f"outcomes.{k}", v
    for k, v in rec.get("measures", {}).items():
        yield f"measures.{k}", v
    yield "needIndex", rec.get("needIndex")
    yield "hpsaScore", rec.get("hpsaScore")
    yield "population", rec.get("patients")


def _prov_for(metric_key: str, provenance: dict) -> tuple[str, str | None]:
    # Map a metric to its catalog source + provenance status.
    group = ("outcomes" if metric_key.startswith("outcomes.")
             else "measures" if metric_key.startswith("measures.")
             else "patients" if metric_key == "population"
             else metric_key)
    p = provenance.get(group)
    return (p.get("status", "stub"), p.get("source_id")) if p else ("derived", None)


def load_dataset(records: list[dict], provenance: dict) -> int:
    """Upsert counties + their metrics (with provenance) for today's vintage."""
    eng = get_engine()
    with eng.begin() as c:
        for rec in records:
            c.execute(_UPSERT_COUNTY, {"fips": rec["id"], "name": rec["name"], "region": rec.get("region"),
                                       "district": rec.get("district"), "rural": rec.get("rural"),
                                       "pop": rec.get("patients")})
            rows = []
            for key, val in _metrics(rec):
                status, source = _prov_for(key, provenance)
                rows.append({"fips": rec["id"], "key": key, "val": val, "status": status, "source": source})
            if rows:
                c.execute(_UPSERT_METRIC, rows)
    return len(records)


def seed_catalog(sources: list[dict], lineage: list[dict]) -> tuple[int, int]:
    """Mirror data_sources.yml + field_lineage.json into the DB."""
    eng = get_engine()
    with eng.begin() as c:
        for s in sources:
            c.execute(text(
                "insert into data_source(source_id,name,provider,access_url,refresh_cadence,"
                "schema_version,ingestion_status,last_verified_date) "
                "values(:id,:name,:prov,:url,:cad,:ver,:stat,:date) on conflict(source_id) do update set "
                "name=excluded.name,provider=excluded.provider,access_url=excluded.access_url,"
                "refresh_cadence=excluded.refresh_cadence,schema_version=excluded.schema_version,"
                "ingestion_status=excluded.ingestion_status,last_verified_date=excluded.last_verified_date"),
                {"id": s["source_id"], "name": s.get("source_name"), "prov": s.get("provider"),
                 "url": s.get("access_url"), "cad": s.get("refresh_cadence"),
                 "ver": str(s.get("schema_version")), "stat": s.get("ingestion_status"),
                 "date": s.get("last_verified_date")})
        for f in lineage:
            c.execute(text(
                "insert into field_lineage(final_field,source_id,original_field,transformation,required_for_mvp) "
                "values(:ff,:sid,:of,:tr,:mvp) on conflict(final_field) do update set "
                "source_id=excluded.source_id,original_field=excluded.original_field,"
                "transformation=excluded.transformation,required_for_mvp=excluded.required_for_mvp"),
                {"ff": f["final_field"], "sid": f.get("source_id"), "of": f.get("original_field"),
                 "tr": f.get("transformation"), "mvp": bool(f.get("required_for_mvp"))})
    return len(sources), len(lineage)
