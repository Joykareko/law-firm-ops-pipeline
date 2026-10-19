# Video walkthrough script (about 4 minutes)

Record with Loom or any screen recorder. Have three windows ready: the Power BI report, VS Code with the project open, and a terminal.
Speak naturally. The bold lines are what to show on screen.

---

## 1. The problem (30 seconds)

**Show: Power BI, Overview page**

> "Hi, I'm Joy. This is a project I built to show how I'd approach the kind of work Swans does.
>
> Law firms usually run on disconnected tools: leads in a CRM like HubSpot, matters and time in something like Clio, invoices in billing, and ad spend in Google and Facebook. The result is that leadership can't easily answer basic questions: which marketing actually brings in paying clients, whether attorneys are overloaded, and how much of their work they actually get paid for.
>
> So I built a pipeline that pulls all of that into one place. The data is synthetic, but I deliberately made it as messy as real exports are."

## 2. How I built it (2 minutes)

**Show: VS Code, `pipeline/extract.py`**

> "Extraction is written the way it would be against real APIs: paginated requests with retries and rate limit handling. For this demo it reads the exported files, so it runs anywhere."

**Show: `data/raw/crm_contacts.json`, scroll to an epoch timestamp, then `pipeline/clean.py`**

> "The raw data has the problems you actually meet. Dates come in three formats, including epoch milliseconds from HubSpot. The same person submits a form twice with different capitalisation. Practice areas are spelled 17 different ways. Time entries have negative hours and decimal slips.
>
> Every fix the cleaning step makes is logged, so nothing changes silently."

**Show: terminal, run `python run_pipeline.py`**

> "Then the data goes through automated quality checks. Warnings get surfaced, but if a check fails, for example a time entry pointing at a matter that doesn't exist, the pipeline stops so leadership never sees numbers built on broken data."

**Show: `models/marts/fct_weekly_leads.sql`**

> "The business logic lives in SQL models, the same pattern as dbt. This one flags any week where a lead channel drops below a quarter of its normal volume. I tuned that threshold so it catches real breakages without firing on normal noise."

**Show: Power BI Model view, then the Realization measure**

> "The pipeline exports a star schema into Power BI. One detail I'm pleased with: invoices bill the previous month's work, so realization uses a second, inactive date relationship with USERELATIONSHIP, and it ignores months that haven't been invoiced yet. Without that, the latest month makes the firm look like it's writing off a fortune."

## 3. The impact (1 minute)

**Show: Power BI, the "What needs attention" cards on the Overview page**

> "These cards are the point of the whole thing: plain language actions, written by DAX measures, that update when you change the dates.
>
> First, Google Ads leads went to zero for three weeks in March while the firm kept paying for ads. In a real firm, that's a broken form or tracking tag, and nobody notices until month end. Here it's flagged automatically.
>
> Second, Facebook costs over four thousand dollars per retained client, against about three hundred for organic search. That's a budget decision ready to be made.
>
> Third, workload is uneven across attorneys, and Personal Injury has more than half its receivables over 90 days old."

**Show: Power BI, Data quality page**

> "And this page shows exactly what was cleaned and what passed, so people trust the numbers."

## 4. Close (20 seconds)

> "I've done this for real before. At Boehringer Ingelheim I built the Python validation pipelines and the Tableau dashboards tracking more than 50 KPIs, which cut manual reporting time by about 40%. At RBC I built API-fed dashboards used by teams in three countries.
>
> What I enjoy most is owning the whole thing, from messy raw data to a decision someone actually makes. Thanks for watching."

---

**Tips**
* Keep it under 5 minutes. Rehearse once, then record in one take; small stumbles are fine.
* Zoom your browser to 110% so text is readable in the recording.
* Don't read the script word for word. Use it as a guide.
