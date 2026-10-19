# Building the dashboard in Power BI

This guide takes you from the pipeline's output to a finished Power BI report. You do the building; the guide gives you the data model, every DAX measure, a layout for each page, and a table of figures to check your numbers against.

Allow about 3 to 5 hours.

---

## 1. Get the data

1. Run the pipeline: `python run_pipeline.py`. It writes 11 CSV files to `data/powerbi/`.
2. In Power BI Desktop: **Home > Get data > Text/CSV**, and load each file. (Or use **Get data > Folder**, point it at `data/powerbi`, and click **Transform data** to split them; loading them one at a time is simpler.)
3. In **Transform data** (Power Query), check the column types:
   * Every column ending in `date` or `_start` is **Date**
   * `is_consulted`, `is_retained`, `billable`, `needs_review`, `is_anomaly`, `is_weekend` are **True/False**
   * Money columns (`amount_billed`, `amount_paid`, `outstanding`, `standard_value`, `spend_usd`, `rate`) are **Fixed decimal number**
4. **Close & Apply.**

| File | What it is | Rows |
| --- | --- | --- |
| `Dates` | Calendar, one row per day, weeks start Monday | 638 |
| `Attorneys` | 7 attorneys, standard rate, 140 hour monthly capacity | 7 |
| `LeadChannels` | 5 lead channels, each marked Paid, Organic or Referral | 5 |
| `Matters` | One row per legal matter, with practice area and attorney | 417 |
| `Leads` | One row per lead, with consultation and retained flags | 4,141 |
| `TimeEntries` | Time entries, with billable hours and standard value | 9,204 |
| `Invoices` | Invoices, with outstanding amount and aging bucket | 1,594 |
| `AdSpend` | Monthly ad spend by channel | 105 |
| `WeeklyLeadAlerts` | Weekly leads per channel, with the anomaly flag | 455 |
| `QualityChecks` | Results of the automated checks | 7 |
| `CleaningLog` | What the cleaning step fixed | 9 |

---

## 2. Build the data model

Open **Model view** and create these relationships. Delete any that Power BI auto-detected and that are not in this list.

| From (one side) | To (many side) | Active |
| --- | --- | --- |
| `Dates[date]` | `TimeEntries[date]` | Yes |
| `Dates[date]` | `Invoices[issued_date]` | Yes |
| `Dates[date]` | `Invoices[work_month_start]` | **No** (used only by Realization) |
| `Dates[date]` | `Leads[created_date]` | Yes |
| `Dates[date]` | `AdSpend[month_start]` | Yes |
| `Dates[date]` | `WeeklyLeadAlerts[week_start]` | Yes |
| `Matters[matter_id]` | `TimeEntries[matter_id]` | Yes |
| `Matters[matter_id]` | `Invoices[matter_id]` | Yes |
| `Attorneys[attorney]` | `Matters[attorney]` | Yes |
| `LeadChannels[channel]` | `Leads[channel]` | Yes |
| `LeadChannels[channel]` | `AdSpend[channel]` | Yes |
| `LeadChannels[channel]` | `WeeklyLeadAlerts[channel]` | Yes |

All relationships are one to many, with single cross filter direction.

Then:

* Select `Dates`, then **Table tools > Mark as date table**, using `date`.
* Select `Dates[month_label]`, then **Column tools > Sort by column > month_start**.
* Select `Invoices[aging_bucket]`, then **Sort by column > aging_order**.
* Hide the key and helper columns in the fact tables (`matter_id`, `channel`, the date columns, `aging_order`), so report builders always use the dimensions.
* Create an empty table to hold measures: **Home > Enter data**, name it `_Measures`, load it, and put every measure below in it.

Why this shape: it is a star schema. Facts hold numbers, dimensions hold the things you slice by. The attorney reaches time and invoices through `Matters`, so there is exactly one filter path and no ambiguity.

---

## 3. Measures (DAX)

Create each with **New measure** in `_Measures`. Set the format shown in brackets.

