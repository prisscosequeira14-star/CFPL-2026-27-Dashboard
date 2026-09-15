import calendar
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

# ============================================================
# CFPL 2026/27 CONFIGURATION
# ============================================================

LEAGUE_ID = 402686
LEAGUE_NAME = "CHINCHINIM FPL 26/27 by ABSgym"
FPL_API = "https://fantasy.premierleague.com/api"
TIMEOUT = 30

st.set_page_config(
    page_title="CFPL 2026/27",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# DESIGN / HEADER FIX
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 3rem;
            max-width: 1450px;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .cfpl-header {
            width: 100%;
            padding: 22px 25px;
            border-radius: 16px;
            background: linear-gradient(135deg, #111827, #1f2937);
            color: white;
            margin-bottom: 22px;
            box-sizing: border-box;
        }

        .cfpl-title {
            font-size: 34px;
            font-weight: 800;
            line-height: 1.2;
            margin: 0;
        }

        .cfpl-subtitle {
            font-size: 16px;
            margin-top: 8px;
            opacity: 0.88;
        }

        .winner-card {
            padding: 24px;
            border-radius: 16px;
            border: 1px solid #e5e7eb;
            background: #fafafa;
            margin: 12px 0 20px 0;
        }

        .winner-label {
            font-size: 14px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .winner-name {
            font-size: 30px;
            font-weight: 800;
            margin-top: 6px;
        }

        .winner-team {
            font-size: 18px;
            margin-top: 4px;
        }

        @media (max-width: 700px) {
            .block-container {
                padding-top: 1rem !important;
                padding-left: 0.8rem !important;
                padding-right: 0.8rem !important;
            }

            .cfpl-header {
                padding: 18px;
            }

            .cfpl-title {
                font-size: 25px;
            }

            .cfpl-subtitle {
                font-size: 14px;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="cfpl-header">
        <div class="cfpl-title">{LEAGUE_NAME}</div>
        <div class="cfpl-subtitle">
            Automatic league standings &bull; Gameweek scores &bull;
            Manager of the Month &bull; Hall of Fame
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# API FUNCTIONS
# ============================================================

def get_json(url):
    response = requests.get(
        url,
        timeout=TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0 CFPL-Dashboard"},
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=300, show_spinner=False)
def get_bootstrap():
    return get_json(f"{FPL_API}/bootstrap-static/")


@st.cache_data(ttl=300, show_spinner=False)
def get_all_league_entries():
    all_results = []
    page = 1
    league_info = {}

    while True:
        data = get_json(
            f"{FPL_API}/leagues-classic/{LEAGUE_ID}/standings/?page_standings={page}"
        )

        if page == 1:
            league_info = data.get("league", {})

        standings = data.get("standings", {})
        all_results.extend(standings.get("results", []))

        if not standings.get("has_next", False):
            break

        page += 1

    return league_info, all_results


@st.cache_data(ttl=300, show_spinner=False)
def get_manager_history(entry_id):
    return get_json(f"{FPL_API}/entry/{entry_id}/history/")


def latest_finished_gameweek(events):
    finished = [
        event["id"]
        for event in events
        if event.get("finished") is True
    ]

    return max(finished) if finished else 0


def event_month(event):
    deadline = event.get("deadline_time")

    if not deadline:
        return None, None

    dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    return dt.year, dt.month


def gameweek_name(gw):
    return f"GW{gw}"


# ============================================================
# LOAD DATA
# ============================================================

try:
    bootstrap = get_bootstrap()
    events = bootstrap.get("events", [])

    league_info, entries = get_all_league_entries()

except Exception as error:
    st.error(
        "The FPL website could not be reached at the moment. "
        "Please try Refresh again shortly."
    )
    st.exception(error)
    st.stop()


latest_gw = latest_finished_gameweek(events)

if latest_gw == 0:
    st.warning("No completed FPL gameweek has been detected yet.")


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("CFPL Controls")
    st.write(f"League ID: {LEAGUE_ID}")

    deduct_hits = st.toggle(
        "Deduct transfer hits",
        value=True,
        help=(
            "When ON, paid transfer points are deducted from each "
            "manager's Gameweek and Manager-of-the-Month score."
        ),
    )

    if st.button("Refresh FPL data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption("Data source: Fantasy Premier League public endpoints.")
    st.caption("Data is cached for 5 minutes to avoid excessive API requests.")


# ============================================================
# CURRENT STANDINGS
# ============================================================

standings_rows = []

for item in entries:
    standings_rows.append(
        {
            "Rank": item.get("rank"),
            "Team": item.get("entry_name", ""),
            "Manager": item.get("player_name", ""),
            "Points": item.get("total", 0),
            "Entry ID": item.get("entry"),
        }
    )

standings_df = pd.DataFrame(standings_rows)

if not standings_df.empty:
    standings_df["Points"] = pd.to_numeric(
        standings_df["Points"], errors="coerce"
    ).fillna(0).astype(int)

    standings_df = standings_df.sort_values(
        ["Points", "Rank"],
        ascending=[False, True],
    ).reset_index(drop=True)

    standings_df["Rank"] = range(1, len(standings_df) + 1)


# ============================================================
# TOP SUMMARY
# ============================================================

if not standings_df.empty:
    leader = standings_df.iloc[0]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Managers", len(standings_df))
    c2.metric(
        "Latest finished GW",
        gameweek_name(latest_gw) if latest_gw else "-",
    )
    c3.metric("League leader", leader["Team"])
    c4.metric("Leader points", int(leader["Points"]))


# ============================================================
# BUILD MANAGER GAMEWEEK HISTORY
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def build_histories(entry_ids):
    output = {}

    for entry_id in entry_ids:
        try:
            history = get_manager_history(int(entry_id))
            output[int(entry_id)] = history.get("current", [])
        except Exception:
            output[int(entry_id)] = []

    return output


entry_ids = (
    standings_df["Entry ID"].dropna().astype(int).tolist()
    if not standings_df.empty
    else []
)

with st.spinner("Loading CFPL manager scores..."):
    histories = build_histories(entry_ids)


# ============================================================
# SCORE HELPERS
# ============================================================

manager_lookup = {}

for _, row in standings_df.iterrows():
    manager_lookup[int(row["Entry ID"])] = {
        "Team": row["Team"],
        "Manager": row["Manager"],
    }


def manager_gw_score(history_row, deduct_transfer_hits=True):
    points = int(history_row.get("points", 0) or 0)
    hit = int(history_row.get("event_transfers_cost", 0) or 0)

    if deduct_transfer_hits:
        return points - hit

    return points


def gameweek_table(gw_number):
    rows = []

    for entry_id, history in histories.items():
        gw_row = next(
            (
                h for h in history
                if int(h.get("event", 0)) == int(gw_number)
            ),
            None,
        )

        if gw_row is None:
            continue

        info = manager_lookup.get(entry_id, {})

        rows.append(
            {
                "Team": info.get("Team", ""),
                "Manager": info.get("Manager", ""),
                "GW Points": manager_gw_score(
                    gw_row,
                    deduct_transfer_hits=deduct_hits,
                ),
                "Raw Points": int(gw_row.get("points", 0) or 0),
                "Transfer Hit": int(
                    gw_row.get("event_transfers_cost", 0) or 0
                ),
            }
        )

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(
            ["GW Points", "Raw Points"],
            ascending=[False, False],
        ).reset_index(drop=True)

        df.insert(0, "Rank", range(1, len(df) + 1))

    return df


# ============================================================
# MONTH FUNCTIONS
# ============================================================

finished_events = [
    event
    for event in events
    if event.get("finished") is True
]


def available_months():
    months = {}

    for event in finished_events:
        year, month = event_month(event)

        if year and month:
            key = (year, month)

            if key not in months:
                months[key] = []

            months[key].append(event["id"])

    return months


month_map = available_months()


def month_label(key):
    year, month = key
    return f"{calendar.month_name[month]} {year}"


def monthly_table(month_key):
    gw_numbers = month_map.get(month_key, [])
    rows = []

    for entry_id, history in histories.items():
        total = 0
        played = 0

        for gw in gw_numbers:
            gw_row = next(
                (
                    h for h in history
                    if int(h.get("event", 0)) == int(gw)
                ),
                None,
            )

            if gw_row is not None:
                total += manager_gw_score(
                    gw_row,
                    deduct_transfer_hits=deduct_hits,
                )
                played += 1

        if played > 0:
            info = manager_lookup.get(entry_id, {})

            rows.append(
                {
                    "Team": info.get("Team", ""),
                    "Manager": info.get("Manager", ""),
                    "Month Points": total,
                    "Gameweeks": played,
                }
            )

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(
            ["Month Points", "Team"],
            ascending=[False, True],
        ).reset_index(drop=True)

        df.insert(0, "Rank", range(1, len(df) + 1))

    return df


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Standings",
        "Gameweek",
        "Manager of the Month",
        "Hall of Fame",
    ]
)


# ============================================================
# TAB 1 - STANDINGS
# ============================================================

with tab1:
    st.subheader("Current League Standings")

    display_standings = standings_df[
        ["Rank", "Team", "Manager", "Points"]
    ].copy()

    st.dataframe(
        display_standings,
        hide_index=True,
        use_container_width=True,
        height=650,
    )


# ============================================================
# TAB 2 - GAMEWEEK
# ============================================================

with tab2:
    st.subheader("Gameweek Results")

    completed_gws = sorted(
        [event["id"] for event in finished_events],
        reverse=True,
    )

    if completed_gws:
        selected_gw = st.selectbox(
            "Select completed Gameweek",
            completed_gws,
            index=0,
            format_func=lambda x: gameweek_name(x),
        )

        gw_df = gameweek_table(selected_gw)

        st.markdown(f"### {gameweek_name(selected_gw)} Ranking")

        if gw_df.empty:
            st.info(
                "No manager history is available for this Gameweek yet. "
                "Try Refresh FPL data shortly."
            )
        else:
            show_columns = [
                "Rank",
                "Team",
                "Manager",
                "GW Points",
            ]

            if deduct_hits:
                show_columns.append("Transfer Hit")

            st.dataframe(
                gw_df[show_columns],
                hide_index=True,
                use_container_width=True,
                height=650,
            )

            winner = gw_df.iloc[0]

            st.success(
                f"{gameweek_name(selected_gw)} leader: "
                f"{winner['Manager']} - {winner['Team']} "
                f"with {int(winner['GW Points'])} points."
            )

    else:
        st.info("There are no completed Gameweeks yet.")


# ============================================================
# TAB 3 - MANAGER OF THE MONTH
# ============================================================

with tab3:
    st.subheader("Manager of the Month")

    sorted_months = sorted(month_map.keys(), reverse=True)

    if sorted_months:
        selected_month = st.selectbox(
            "Select month",
            sorted_months,
            index=0,
            format_func=month_label,
            key="motm_month",
        )

        motm_df = monthly_table(selected_month)

        month_gws = month_map[selected_month]

        st.caption(
            "Gameweeks counted: "
            + ", ".join(gameweek_name(gw) for gw in month_gws)
        )

        if not motm_df.empty:
            winner = motm_df.iloc[0]

            st.markdown(
                f"""
                <div class="winner-card">
                    <div class="winner-label">
                        Manager of the Month - {month_label(selected_month)}
                    </div>
                    <div class="winner-name">
                        {winner["Manager"]}
                    </div>
                    <div class="winner-team">
                        {winner["Team"]} &mdash;
                        {int(winner["Month Points"])} points
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.dataframe(
                motm_df[
                    [
                        "Rank",
                        "Team",
                        "Manager",
                        "Month Points",
                        "Gameweeks",
                    ]
                ],
                hide_index=True,
                use_container_width=True,
                height=650,
            )

        else:
            st.info("No monthly results are available.")

    else:
        st.info("No completed monthly results are available yet.")


# ============================================================
# TAB 4 - HALL OF FAME
# ============================================================

with tab4:
    st.subheader("Manager of the Month Hall of Fame")

    hall_rows = []

    for month_key in sorted(month_map.keys()):
        df = monthly_table(month_key)

        if not df.empty:
            winner = df.iloc[0]

            hall_rows.append(
                {
                    "Month": month_label(month_key),
                    "Manager": winner["Manager"],
                    "Team": winner["Team"],
                    "Points": int(winner["Month Points"]),
                    "Gameweeks": ", ".join(
                        gameweek_name(gw)
                        for gw in month_map[month_key]
                    ),
                }
            )

    if hall_rows:
        hall_df = pd.DataFrame(hall_rows)

        st.dataframe(
            hall_df,
            hide_index=True,
            use_container_width=True,
        )

    else:
        st.info("The Hall of Fame will appear after completed Gameweeks.")


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"{LEAGUE_NAME} | League ID {LEAGUE_ID} | "
    "Unofficial community dashboard using Fantasy Premier League data."
)