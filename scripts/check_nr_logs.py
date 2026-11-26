"""
Prove the app's logs reach New Relic: find the one log line this traffic run marked, then count
all of the app's log lines over the run.

Run by .github/workflows/traffic.yml. A NerdGraph query against the wrong account returns count 0
with no error, so only a found marker proves the logs arrive. When the marker is missing, a count
of deployment markers tells "this key cannot read the account" apart from "the logs go elsewhere".

Environment:
    HEROKU_API_KEY, HEROKU_APP_NAME      to read the app's NEW_RELIC_APP_NAME setting
    NEW_RELIC_API_KEY                    New Relic User key (NRAK-...)
    NEW_RELIC_ACCOUNT_ID                 account the logs must reach
    LOG_MARKER                           text the run put in one request's URL
    MINUTES                              length of the run
"""

import logging
import os
import re
import sys
import time

from mark_deploy import heroku, nerdgraph

logger = logging.getLogger(__name__)

WAIT_SECONDS = 120
POLL_SECONDS = 15
QUERY = "query($a: Int!, $q: Nrql!) { actor { account(id: $a) { nrql(query: $q) { results } } } }"


def count(account_id: str, nrql: str, api_key: str) -> int:
    account = nerdgraph(QUERY, {"a": int(account_id), "q": nrql}, api_key)["actor"]["account"]
    return account["nrql"]["results"][0]["count"]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    marker = os.environ["LOG_MARKER"]
    if not re.fullmatch(r"[A-Za-z0-9-]+", marker):
        raise ValueError(f"Unexpected log marker {marker!r}")
    api_key, account_id = os.environ["NEW_RELIC_API_KEY"], os.environ["NEW_RELIC_ACCOUNT_ID"]
    app_name = heroku(
        f"/apps/{os.environ['HEROKU_APP_NAME']}/config-vars", os.environ["HEROKU_API_KEY"]
    )["NEW_RELIC_APP_NAME"]
    if not account_id.isdigit() or "'" in app_name:
        raise ValueError(f"Unexpected account id {account_id!r} or app name {app_name!r}")
    since = f"SINCE {int(float(os.environ['MINUTES'])) + 5} minutes ago"

    marker_nrql = f"SELECT count(*) FROM Log WHERE message LIKE '%{marker}%' {since}"
    deadline = time.monotonic() + WAIT_SECONDS
    while (found := count(account_id, marker_nrql, api_key)) == 0 and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
    app_nrql = f"SELECT count(*) FROM Log WHERE entity.name = '{app_name}' {since}"
    logger.info(
        "%s -> %d rows in account %s", app_nrql, count(account_id, app_nrql, api_key), account_id
    )
    if found:
        logger.info(
            "Marker %s found in account %s: the app's logs arrive there", marker, account_id
        )
        return 0

    deployments = count(account_id, "SELECT count(*) FROM Deployment SINCE 1 month ago", api_key)
    if deployments:
        logger.error(
            "Account %s is readable (%d deployment markers), but marker %s never arrived: "
            "NEW_RELIC_LICENSE_KEY on Heroku belongs to another account, or log forwarding is off",
            account_id,
            deployments,
            marker,
        )
    else:
        logger.error(
            "Marker %s not found and no deployment markers either: NEW_RELIC_API_KEY cannot read "
            "account %s",
            marker,
            account_id,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
