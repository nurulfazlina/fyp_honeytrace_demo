import dash
from dash import dcc, html, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dash.dependencies import Input, Output, State
import datetime
import os

CSV_PATH = "attacks.zip"
CACHE = {"mtime": 0, "df": pd.DataFrame()}

app = dash.Dash(__name__)
server = app.server
app.title = "HoneyTrace | SOC Dashboard"

# Colour tokens 
BG       = "#080c14"
SURFACE  = "#0d1520"
BORDER   = "#1a2540"
ACCENT   = "#00d4ff"
RED      = "#ff3b5c"
GREEN    = "#00e5a0"
YELLOW   = "#f5c542"
PURPLE   = "#a855f7"
TEXT     = "#f8fafc"
MUTED    = "#94a3b8"

FONT = "'SF Pro Display', sans-serif"

ALL_NODES = ["rpi0", "rpi1", "rpi2"]

def card(children, style=None):
    base = {
        "backgroundColor": SURFACE,
        "border": f"1px solid {BORDER}",
        "borderRadius": "8px",
        "padding": "18px",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.35)",
    }
    if style:
        base.update(style)
    return html.Div(children, style=base)

def stat_card(label, id_, color):
    return card([
        html.Div(label, style={"fontSize": "10px", "fontWeight": "bold", "color": MUTED, "letterSpacing": "2px", "textTransform": "uppercase", "fontFamily": FONT}),
        html.Div(id=id_, children="—", style={"fontSize": "32px", "fontWeight": "700", "color": color, "fontFamily": FONT, "marginTop": "4px"}),
    ], style={"flex": "1", "minWidth": "160px", "borderTop": f"3px solid {color}"})

def dark_fig(fig, title=""):
    fig.update_layout(
        title=dict(text=title, font=dict(color=TEXT, size=12, family=FONT), x=0),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=TEXT, family=FONT, size=11),
        margin=dict(l=10, r=10, t=36, b=10),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(size=10)),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(size=10)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    )
    return fig

# Sidebar 
sidebar = html.Div(id= "sidebar",style={
    "width": "220px",
    "minWidth": "220px",
    "backgroundColor": SURFACE,
    "border": f"1px solid {BORDER}",
    "borderRadius": "8px",
    "padding": "20px 16px",
    "display": "flex",
    "flexDirection": "column",
    "gap": "20px",
    "alignSelf": "flex-start",
    "position": "sticky",
    "top": "20px",
}, children=[
    # Title
    html.Div([
        html.Div("FILTER", style={"color": ACCENT, "fontSize": "10px",
                                   "letterSpacing": "3px", "marginBottom": "12px"}),
        html.Div(style={"borderBottom": f"1px solid {BORDER}", "marginBottom": "14px"}),
    ]),
 
    # Node filter
    html.Div([
        html.Div("🖥️  NODES", style={"color": MUTED, "fontSize": "10px",
                                      "letterSpacing": "2px", "marginBottom": "10px"}),
        dcc.Checklist(
            id="node-filter",
            options=[{"label": html.Span(n, style={"color": TEXT, "fontFamily": FONT,
                                                    "fontSize": "12px", "marginLeft": "6px"}),
                      "value": n}
                     for n in ALL_NODES],
            value=ALL_NODES,   # all selected by default
            labelStyle={"display": "flex", "alignItems": "center",
                        "marginBottom": "10px", "cursor": "pointer"},
            inputStyle={"accentColor": ACCENT, "width": "14px", "height": "14px"},
        ),
    ]),
 
    # Select all / clear buttons
    html.Div([
        html.Button("Select All", id="btn-all", n_clicks=0, style={
            "backgroundColor": "transparent", "border": f"1px solid {ACCENT}",
            "color": ACCENT, "fontFamily": FONT, "fontSize": "10px",
            "padding": "5px 10px", "cursor": "pointer", "borderRadius": "4px",
            "width": "100%", "marginBottom": "6px", "letterSpacing": "1px",
        }),
        html.Button("Clear All", id="btn-clear", n_clicks=0, style={
            "backgroundColor": "transparent", "border": f"1px solid {RED}",
            "color": RED, "fontFamily": FONT, "fontSize": "10px",
            "padding": "5px 10px", "cursor": "pointer", "borderRadius": "4px",
            "width": "100%", "letterSpacing": "1px",
        }),
    ]),
 
    html.Div(style={"borderBottom": f"1px solid {BORDER}"}),
 
    # Active filter indicator
    html.Div([
        html.Div("ACTIVE FILTER", style={"color": MUTED, "fontSize": "9px",
                                          "letterSpacing": "2px", "marginBottom": "6px"}),
        html.Div(id="active-filter-label", style={"color": GREEN, "fontSize": "11px",
                                                    "fontFamily": FONT}),
    ]),
])

