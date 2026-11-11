
import os
import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st

st.set_page_config(
    page_title="PulseIQ - Team Productivity",
    page_icon="📊",
    layout="wide"
)

st.title("PulseIQ Team Productivity Dashboard")
st.caption("Task 8 — Velocity, cycle time, delivery reliability and blocked work")

# ------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------
st.sidebar.header("Database Connection")
st.sidebar.header("Database Connection")
db_name = st.sidebar.text_input("Database", value="pulseiq_wh")
db_user = st.sidebar.text_input("Username", value="postgres")
db_host = st.sidebar.text_input("Host", value="localhost")
db_port = st.sidebar.text_input("Port", value="5432")
db_password = st.sidebar.text_input("Password", type="password")

if not db_password:
    st.info("Enter your PostgreSQL password in the sidebar to load Task 8 data.")
    st.stop()

try:
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        connect_timeout=5
    )

    teams = pd.read_sql_query(
        """
        SELECT team_id, team_name
        FROM dw.dim_team
        ORDER BY team_name
        """,
        conn
    )

    sprints = pd.read_sql_query(
        """
        SELECT sprint_id, sprint_name
        FROM dw.dim_sprint
        ORDER BY sprint_name
        """,
        conn
    )

    tasks = pd.read_sql_query(
        """
        SELECT
            task_id,
            team_id,
            sprint_id,
            story_points,
            status,
            cycle_time_days,
            completed_on_time,
            reopened_count
        FROM dw.fact_task
        """,
        conn
    )
    conn.close()

except Exception as e:
    st.error(f"Could not load PostgreSQL data: {e}")
    st.stop()

if tasks.empty:
    st.warning("No task records were found in dw.fact_task.")
    st.stop()

# ------------------------------------------------------------
# CLEAN AND JOIN DATA
# ------------------------------------------------------------
tasks["story_points"] = pd.to_numeric(tasks["story_points"], errors="coerce")
tasks["cycle_time_days"] = pd.to_numeric(tasks["cycle_time_days"], errors="coerce")
tasks["reopened_count"] = pd.to_numeric(
    tasks["reopened_count"], errors="coerce"
).fillna(0)

tasks["status"] = tasks["status"].fillna("Unknown").astype(str)
tasks["completed_on_time"] = (
    tasks["completed_on_time"].fillna("").astype(str).str.upper().str.strip()
)

tasks = tasks.merge(teams, on="team_id", how="left")
tasks = tasks.merge(sprints, on="sprint_id", how="left")
tasks["team_name"] = tasks["team_name"].fillna(tasks["team_id"].astype(str))
tasks["sprint_name"] = tasks["sprint_name"].fillna(tasks["sprint_id"].astype(str))

# ------------------------------------------------------------
# FILTERS
# ------------------------------------------------------------
st.sidebar.header("Dashboard Filters")

team_options = sorted(tasks["team_name"].dropna().unique().tolist())
sprint_options = sorted(tasks["sprint_name"].dropna().unique().tolist())

selected_teams = st.sidebar.multiselect(
    "Teams",
    options=team_options,
    default=team_options
)
selected_sprints = st.sidebar.multiselect(
    "Sprints",
    options=sprint_options,
    default=sprint_options
)

filtered = tasks[
    tasks["team_name"].isin(selected_teams)
    & tasks["sprint_name"].isin(selected_sprints)
].copy()

if filtered.empty:
    st.warning("No tasks match these filters. Select at least one team and sprint.")
    st.stop()

# ------------------------------------------------------------
# METRIC DEFINITIONS
# Done tasks are used for delivery metrics.
# Cancelled tasks are excluded from delivery metrics.
# On-time rate excludes unknown/NULL Y/N values.
# ------------------------------------------------------------
done = filtered[filtered["status"].str.casefold() == "done"].copy()
blocked = filtered[filtered["status"].str.casefold() == "blocked"]
cancelled = filtered[filtered["status"].str.casefold() == "cancelled"]

velocity = done["story_points"].fillna(0).sum()
valid_cycle = done.loc[
    done["cycle_time_days"].notna()
    & (done["cycle_time_days"] >= 0),
    "cycle_time_days"
]
avg_cycle = valid_cycle.mean()

known_delivery = done[
    done["completed_on_time"].isin(["Y", "N"])
]
on_time_rate = (
    100 * (known_delivery["completed_on_time"] == "Y").mean()
    if not known_delivery.empty else None
)

