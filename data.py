"""
Data layer for the FieldPro Brand Awareness Dashboard.
"""

import re
from datetime import date, timedelta

import pandas as pd
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    Metric,
    RunReportRequest,
)
from googleapiclient.discovery import build

from auth import get_credentials


GA4_PROPERTY_ID = "397004121"
SEARCH_CONSOLE_PROPERTY = "sc-domain:fieldproapp.com"
DEMO_EVENT_NAME = "completed_demo_form"

# Updated regex catches typos: fielpro, feild pro, etc.
BRAND_PATTERN = re.compile(
    r"field\s*[-]?\s*pro|fie[l]?d\s*pro|feild\s*pro|feildpro|fielpro|optimetriks",
    re.IGNORECASE,
)

LLM_SOURCES = [
    "chatgpt.com",
    "perplexity.ai",
    "claude.ai",
    "gemini.google.com",
    "copilot.microsoft.com",
]


def _get_ga4_client():
    return BetaAnalyticsDataClient(credentials=get_credentials())


def _get_sc_service():
    return build("searchconsole", "v1", credentials=get_credentials())


def _date_strings(period_days, end_offset_days=0):
    end = date.today() - timedelta(days=end_offset_days)
    start = end - timedelta(days=period_days)
    return str(start), str(end)


def _is_brand_query(query):
    return bool(BRAND_PATTERN.search(query))


def get_brand_split(period_days=7, end_offset_days=0):
    service = _get_sc_service()
    start_str, end_str = _date_strings(period_days, end_offset_days)
    response = service.searchanalytics().query(
        siteUrl=SEARCH_CONSOLE_PROPERTY,
        body={"startDate": start_str, "endDate": end_str, "dimensions": ["query"], "rowLimit": 25000},
    ).execute()
    brand_clicks = 0
    nonbrand_clicks = 0
    for row in response.get("rows", []):
        if _is_brand_query(row["keys"][0]):
            brand_clicks += int(row["clicks"])
        else:
            nonbrand_clicks += int(row["clicks"])
    return {"brand_clicks": brand_clicks, "nonbrand_clicks": nonbrand_clicks}


def get_direct_sessions(period_days=7, end_offset_days=0):
    client = _get_ga4_client()
    start_str, end_str = _date_strings(period_days, end_offset_days)
    response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions")],
    ))
    for row in response.rows:
        if row.dimension_values[0].value == "Direct":
            return int(row.metric_values[0].value)
    return 0


def get_llm_sessions(period_days=7, end_offset_days=0):
    client = _get_ga4_client()
    start_str, end_str = _date_strings(period_days, end_offset_days)
    response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        dimensions=[Dimension(name="sessionSource")],
        metrics=[Metric(name="sessions")],
    ))
    total = 0
    for row in response.rows:
        source = row.dimension_values[0].value.lower()
        if any(llm in source for llm in LLM_SOURCES):
            total += int(row.metric_values[0].value)
    return total


def get_total_demos(period_days=7, end_offset_days=0):
    client = _get_ga4_client()
    start_str, end_str = _date_strings(period_days, end_offset_days)
    response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(value=DEMO_EVENT_NAME),
        )),
    ))
    if response.rows:
        return int(response.rows[0].metric_values[0].value)
    return 0


def get_demos_from_organic_and_llm(period_days=7, end_offset_days=0):
    client = _get_ga4_client()
    start_str, end_str = _date_strings(period_days, end_offset_days)
    response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        dimensions=[Dimension(name="sessionDefaultChannelGroup"), Dimension(name="sessionSource")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(value=DEMO_EVENT_NAME),
        )),
    ))
    total = 0
    for row in response.rows:
        channel = row.dimension_values[0].value
        source = row.dimension_values[1].value.lower()
        if channel == "Organic Search" or any(llm in source for llm in LLM_SOURCES):
            total += int(row.metric_values[0].value)
    return total


def get_tier1_metrics(period_days=7, end_offset_days=0):
    sc = get_brand_split(period_days, end_offset_days)
    direct = get_direct_sessions(period_days, end_offset_days)
    llm = get_llm_sessions(period_days, end_offset_days)
    demos = get_total_demos(period_days, end_offset_days)
    demos_org_llm = get_demos_from_organic_and_llm(period_days, end_offset_days)
    return {
        "non_brand_organic": sc["nonbrand_clicks"],
        "llm_referral": llm,
        "already_aware": sc["brand_clicks"] + direct,
        "total_demos": demos,
        "demos_org_llm": demos_org_llm,
        "brand_organic": sc["brand_clicks"],
        "direct": direct,
    }


