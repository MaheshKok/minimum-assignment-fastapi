"""
Replay traffic against a running API so New Relic sees a production-like day: steady normal
use (browsing, adding activities, calculating) with an incident roughly once an hour.

Only incidents that need nothing but HTTP calls live here (scenarios 1, 4, 5, 7, 9). The others
change the server itself (data files, config, the database) and are run by hand.

Usage:
    # steady traffic for 55 minutes, one incident at a random minute
    REPLAY_BASE_URL=https://example.herokuapp.com python scripts/replay_scenarios.py --duration 55
    # fire chosen incident scenarios once, back to back
    python scripts/replay_scenarios.py --base-url http://localhost:8000 --only 4,9 --gap 0.2

Exit code is 1 when any response status differs from what was expected.
"""

import argparse
import asyncio
import logging
import os
import random
import sys
import uuid
from datetime import date, timedelta

import httpx

API = "/api/v1"
KINDS = ("electricity", "air-travel", "goods-services")
# Fields copied from an existing row when adding a new one, and which of them is the amount.
COPIED_FIELDS = {
    "electricity": ("country", "usage_kwh"),
    "air-travel": ("distance_miles", "flight_range", "passenger_class"),
    "goods-services": ("supplier_category", "spend_gbp", "description"),
}
AMOUNT_FIELD = {
    "electricity": "usage_kwh",
    "air-travel": "distance_miles",
    "goods-services": "spend_gbp",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
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


# ---- incident scenarios -------------------------------------------------------------------


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


# ---- normal traffic -----------------------------------------------------------------------


async def load_templates(r: Runner) -> dict[str, list[dict]]:
    """Existing rows per activity type; new rows copy their values so factor matching works."""
    templates = {}
    for kind in KINDS:
        resp = await r.call("GET", f"{API}/activities/{kind}", 200, params={"limit": 100})
        templates[kind] = resp.json() if resp.status_code == 200 else []
    return templates


async def add_activity(r: Runner, templates: dict[str, list[dict]]) -> None:
    """A user records a new activity, then asks for its emissions."""
    kinds = [kind for kind, rows in templates.items() if rows]
    if not kinds:
        return
    kind = random.choice(kinds)
    row = random.choice(templates[kind])
    body = {field: row[field] for field in COPIED_FIELDS[kind]}
    amount = AMOUNT_FIELD[kind]
    body[amount] = round(float(row[amount]) * random.uniform(0.8, 1.2), 2)
    body |= {"date": date.today().isoformat(), "source_file": "replay-generator"}
    resp = await r.call("POST", f"{API}/activities/{kind}", 201, json=body)
    if resp.status_code == 201:
        ids = [resp.json()["id"]]
        await r.call("POST", f"{API}/calculations/calculate", 200, json={"activity_ids": ids})


async def browse(r: Runner) -> None:
    """A user looks at data and reports; every request here is valid."""
    today = date.today()
    this_year = {"from_date": f"{today.year}-01-01", "to_date": today.isoformat()}
    last_month = today.replace(day=1) - timedelta(days=1)
    choice = random.randrange(7)
    if choice == 0:
        await r.call("GET", f"{API}/factors/", 200, params={"limit": 20})
    elif choice == 1:
        await r.call("GET", f"{API}/activities/{random.choice(KINDS)}", 200, params={"limit": 20})
    elif choice == 2:
        params = {"sort_by_co2e": random.choice(["asc", "desc"])}
        if random.random() < 0.5:
            params["scope"] = random.choice([2, 3])
        await r.call("GET", f"{API}/reports/emissions", 200, params=params)
    elif choice == 3:
        await r.call("GET", f"{API}/summaries/latest", 200)
    elif choice == 4:
        await r.call("GET", f"{API}/summaries/total", 200, params=this_year)
    elif choice == 5:
        await r.call("GET", f"{API}/summaries/monthly/{last_month.year}/{last_month.month}", 200)
    else:
        breakdown = random.choice(["scope", "category", "activity"])
        await r.call(
            "GET",
            f"{API}/summaries/breakdown",
            200,
            params={**this_year, "breakdown_by": breakdown},
        )


async def normal_step(r: Runner, templates: dict[str, list[dict]]) -> None:
    roll = random.random()
    if roll < 0.75:
        await browse(r)
    elif roll < 0.95:
        await add_activity(r, templates)
    else:
        await r.call("POST", f"{API}/aggregations/daily", 200)  # yesterday's summary


async def steady(
    r: Runner, scenarios: dict, chosen: list[int], minutes: float, interval: float, every: float
) -> None:
    """Normal traffic for `minutes`, with one incident at a random point in each `every` window."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    end = start + minutes * 60
    incidents = []
    window = 0.0
    while window < minutes:
        span = min(every, minutes - window)
        incidents.append(start + (window + random.uniform(0.1, 0.9) * span) * 60)
        window += every

    r.label = "normal"
    templates = await load_templates(r)
    while loop.time() < end:
        if incidents and loop.time() >= incidents[0]:
            incidents.pop(0)
            r.label, scenario = scenarios[random.choice(chosen)]
            await scenario(r)
            r.label = "normal"
        else:
            await normal_step(r, templates)
        await asyncio.sleep(random.uniform(0.5, 1.5) * interval)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default=os.environ.get("REPLAY_BASE_URL"))
    parser.add_argument("--only", help="comma-separated incident scenarios, e.g. 1,4")
    parser.add_argument("--gap", type=float, default=1.0, help="seconds between scenario requests")
    parser.add_argument("--burst", type=int, default=30, help="parallel requests in scenario 7")
    parser.add_argument(
        "--duration", type=float, help="minutes of steady traffic; omit to fire scenarios once"
    )
    parser.add_argument(
        "--interval", type=float, default=15, help="average seconds between normal requests"
    )
    parser.add_argument(
        "--incident-every", type=float, default=60, help="minutes per incident in steady mode"
    )
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
        if args.duration:
            await steady(r, scenarios, chosen, args.duration, args.interval, args.incident_every)
        else:
            for number in chosen:
                r.label, scenario = scenarios[number]
                await scenario(r)

    if r.mismatches:
        logger.info("%d unexpected result(s):\n  %s", len(r.mismatches), "\n  ".join(r.mismatches))
        return 1
    logger.info("all requests behaved as expected")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
