"""Use TigZig's documented public educational API; preserve original responses.

No direct Yahoo scraping or untrusted provider scripts. Public API access is not
an institutional data licence or independent verification of upstream rights.
Raw data stay under ignored data/; do not redistribute the source bundle.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from portfolioos.empirical_protocol import ASSETS
from portfolioos.historical import file_hash

BASE = "https://yfin-h.tigzig.com"


def fetch(path, params, destination):
    url = BASE + path + "?" + urlencode(params)
    with urlopen(url, timeout=180) as response:
        payload = response.read()
        metadata = {
            "url": url,
            "status": response.status,
            "headers": dict(response.headers),
        }
    destination.write_bytes(payload)
    return json.loads(payload), metadata


def acquire(output, start="2009-01-01", end="2026-09-30"):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    params = {"tickers": ",".join(ASSETS), "start_date": start, "end_date": end}
    bars, price_meta = fetch(
        "/v1/get-all-prices/", params, root / "original_prices.json"
    )
    actions_source, action_meta = fetch(
        "/v1/get-actions/",
        {"tickers": ",".join(ASSETS)},
        root / "original_actions.json",
    )
    rows, actions = {}, []
    for date, instruments in bars.items():
        if not isinstance(instruments, dict) or set(instruments) != set(ASSETS):
            raise ValueError(f"Incomplete provider bar on {date}")
        rows[date] = {}
        for asset in ASSETS:
            bar = instruments[asset]
            rows[date][asset] = bar["Close"]
            for field, kind in [
                ("Dividends", "distribution"),
                ("Stock Splits", "split"),
            ]:
                value = bar[field]
                if value:
                    actions.append(
                        {"date": date, "asset": asset, "type": kind, "value": value}
                    )
    prices = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=ASSETS)
    prices.index = pd.DatetimeIndex(prices.index, name="date")
    prices.to_csv(root / "prices.csv", float_format="%.17g")
    pd.DataFrame(actions, columns=["date", "asset", "type", "value"]).to_csv(
        root / "actions.csv", index=False, float_format="%.17g"
    )
    # Original action response is independent endpoint evidence, not an invented
    # empty ledger. Consistency is evaluated in the formal data-quality stage.
    if not isinstance(actions_source, dict):
        raise ValueError("Invalid provider actions response")
    source_files = [
        "prices.csv",
        "actions.csv",
        "original_prices.json",
        "original_actions.json",
    ]
    manifest = {
        "source": "TigZig public Yahoo Finance Data API (upstream Yahoo via yfinance)",
        "source_url": BASE + "/redoc",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "license": (
            "Operator openly provides no-auth API for educational/demonstration use; "
            "terms reviewed at https://www.tigzig.com/terms. No independently verified "
            "upstream redistribution licence or institutional data licence is claimed. "
            "Raw data retained locally; not redistributed."
        ),
        "access_documentation": "https://www.tigzig.com/apis/yahoo-finance",
        "adjustment_documentation": "https://in.help.yahoo.com/kb/adjusted-close-sln28256.html",
        "adjustment_convention": "split_and_distribution_adjusted_close",
        "provider_close_field": (
            "auto_adjusted Close per operator documentation; not raw Close"
        ),
        "universe_selection": (
            "Retrospectively selected fixed ten-ETF panel from user Phase 2 proposal"
        ),
        "survivorship_limitations": (
            "Surviving funds selected today; no unbiased historical universe claim"
        ),
        "revision_policy": (
            "Latest retrieval vintage; historical revisions and corrections possible"
        ),
        "calendar": (
            "NYSE regular sessions, checked independently with pandas_market_calendars"
        ),
        "timezone": "America/New_York; dates are local trading-session labels",
        "sha256": {name: file_hash(root / name) for name in source_files},
        "requests": [price_meta, action_meta],
        "requested_range": [start, end],
        "data_kind": "historical",
        "upstream_rights_independently_verified": False,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        f"Acquired {len(prices)} session rows, {len(actions)} corporate actions; "
        "holdout not evaluated"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", default="2009-01-01")
    parser.add_argument("--end", default="2026-09-30")
    args = parser.parse_args()
    acquire(args.output, args.start, args.end)