# ── Layout ───────────────────────────────────────────────────────
app.layout = html.Div(style={
    "backgroundColor": BG,
    "minHeight": "100vh",
    "fontFamily": FONT,
    "color": TEXT,
    "padding": "20px 28px",
}, children=[
 
    # Real-time clock
    dcc.Interval(
        id="clock-tick",
        interval=1000,
        n_intervals=0
    ),

    # Dashboard refresh
    dcc.Interval(
        id="data-tick",
        interval=60_000,
        n_intervals=0,
        disabled=True
    ),

    # Dummy div for resize callback
    html.Div(id="dummy-resize", style={"display": "none"}),
 
    # ── Header ──
    html.Div(style={
        "display": "flex", "alignItems": "center", "justifyContent": "space-between",
        "borderBottom": f"1px solid {BORDER}", "paddingBottom": "14px", "marginBottom": "22px",
    }, children=[
        
        # --- LEFT SIDE: Hamburger Button + Title ---
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "15px"}, children=[
            # The Toggle Button
            html.Button("☰", id="sidebar-toggle", n_clicks=0, style={
                "backgroundColor": "transparent", "color": ACCENT, 
                "border": "none", "fontSize": "24px", "cursor": "pointer",
                "padding": "0", "marginTop": "-5px"
            }),
            
            # The Title
            html.Div([
                html.Span("🍯 ", style={"fontSize": "28px"}),
                html.Span("HONEYTRACE", style={"color": "#ffe082", "fontSize": "26px",
                                          "fontWeight": "900", "letterSpacing": "3px", "textShadow": f"0 0 6px #EBA937, 0 0 12px #EBA937"}),
                html.Div("REAL-TIME HONEYPOT INTRUSION ANALYTICS", style={"color": MUTED, "fontSize": "9px",
                                                                  "letterSpacing": "4px", "marginTop": "2px"}),
            ]),
        ]),
 
        # --- RIGHT SIDE: Clock + System Online ---
        html.Div([
            html.Div(id="clock", style={"color": ACCENT, "fontSize": "13px", "textAlign": "right"}),
            html.Div("SYSTEM DEMO", style={"color": GREEN, "fontSize": "9px",
                                             "letterSpacing": "3px", "textAlign": "right", "marginTop": "3px"}),
            html.Div(id="refresh-countdown", style={"color": MUTED, "fontSize": "9px",
                                             "letterSpacing": "2px", "textAlign": "right", "marginTop": "3px"}),
        ]),
    ]),
 
    # ── Main body: sidebar + content ──
    html.Div(style={"display": "flex", "gap": "18px", "alignItems": "flex-start"}, children=[
 
        sidebar,
 
        # ── Right-side content ──
        html.Div(style={"flex": "1", "minWidth": "0", "width": "100%", "overflowX": "hidden", "transition": "all 0.3s ease-in-out"}, children=[

            dcc.Loading(
                id="loading-spinner",
                type="circle",       
                color=ACCENT,
                fullscreen=True, 
                style={"backgroundColor": "rgba(8, 12, 20, 0.6)"},

                children=[
 
                    # Stat Cards
                    html.Div(style={"display": "flex", "gap": "14px", "marginBottom": "20px", "flexWrap": "wrap"}, children=[
                        stat_card("Total Attack Attempts",  "s-total",    RED),
                        stat_card("Unique Attacker IPs",    "s-ips",      YELLOW),
                        stat_card("Intrusion Sessions",      "s-sessions", PURPLE),
                        stat_card("Commands Run", "s-cmds",     ACCENT),
                        stat_card("Nodes Displayed", "s-nodes",    GREEN),
                    ]),
 
                    # Row 1: Country chart + Timeline
                    html.Div(style={"display": "flex", "gap": "14px", "marginBottom": "14px"}, children=[
                        card([dcc.Graph(id="top-countries", style={"height": "320px"})],
                            style={"flex": "1.4", "padding": "10px"}),
                        card([dcc.Graph(id="timeline",      style={"height": "320px"})],
                            style={"flex": "1",   "padding": "10px"}),
                    ]),
 
                    # Row 2: Top IPs + Usernames + Passwords
                    html.Div(style={"display": "flex", "gap": "14px", "marginBottom": "14px"}, children=[
                        card([dcc.Graph(id="top-ips",   style={"height": "260px"})], style={"flex": "1", "padding": "10px"}),
                        card([dcc.Graph(id="top-users", style={"height": "260px"})], style={"flex": "1", "padding": "10px"}),
                        card([dcc.Graph(id="top-pass",  style={"height": "260px"})], style={"flex": "1", "padding": "10px"}),
                    ]),
 
                    # Row 3: Node Donut + Commands + Live Feed
                    html.Div(style={"display": "flex", "gap": "14px", "marginBottom": "14px"}, children=[
                        card([dcc.Graph(id="nodes-donut", style={"height": "280px"})], style={"flex": "0.7", "padding": "10px"}),
                        card([dcc.Graph(id="top-cmds",    style={"height": "280px"})], style={"flex": "1",   "padding": "10px"}),
                        card([
                            html.Div("⚡ LIVE EVENT FEED", style={"color": ACCENT, "fontSize": "10px",
                                                               "letterSpacing": "3px", "marginBottom": "10px"}),
                            html.Div(id="live-feed", style={"overflowY": "auto", "height": "230px"}),
                        ],  style={"flex": "1.1", "padding": "14px"}),
                    ]),
 
                    # Footer
                    html.Div(style={
                        "borderTop": f"1px solid {BORDER}", "paddingTop": "10px", "marginTop": "6px",
                        "display": "flex", "justifyContent": "space-between",
                    }, children=[
                        html.Div("HoneyTrace v1.0 — Raspberry Pi Cluster Honeypot",
                             style={"color": MUTED, "fontSize": "10px"}),
                        html.Div(id="last-updated", style={"color": MUTED, "fontSize": "10px"}),
                    ]),
                    
                ] # 1. Closes dcc.Loading 'children' list
            ) # 2. Closes dcc.Loading component itself
            
        ]), # 3. Closes 'Right-side content' Div
    ]), # 4. Closes 'Main body' Div
]) # 5. Closes app.layout Div
 

