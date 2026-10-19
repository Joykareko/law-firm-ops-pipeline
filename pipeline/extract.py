"""
Extract step.

In production this pulls from the CRM and practice management APIs. The functions
below show that pattern (auth header, pagination, retries). For the portfolio
version, the same functions fall back to the exported files in data/raw, so the
project runs anywhere without credentials.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def _get_paginated(url: str, token: str, results_key: str, page_param: str = "after") -> list[dict]:
    """Generic cursor-paginated GET with simple retry, as used by HubSpot and Clio style APIs."""
    rows, cursor = [], None
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    while True:
        params = {"limit": 100}
        if cursor:
            params[page_param] = cursor
        for attempt in range(3):
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 429:          # rate limited: back off and retry
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            break
        payload = resp.json()
        rows.extend(payload.get(results_key, []))
        cursor = payload.get("paging", {}).get("next", {}).get(page_param)
        if not cursor:
            return rows


def extract_crm_contacts() -> pd.DataFrame:
    token = os.getenv("CRM_API_TOKEN")
    if token:
        records = _get_paginated("https://api.hubapi.com/crm/v3/objects/contacts", token, "results")
    else:
        records = json.loads((RAW / "crm_contacts.json").read_text())["contacts"]
    return pd.json_normalize(records)


def extract_matters() -> pd.DataFrame:
    token = os.getenv("PM_API_TOKEN")
    if token:
        records = _get_paginated("https://app.clio.com/api/v4/matters", token, "data")
    else:
        records = json.loads((RAW / "pm_matters.json").read_text())["data"]
    return pd.json_normalize(records)


def extract_time_entries() -> pd.DataFrame:
    return pd.read_csv(RAW / "time_entries.csv")


def extract_invoices() -> pd.DataFrame:
    return pd.read_csv(RAW / "invoices.csv")


def extract_marketing_spend() -> pd.DataFrame:
    return pd.read_csv(RAW / "marketing_spend.csv")


def extract_all() -> dict[str, pd.DataFrame]:
    return {
        "contacts": extract_crm_contacts(),
        "matters": extract_matters(),
        "time_entries": extract_time_entries(),
        "invoices": extract_invoices(),
        "marketing_spend": extract_marketing_spend(),
    }