def get_tier1_with_comparison(period_days=7):
    print(f"Fetching Tier 1 — current and previous {period_days} days...")
    current = get_tier1_metrics(period_days, end_offset_days=0)
    previous = get_tier1_metrics(period_days, end_offset_days=period_days)
    deltas = {}
    for key in current:
        cur, prev = current[key], previous[key]
        deltas[key] = None if prev == 0 else round(100 * (cur - prev) / prev, 1)
    return {"current": current, "previous": previous, "deltas": deltas}


def get_daily_breakdown(period_days=28):
    print(f"Fetching daily breakdown for last {period_days} days...")
    start_str, end_str = _date_strings(period_days, 0)

    sc = _get_sc_service()
    sc_response = sc.searchanalytics().query(
        siteUrl=SEARCH_CONSOLE_PROPERTY,
        body={"startDate": start_str, "endDate": end_str, "dimensions": ["date", "query"], "rowLimit": 25000},
    ).execute()

    sc_daily = {}
    for row in sc_response.get("rows", []):
        d, query = row["keys"]
        clicks = int(row["clicks"])
        if d not in sc_daily:
            sc_daily[d] = {"brand": 0, "nonbrand": 0}
        if _is_brand_query(query):
            sc_daily[d]["brand"] += clicks
        else:
            sc_daily[d]["nonbrand"] += clicks

    client = _get_ga4_client()
    direct_response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        dimensions=[Dimension(name="date"), Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions")],
    ))
    direct_daily = {}
    for row in direct_response.rows:
        ga = row.dimension_values[0].value
        d = f"{ga[:4]}-{ga[4:6]}-{ga[6:]}"
        if row.dimension_values[1].value == "Direct":
            direct_daily[d] = int(row.metric_values[0].value)

    llm_response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        dimensions=[Dimension(name="date"), Dimension(name="sessionSource")],
        metrics=[Metric(name="sessions")],
    ))
    llm_daily = {}
    for row in llm_response.rows:
        ga = row.dimension_values[0].value
        d = f"{ga[:4]}-{ga[4:6]}-{ga[6:]}"
        source = row.dimension_values[1].value.lower()
        if any(llm in source for llm in LLM_SOURCES):
            llm_daily[d] = llm_daily.get(d, 0) + int(row.metric_values[0].value)

    all_dates = pd.date_range(start=start_str, end=end_str, freq="D")
    rows = []
    for d in all_dates:
        ds = d.strftime("%Y-%m-%d")
        sc_day = sc_daily.get(ds, {"brand": 0, "nonbrand": 0})
        rows.append({
            "date": d,
            "non_brand_organic": sc_day["nonbrand"],
            "llm_referral": llm_daily.get(ds, 0),
            "already_aware": sc_day["brand"] + direct_daily.get(ds, 0),
        })
    return pd.DataFrame(rows).set_index("date")


def get_top_nonbrand_queries(period_days=28, limit=20):
    """Top non-brand queries by clicks, with Signal classification."""
    service = _get_sc_service()
    start_str, end_str = _date_strings(period_days, 0)

    response = service.searchanalytics().query(
        siteUrl=SEARCH_CONSOLE_PROPERTY,
        body={"startDate": start_str, "endDate": end_str, "dimensions": ["query"], "rowLimit": 25000},
    ).execute()

    rows = []
    for row in response.get("rows", []):
        query = row["keys"][0]
        if _is_brand_query(query):
            continue

        clicks = int(row["clicks"])
        impressions = int(row["impressions"])
        ctr = round(row["ctr"] * 100, 1)
        position = round(row["position"], 1)

        if position <= 3:
            signal = "Strong"
        elif position <= 10:
            signal = "Page 1"
        elif position <= 20:
            signal = "Borderline"
        elif impressions > 100:
            signal = "Title opp."
        else:
            signal = "Long tail"

        rows.append({
            "query": query,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": ctr,
            "position": position,
            "signal": signal,
        })

    rows.sort(key=lambda r: r["clicks"], reverse=True)
    return pd.DataFrame(rows[:limit])


if __name__ == "__main__":
    print(get_top_nonbrand_queries(period_days=28, limit=10))


