"""
Replay incident scenarios against a running API: normal traffic with failures mixed in,
so New Relic records realistic requests, errors and recoveries.

Only the scenarios that need nothing but HTTP calls live here (1, 4, 5, 7, 9). The others
change the server itself (data files, config, the database) and are run by hand.

Usage:
    REPLAY_BASE_URL=https://example.herokuapp.com python scripts/replay_scenarios.py
    python scripts/replay_scenarios.py --base-url http://localhost:8000 --only 4,9 --gap 0.2

Exit code is 1 when any response status differs from what its scenario expects.
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid

import httpx

API = "/api/v1"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, client: httpx.AsyncClient, gap: float) -> None:
        self.client = client
        self.gap = gap
        self.label = "warmup"
        self.mismatches: list[str] = []

    async def call(self, method: str, path: str, *expect: int, **kwargs) -> httpx.Response:
        # The User-Agent marks each request with its scenario, which New Relic stores
        # on transactions and errors, so one scenario's traffic can be filtered out.
        try:
            resp = await self.client.request(
                method, path, headers={"User-Agent": f"replay/{self.label}"}, **kwargs
            )
        except httpx.HTTPError as exc:
            self.mismatches.append(f"{self.label} {method} {path}: {exc!r}")
            logger.info(f"BAD {self.label:<12} {method} {path} -> {exc!r}")
            await asyncio.sleep(self.gap)
            return httpx.Response(599)
        ok = resp.status_code in expect
        if not ok:
            self.mismatches.append(
                f"{self.label} {method} {path}: got {resp.status_code}, expected {sorted(expect)}"
            )
        logger.info(
            f"{'ok ' if ok else 'BAD'} {self.label:<12} {method} {path} {kwargs.get('params') or ''}"
            f" -> {resp.status_code}"
        )
        await asyncio.sleep(self.gap)
        return resp


async def partial_batch(r: Runner) -> None:
    """1: a calculation batch where one activity id does not exist."""
    resp = await r.call("GET", f"{API}/activities/electricity", 200, params={"limit": 3})
    ids = [row["id"] for row in resp.json()] if resp.status_code == 200 else []
    await r.call("POST", f"{API}/calculations/calculate", 200, json={"activity_ids": ids})
    await r.call(
        "POST",
        f"{API}/calculations/calculate",
        200,
        json={"activity_ids": [*ids, str(uuid.uuid4())]},
    )


async def client_mistakes(r: Runner) -> None:
    """4: normal report traffic with typical caller mistakes in between."""
    year = {"from_date": "2025-01-01", "to_date": "2025-12-31"}
    await r.call("GET", f"{API}/reports/emissions", 200, params={"scope": 2})
    await r.call("GET", f"{API}/summaries/total", 200, params=year)
    await r.call("GET", f"{API}/reports/emissions", 422, params={"scope": 1})
    await r.call(
        "GET", f"{API}/summaries/breakdown", 422, params={**year, "breakdown_by": "country"}
    )
    await r.call(
        "GET",
        f"{API}/summaries/total",
        400,
        params={"from_date": "2025-12-31", "to_date": "2025-01-01"},
    )
    await r.call("GET", f"{API}/factors/not-a-uuid", 422)
    await r.call("GET", f"{API}/factors/{uuid.uuid4()}", 404)
    await r.call("GET", f"{API}/reports/emissions", 200, params={"sort_by_co2e": "desc"})


async def backfill_typo(r: Runner) -> None:
    """5: a caller typo in aggregation_type comes back as a server error, not a 400."""
    week = {"from_date": "2025-01-01", "to_date": "2025-01-07"}
    await r.call(
        "POST", f"{API}/aggregations/backfill", 200, params={**week, "aggregation_type": "daily"}
    )
    await r.call(
        "POST", f"{API}/aggregations/backfill", 500, params={**week, "aggregation_type": "weekly"}
    )
    await r.call("GET", f"{API}/summaries/latest", 200)


async def pool_burst(r: Runner, burst: int) -> None:
    """7: many slow backfills at once exhaust the 6-connection pool."""
    await r.call("GET", f"{API}/summaries/latest", 200)
    year = {"from_date": "2025-01-01", "to_date": "2025-12-31", "aggregation_type": "daily"}
    # 500 is the pool timeout inside the app; 503 is Heroku's router giving up after 30 seconds.
    results = await asyncio.gather(
        *(
            r.call("POST", f"{API}/aggregations/backfill", 200, 500, 503, params=year)
            for _ in range(burst)
        )
    )
    if all(resp.status_code == 200 for resp in results):
        r.mismatches.append(f"{r.label}: all {burst} burst requests succeeded, no failure seen")
    # Recovery: once the burst drains, ordinary reads work again.
    await r.call("GET", f"{API}/summaries/latest", 200)


async def wrong_month(r: Runner) -> None:
    """9: month=0 is accepted and silently aggregates last month."""
    await r.call("POST", f"{API}/aggregations/monthly", 200, params={"year": 2025, "month": 10})
    await r.call("POST", f"{API}/aggregations/monthly", 400, params={"year": 2025, "month": 13})
    await r.call("POST", f"{API}/aggregations/monthly", 200, params={"month": 0})


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default=os.environ.get("REPLAY_BASE_URL"))
    parser.add_argument("--only", help="comma-separated scenario numbers, e.g. 1,4")
    parser.add_argument("--gap", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--burst", type=int, default=30, help="parallel requests in scenario 7")
    args = parser.parse_args()
    if not args.base_url:
        parser.error("set --base-url or REPLAY_BASE_URL")

    scenarios = {
        1: ("1-partial", partial_batch),
        4: ("4-client", client_mistakes),
        5: ("5-backfill", backfill_typo),
        7: ("7-burst", lambda r: pool_burst(r, args.burst)),
        9: ("9-month", wrong_month),
    }
    chosen = [int(n) for n in args.only.split(",")] if args.only else list(scenarios)
    unknown = set(chosen) - set(scenarios)
    if unknown:
        parser.error(f"no scenario {sorted(unknown)}; choose from {sorted(scenarios)}")

    # 35 seconds covers an Eco dyno waking from sleep and Heroku's 30-second router limit.
    async with httpx.AsyncClient(base_url=args.base_url, timeout=35) as client:
        r = Runner(client, args.gap)
        await r.call("GET", "/health", 200)
        for number in chosen:
            r.label, scenario = scenarios[number]
            await scenario(r)

    if r.mismatches:
        logger.info(
            "\n%d unexpected result(s):\n  %s", len(r.mismatches), "\n  ".join(r.mismatches)
        )
        return 1
    logger.info("\nall scenarios behaved as expected")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