@app.callback(
    [Output("clock", "children"),
     Output("refresh-countdown", "children")],
    Input("clock-tick", "n_intervals")
)
def update_clock(n):
    #return datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    n = n or 0
    now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    remaining =  60 - (n % 60)
    countdown_text = f"NEXT REFRESH IN: {remaining}s"

    return now, countdown_text

# ── Sidebar Toggle Callback ─────────────────────────────
@app.callback(
    Output("sidebar", "style"),
    Input("sidebar-toggle", "n_clicks"),
    State("sidebar", "style"),
    prevent_initial_call=True
)
def toggle_sidebar(n_clicks, current_style):
    if current_style is None:
        current_style = {}

    if n_clicks % 2 == 1:
        # Hide the sidebar
        current_style["width"] = "0px"
        current_style["minWidth"] = "0px"
        current_style["padding"] = "0px"
        current_style["border"] = "none"
        current_style["overflow"] = "hidden"
    else:
        # Show the sidebar
        current_style["width"] = "220px"
        current_style["minWidth"] = "220px"
        current_style["padding"] = "20px 16px"
        current_style["border"] = f"1px solid {BORDER}"
        current_style["overflow"] = "visible"
        current_style["display"] = "flex"

    current_style["transition"] = "all 0.3s ease-in-out"

    return current_style

# ── Force Graphs to Resize on Sidebar Toggle ──
app.clientside_callback(
    """
    function(n_clicks) {
        // Wait 400ms to guarantee the 0.3s CSS slide animation is completely finished
        setTimeout(function() {
            window.dispatchEvent(new Event('resize'));
        }, 400);
        return window.dash_clientside.no_update;
    }
    """,
    Output("dummy-resize", "children"), # Targets the invisible div safely
    Input("sidebar-toggle", "n_clicks"),
    prevent_initial_call=True
)

# ── Select All / Clear All callback ─────────────────────────────
@app.callback(
    Output("node-filter", "value"),
    [Input("btn-all",   "n_clicks"),
     Input("btn-clear", "n_clicks")],
    prevent_initial_call=True,
)
def toggle_nodes(btn_all, btn_clear):
    ctx = dash.callback_context
    if not ctx.triggered:
        return ALL_NODES
    triggered = ctx.triggered[0]["prop_id"]
    return ALL_NODES if "btn-all" in triggered else []
 
