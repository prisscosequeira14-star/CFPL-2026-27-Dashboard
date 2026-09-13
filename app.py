import calendar
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import pandas as pd
import requests
import streamlit as st

# -----------------------------
# CFPL 2026/27 configuration
# -----------------------------
LEAGUE_ID = 402686
LEAGUE_NAME = "CHINCHINIM FPL 26/27 by ABSgym"
FPL_API = "https://fantasy.premierleague.com/api"
REQUEST_TIMEOUT = 20

st.set_page_config(
    page_title="CFPL 2026/27",
    page_icon="🏆",
    layout="wide",
)

# -----------------------------
# Styling
# -----------------------------
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    .cfpl-title {font-size: 2rem; font-weight: 800; line-height: 1.1; margin-bottom: .15rem;}
    .cfpl-sub {color: #6b7280; margin-bottom: 1rem;}
    .winner-card {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 16px;
        padding: 18px;
        margin: 8px 0 16px 0;
    }
    .winner-name {font-size: 1.45rem; font-weight: 800;}
    .winner-score {font-size: 2rem; font-weight: 900;}
    .small-muted {color:#6b7280; font-size:.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# API helpers
# -----------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_json(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 CFPL-Dashboard/1.0",
        "Accept": "application/json",
    }
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=300, show_spinner=False)
def get_bootstrap() -> dict:
    return get_json(f"{FPL_API}/bootstrap-static/")


@st.cache_data(ttl=300, show_spinner=False)
def get_all_league_entries(league_id: int) -> Tuple[dict, List[dict]]:
    page = 1
    entries = []
    league_meta = {}

    while True:
        data = get_json(
            f"{FPL_API}/leagues-classic/{league_id}/standings/"
            f"?page_standings={page}"
        )
        if not league_meta:
            league_meta = data.get("league", {})

        standings = data.get("standings", {})
        results = standings.get("results", [])
        entries.extend(results)

        if not standings.get("has_next", False):
            break

        page += 1
        # Safety stop for an accidentally huge league.
        if page > 100:
            break

    return league_meta, entries


@st.cache_data(ttl=300, show_spinner=False)
def get_entry_history(entry_id: int) -> dict:
    return get_json(f"{FPL_API}/entry/{entry_id}/history/")


def fmt_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "-"


def ordinal_rank(rank: int) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return f"{medals.get(rank, '')} {rank}".strip()


def event_month_map(events: List[dict]) -> Dict[int, str]:
    mapping = {}
    for event in events:
        deadline = event.get("deadline_time")
        if not deadline:
            continue
        dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        mapping[int(event["id"])] = dt.strftime("%Y-%m")
    return mapping


def month_label(month_key: str) -> str:
    try:
        dt = datetime.strptime(month_key, "%Y-%m")
        return dt.strftime("%B %Y")
    except ValueError:
        return month_key


def build_data(entries: List[dict], events: List[dict], deduct_hits: bool):
    event_to_month = event_month_map(events)
    completed_events = {
        int(e["id"]): e for e in events
        if e.get("finished") or e.get("data_checked")
    }

    standing_rows = []
    history_rows = []

    progress = st.progress(0, text="Loading manager histories…")
    total = max(len(entries), 1)

    for i, row in enumerate(entries, start=1):
        entry_id = int(row["entry"])
        manager = row.get("player_name", "Unknown manager")
        team = row.get("entry_name", "Unknown team")

        standing_rows.append({
            "Rank": int(row.get("rank", 0) or 0),
            "Team": team,
            "Manager": manager,
            "Total Points": int(row.get("total", 0) or 0),
            "Entry ID": entry_id,
        })

        try:
            hist = get_entry_history(entry_id)
            for gw in hist.get("current", []):
                event = int(gw.get("event", 0) or 0)
                raw_points = int(gw.get("points", 0) or 0)
                hit = int(gw.get("event_transfers_cost", 0) or 0)
                net_points = raw_points - hit if deduct_hits else raw_points

                history_rows.append({
                    "Entry ID": entry_id,
                    "Manager": manager,
                    "Team": team,
                    "GW": event,
                    "GW Points": raw_points,
                    "Transfer Hit": hit,
                    "Net Points": net_points,
                    "Total Points at GW": int(gw.get("total_points", 0) or 0),
                    "Overall Rank": int(gw.get("overall_rank", 0) or 0),
                    "Month": event_to_month.get(event, "Unknown"),
                    "GW Finished": event in completed_events,
                })
        except requests.RequestException:
            # Keep the manager in overall standings even if one history request fails.
            pass

        progress.progress(i / total, text=f"Loading manager histories… {i}/{len(entries)}")

    progress.empty()

    standings_df = pd.DataFrame(standing_rows)
    history_df = pd.DataFrame(history_rows)

    if not standings_df.empty:
        standings_df = standings_df.sort_values(["Rank", "Total Points"], ascending=[True, False])

    return standings_df, history_df