def get_top_organic_landing_pages(period_days=28, limit=20):
    """Top organic landing pages — which pages strangers enter through from search."""
    client = _get_ga4_client()
    start_str, end_str = _date_strings(period_days, 0)

    response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        dimensions=[
            Dimension(name="landingPagePlusQueryString"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagementRate"),
            Metric(name="averageSessionDuration"),
        ],
    ))

    page_totals = {}
    for row in response.rows:
        page = row.dimension_values[0].value
        channel = row.dimension_values[1].value
        if channel != "Organic Search":
            continue

        sessions = int(row.metric_values[0].value)
        eng_rate = float(row.metric_values[1].value)
        avg_dur = float(row.metric_values[2].value)

        if page not in page_totals:
            page_totals[page] = {"sessions": 0, "weighted_eng": 0.0, "weighted_dur": 0.0}

        page_totals[page]["sessions"] += sessions
        page_totals[page]["weighted_eng"] += eng_rate * sessions
        page_totals[page]["weighted_dur"] += avg_dur * sessions

    rows = []
    for page, totals in page_totals.items():
        s = totals["sessions"]
        if s == 0:
            continue
        rows.append({
            "page": page,
            "sessions": s,
            "engagement_rate": round(100 * totals["weighted_eng"] / s, 1),
            "avg_duration_sec": round(totals["weighted_dur"] / s, 1),
        })

    rows.sort(key=lambda r: r["sessions"], reverse=True)
    return pd.DataFrame(rows[:limit])


def get_llm_citations(period_days=28, limit=20):
    """
    Which pages did LLM-driven sessions land on?
    """
    client = _get_ga4_client()
    start_str, end_str = _date_strings(period_days, 0)

    response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        dimensions=[
            Dimension(name="landingPagePlusQueryString"),
            Dimension(name="sessionSource"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagementRate"),
        ],
    ))

    rows = []
    for row in response.rows:
        page = row.dimension_values[0].value
        source = row.dimension_values[1].value.lower()

        matched_llm = None
        for llm in LLM_SOURCES:
            if llm in source:
                matched_llm = llm
                break

        if not matched_llm:
            continue

        sessions = int(row.metric_values[0].value)
        eng_rate = float(row.metric_values[1].value)

        source_pretty = {
            "chatgpt.com": "ChatGPT",
            "perplexity.ai": "Perplexity",
            "claude.ai": "Claude",
            "gemini.google.com": "Gemini",
            "copilot.microsoft.com": "Copilot",
        }.get(matched_llm, matched_llm)

        rows.append({
            "page": page,
            "source": source_pretty,
            "sessions": sessions,
            "engagement_rate": round(100 * eng_rate, 1),
        })

    rows.sort(key=lambda r: r["sessions"], reverse=True)
    return pd.DataFrame(rows[:limit])


def get_demo_funnel(period_days=28):
    """
    3-stage demo conversion funnel.
    Sessions -> Clicked Book a Demo -> Completed form.
    Skips form_start (GA4 auto-event fires on any form, not just demo).
    """
    client = _get_ga4_client()
    start_str, end_str = _date_strings(period_days, 0)

    sessions_response = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        metrics=[Metric(name="sessions")],
    ))
    total_sessions = int(sessions_response.rows[0].metric_values[0].value) if sessions_response.rows else 0

    event_counts = {}
    for event_name in ["clicked_book_a_demo_button", "completed_demo_form"]:
        ev_response = client.run_report(RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
            dimension_filter=FilterExpression(filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(value=event_name),
            )),
        ))
        event_counts[event_name] = int(ev_response.rows[0].metric_values[0].value) if ev_response.rows else 0

    stages = [
        ("Sessions", total_sessions),
        ("Clicked Book a Demo", event_counts["clicked_book_a_demo_button"]),
        ("Completed form", event_counts["completed_demo_form"]),
    ]

    rows = []
    for i, (label, count) in enumerate(stages):
        if i == 0:
            step_rate = None
            overall_rate = None
        else:
            prev_count = stages[i - 1][1]
            step_rate = round(100 * count / prev_count, 2) if prev_count > 0 else 0.0
            overall_rate = round(100 * count / total_sessions, 3) if total_sessions > 0 else 0.0

        rows.append({
            "stage": label,
            "count": count,
            "step_rate": step_rate,
            "overall_rate": overall_rate,
        })

    return pd.DataFrame(rows)
