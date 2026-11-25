"""
Pin a commit that Heroku has just released on the New Relic app's timeline (a deployment marker).

Run by .github/workflows/deploy.yml after the commit is pushed to Heroku. It waits until the
release built from the commit has finished its release phase, then places the marker at the moment
that release went live. The New Relic app is found by the name in the Heroku app's own
NEW_RELIC_APP_NAME setting, so the name is kept in one place.

Environment:
    HEROKU_API_KEY, HEROKU_APP_NAME      Heroku Platform API token and app name
    NEW_RELIC_API_KEY                    New Relic User key (NRAK-...)
    NEW_RELIC_ACCOUNT_ID                 account that holds the app
    GIT_SHA                              the full commit id that was pushed
    DEPLOY_USER, DEPLOY_DESCRIPTION, DEPLOY_LINK   optional details shown on the marker
"""

import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

HEROKU_API = "https://api.heroku.com"
NERDGRAPH = "https://api.newrelic.com/graphql"
RELEASES_SCANNED = 20
WAIT_SECONDS = 600
POLL_SECONDS = 10


def _call(url: str, headers: dict, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def heroku(path: str, token: str, extra_headers: dict | None = None):
    headers = {
        "Accept": "application/vnd.heroku+json; version=3",
        "Authorization": f"Bearer {token}",
        **(extra_headers or {}),
    }
    return _call(f"{HEROKU_API}{path}", headers)


def nerdgraph(query: str, variables: dict, api_key: str) -> dict:
    headers = {"API-Key": api_key, "Content-Type": "application/json"}
    result = _call(NERDGRAPH, headers, {"query": query, "variables": variables})
    if result.get("errors"):
        raise RuntimeError(f"NerdGraph refused the request: {result['errors']}")
    return result["data"]


def deploy_release(releases: list[dict], slug_commits: dict[str, str], sha: str) -> dict | None:
    """The first release built from `sha`: later releases reuse its slug for setting changes."""
    built_from_sha = [
        release
        for release in releases
        if release.get("slug") and slug_commits.get(release["slug"]["id"]) == sha
    ]
    return min(built_from_sha, key=lambda release: release["version"], default=None)


def wait_for_release(app: str, token: str, sha: str) -> dict:
    deadline = time.monotonic() + WAIT_SECONDS
    slug_commits: dict[str, str] = {}
    while True:
        releases = heroku(
            f"/apps/{app}/releases",
            token,
            {"Range": f"version ..; order=desc, max={RELEASES_SCANNED}"},
        )
        for release in releases:
            slug_id = (release.get("slug") or {}).get("id")
            if slug_id and slug_id not in slug_commits:
                slug_commits[slug_id] = heroku(f"/apps/{app}/slugs/{slug_id}", token)["commit"]
        release = deploy_release(releases, slug_commits, sha)
        status = release["status"] if release else "not found"
        if status == "succeeded":
            return release
        if status == "failed":
            raise RuntimeError(f"Heroku release v{release['version']} of {sha} failed")
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"No succeeded Heroku release of {sha} in the last {RELEASES_SCANNED} releases "
                f"after {WAIT_SECONDS}s (last status: {status})"
            )
        logger.info("Release of %s is %s; checking again in %ss", sha[:7], status, POLL_SECONDS)
        time.sleep(POLL_SECONDS)


def went_live_ms(release: dict) -> int:
    """When the release finished its release phase; it does not move when later releases replace it."""
    went_live = datetime.fromisoformat(release["updated_at"].replace("Z", "+00:00"))
    return int(went_live.timestamp() * 1000)


def already_marked(account_id: str, guid: str, sha: str, api_key: str) -> bool:
    """Lets a re-run repair a missing marker without ever pinning the same commit twice."""
    if not all(char in "0123456789abcdef" for char in sha):
        raise ValueError(f"Unexpected commit id {sha!r}")
    nrql = (
        f"SELECT count(*) FROM Deployment WHERE entity.guid = '{guid}' AND commit = '{sha}' "
        "SINCE 1 month ago"
    )
    query = (
        "query($a: Int!, $q: Nrql!) { actor { account(id: $a) { nrql(query: $q) { results } } } }"
    )
    account = nerdgraph(query, {"a": int(account_id), "q": nrql}, api_key)["actor"]["account"]
    return account["nrql"]["results"][0]["count"] > 0


def entity_guid(account_id: str, app_name: str, api_key: str) -> str:
    if not account_id.isdigit() or "'" in app_name:
        raise ValueError(f"Unexpected account id {account_id!r} or app name {app_name!r}")
    search = (
        f"name = '{app_name}' AND domain = 'APM' AND type = 'APPLICATION' "
        f"AND accountId = {account_id}"
    )
    query = (
        "query($q: String!) { actor { entitySearch(query: $q) { results { entities { guid } } } } }"
    )
    entities = nerdgraph(query, {"q": search}, api_key)["actor"]["entitySearch"]["results"][
        "entities"
    ]
    if len(entities) != 1:
        raise RuntimeError(f"Expected one New Relic app for {search!r}, found {len(entities)}")
    return entities[0]["guid"]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app, token = os.environ["HEROKU_APP_NAME"], os.environ["HEROKU_API_KEY"]
    api_key, account_id = os.environ["NEW_RELIC_API_KEY"], os.environ["NEW_RELIC_ACCOUNT_ID"]
    sha = os.environ["GIT_SHA"]

    release = wait_for_release(app, token, sha)
    app_name = heroku(f"/apps/{app}/config-vars", token)["NEW_RELIC_APP_NAME"]
    guid = entity_guid(account_id, app_name, api_key)
    if already_marked(account_id, guid, sha, api_key):
        logger.info("%s already has a marker on %s; nothing to do", sha[:7], app_name)
        return 0

    deployment = {
        "entityGuid": guid,
        "version": sha[:7],
        "commit": sha,
        "deploymentType": "BASIC",
        "timestamp": went_live_ms(release),
        "description": (
            os.environ.get("DEPLOY_DESCRIPTION") or f"Heroku v{release['version']}"
        ).splitlines()[0][:500],
    }
    for field, variable in (("user", "DEPLOY_USER"), ("deepLink", "DEPLOY_LINK")):
        if os.environ.get(variable):
            deployment[field] = os.environ[variable]

    mutation = (
        "mutation($d: ChangeTrackingDeploymentInput!) "
        "{ changeTrackingCreateDeployment(deployment: $d) { deploymentId } }"
    )
    created = nerdgraph(mutation, {"d": deployment}, api_key)["changeTrackingCreateDeployment"]
    logger.info(
        "Marked %s (Heroku v%s, live %s) on %s: deployment %s",
        sha[:7],
        release["version"],
        release["updated_at"],
        app_name,
        created["deploymentId"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
