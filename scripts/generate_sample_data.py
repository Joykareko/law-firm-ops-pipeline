"""
Generate realistic, deliberately messy sample data for a small US law firm.

The files mimic what you get when you export from the tools a firm actually uses:
  * crm_contacts.json      HubSpot style lead export (timestamps in epoch ms, mixed casing)
  * pm_matters.json        Clio style matter export (inconsistent practice area labels)
  * time_entries.csv       Timekeeping export (duplicates, bad hours, missing rates)
  * invoices.csv           Billing export (partial payments, a few impossible values)
  * marketing_spend.csv    Monthly ad spend by channel

All names and numbers are synthetic. Run:  python scripts/generate_sample_data.py
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
rng = np.random.default_rng(SEED)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

START = date(2025, 1, 1)
END = date(2026, 9, 30)

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
         "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
         "Thomas", "Sarah", "Carlos", "Maria", "Daniel", "Nancy", "Kevin", "Lisa", "Brian",
         "Angela", "Jason", "Rachel", "Eric", "Laura", "Aisha", "Wei", "Priya", "Omar"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas",
        "Taylor", "Moore", "Jackson", "Martin", "Lee", "Walker", "Hall", "Allen", "Young",
        "King", "Wright", "Scott", "Green", "Baker", "Adams", "Nguyen", "Patel", "Khan"]

# channel: (share of leads, consult rate, retain rate given consult)
SOURCES = {
    "Google Ads":       (0.34, 0.40, 0.19),
    "Referral":         (0.18, 0.68, 0.32),
    "Website Organic":  (0.22, 0.42, 0.21),
    "Facebook Ads":     (0.16, 0.28, 0.11),
    "Legal Directory":  (0.10, 0.36, 0.17),
}

# practice area: (share, clean label variants that show up in the export)
PRACTICE = {
    "Family Law":       (0.30, ["Family Law", "family law", "FAMILY LAW", "Family"]),
    "Personal Injury":  (0.25, ["Personal Injury", "personal injury", "PI", "Personal Injury "]),
    "Estate Planning":  (0.20, ["Estate Planning", "estate planning", "Estate Plan"]),
    "Business Law":     (0.15, ["Business Law", "business law", "Business"]),
    "Real Estate":      (0.10, ["Real Estate", "real estate", "RE"]),
}

ATTORNEYS = {
    "A. Morgan":   {"rate": 450, "areas": ["Business Law", "Real Estate"], "partner": True},
    "B. Chen":     {"rate": 425, "areas": ["Family Law"], "partner": True},
    "C. Okafor":   {"rate": 375, "areas": ["Personal Injury"], "partner": False},
    "D. Rivera":   {"rate": 350, "areas": ["Family Law", "Estate Planning"], "partner": False},
    "E. Schultz":  {"rate": 325, "areas": ["Estate Planning", "Real Estate", "Business Law"], "partner": False},
    "F. Haddad":   {"rate": 300, "areas": ["Personal Injury", "Family Law"], "partner": False},
    "G. Brooks":   {"rate": 275, "areas": ["Business Law", "Estate Planning", "Personal Injury"], "partner": False},
}

# How often an attorney logs time on a matter on a working day, by practice area.
# Personal injury files sit idle for long stretches while waiting on insurers and courts.
ENTRY_PROB = {"Family Law": 0.30, "Personal Injury": 0.20, "Estate Planning": 0.42,
              "Business Law": 0.42, "Real Estate": 0.42}

# A real looking incident: the Google Ads form integration broke for three weeks.
OUTAGE_START = date(2026, 3, 9)
OUTAGE_END = date(2026, 3, 29)


def daterange(d0: date, d1: date):
    for n in range((d1 - d0).days + 1):
        yield d0 + timedelta(days=n)


def messy_date(d: date | datetime) -> str | int:
    """Exports rarely agree on a date format. Mix ISO, US style and epoch ms."""
    if isinstance(d, date) and not isinstance(d, datetime):
        d = datetime(d.year, d.month, d.day, random.randint(8, 18), random.randint(0, 59))
    roll = random.random()
    if roll < 0.70:
        return int(d.timestamp() * 1000)          # HubSpot style epoch milliseconds
    if roll < 0.85:
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    return d.strftime("%m/%d/%Y")


def weekly_lead_volume(day: date, source: str) -> float:
    """Base daily lead rate with growth, weekday effect and a seasonal wave."""
    t = (day - START).days / 365
    growth = 1 + 0.25 * t
    weekday = 0.45 if day.weekday() >= 5 else 1.0
    season = 1 + 0.12 * np.sin(2 * np.pi * (day.timetuple().tm_yday / 365))
    base = 6.4 * SOURCES[source][0]
    rate = base * growth * weekday * season
    if source == "Google Ads" and OUTAGE_START <= day <= OUTAGE_END:
        rate *= 0.08
    return rate


def main() -> None:
    contacts, matters, time_rows, invoices = [], [], [], []
    contact_id, matter_seq = 100000, 1
    open_until: dict[str, list[date]] = {a: [] for a in ATTORNEYS}  # close dates of each attorney's matters

    # ---------------- CRM contacts ----------------
    for day in daterange(START, END):
        for source in SOURCES:
            for _ in range(rng.poisson(weekly_lead_volume(day, source))):
                contact_id += 1
                fn, ln = random.choice(FIRST), random.choice(LAST)
                email = f"{fn}.{ln}{random.randint(1, 999)}@example.com".lower()
                _, consult_p, retain_p = SOURCES[source]
                consulted = random.random() < consult_p
                retained = consulted and random.random() < retain_p
                stage = "customer" if retained else ("opportunity" if consulted else "lead")
                created = datetime(day.year, day.month, day.day, random.randint(7, 21), random.randint(0, 59))
                consult_dt = created + timedelta(days=random.randint(1, 12)) if consulted else None
                retained_dt = consult_dt + timedelta(days=random.randint(0, 21)) if retained else None
                if retained_dt and retained_dt.date() > END:
                    retained_dt, stage = None, "opportunity"
                contacts.append({
                    "vid": contact_id,
                    "properties": {
                        "firstname": fn,
                        "lastname": ln,
                        "email": email if random.random() > 0.06 else email.upper(),
                        "hs_analytics_source": source if random.random() > 0.03 else source.lower(),
                        "lifecyclestage": stage,
                        "createdate": messy_date(created),
                        "consultation_date": messy_date(consult_dt) if consult_dt else None,
                        "retained_date": messy_date(retained_dt) if retained_dt else None,
                    },
                })
                # Messiness: the same person submits the form twice
                if random.random() < 0.035:
                    dup = json.loads(json.dumps(contacts[-1]))
                    contact_id += 1
                    dup["vid"] = contact_id
                    dup["properties"]["email"] = " " + email.title() + " "
                    dup["properties"]["lifecyclestage"] = "lead"
                    dup["properties"]["consultation_date"] = None
                    dup["properties"]["retained_date"] = None
                    contacts.append(dup)

                if retained_dt:
                    area = random.choices(list(PRACTICE), weights=[v[0] for v in PRACTICE.values()])[0]
                    open_d = retained_dt.date()
                    candidates = [a for a, v in ATTORNEYS.items() if area in v["areas"]]
                    # Intake assigns the new matter to whoever has the lightest active caseload
                    atty = min(candidates, key=lambda a: (sum(c > open_d for c in open_until[a]), random.random()))
                    length = {"Family Law": 150, "Personal Injury": 240, "Estate Planning": 45,
                              "Business Law": 90, "Real Estate": 60}[area]
                    close_d = open_d + timedelta(days=int(rng.gamma(2.0, length / 2)))
                    status = "Closed" if close_d <= END else "Open"
                    open_until[atty].append(close_d)
                    matter_id = f"M-{matter_seq:05d}"
                    matter_seq += 1
                    client_email = email
                    if random.random() < 0.08:
                        client_email = email.replace("@example.com", "@Example.com ")
                    if random.random() < 0.015:
                        client_email = f"unknown{random.randint(1, 9999)}@example.com"  # orphan
                    matters.append({
                        "id": matter_id,
                        "client": {"email": client_email},
                        "practice_area": {"name": random.choice(PRACTICE[area][1])},
                        "responsible_attorney": {"name": atty},
                        "open_date": open_d.isoformat(),
                        "close_date": close_d.isoformat() if status == "Closed" else None,
                        "status": status,
                    })

                    # ---------------- time entries ----------------
                    last_day = min(close_d, END)
                    d = open_d
                    month_hours: dict[str, float] = {}
                    while d <= last_day:
                        if d.weekday() < 5 and random.random() < ENTRY_PROB[area]:
                            hours = round(max(0.1, rng.gamma(2.0, 0.9)), 1)
                            billable = random.random() > 0.12
                            rate = ATTORNEYS[atty]["rate"]
                            row = {
                                "entry_id": f"T{len(time_rows) + 1:07d}",
                                "matter_id": matter_id,
                                "attorney": atty,
                                "date": d.strftime("%Y-%m-%d") if random.random() > 0.1 else d.strftime("%m/%d/%Y"),
                                "hours": hours,
                                "rate": rate if random.random() > 0.02 else None,
                                "billable": "Yes" if billable else "No",
                                "description": random.choice([
                                    "Client call", "Drafting", "Research", "Court filing",
                                    "Document review", "Negotiation", "Email correspondence"]),
                            }
                            r = random.random()
                            if r < 0.004:
                                row["hours"] = -row["hours"]          # sign error
                            elif r < 0.007:
                                row["hours"] = round(row["hours"] * 10, 1)  # decimal slip
                            time_rows.append(row)
                            if random.random() < 0.012:
                                time_rows.append(dict(row))           # exact duplicate export
                            if billable and row["hours"] > 0:
                                key = d.strftime("%Y-%m")
                                month_hours[key] = month_hours.get(key, 0) + row["hours"] * rate
                        d += timedelta(days=1)

                    # ---------------- invoices ----------------
                    for ym, standard_value in sorted(month_hours.items()):
                        y, m = map(int, ym.split("-"))
                        issued = (date(y, m, 28) + timedelta(days=4)).replace(day=1) + timedelta(days=4)
                        if issued > END:
                            continue
                        realization = rng.uniform(0.82, 0.98) if area != "Personal Injury" else rng.uniform(0.70, 0.92)
                        billed = round(standard_value * realization, 2)
                        lag = int(rng.gamma(2.2, 14))
                        pay_prob = 0.97 if area != "Personal Injury" else 0.88
                        paid_date = issued + timedelta(days=lag)
                        if random.random() < pay_prob and paid_date <= END:
                            paid = billed if random.random() > 0.05 else round(billed * rng.uniform(0.5, 0.9), 2)
                        else:
                            paid, paid_date = 0.0, None
                        if random.random() < 0.003:
                            paid = round(billed * 1.5, 2)  # impossible overpayment, a data entry error
                        invoices.append({
                            "invoice_id": f"INV-{len(invoices) + 1:06d}",
                            "matter_id": matter_id,
                            "issued_date": issued.isoformat(),
                            "amount_billed": billed,
                            "amount_paid": paid,
                            "paid_date": paid_date.isoformat() if paid_date else None,
                        })

    # ---------------- marketing spend ----------------
    spend_rows = []
    months = pd.period_range(START, END, freq="M")
    base_spend = {"Google Ads": 9500, "Facebook Ads": 4200, "Legal Directory": 1800,
                  "Website Organic": 1200, "Referral": 0}
    for p in months:
        for src, base in base_spend.items():
            amt = base * (1 + 0.15 * ((p.ordinal - months[0].ordinal) / 12)) * rng.uniform(0.9, 1.1)
            spend_rows.append({"month": str(p), "channel": src, "spend_usd": round(amt, 2)})

    (RAW / "crm_contacts.json").write_text(json.dumps({"contacts": contacts}, indent=1))
    (RAW / "pm_matters.json").write_text(json.dumps({"data": matters}, indent=1))
    pd.DataFrame(time_rows).to_csv(RAW / "time_entries.csv", index=False)
    pd.DataFrame(invoices).to_csv(RAW / "invoices.csv", index=False)
    pd.DataFrame(spend_rows).to_csv(RAW / "marketing_spend.csv", index=False)

    print(f"contacts={len(contacts):,} matters={len(matters):,} "
          f"time_entries={len(time_rows):,} invoices={len(invoices):,}")


if __name__ == "__main__":
    main()