reopened = filtered[filtered["reopened_count"] > 0]
reopened_events = filtered["reopened_count"].sum()

# ------------------------------------------------------------
# KPI CARDS
# ------------------------------------------------------------
st.subheader("Productivity Overview")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Velocity (Story Points)", f"{velocity:,.0f}")
c2.metric(
    "Average Cycle Time",
    f"{avg_cycle:.1f} days" if pd.notna(avg_cycle) else "N/A"
)
c3.metric(
    "On-Time Delivery",
    f"{on_time_rate:.1f}%" if on_time_rate is not None else "N/A"
)
c4.metric("Blocked Tasks", f"{len(blocked):,}")
c5.metric("Reopened Tasks", f"{len(reopened):,}")

c6, c7, c8 = st.columns(3)
c6.metric("Completed Tasks", f"{len(done):,}")
c7.metric("Cancelled Tasks (Excluded from Delivery)", f"{len(cancelled):,}")
c8.metric("Total Reopen Events", f"{reopened_events:,.0f}")

st.caption(
    "On-time rate uses only completed tasks with Y/N delivery values. "
    "Cancelled tasks are excluded from velocity, cycle-time and on-time metrics."
)

# ------------------------------------------------------------
# TEAM COMPARISON
# ------------------------------------------------------------
st.divider()
st.subheader("Team Performance Comparison")

team_summary = filtered.assign(
    is_done=filtered["status"].str.casefold().eq("done"),
    is_blocked=filtered["status"].str.casefold().eq("blocked"),
    is_cancelled=filtered["status"].str.casefold().eq("cancelled"),
    is_reopened=filtered["reopened_count"].gt(0)
).groupby("team_name", as_index=False).agg(
    total_tasks=("task_id", "count"),
    velocity=("story_points", lambda s: s[
        filtered.loc[s.index, "status"].str.casefold().eq("done")
    ].fillna(0).sum()),
    completed_tasks=("is_done", "sum"),
    blocked_tasks=("is_blocked", "sum"),
    cancelled_tasks=("is_cancelled", "sum"),
    reopened_tasks=("is_reopened", "sum")
)

team_done = filtered[filtered["status"].str.casefold() == "done"].copy()
team_done["cycle_valid"] = (
    team_done["cycle_time_days"].notna()
    & (team_done["cycle_time_days"] >= 0)
)

cycle_by_team = team_done[team_done["cycle_valid"]].groupby(
    "team_name", as_index=False
)["cycle_time_days"].mean().rename(
    columns={"cycle_time_days": "avg_cycle_time_days"}
)

team_on_time = team_done[
    team_done["completed_on_time"].isin(["Y", "N"])
].copy()
if not team_on_time.empty:
    team_on_time["on_time"] = team_on_time["completed_on_time"].eq("Y")
    on_time_by_team = team_on_time.groupby("team_name", as_index=False).agg(
        on_time_rate=("on_time", "mean")
    )
    on_time_by_team["on_time_rate"] *= 100
else:
    on_time_by_team = pd.DataFrame(columns=["team_name", "on_time_rate"])

team_summary = team_summary.merge(cycle_by_team, on="team_name", how="left")
team_summary = team_summary.merge(on_time_by_team, on="team_name", how="left")

left, right = st.columns(2)