# ── Helpers ──────────────────────────────────────────────────────
def load_data():
    try:
        #df = pd.read_csv(CSV_PATH) (old code)
        

        # Force timestamp conversion safely
        #df["timestamp"] = pd.to_datetime(
            #df["timestamp"],
            #errors="coerce"
        #)

        # Remove invalid timestamps
        #df = df.dropna(subset=["timestamp"])

        #return df
        #except Exception as e:
        #print(f"Error loading CSV: {e}")
        #return pd.DataFrame()

        # Check exactly when the CSV was last updated
        current_mtime = os.path.getmtime(CSV_PATH)

        # If the file hasn't changed, use the instant memory cache!
        if current_mtime == CACHE["mtime"] and not CACHE["df"].empty:
            return CACHE["df"].copy()

        # If the file is new, read the disk
        df = pd.read_csv(CSV_PATH)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])

        # Save the new data to the cache
        CACHE["mtime"] = current_mtime
        CACHE["df"] = df

        return df.copy()
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return pd.DataFrame()
        
 
def feed_row(ts, event_id, src_ip, extra=""):
    color_map = {
        "cowrie.login.failed":    RED,
        "cowrie.login.success":   GREEN,
        "cowrie.command.input":   YELLOW,
        "cowrie.session.connect": ACCENT,
    }
    dot_color   = color_map.get(event_id, MUTED)
    short_event = event_id.replace("cowrie.", "") if event_id else "event"
    label       = str(ts)[:16] if ts else "—"
    return html.Div(style={
        "display": "flex", "alignItems": "flex-start", "gap": "8px",
        "padding": "5px 0", "borderBottom": f"1px solid {BORDER}",
    }, children=[
        html.Div("●", style={"color": dot_color, "fontSize": "8px",
                             "marginTop": "4px", "flexShrink": "0"}),
        html.Div([
            html.Span(label,         style={"color": MUTED,     "fontSize": "10px", "marginRight": "8px"}),
            html.Span(src_ip or "—", style={"color": ACCENT,    "fontSize": "10px", "marginRight": "8px"}),
            html.Span(short_event,   style={"color": dot_color, "fontSize": "10px"}),
            html.Div(str(extra)[:60] if extra else "",
                     style={"color": TEXT, "fontSize": "9px", "marginTop": "1px", "opacity": "0.7"}),
        ]),
    ])
 
def empty_fig(title):
    fig = go.Figure()
    fig.add_annotation(text="No data", showarrow=False,
                       font=dict(color=MUTED, size=12))
    return dark_fig(fig, title)
 