### Revenue and collections

```dax
Billed = SUM ( Invoices[amount_billed] )                                  -- [Currency, 0 dp]

Collected = SUM ( Invoices[amount_paid] )                                 -- [Currency, 0 dp]

Collection Rate = DIVIDE ( [Collected], [Billed] )                             -- [Percentage, 1 dp]

Standard Value = SUM ( TimeEntries[standard_value] )                             -- [Currency, 0 dp]
```

Realization compares what was billed with the time it covers. Invoices bill the previous month's work, so it switches to the inactive `work_month_start` relationship. It also ignores months that have not been invoiced yet; otherwise the latest month would drag the figure down.

Note: DAX does not allow a measure inside a simple CALCULATE filter such as `Dates[date] <= [Some Measure]`, so the cut-off date is stored in a variable first.

```dax
Last Invoiced Work Month =
CALCULATE ( MAX ( Invoices[work_month_start] ), REMOVEFILTERS () )

Realization =                                                                  -- [Percentage, 1 dp]
VAR CutOff = EOMONTH ( [Last Invoiced Work Month], 0 )
VAR BilledForWork =
    CALCULATE ( [Billed], USERELATIONSHIP ( Dates[date], Invoices[work_month_start] ) )
VAR InvoicedWorkValue =
    CALCULATE ( [Standard Value], KEEPFILTERS ( Dates[date] <= CutOff ) )
RETURN
    DIVIDE ( BilledForWork, InvoicedWorkValue )

Unbilled Work =                                                                -- [Currency, 0 dp]
VAR CutOff = EOMONTH ( [Last Invoiced Work Month], 0 )
RETURN
    CALCULATE ( [Standard Value], KEEPFILTERS ( Dates[date] > CutOff ) )
```

### Receivables (a snapshot at 30 Sep 2026, so the date slicer is ignored)

```dax
Receivables = CALCULATE ( SUM ( Invoices[outstanding] ), REMOVEFILTERS ( Dates ) )   -- [Currency, 0 dp]

Receivables Over 90 Days =
CALCULATE ( [Receivables], Invoices[aging_bucket] = "Over 90 days" )                   -- [Currency, 0 dp]

Share Over 90 Days = DIVIDE ( [Receivables Over 90 Days], [Receivables] )                   -- [Percentage, 0 dp]
```

### Team

```dax
Billable Hours = SUM ( TimeEntries[billable_hours] )                             -- [Whole number]

Capacity Hours =
SUMX (
    SUMMARIZE ( TimeEntries, Attorneys[attorney], Dates[month_start] ),
    CALCULATE ( MAX ( Attorneys[monthly_capacity_hours] ) )
)

Utilization = DIVIDE ( [Billable Hours], [Capacity Hours] )                    -- [Percentage, 0 dp]
```

Capacity counts each attorney's 140 hours only for months in which they recorded time, so a month before someone joined does not count against them.

### Intake and marketing

```dax
Lead Count = COUNTROWS ( Leads )                                               -- [Whole number]

Consultations = CALCULATE ( [Lead Count], Leads[is_consulted] = TRUE () )      -- [Whole number]

Retained Clients = CALCULATE ( [Lead Count], Leads[is_retained] = TRUE () )    -- [Whole number]

Lead to Consult = DIVIDE ( [Consultations], [Lead Count] )                          -- [Percentage, 0 dp]

Consult to Retained = DIVIDE ( [Retained Clients], [Consultations] )           -- [Percentage, 0 dp]

Ad Spend = SUM ( AdSpend[spend_usd] )                             -- [Currency, 0 dp]

Cost per Retained Client =                                                     -- [Currency, 0 dp]
IF ( [Ad Spend] > 0, DIVIDE ( [Ad Spend], [Retained Clients] ) )
```

The `IF` leaves Referral blank instead of showing $0, since referrals have no ad spend.

### "What needs attention" text

These measures write plain sentences that update with the date slicer. Show each one in a **Card (new)** or a **Text box** with a dynamic value.

