"""
The FieldPro Brand Awareness Dashboard.
"""

import altair as alt
import pandas as pd
import streamlit as st

from data import (
    get_tier1_with_comparison,
    get_daily_breakdown,
    get_top_nonbrand_queries,
    get_top_organic_landing_pages,
    get_llm_citations,
    get_demo_funnel,
)

st.set_page_config(
    page_title="FieldPro · Brand Awareness",
    page_icon="📊",
    layout="wide",
)

# ============ Custom CSS — card styling for metrics ============
st.markdown("""
<style>
/* Wrap each st.metric in a proper card */
[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border: 1px solid #ECE8E0;
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(24, 34, 42, 0.04);
}

/* Tighten label */
[data-testid="stMetricLabel"] {
    font-size: 13px;
    color: #5A6470;
    font-weight: 500;
}

/* Value styling */
[data-testid="stMetricValue"] {
    font-size: 32px;
    font-weight: 700;
    color: #18222A;
    line-height: 1.1;
}

/* Delta pill styling */
[data-testid="stMetricDelta"] {
    font-size: 12px;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600, show_spinner=False)
def load_tier1(period_days):
    return get_tier1_with_comparison(period_days=period_days)


@st.cache_data(ttl=3600, show_spinner=False)
def load_daily(period_days):
    return get_daily_breakdown(period_days=period_days)


@st.cache_data(ttl=3600, show_spinner=False)
def load_queries(period_days, limit=20):
    return get_top_nonbrand_queries(period_days=period_days, limit=limit)


@st.cache_data(ttl=3600, show_spinner=False)
def load_pages(period_days, limit=15):
    return get_top_organic_landing_pages(period_days=period_days, limit=limit)


@st.cache_data(ttl=3600, show_spinner=False)
def load_llm(period_days, limit=20):
    return get_llm_citations(period_days=period_days, limit=limit)


@st.cache_data(ttl=3600, show_spinner=False)
def load_funnel(period_days):
    return get_demo_funnel(period_days=period_days)


# ============ Header ============
header_left, header_right = st.columns([5, 1])
with header_left:
    st.title("FieldPro Brand Awareness")
    st.caption("Tracking the shift from brand-dependent traffic to organic-driven growth")
with header_right:
    st.write("")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()


# ============ Date filter ============
range_options = {"Last 7 days": 7, "Last 28 days": 28, "Last 90 days": 90}
selected_label = st.radio(
    "Date range",
    options=list(range_options.keys()),
    horizontal=True,
    label_visibility="collapsed",
)
period_days = range_options[selected_label]


# ============ Fetch headline ============
with st.spinner(f"Loading data for {selected_label.lower()}..."):
    data = load_tier1(period_days=period_days)

current = data["current"]
deltas = data["deltas"]


def format_delta(percent):
    if percent is None:
        return None
    return f"{percent:+.1f}%"


# ============ Headline cards ============
st.subheader(f"Headline metrics — {selected_label.lower()} vs previous {period_days} days")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Non-brand organic ⭐", f"{current['non_brand_organic']:,}",
              delta=format_delta(deltas["non_brand_organic"]),
              help="Strangers discovering FieldPro through Google search (excluding brand queries)")
with col2:
    st.metric("LLM referral", f"{current['llm_referral']:,}",
              delta=format_delta(deltas["llm_referral"]),
              help="Sessions from ChatGPT, Perplexity, Claude, Gemini, Copilot")
with col3:
    st.metric("Already aware", f"{current['already_aware']:,}",
              delta=format_delta(deltas["already_aware"]), delta_color="off",
              help="Brand organic + Direct — people who already know FieldPro. Stable here is fine.")
with col4:
    st.metric("Total demos", f"{current['total_demos']:,}",
              delta=format_delta(deltas["total_demos"]),
              help="All completed_demo_form events")
with col5:
    total = current["total_demos"]
    org_llm = current["demos_org_llm"]
    share_str = f"{round(100 * org_llm / total)}% of total" if total > 0 else "—"
    st.metric("Demos · org+LLM", f"{org_llm:,}",
              delta=format_delta(deltas["demos_org_llm"]),
              help="Demos from organic search or LLM referrals — the earned-channel slice")
    st.caption(share_str)


# ============ Trend charts ============
st.markdown("---")
st.subheader(f"Daily trend — {selected_label.lower()}")
st.caption("Search Console data has a 2 to 3 day reporting lag — most recent days will look low.")

with st.spinner("Loading daily breakdown..."):
    daily_df = load_daily(period_days=period_days)


def make_chart(df, column, color, title):
    chart_df = df.reset_index()[["date", column]].rename(columns={column: "value"})
    return (
        alt.Chart(chart_df, title=title)
        .mark_line(color=color, strokeWidth=2.5, point=alt.OverlayMarkDef(filled=True, size=40))
        .encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %d", labelFontSize=11)),
            y=alt.Y("value:Q", title=None, axis=alt.Axis(labelFontSize=11), scale=alt.Scale(zero=True)),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%b %d"),
                alt.Tooltip("value:Q", title="Value", format=","),
            ],
        )
        .properties(height=200)
        .configure_axis(grid=True, gridColor="#ECE8E0", domainOpacity=0)
        .configure_view(strokeWidth=0)
        .configure_title(fontSize=13, anchor="start", color="#18222A")
    )


COLOR_NONBRAND = "#FEBD55"
COLOR_LLM = "#124E5D"
COLOR_AWARE = "#7A8A95"

ccol1, ccol2, ccol3 = st.columns(3)
with ccol1:
    st.altair_chart(make_chart(daily_df, "non_brand_organic", COLOR_NONBRAND, "Non-brand organic ⭐"),
                    use_container_width=True)
with ccol2:
    st.altair_chart(make_chart(daily_df, "llm_referral", COLOR_LLM, "LLM referral"),
                    use_container_width=True)
with ccol3:
    st.altair_chart(make_chart(daily_df, "already_aware", COLOR_AWARE, "Already aware"),
                    use_container_width=True)


# ============ Demo funnel ============
st.markdown("---")
st.subheader(f"Demo funnel — {selected_label.lower()}")
st.caption("Where prospects drop off on the path to a booked demo. Step rate = conversion from previous stage.")

with st.spinner("Loading funnel..."):
    funnel_df = load_funnel(period_days=period_days)

if funnel_df.empty or funnel_df["count"].iloc[0] == 0:
    st.info("No funnel data in this period yet.")
else:
    funnel_chart = (
        alt.Chart(funnel_df)
        .mark_bar(cornerRadius=4, color="#124E5D")
        .encode(
            y=alt.Y("stage:N", sort=None, title=None, axis=alt.Axis(labelFontSize=12)),
            x=alt.X("count:Q", title=None, axis=alt.Axis(labelFontSize=11, format=",")),
            tooltip=[
                alt.Tooltip("stage:N", title="Stage"),
                alt.Tooltip("count:Q", title="Count", format=","),
                alt.Tooltip("step_rate:Q", title="Step rate %", format=".2f"),
                alt.Tooltip("overall_rate:Q", title="Overall %", format=".3f"),
            ],
        )
        .properties(height=160)
        .configure_axis(grid=False, domainOpacity=0)
        .configure_view(strokeWidth=0)
    )

    chart_col, table_col = st.columns([2, 1])

    with chart_col:
        st.altair_chart(funnel_chart, use_container_width=True)

    with table_col:
        for _, row in funnel_df.iterrows():
            if pd.isna(row["step_rate"]):
                st.markdown(f"**{row['stage']}** — {int(row['count']):,}")
            else:
                st.markdown(
                    f"**{row['stage']}** — {int(row['count']):,}  \n"
                    f":gray[Step: {row['step_rate']:.2f}% · Overall: {row['overall_rate']:.3f}%]"
                )


# ============ Top non-brand queries ============
st.markdown("---")
st.subheader(f"Top non-brand search queries — {selected_label.lower()}")
st.caption("What strangers are searching for that brings them to FieldPro. Signal column suggests where to act.")

with st.spinner("Loading queries..."):
    queries_df = load_queries(period_days=period_days, limit=20)

if queries_df.empty:
    st.info("No non-brand queries in this period yet.")
else:
    display_df = queries_df.copy()
    display_df.columns = ["Query", "Clicks", "Impressions", "CTR (%)", "Avg position", "Signal"]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Query": st.column_config.TextColumn(width="large"),
            "Clicks": st.column_config.NumberColumn(format="%d"),
            "Impressions": st.column_config.NumberColumn(format="%d"),
            "CTR (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg position": st.column_config.NumberColumn(format="%.1f"),
            "Signal": st.column_config.TextColumn(width="small"),
        },
    )

    st.caption(
        "**Signal guide:** "
        "**Strong** (avg position less than 3) · "
        "**Page 1** (4 to 10) · "
        "**Borderline** (11 to 20) · "
        "**Title opp.** (greater than 20 but more than 100 impressions) · "
        "**Long tail** (low impressions)"
    )


# ============ Top organic landing pages ============
st.markdown("---")
st.subheader(f"Top organic landing pages — {selected_label.lower()}")
st.caption("Where strangers arrive from search. Use engagement rate and avg duration to spot what is working.")

with st.spinner("Loading landing pages..."):
    pages_df = load_pages(period_days=period_days, limit=15)

if pages_df.empty:
    st.info("No organic landing pages in this period yet.")
else:
    display_pages = pages_df.copy()
    display_pages.columns = ["Page", "Sessions", "Engagement rate (%)", "Avg duration (sec)"]

    st.dataframe(
        display_pages,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Page": st.column_config.TextColumn(width="large"),
            "Sessions": st.column_config.NumberColumn(format="%d"),
            "Engagement rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg duration (sec)": st.column_config.NumberColumn(format="%.0f"),
        },
    )


# ============ LLM citations ============
st.markdown("---")
st.subheader(f"LLM citations — {selected_label.lower()}")
st.caption("Which pages AI assistants (ChatGPT, Claude, Perplexity, Gemini, Copilot) sent visitors to.")

with st.spinner("Loading LLM citations..."):
    llm_df = load_llm(period_days=period_days, limit=20)

if llm_df.empty:
    st.info("No LLM-driven sessions in this period yet.")
else:
    display_llm = llm_df.copy()
    display_llm.columns = ["Page", "Source", "Sessions", "Engagement rate (%)"]

    st.dataframe(
        display_llm,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Page": st.column_config.TextColumn(width="large"),
            "Source": st.column_config.TextColumn(width="small"),
            "Sessions": st.column_config.NumberColumn(format="%d"),
            "Engagement rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )


# ============ Already aware breakdown ============
st.markdown("---")
st.caption("**Already aware breakdown** — drill-down on the existing-audience card")

bcol1, bcol2 = st.columns(2)
with bcol1:
    st.metric("Brand organic", f"{current['brand_organic']:,}",
              delta=format_delta(deltas["brand_organic"]),
              help='Searched "FieldPro" or similar in Google')
with bcol2:
    st.metric("Direct", f"{current['direct']:,}",
              delta=format_delta(deltas["direct"]), delta_color="off",
              help="Typed URL, used bookmark, or referrer was stripped")