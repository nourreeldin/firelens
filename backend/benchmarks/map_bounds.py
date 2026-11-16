"""Read-only map bounds A/B benchmark over real local HTTP requests.

Run from backend: python -m benchmarks.map_bounds
Uses DATABASE_URL from backend settings; never prints or saves credentials.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import socket
import statistics
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter

import asyncpg
import httpx
import uvicorn

from app.core.config import Settings
from app.db.database import Database
from app.repositories import fire_repository
from app.repositories.filters import build_fire_filters
from app.schemas.common import FireFilters

OUTPUT = Path(__file__).parent / "results" / "map_bounds"
REPEATS = 9
PLAN_REPEATS = 3
WARMUPS = 2


def before_filters(filters: FireFilters, *, param_offset: int = 0):
    """Freeze the original COALESCE predicate; reuse unchanged common filters."""
    without_bbox = filters.model_copy(update={
        key: None for key in ("min_longitude", "min_latitude", "max_longitude", "max_latitude")
    })
    builder = build_fire_filters(without_bbox, param_offset=param_offset)
    if filters.bbox is not None:
        builder.add(
            "ST_Intersects(COALESCE(geom, "
            "ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)), "
            "ST_MakeEnvelope({}, {}, {}, {}, 4326))", *filters.bbox,
        )
    return builder


BUILDERS = {"before": before_filters, "after": build_fire_filters}
CASES = {
    "egypt_narrow": dict(region_id="EGY", sensor="VIIRS", min_longitude=30.8,
                          min_latitude=29.8, max_longitude=31.8, max_latitude=30.8),
    "south_africa_narrow": dict(region_id="ZAF", sensor="VIIRS", min_longitude=28.0,
                                min_latitude=-29.0, max_longitude=29.0, max_latitude=-28.0),
    "south_africa_wide_both_sensors": dict(region_id="ZAF", min_longitude=16.0,
                                           min_latitude=-35.0, max_longitude=33.0, max_latitude=-22.0),
}


def summary(values):
    ordered = sorted(values)
    return {"samples_ms": values, "median_ms": statistics.median(values),
            "min_ms": min(values), "max_ms": max(values),
            "p95_ms": ordered[math.ceil(len(ordered) * 0.95) - 1]}


def nodes(plan):
    yield plan
    for child in plan.get("Plans", []):
        yield from nodes(child)


def describe_plan(document):
    plan = document[0]["Plan"]
    return {
        "execution_ms": document[0]["Execution Time"],
        "planning_ms": document[0]["Planning Time"],
        "indexes": sorted({node["Index Name"] for node in nodes(plan) if "Index Name" in node}),
        "nodes": sorted({node["Node Type"] for node in nodes(plan)}),
        "shared_hit_blocks": plan.get("Shared Hit Blocks", 0),
        "shared_read_blocks": plan.get("Shared Read Blocks", 0),
        "temp_read_blocks": plan.get("Temp Read Blocks", 0),
        "temp_written_blocks": plan.get("Temp Written Blocks", 0),
    }


async def check_fallback(connection):
    """Synthetic data exists only in a read-only CTE, never in a real table."""
    fixture = """WITH hotspots AS (
        SELECT * FROM (VALUES
            (1, 30.0, 31.0, ST_SetSRID(ST_MakePoint(31,30),4326), '2020-07-15'::date, 'EGY', 'VIIRS'),
            (2, 30.0, 31.0, NULL::geometry, '2020-07-15'::date, 'EGY', 'VIIRS'),
            (3, 29.8, 30.8, NULL::geometry, '2020-07-15'::date, 'EGY', 'VIIRS'),
            (4, 30.8, 31.8, NULL::geometry, '2020-07-15'::date, 'EGY', 'VIIRS'),
            (5, 30.0, 32.0, NULL::geometry, '2020-07-15'::date, 'EGY', 'VIIRS'),
            (6, 30.0, 31.0, NULL::geometry, '2020-07-15'::date, 'ZAF', 'VIIRS'),
            (7, 30.0, 31.0, NULL::geometry, '2019-07-15'::date, 'EGY', 'VIIRS'),
            (8, 30.0, 31.0, NULL::geometry, '2020-07-15'::date, 'EGY', 'MODIS'),
            (9, 0.0, 0.0, ST_SetSRID(ST_MakePoint(31,30),4326), '2020-07-15'::date, 'EGY', 'VIIRS'),
            (10,30.0, 31.0, ST_SetSRID(ST_MakePoint(0,0),4326), '2020-07-15'::date, 'EGY', 'VIIRS')
        ) AS sample(id, latitude, longitude, geom, acq_date, country_code, sensor)
    ) """
    filters = FireFilters(start_date=date(2020, 1, 1), end_date=date(2020, 12, 31),
                          **CASES["egypt_narrow"])
    result = {}
    for version, make_builder in BUILDERS.items():
        builder = make_builder(filters)
        rows = await connection.fetch(
            fixture + "SELECT id, geom IS NULL AS missing_geom FROM hotspots "
            + builder.where_sql + " ORDER BY id", *builder.params,
        )
        result[version] = [dict(row) for row in rows]
    assert result["before"] == result["after"]
    assert [row["id"] for row in result["after"]] == [1, 2, 3, 4, 9]
    return {"matched": True, "rows": result, "null_geometry_matches": 3,
            "coverage": "inside/outside, inclusive corners, authoritative non-null geometry, country/date/sensor guards"}


async def check_results(connection, filters):
    before, after = (make(filters) for make in BUILDERS.values())
    assert before.params == after.params
    query = f"""WITH before_rows AS MATERIALIZED (
        SELECT id, geom IS NULL AS missing_geom FROM public.fire_hotspots {before.where_sql}
    ), after_rows AS MATERIALIZED (
        SELECT id, geom IS NULL AS missing_geom FROM public.fire_hotspots {after.where_sql}
    ) SELECT
        (SELECT COUNT(*) FROM before_rows) AS before_count,
        (SELECT COUNT(*) FROM after_rows) AS after_count,
        (SELECT COUNT(*) FROM (SELECT id FROM before_rows EXCEPT SELECT id FROM after_rows) AS d) AS before_only,
        (SELECT COUNT(*) FROM (SELECT id FROM after_rows EXCEPT SELECT id FROM before_rows) AS d) AS after_only,
        (SELECT COUNT(*) FROM after_rows WHERE missing_geom) AS missing_geom_matches
    """
    result = dict(await connection.fetchrow(query, *before.params))
    assert result["before_only"] == result["after_only"] == 0
    return result


async def plans(connection, filters, name):
    result = {version: {"count": [], "page": []} for version in BUILDERS}
    for repeat in range(PLAN_REPEATS):
        versions = list(BUILDERS) if repeat % 2 == 0 else list(reversed(BUILDERS))
        for version in versions:
            builder = BUILDERS[version](filters)
            queries = {
                "count": (f"SELECT COUNT(*) FROM public.fire_hotspots {builder.where_sql}", builder.params),
                "page": (f"""SELECT {fire_repository.FIRE_SELECT_COLUMNS}
                    FROM public.fire_hotspots {builder.where_sql}
                    ORDER BY acq_datetime_utc DESC NULLS LAST, id DESC
                    LIMIT ${len(builder.params)+1} OFFSET ${len(builder.params)+2}""", [*builder.params, 100, 0]),
            }
            for kind, (query, params) in queries.items():
                raw = await connection.fetchval("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query, *params)
                document = json.loads(raw) if isinstance(raw, str) else raw
                path = OUTPUT / f"{name}-{version}-{kind}-{repeat+1}.json"
                path.write_text(json.dumps(document, indent=2), encoding="utf-8")
                result[version][kind].append(describe_plan(document))
    return result


async def benchmark_api(pool, cases):
    # A real loopback HTTP server, with the same API/repositories/serialization.
    # Its lifespan reuses the benchmark pool; all database operations are reads.
    os.environ["DEBUG"] = "false"
    from app.main import create_app

    app = create_app(Settings(debug=False))

    @asynccontextmanager
    async def lifespan(application):
        application.state.database = Database(pool)
        yield
        application.state.database = None

    app.router.lifespan_context = lifespan
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    original = fire_repository.build_fire_filters
    output = {}
    try:
        while not server.started:
            if task.done():
                await task
                raise RuntimeError("Benchmark server stopped before startup")
            await asyncio.sleep(0.01)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=120) as client:
            for name, filters in cases.items():
                params = {key: str(value.value if hasattr(value, "value") else value)
                          for key, value in filters.model_dump(exclude_none=True).items()}
                params.update(limit="100", offset="0")
                samples = {version: [] for version in BUILDERS}
                responses = {}
                for repeat in range(WARMUPS + REPEATS):
                    versions = list(BUILDERS) if repeat % 2 == 0 else list(reversed(BUILDERS))
                    for version in versions:
                        fire_repository.build_fire_filters = BUILDERS[version]
                        started = perf_counter()
                        response = await client.get("/api/v1/fires", params=params)
                        elapsed = (perf_counter() - started) * 1000
                        response.raise_for_status()
                        payload = response.json()
                        if version in responses:
                            assert responses[version] == payload
                        responses[version] = payload
                        if repeat >= WARMUPS:
                            samples[version].append(elapsed)
                    assert responses["before"] == responses["after"]
                output[name] = {version: summary(values) for version, values in samples.items()}
                output[name]["responses_identical"] = True
                output[name]["page_rows"] = len(responses["after"]["data"])
                output[name]["total"] = responses["after"]["pagination"]["total"]
                print(f"{name}: HTTP medians " + json.dumps({v: round(output[name][v]["median_ms"], 2) for v in BUILDERS}), flush=True)
    finally:
        fire_repository.build_fire_filters = original
        server.should_exit = True
        await task
        sock.close()
    return output


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    settings = Settings(debug=False)
    pool = await asyncpg.create_pool(
        dsn=settings.database_dsn, min_size=1, max_size=1, timeout=15,
        command_timeout=120, server_settings={"default_transaction_read_only": "on"},
    )
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "api_repeats": REPEATS, "warmups_per_version": WARMUPS,
              "plan_repeats": PLAN_REPEATS, "endpoint": "/api/v1/fires?limit=100&offset=0",
              "api_transport": "real loopback HTTP, reused connection, actual API handlers, remote configured database",
              "cases": {}}
    try:
        cases = {name: FireFilters(start_date=date(2020, 1, 1), end_date=date(2020, 12, 31), **values)
                 for name, values in CASES.items()}
        async with pool.acquire() as connection:
            report["database"] = dict(await connection.fetchrow("""
                SELECT current_setting('server_version') AS postgres_version,
                       current_setting('plan_cache_mode') AS plan_cache_mode,
                       current_setting('enable_seqscan') AS enable_seqscan,
                       current_setting('enable_bitmapscan') AS enable_bitmapscan,
                       current_setting('default_transaction_read_only') AS read_only,
                       (SELECT count(*) FROM public.fire_hotspots) AS rows,
                       (SELECT count(*) FROM public.fire_hotspots WHERE geom IS NULL) AS null_geometries,
                       (SELECT indexdef FROM pg_indexes WHERE schemaname='public'
                         AND indexname='idx_fire_hotspots_geom') AS spatial_index
            """))
            report["fallback_fixture"] = await check_fallback(connection)
            print("Read-only fallback fixture passed", flush=True)
            for name, filters in cases.items():
                async with connection.transaction(isolation="repeatable_read", readonly=True):
                    equality = await check_results(connection, filters)
                print(f"{name}: full result sets match ({equality['after_count']} rows)", flush=True)
                report["cases"][name] = {"filters": filters.model_dump(mode="json", exclude_none=True),
                                          "equality": equality,
                                          "plans": await plans(connection, filters, name)}
        report["api"] = await benchmark_api(pool, cases)
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (OUTPUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved evidence to {OUTPUT}", flush=True)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