```dax
Alert Lead Outage =
VAR Alerts = FILTER ( WeeklyLeadAlerts, WeeklyLeadAlerts[is_anomaly] = TRUE () )
VAR Channels =
    CONCATENATEX ( DISTINCT ( SELECTCOLUMNS ( Alerts, "@ch", WeeklyLeadAlerts[channel] ) ), [@ch], " and " )
VAR Weeks =
    CONCATENATEX ( Alerts, FORMAT ( WeeklyLeadAlerts[week_start], "d mmm yyyy" ), ", ", WeeklyLeadAlerts[week_start], ASC )
VAR Lost = SUMX ( Alerts, WeeklyLeadAlerts[trailing_avg] - WeeklyLeadAlerts[leads] )
RETURN
    IF (
        ISEMPTY ( Alerts ),
        "No lead channel outages detected in this period.",
        Channels & " leads collapsed in the weeks of " & Weeks & ". About " & FORMAT ( Lost, "0" )
            & " leads were lost while ad spend continued. Check the web form and tracking integration."
    )

Alert Channel Cost =
VAR Paid = FILTER ( ADDCOLUMNS ( VALUES ( LeadChannels[channel] ), "@cpr", [Cost per Retained Client] ), NOT ISBLANK ( [@cpr] ) )
VAR Worst = TOPN ( 1, Paid, [@cpr], DESC )
VAR Best = TOPN ( 1, Paid, [@cpr], ASC )
RETURN
    MAXX ( Worst, LeadChannels[channel] ) & " costs " & FORMAT ( MAXX ( Worst, [@cpr] ), "$#,0" )
        & " per retained client, versus " & FORMAT ( MAXX ( Best, [@cpr] ), "$#,0" )
        & " for " & MAXX ( Best, LeadChannels[channel] ) & "."

Alert Workload =
VAR T = ADDCOLUMNS ( VALUES ( Attorneys[attorney] ), "@u", [Utilization] )
VAR Hi = TOPN ( 1, T, [@u], DESC )
VAR Lo = TOPN ( 1, T, [@u], ASC )
RETURN
    "Workload is uneven: " & MAXX ( Hi, Attorneys[attorney] ) & " is at " & FORMAT ( MAXX ( Hi, [@u] ), "0%" )
        & " of capacity while " & MAXX ( Lo, Attorneys[attorney] ) & " is at " & FORMAT ( MAXX ( Lo, [@u] ), "0%" ) & "."

Alert Slow Collections =
VAR T = ADDCOLUMNS ( VALUES ( Matters[practice_area] ), "@s", [Share Over 90 Days] )
VAR W = TOPN ( 1, T, [@s], DESC )
RETURN
    MAXX ( W, Matters[practice_area] ) & " has the slowest collections: " & FORMAT ( MAXX ( W, [@s] ), "0%" )
        & " of its receivables are more than 90 days old."
```

---

## 4. Build the pages

Import the colour theme first: **View > Themes > Browse for themes > `powerbi/theme.json`**. It applies a colour-blind-checked palette and a clean background.

Put a **date slicer** (between style, on `Dates[date]`) at the top of every page, and use **View > Sync slicers** so it carries across pages. Set it to 1 Oct 2025 to 30 Sep 2026.

### Page 1: Overview

* **Five cards** across the top: `Billed`, `Collected`, `Retained Clients`, `Utilization`, `Receivables Over 90 Days`. Under each, a small text card with the context (`Collection Rate`, "of 140 hours a month", `Share Over 90 Days`).
* Below them, a heading **What needs attention** and four cards showing `Alert Lead Outage`, `Alert Channel Cost`, `Alert Workload` and `Alert Slow Collections`. Give the outage card a light red background and the others light yellow or blue, so the most urgent item stands out.

### Page 2: Intake and marketing