with left:
    fig = px.bar(
        team_summary.sort_values("velocity", ascending=False),
        x="team_name",
        y="velocity",
        title="Velocity by Team",
        labels={"team_name": "Team", "velocity": "Story Points"}
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    fig = px.bar(
        team_summary.sort_values("avg_cycle_time_days", ascending=False),
        x="team_name",
        y="avg_cycle_time_days",
        title="Average Cycle Time by Team",
        labels={
            "team_name": "Team",
            "avg_cycle_time_days": "Average Days"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)

with left:
    fig = px.bar(
        team_summary.sort_values("on_time_rate", ascending=False),
        x="team_name",
        y="on_time_rate",
        title="On-Time Delivery Rate by Team",
        labels={"team_name": "Team", "on_time_rate": "On-Time Rate (%)"}
    )
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)

with right:
    fig = px.bar(
        team_summary.sort_values("blocked_tasks", ascending=False),
        x="team_name",
        y="blocked_tasks",
        title="Blocked Tasks by Team",
        labels={"team_name": "Team", "blocked_tasks": "Blocked Tasks"}
    )
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# SPRINT COMPARISON
# ------------------------------------------------------------
st.divider()
st.subheader("Sprint-by-Sprint Delivery")

sprint_done = filtered[filtered["status"].str.casefold() == "done"].copy()
sprint_summary = sprint_done.groupby("sprint_name", as_index=False).agg(
    velocity=("story_points", "sum"),
    completed_tasks=("task_id", "count"),
    avg_cycle_time_days=("cycle_time_days", "mean")
)

sprint_delivery = sprint_done[
    sprint_done["completed_on_time"].isin(["Y", "N"])
].copy()

if not sprint_delivery.empty:
    sprint_delivery["on_time"] = sprint_delivery["completed_on_time"].eq("Y")
    sprint_rate = sprint_delivery.groupby("sprint_name", as_index=False).agg(
        on_time_rate=("on_time", "mean")
    )
    sprint_rate["on_time_rate"] *= 100
    sprint_summary = sprint_summary.merge(
        sprint_rate, on="sprint_name", how="left"
    )
else:
    sprint_summary["on_time_rate"] = pd.NA

fig = px.line(
    sprint_summary,
    x="sprint_name",
    y="velocity",
    markers=True,
    title="Velocity Trend Across Sprints",
    labels={"sprint_name": "Sprint", "velocity": "Story Points"}
)
st.plotly_chart(fig, use_container_width=True)

fig = px.bar(
    sprint_summary,
    x="sprint_name",
    y="on_time_rate",
    title="On-Time Delivery Rate by Sprint",
    labels={"sprint_name": "Sprint", "on_time_rate": "On-Time Rate (%)"}
)
fig.update_yaxes(range=[0, 100])
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# TASK STATUS AND REOPEN ANALYSIS
# ------------------------------------------------------------
st.divider()
st.subheader("Work Status and Reopened Tasks")

status_summary = filtered["status"].value_counts().rename_axis(
    "status"
).reset_index(name="task_count")

fig = px.bar(
    status_summary,
    x="status",
    y="task_count",
    title="Task Status Distribution",
    labels={"status": "Status", "task_count": "Tasks"}
)
st.plotly_chart(fig, use_container_width=True)

reopen_summary = filtered.groupby("team_name", as_index=False).agg(
    reopened_tasks=("reopened_count", lambda s: (s > 0).sum()),
    reopen_events=("reopened_count", "sum")
).sort_values("reopen_events", ascending=False)

fig = px.bar(
    reopen_summary,
    x="team_name",
    y="reopen_events",
    title="Reopen Events by Team",
    labels={"team_name": "Team", "reopen_events": "Reopen Events"}
)
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# FINDINGS
# ------------------------------------------------------------
st.divider()
st.subheader("Key Findings")

best_velocity = team_summary.sort_values("velocity", ascending=False).head(1)
if not best_velocity.empty:
    st.write(
        f"- Highest velocity: **{best_velocity.iloc[0]['team_name']}** "
        f"({best_velocity.iloc[0]['velocity']:.0f} story points)."
    )

if not cycle_by_team.empty:
    slowest = cycle_by_team.sort_values(
        "avg_cycle_time_days", ascending=False
    ).iloc[0]
    st.write(
        f"- Longest average cycle time: **{slowest['team_name']}** "
        f"({slowest['avg_cycle_time_days']:.1f} days)."
    )

if on_time_rate is not None:
    st.write(f"- Overall on-time delivery rate: **{on_time_rate:.1f}%**.")

st.write(f"- Blocked tasks in current filters: **{len(blocked):,}**.")
st.write(f"- Cancelled tasks are tracked separately: **{len(cancelled):,}**.")
st.write(
    f"- Tasks reopened at least once: **{len(reopened):,}**; "
    f"reopen events: **{reopened_events:,.0f}**."
)

# ------------------------------------------------------------
# DETAIL TABLES
# ------------------------------------------------------------
with st.expander("View Team Metrics Table"):
    st.dataframe(
        team_summary.sort_values("velocity", ascending=False),
        use_container_width=True,
        hide_index=True
    )

with st.expander("View Sprint Metrics Table"):
    st.dataframe(
        sprint_summary,
        use_container_width=True,
        hide_index=True
    )

with st.expander("View Filtered Task Data"):
    st.dataframe(filtered, use_container_width=True, hide_index=True)

st.success("Task 8 dashboard loaded.")