def monthly_table(history_df: pd.DataFrame, month_key: str) -> pd.DataFrame:
    if history_df.empty:
        return pd.DataFrame()

    month_df = history_df[
        (history_df["Month"] == month_key) &
        (history_df["GW Finished"])
    ].copy()

    if month_df.empty:
        return pd.DataFrame()

    grouped = (
        month_df.groupby(["Entry ID", "Manager", "Team"], as_index=False)
        .agg(
            Monthly_Points=("Net Points", "sum"),
            GWs=("GW", "count"),
            Hits=("Transfer Hit", "sum"),
        )
        .sort_values(["Monthly_Points", "Manager"], ascending=[False, True])
        .reset_index(drop=True)
    )
    grouped["Rank"] = grouped["Monthly_Points"].rank(
        method="min", ascending=False
    ).astype(int)

    return grouped[["Rank", "Manager", "Team", "Monthly_Points", "GWs", "Hits", "Entry ID"]]


def manager_of_month_history(history_df: pd.DataFrame) -> pd.DataFrame:
    if history_df.empty:
        return pd.DataFrame()

    valid = history_df[
        (history_df["Month"] != "Unknown") &
        (history_df["GW Finished"])
    ].copy()

    if valid.empty:
        return pd.DataFrame()

    rows = []
    for month_key in sorted(valid["Month"].unique()):
        table = monthly_table(valid, month_key)
        if table.empty:
            continue
        winning_score = int(table["Monthly_Points"].max())
        winners = table[table["Monthly_Points"] == winning_score]
        for _, winner in winners.iterrows():
            rows.append({
                "Month": month_label(month_key),
                "Manager": winner["Manager"],
                "Team": winner["Team"],
                "Points": winning_score,
                "GWs": int(winner["GWs"]),
            })

    return pd.DataFrame(rows)


def latest_finished_gw(events: List[dict]):
    finished = [
        int(e["id"]) for e in events
        if e.get("finished") or e.get("data_checked")
    ]
    return max(finished) if finished else None


# -----------------------------
# App header + controls
# -----------------------------
st.markdown(f'<div class="cfpl-title">🏆 {LEAGUE_NAME}</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="cfpl-sub">Automatic league standings • Gameweek scores • Manager of the Month</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("CFPL Controls")
    st.caption(f"League ID: {LEAGUE_ID}")
    deduct_hits = st.toggle(
        "Deduct transfer hits",
        value=True,
        help="Recommended: a -4/-8 transfer hit reduces that manager's monthly score."
    )
    if st.button("🔄 Refresh FPL data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("Data source: Fantasy Premier League public endpoints.")
    st.caption("Monthly grouping: official FPL Gameweek deadline month.")

try:
    bootstrap = get_bootstrap()
    events = bootstrap.get("events", [])
    league_meta, entries = get_all_league_entries(LEAGUE_ID)

    if not entries:
        st.error(
            "No managers were returned for this league. "
            "Check that the league is active and accessible."
        )
        st.stop()

    standings_df, history_df = build_data(entries, events, deduct_hits)

except requests.RequestException as exc:
    st.error(
        "I couldn't reach the Fantasy Premier League data service right now. "
        "Use the Refresh button and try again."
    )
    st.caption(str(exc))
    st.stop()
except Exception as exc:
    st.error("The dashboard hit an unexpected data error.")
    st.caption(str(exc))
    st.stop()

league_display_name = league_meta.get("name", LEAGUE_NAME)
if league_display_name and league_display_name != LEAGUE_NAME:
    st.caption(f"FPL league name returned: {league_display_name}")

latest_gw = latest_finished_gw(events)
num_managers = len(standings_df)
leader = standings_df.iloc[0] if not standings_df.empty else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("Managers", num_managers)
col2.metric("Latest finished GW", f"GW{latest_gw}" if latest_gw else "—")
col3.metric("League leader", leader["Team"] if leader is not None else "—")
col4.metric("Leader points", fmt_int(leader["Total Points"]) if leader is not None else "—")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🏆 Standings", "⚽ Gameweek", "👑 Manager of the Month", "🏅 Hall of Fame"]
)

# -----------------------------
# Standings
# -----------------------------
with tab1:
    st.subheader("Current League Standings")
    table = standings_df[["Rank", "Team", "Manager", "Total Points"]].copy()
    table["Rank"] = table["Rank"].apply(ordinal_rank)
    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Rank": st.column_config.TextColumn("Rank", width="small"),
            "Total Points": st.column_config.NumberColumn("Points", format="%d"),
        },
    )