* **Line chart**: X = `WeeklyLeadAlerts[week_start]`, Y = `leads`, Legend = `LeadChannels[channel]`. Add a slicer on channel and default it to Google Ads and Website Organic. To mark the outage, add `is_anomaly` as a tooltip, or use **Markers > conditional formatting** to colour anomaly weeks red.
* **Bar chart (horizontal)**: Y = `LeadChannels[channel]`, X = `Cost per Retained Client`, sorted descending, data labels on.
* **Table (funnel by channel)**: `channel`, `Lead Count`, `Consultations`, `Retained Clients`, `Lead to Consult`, `Consult to Retained`, `Ad Spend`.

### Page 3: Team performance

* **Bar chart (horizontal)**: Y = `Attorneys[attorney]`, X = `Utilization`. In **Analytics**, add a **constant line at 1** (100%) labelled "Target". Optional: conditional colour bars above 100% orange.
* **Table**: `attorney`, `Billable Hours`, `Realization`, `Collection Rate`, with **conditional formatting > data bars** on Realization.
* **Card**: `Unbilled Work`, captioned "Work done but not yet invoiced".

### Page 4: Revenue and collections

* **Line chart**: X = `Dates[month_start]`, Y = `Billed` and `Collected`. Add a text note: "Recent invoices are still within payment terms, so the latest months will rise."
* **Line chart**: X = `Dates[month_start]`, Y = `Billed`, Legend = `Matters[practice_area]`.
* **Column chart**: X = `Invoices[aging_bucket]`, Y = `Receivables`. Filter the visual to exclude "Paid". Use a single blue, or a light to dark blue gradient by age.
* **Matrix**: rows = `practice_area`, columns = `aging_bucket`, values = `Receivables`.

### Page 5: Data quality

* **Table**: `QualityChecks` (check, failing_rows, status), with conditional formatting on status (PASS green, WARN amber, FAIL red), always alongside the word.
* **Table**: `CleaningLog` (table, issue, rows_affected, action).
* A short text box: "These checks run every time the pipeline runs. A FAIL stops the data from refreshing."

---

## 5. Check your numbers

With the date slicer set to **1 Oct 2025 to 30 Sep 2026**, your measures should show:

| Measure | Expected |
| --- | --- |
| Billed | $3,262,864 |
| Collected | $2,767,060 |
| Collection Rate | 84.8% |
| Lead Count | 2,545 |
| Consultations | 1,144 |
| Retained Clients | 263 |
| Ad Spend | $239,592 |
| Utilization | 92.8% |
| Realization | 88.6% |
| Unbilled Work | $473,660 |
| Receivables (any date range) | $571,562 |
| Receivables Over 90 Days | $246,032 (43%) |

Cost per retained client:

| Channel | Expected |
| --- | --- |
| Facebook Ads | $4,295 |
| Google Ads | $1,899 |
| Legal Directory | $1,287 |
| Website Organic | $298 |
| Referral | blank |

Utilization by attorney: A. Morgan 105%, B. Chen 100%, C. Okafor 75%, D. Rivera 101%, E. Schultz 106%, F. Haddad 87%, G. Brooks 74%.

Realization by attorney: A. Morgan 89.4%, B. Chen 91.3%, C. Okafor 80.6%, D. Rivera 92.3%, E. Schultz 89.2%, F. Haddad 91.0%, G. Brooks 81.4%.

Lead outage alert: Google Ads, weeks of 9, 16 and 23 Mar 2026, about 43 leads lost.

Slowest collections: Personal Injury, 56% over 90 days.

If a figure is off, the usual causes are: a date column still loaded as text, a relationship pointing the wrong way, or a slicer not synced to that page.

---

## 6. Finish and share

* Save the file as `powerbi/law_firm_ops.pbix` and commit it to the repo.
* **File > Export > Export to PDF** and add the PDF to the repo, so people without Power BI can see it.
* Take a screenshot of the Overview page, save it as `docs/dashboard.png` (replacing the current one), and it will show at the top of the README.
* If you have a work or school Power BI account, you can publish to the Power BI service and share a link. **Publish to web** creates a public link, so only use it because this data is synthetic.
