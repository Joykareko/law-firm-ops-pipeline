"""
Clean step.

Every fix here is logged, so the data quality page can show exactly what was changed
and why. Nothing is silently dropped.
"""
from __future__ import annotations

import pandas as pd

PRACTICE_MAP = {
    "family law": "Family Law", "family": "Family Law",
    "personal injury": "Personal Injury", "pi": "Personal Injury",
    "estate planning": "Estate Planning", "estate plan": "Estate Planning",
    "business law": "Business Law", "business": "Business Law",
    "real estate": "Real Estate", "re": "Real Estate",
}
SOURCE_MAP = {
    "google ads": "Google Ads", "referral": "Referral", "website organic": "Website Organic",
    "facebook ads": "Facebook Ads", "legal directory": "Legal Directory",
}


class CleaningLog:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, table: str, issue: str, rows: int, action: str) -> None:
        if rows:
            self.rows.append({"table": table, "issue": issue, "rows_affected": int(rows), "action": action})

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=["table", "issue", "rows_affected", "action"])


def parse_mixed_dates(s: pd.Series) -> pd.Series:
    """Handle epoch milliseconds, ISO timestamps and US style dates in one column."""
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    numeric = pd.to_numeric(s, errors="coerce")
    is_epoch = numeric.notna() & (numeric > 1e11)
    out[is_epoch] = pd.to_datetime(numeric[is_epoch], unit="ms")
    rest = s[~is_epoch & s.notna()].astype(str)
    iso = pd.to_datetime(rest, format="ISO8601", errors="coerce", utc=True).dt.tz_localize(None)
    us = pd.to_datetime(rest, format="%m/%d/%Y", errors="coerce")
    out[rest.index] = iso.fillna(us)
    return out.dt.normalize()


def normalize_email(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.lower()


def clean_contacts(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    df = df.rename(columns=lambda c: c.replace("properties.", ""))
    df["email"] = normalize_email(df["email"])
    raw_src = df["hs_analytics_source"].astype(str)
    df["source"] = raw_src.str.strip().str.lower().map(SOURCE_MAP).fillna("Unknown")
    log.add("contacts", "Inconsistent source casing", (raw_src != df["source"]).sum(), "Mapped to standard channel names")
    for col in ["createdate", "consultation_date", "retained_date"]:
        df[col] = parse_mixed_dates(df[col])
    log.add("contacts", "Mixed date formats (epoch ms, ISO, US)", len(df), "Parsed to a single date type")

    # Duplicate form submissions: keep the record that went furthest in the funnel
    stage_rank = {"customer": 3, "opportunity": 2, "lead": 1}
    df["stage_rank"] = df["lifecyclestage"].map(stage_rank).fillna(0)
    before = len(df)
    df = (df.sort_values(["email", "stage_rank", "createdate"], ascending=[True, False, True])
            .drop_duplicates("email", keep="first"))
    log.add("contacts", "Duplicate contacts (same email, different casing or spaces)", before - len(df),
            "Kept the record furthest along the funnel")
    return df[["vid", "firstname", "lastname", "email", "source", "lifecyclestage",
               "createdate", "consultation_date", "retained_date"]].rename(columns={"vid": "contact_id"})


def clean_matters(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    df = df.rename(columns={"id": "matter_id", "client.email": "client_email",
                            "practice_area.name": "practice_area_raw",
                            "responsible_attorney.name": "attorney"})
    df["client_email"] = normalize_email(df["client_email"])
    df["practice_area"] = df["practice_area_raw"].str.strip().str.lower().map(PRACTICE_MAP)
    n_labels = df["practice_area_raw"].nunique()
    log.add("matters", f"Practice area labels in {n_labels} different spellings",
            (df["practice_area_raw"] != df["practice_area"]).sum(), "Mapped to 5 standard practice areas")
    df["open_date"] = pd.to_datetime(df["open_date"])
    df["close_date"] = pd.to_datetime(df["close_date"])
    return df[["matter_id", "client_email", "practice_area", "attorney", "open_date", "close_date", "status"]]


def clean_time_entries(df: pd.DataFrame, matters: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates()
    log.add("time_entries", "Exact duplicate rows from repeated exports", before - len(df), "Removed")

    df["date"] = parse_mixed_dates(df["date"])
    df["billable"] = df["billable"].eq("Yes")

    neg = df["hours"] < 0
    log.add("time_entries", "Negative hours (sign error)", neg.sum(), "Converted to positive")
    df.loc[neg, "hours"] = df.loc[neg, "hours"].abs()

    too_long = df["hours"] > 12
    log.add("time_entries", "Over 12 hours in one entry (likely decimal slip)", too_long.sum(),
            "Divided by 10 and flagged for review")
    df["needs_review"] = too_long
    df.loc[too_long, "hours"] = (df.loc[too_long, "hours"] / 10).round(1)

    # Missing rate: fill with that attorney's standard rate
    std_rate = df.groupby("attorney")["rate"].median()
    missing = df["rate"].isna()
    log.add("time_entries", "Missing billing rate", missing.sum(), "Filled with attorney's standard rate")
    df.loc[missing, "rate"] = df.loc[missing, "attorney"].map(std_rate)
    return df


def clean_invoices(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    df["issued_date"] = pd.to_datetime(df["issued_date"])
    df["paid_date"] = pd.to_datetime(df["paid_date"])
    over = df["amount_paid"] > df["amount_billed"]
    log.add("invoices", "Paid more than billed (data entry error)", over.sum(),
            "Capped at billed amount and flagged for finance")
    df["needs_review"] = over
    df.loc[over, "amount_paid"] = df.loc[over, "amount_billed"]
    return df


def clean_all(raw: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    log = CleaningLog()
    contacts = clean_contacts(raw["contacts"].copy(), log)
    matters = clean_matters(raw["matters"].copy(), log)
    time_entries = clean_time_entries(raw["time_entries"].copy(), matters, log)
    invoices = clean_invoices(raw["invoices"].copy(), log)
    spend = raw["marketing_spend"].copy()
    return ({"contacts": contacts, "matters": matters, "time_entries": time_entries,
             "invoices": invoices, "marketing_spend": spend}, log.to_frame())