# ── Main callback ─────────────────────────────────────────────────
@app.callback(
    [Output("s-total",            "children"),
     Output("s-ips",              "children"),
     Output("s-sessions",         "children"),
     Output("s-cmds",             "children"),
     Output("s-nodes",            "children"),
     Output("top-countries",      "figure"),
     Output("timeline",           "figure"),
     Output("top-ips",            "figure"),
     Output("top-users",          "figure"),
     Output("top-pass",           "figure"),
     Output("top-cmds",           "figure"),
     Output("nodes-donut",        "figure"),
     Output("live-feed",          "children"),
     Output("last-updated",       "children"),
     Output("active-filter-label","children"),
    ],
    [Input("data-tick",        "n_intervals"),
     Input("node-filter", "value")],
     [State("node-filter", "value")],
)
def refresh(_, selected_nodes, state_nodes):
    selected_nodes = selected_nodes if selected_nodes is not None else state_nodes
    now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
 
    # Active filter label shown in sidebar
    if not selected_nodes:
        filter_label = "⚠ None selected"
    elif len(selected_nodes) == len(ALL_NODES):
        filter_label = "All nodes"
    else:
        filter_label = " + ".join(sorted(selected_nodes))
 
    df = load_data()
 
    if df.empty or not selected_nodes:
        return (
            "0", "0", "0", "0", "0",
            empty_fig("TOP ATTACKER COUNTRIES"),
            empty_fig("EVENTS OVER TIME"),
            empty_fig("TOP SOURCE IPs"),
            empty_fig("TOP USERNAMES TRIED"),
            empty_fig("TOP PASSWORDS TRIED"),
            empty_fig("TOP COMMANDS EXECUTED"),
            empty_fig("NODE DISTRIBUTION"),
            [html.Div("Waiting for data…", style={"color": MUTED, "fontSize": "11px"})],
            f"Last updated: {now}",
            filter_label,
        )
 
    # Apply node filter
    df = df[df["node"].isin(selected_nodes)]
 
    if df.empty:
        return (
            "0", "0", "0", "0", "0",
            empty_fig("TOP ATTACKER COUNTRIES"),
            empty_fig("EVENTS OVER TIME"),
            empty_fig("TOP SOURCE IPs"),
            empty_fig("TOP USERNAMES TRIED"),
            empty_fig("TOP PASSWORDS TRIED"),
            empty_fig("TOP COMMANDS EXECUTED"),
            empty_fig("NODE DISTRIBUTION"),
            [html.Div("No data for selected nodes.", style={"color": MUTED, "fontSize": "11px"})],
            f"Last updated: {now}",
            filter_label,
        )
 
    # ── Stats ──
    total    = f"{len(df):,}"
    uniq_ips = f"{df['src_ip'].nunique():,}"
    sessions = f"{df['session'].nunique():,}"
    cmds     = f"{int(df['input'].notna().sum()):,}"
    nodes    = f"{df['node'].nunique()}"
 
    # ── Top Countries (replaces map) ──
    if "country" in df.columns:
        country_counts = (
            df[~df["country"].isin(["Unknown", "Local/Internal", ""])]
            .groupby("country")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=True)
            .tail(15)
        )
        fig_countries = px.bar(
            country_counts, x="count", y="country", orientation="h",
            color="count",
            color_continuous_scale=[[0, "#1a2540"], [0.5, ACCENT], [1.0, RED]],
        )
        fig_countries.update_traces(marker_line_width=0)
        fig_countries.update_coloraxes(showscale=False)
        dark_fig(fig_countries, "TOP ATTACKER COUNTRIES")
    else:
        fig_countries = empty_fig("TOP ATTACKER COUNTRIES — run parser.py first")
 
    # ── Timeline ──
    df_t  = df.copy()
    df_t["hour"] = df_t["timestamp"].dt.floor("h")
    tc    = df_t.groupby("hour").size().reset_index(name="count")
    fig_time = go.Figure(go.Scatter(
        x=tc["hour"], y=tc["count"],
        mode="lines+markers",
        line=dict(color=ACCENT, width=2),
        marker=dict(color=ACCENT, size=5),
        fill="tozeroy",
        fillcolor="rgba(0,212,255,0.07)",
    ))
    dark_fig(fig_time, "EVENTS OVER TIME")
 
    # ── Top IPs ──
    top_ips = df["src_ip"].value_counts().head(10).reset_index()
    top_ips.columns = ["src_ip", "count"]
    fig_ips = px.bar(top_ips, x="count", y="src_ip", orientation="h",
                     color_discrete_sequence=[ACCENT])
    dark_fig(fig_ips, "TOP SOURCE IPs")
    fig_ips.update_traces(marker_line_width=0)
 
    # ── Top Usernames ──
    logins = df[df["event_id"] == "cowrie.login.failed"]
    top_u  = logins["username"].value_counts().head(10).reset_index()
    top_u.columns = ["username", "count"]
    fig_users = px.bar(top_u, x="count", y="username", orientation="h",
                       color_discrete_sequence=[PURPLE])
    dark_fig(fig_users, "TOP USERNAMES TRIED")
    fig_users.update_traces(marker_line_width=0)
 
    # ── Top Passwords ──
    top_p = logins["password"].value_counts().head(10).reset_index()
    top_p.columns = ["password", "count"]
    fig_pass = px.bar(top_p, x="count", y="password", orientation="h",
                      color_discrete_sequence=[YELLOW])
    dark_fig(fig_pass, "TOP PASSWORDS TRIED")
    fig_pass.update_traces(marker_line_width=0)

 
    # ── Top Commands ──
    cmds_df = df[df["input"].notna() & (df["input"] != "")]
    top_c   = cmds_df["input"].value_counts().head(10).reset_index()
    top_c.columns = ["command", "count"]
    fig_cmds = px.bar(top_c, x="count", y="command", orientation="h",
                      color_discrete_sequence=[GREEN])
    dark_fig(fig_cmds, "TOP COMMANDS EXECUTED")
    fig_cmds.update_traces(marker_line_width=0)
 
    # ── Node Donut ──
    nc = df.groupby("node").size().reset_index(name="count")
    fig_donut = px.pie(nc, names="node", values="count",
                       hole=0.55,
                       color_discrete_sequence=[RED, ACCENT, GREEN])
    fig_donut.update_traces(textfont_size=10, marker=dict(line=dict(color=BG, width=2)))
    dark_fig(fig_donut, "NODE DISTRIBUTION")
 
    # ── Live Feed ──
    recent    = df.sort_values("timestamp", ascending=False).head(30)
    feed_rows = [
        feed_row(row["timestamp"], row["event_id"], row["src_ip"],
                 row["input"] if pd.notna(row.get("input")) else row.get("username", ""))
        for _, row in recent.iterrows()
    ]
 
    return (
        total, uniq_ips, sessions, cmds, nodes,
        fig_countries, fig_time,
        fig_ips, fig_users, fig_pass, fig_cmds, fig_donut,
        feed_rows,
        f"Last updated: {now}",
        filter_label,
    )
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)