# -----------------------------
# Gameweek
# -----------------------------
with tab2:
    st.subheader("Gameweek Results")

    available_gws = []
    if not history_df.empty:
        available_gws = sorted(
            history_df.loc[history_df["GW Finished"], "GW"].dropna().astype(int).unique(),
            reverse=True,
        )

    if not available_gws:
        st.info("No completed Gameweek data is available yet.")
    else:
        selected_gw = st.selectbox(
            "Choose Gameweek",
            available_gws,
            index=0,
            format_func=lambda x: f"GW{x}",
        )

        gw_df = history_df[
            (history_df["GW"] == selected_gw) &
            (history_df["GW Finished"])
        ].copy()

        gw_df = gw_df.sort_values(
            ["Net Points", "Manager"], ascending=[False, True]
        ).reset_index(drop=True)
        gw_df["Rank"] = gw_df["Net Points"].rank(
            method="min", ascending=False
        ).astype(int)

        if not gw_df.empty:
            winning_score = int(gw_df["Net Points"].max())
            winners = gw_df[gw_df["Net Points"] == winning_score]

            winner_names = " & ".join(winners["Manager"].tolist())
            winner_teams = " & ".join(winners["Team"].tolist())
            st.markdown(
                f"""
                <div class="winner-card">
                    <div class="small-muted">🔥 Manager of GW{selected_gw}</div>
                    <div class="winner-name">{winner_names}</div>
                    <div>{winner_teams}</div>
                    <div class="winner-score">{winning_score} pts</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            show = gw_df[
                ["Rank", "Manager", "Team", "Net Points", "GW Points", "Transfer Hit"]
            ].copy()
            show["Rank"] = show["Rank"].apply(ordinal_rank)
            st.dataframe(
                show,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Net Points": st.column_config.NumberColumn("Score", format="%d"),
                    "GW Points": st.column_config.NumberColumn("Raw GW Points", format="%d"),
                    "Transfer Hit": st.column_config.NumberColumn("Hits", format="%d"),
                },
            )

# -----------------------------
# Manager of the Month
# -----------------------------
with tab3:
    st.subheader("Manager of the Month")

    months = []
    if not history_df.empty:
        months = sorted(
            [
                m for m in history_df.loc[
                    history_df["GW Finished"], "Month"
                ].dropna().unique()
                if m != "Unknown"
            ],
            reverse=True,
        )

    if not months:
        st.info("No completed monthly Gameweek data is available yet.")
    else:
        selected_month = st.selectbox(
            "Choose month",
            months,
            index=0,
            format_func=month_label,
        )
        month_df = monthly_table(history_df, selected_month)

        if month_df.empty:
            st.info("No completed Gameweeks fall in this month yet.")
        else:
            winning_score = int(month_df["Monthly_Points"].max())
            winners = month_df[month_df["Monthly_Points"] == winning_score]
            winner_names = " & ".join(winners["Manager"].tolist())
            winner_teams = " & ".join(winners["Team"].tolist())

            st.markdown(
                f"""
                <div class="winner-card">
                    <div class="small-muted">👑 {month_label(selected_month)} Manager of the Month</div>
                    <div class="winner-name">{winner_names}</div>
                    <div>{winner_teams}</div>
                    <div class="winner-score">{winning_score} pts</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            show = month_df[
                ["Rank", "Manager", "Team", "Monthly_Points", "GWs", "Hits"]
            ].copy()
            show["Rank"] = show["Rank"].apply(ordinal_rank)
            st.dataframe(
                show,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Monthly_Points": st.column_config.NumberColumn("Monthly Points", format="%d"),
                    "GWs": st.column_config.NumberColumn("Gameweeks", format="%d"),
                    "Hits": st.column_config.NumberColumn("Transfer Hits", format="%d"),
                },
            )

            st.caption(
                "Ties are kept as joint winners. "
                "Gameweeks are grouped by the month of the official FPL deadline."
            )

# -----------------------------
# Hall of Fame
# -----------------------------
with tab4:
    st.subheader("Manager of the Month Hall of Fame")
    motm = manager_of_month_history(history_df)

    if motm.empty:
        st.info("The Hall of Fame will fill automatically as monthly results become available.")
    else:
        counts = (
            motm.groupby(["Manager", "Team"], as_index=False)
            .size()
            .rename(columns={"size": "MOTM Awards"})
            .sort_values(["MOTM Awards", "Manager"], ascending=[False, True])
            .reset_index(drop=True)
        )
        counts.insert(0, "Rank", range(1, len(counts) + 1))
        counts["Rank"] = counts["Rank"].apply(ordinal_rank)

        st.markdown("#### 🏅 Awards Table")
        st.dataframe(
            counts,
            hide_index=True,
            use_container_width=True,
        )

        st.markdown("#### 📅 Monthly Winners")
        st.dataframe(
            motm,
            hide_index=True,
            use_container_width=True,
        )

st.divider()
st.caption(
    "CFPL Dashboard • Refreshes cached FPL data every 5 minutes. "
    "This is an independent community dashboard and is not affiliated with the Premier League."
)
