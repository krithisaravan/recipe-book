"""
shared.py — common page setup: theme CSS + top navigation bar.
"""
import streamlit as st

PALETTE = {
    "bg":            "#F5EDE0",   # warm parchment
    "bg_secondary":  "#EDE0CE",   # deeper parchment
    "border":        "#D4B896",   # warm tan border
    "pink":          "#EEC9C0",   # muted terracotta-pink inputs
    "pink_border":   "#D4A090",   # terracotta border
    "pink_accent":   "#A0522D",   # sienna — links, active states
    "terracotta":    "#C1603A",   # terracotta accent
    "brown":         "#5C3D2E",   # dark brown — text on light
    "text":          "#2C1A0E",   # deep espresso text
    "text_muted":    "#7A5C44",   # warm muted brown
    "black":         "#2C1A0E",   # buttons
    "white":         "#FFFDF8",   # warm white
    "unknown_bg":    "#F3D9B1",   # cost-unknown flag background
}

# Task-first ordering: what she'd say she wants to do, not which database
# table it edits. Saved Products earns a real tab since Quote a Cake already
# links to it — a page worth linking to is worth navigating to directly.
PAGES = [
    ("app.py",                              "Home"),
    ("pages/2_Recipes.py",                  "Add a Recipe"),
    ("pages/3_Quote_a_Cake.py",             "Quote a Cake"),
    ("pages/1_Ingredients_&_Packaging.py",  "Manage Costs"),
    ("pages/4_Products_&_Pricing.py",       "Saved Products"),
]

FONT_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Sorts+Mill+Goudy:ital@0;1&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;1,9..144,300;1,9..144,400&family=DM+Sans:wght@400;500&display=swap');"


def _base_css() -> str:
    p = PALETTE
    return f"""
    {FONT_IMPORT}

    html, body, [class*="css"] {{
        font-family: 'Fraunces', Georgia, serif;
        font-weight: 300;
        font-variation-settings: 'opsz' 9;
    }}

    .stApp {{ background: {p['bg']} !important; }}

    /* Pull content up so the nav sits at the very top of the viewport */
    .block-container {{
        padding-top: 3rem !important;
    }}

    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}

    /* ── Global text ── */
    h1, h2, h3, h4, h5, h6 {{
        font-family: 'Sorts Mill Goudy', Georgia, serif !important;
        font-weight: 400 !important;
        color: {p['text']} !important;
    }}
    h1 {{
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    p, span, div, label, li,
    .stMarkdown, .stMarkdown p, .stMarkdown li,
    [data-testid="stCaptionContainer"],
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stText"] {{
        color: {p['text']} !important;
        font-family: 'Fraunces', Georgia, serif !important;
        font-weight: 300 !important;
    }}
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    .stCaption, small {{
        color: {p['text_muted']} !important;
        font-size: 0.82rem !important;
    }}

    /* ── Nav bar — one continuous strip, stuck to the top of the viewport ── */
    /* Raw HTML/anchor tags rather than st.page_link: styling tabs this
       specific needs more control over the DOM than Streamlit's own
       page-link component exposes, and earlier attempts at reaching it via
       generic attribute selectors kept catching unrelated page_link usages
       elsewhere on the page (the Dashboard's task cards, for one). Clicking
       a nav link here does a full page reload rather than Streamlit's
       instant swap — the same trade already made for the Dashboard cards
       and the standalone "Saved products" link.

       Shaped like real folder tabs: rounded top corners, sitting on a
       shared baseline (align-items: flex-end), with the active one taller
       via extra top padding so it visibly pokes up above its neighbors —
       rather than everyone lining up flush with the very top of the
       viewport, which needed guessing at exactly how much of Streamlit's
       own top toolbar to fight past and twice ended up hiding the bar
       behind it instead. */
    .main-nav {{
        position: sticky;
        top: 0;
        z-index: 999;
        display: flex;
        align-items: flex-end;
        gap: 0.5rem;
        margin: 0 0 1.5rem 0;
        background: transparent;
    }}
    .main-nav-tab {{
        flex: 1;
        text-align: center;
        padding: 0.85rem 0.5rem;
        text-decoration: none !important;
        color: {p['text']} !important;
        font-family: 'Fraunces', serif;
        font-size: 0.92rem;
        font-weight: 300;
        background: {p['pink']};
        border: 1px solid {p['pink_border']};
        border-radius: 12px 12px 0 0;
        transition: background 0.15s ease, padding 0.15s ease;
    }}
    .main-nav-tab:hover {{ background: {p['pink_border']}; }}
    .main-nav-tab.active {{
        background: {p['black']} !important;
        color: {p['white']} !important;
        padding-top: calc(0.85rem + 9px);
        position: relative;
        z-index: 2;
        box-shadow: 0 -2px 8px rgba(44, 26, 14, 0.18);
    }}
    .main-nav-tab.active:hover {{ background: {p['black']} !important; }}

    /* ── Footer (export button lives here, not the nav) ── */
    .footer-note {{
        text-align: center;
        color: {p['text_muted']};
        font-size: 0.78rem;
        margin-top: 0.5rem;
        margin-bottom: 0.6rem;
    }}

    /* ── Inputs ── */
    input, textarea,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
        background-color: {p['white']} !important;
        color: {p['text']} !important;
        border-color: {p['border']} !important;
        font-family: 'Fraunces', serif !important;
        font-weight: 300 !important;
    }}
    [data-testid="stNumberInput"] > div {{
        background-color: {p['white']} !important;
        border-color: {p['border']} !important;
    }}
    [data-baseweb="select"] span, [data-baseweb="select"] div {{
        color: {p['text']} !important;
        background-color: {p['white']} !important;
        font-family: 'Fraunces', serif !important;
    }}
    [data-testid="stRadio"] label, [data-testid="stRadio"] span {{
        color: {p['text']} !important;
    }}
    input::placeholder, textarea::placeholder {{
        color: {p['text_muted']} !important;
    }}
    [data-testid="stNumberInput"] button {{
        background: {p['bg_secondary']} !important;
        color: {p['text']} !important;
        border-color: {p['border']} !important;
    }}

    /* ── Buttons ── */
    button[kind="primary"],
    [data-testid="stBaseButton-primary"],
    div[data-testid="stForm"] button[kind="primaryFormSubmit"],
    div[data-testid="stForm"] button[type="submit"] {{
        background: {p['black']} !important;
        color: {p['white']} !important;
        border-radius: 8px !important;
        font-family: 'Fraunces', serif !important;
        font-weight: 300 !important;
        font-variation-settings: 'opsz' 9 !important;
        border: none !important;
    }}
    button[kind="primary"] *,
    [data-testid="stBaseButton-primary"] *,
    div[data-testid="stForm"] button[kind="primaryFormSubmit"] *,
    div[data-testid="stForm"] button[type="submit"] * {{
        color: {p['white']} !important;
        font-family: 'Fraunces', serif !important;
    }}
    button[kind="secondary"],
    [data-testid="stBaseButton-secondary"] {{
        background: transparent !important;
        color: {p['text']} !important;
        border: 1px solid {p['border']} !important;
        border-radius: 8px !important;
        font-family: 'Fraunces', serif !important;
        font-weight: 300 !important;
    }}
    button[kind="secondary"] *,
    [data-testid="stBaseButton-secondary"] * {{
        color: {p['text']} !important;
        font-family: 'Fraunces', serif !important;
    }}

    /* ── Download button ── */
    [data-testid="stDownloadButton"] button {{
        background: {p['bg_secondary']} !important;
        color: {p['text']} !important;
        border: 1px solid {p['border']} !important;
        border-radius: 8px !important;
        font-family: 'Fraunces', serif !important;
        font-weight: 300 !important;
    }}
    [data-testid="stDownloadButton"] button p,
    [data-testid="stDownloadButton"] button span {{
        color: {p['text']} !important;
    }}

    /* ── Dataframes ── */
    [data-testid="stDataFrame"] {{ background: {p['white']} !important; }}
    [data-testid="stDataFrame"] * {{
        color: {p['text']} !important;
        font-family: 'Fraunces', serif !important;
        font-weight: 300 !important;
    }}
    [data-testid="stDataFrame"] thead tr th {{
        background: {p['bg_secondary']} !important;
        color: {p['brown']} !important;
    }}
    [data-testid="stDataFrame"] tbody tr {{ background: {p['white']} !important; }}
    [data-testid="stDataFrame"] tbody tr:nth-child(even) {{
        background: #FAF3E8 !important;
    }}

    /* ── Tabs — same pill treatment as the top nav, so they read as ── */
    /* ── real navigation, not easy-to-miss faint text. Streamlit has ── */
    /* ── changed the internal tab DOM across versions (data-baseweb  ── */
    /* ── in older releases, data-testid="stTab" in newer ones), so   ── */
    /* ── every rule below targets BOTH plus the version-independent  ── */
    /* ── role="tab" ARIA attribute, to survive either implementation.── */
    [data-baseweb="tab-list"], [role="tablist"] {{
        gap: 0.5rem !important;
        border-bottom: none !important;
        margin-bottom: 0.5rem !important;
    }}
    [data-baseweb="tab"], [data-testid="stTab"], [role="tab"] {{
        color: {p['text_muted']} !important;
        font-family: 'Fraunces', serif !important;
        font-weight: 400 !important;
        font-size: 1rem !important;
        padding: 0.55rem 1.2rem !important;
        border-radius: 8px !important;
        border: 1px solid {p['border']} !important;
        background: {p['white']} !important;
    }}
    [data-baseweb="tab"] *, [data-testid="stTab"] *, [role="tab"] * {{
        color: inherit !important;
        background: transparent !important;
        font-family: 'Fraunces', serif !important;
    }}
    [data-baseweb="tab"]:hover, [data-testid="stTab"]:hover, [role="tab"]:hover {{
        background: {p['pink']} !important;
        border-color: {p['pink_border']} !important;
        color: {p['text']} !important;
    }}
    [data-baseweb="tab"][aria-selected="true"],
    [data-testid="stTab"][aria-selected="true"],
    [role="tab"][aria-selected="true"] {{
        color: {p['white']} !important;
        background: {p['black']} !important;
        border-color: {p['black']} !important;
    }}
    [data-baseweb="tab"][aria-selected="true"] *,
    [data-testid="stTab"][aria-selected="true"] *,
    [role="tab"][aria-selected="true"] *,
    [data-baseweb="tab"][aria-selected="true"] p,
    [data-testid="stTab"][aria-selected="true"] p,
    [role="tab"][aria-selected="true"] p {{
        color: {p['white']} !important;
        background: transparent !important;
    }}
    [data-baseweb="tab-highlight"],
    [data-baseweb="tab-border"],
    .react-aria-SelectionIndicator {{
        display: none !important;
    }}

    /* ── Expanders ── */
    .streamlit-expanderHeader {{
        font-family: 'Fraunces', serif !important;
        font-weight: 300 !important;
        color: {p['text']} !important;
    }}

    /* ── Sliders ── */
    [data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stThumbValue"] {{
        color: {p['text']} !important;
    }}

    a, a:visited {{ color: {p['terracotta']} !important; }}

    hr.divider {{ border: none; border-top: 1px solid {p['border']}; margin: 1.1rem 0; }}

    .cost-badge {{
        display: inline-block;
        background: {p['bg_secondary']};
        color: {p['brown']};
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 0.82rem;
        font-family: 'Fraunces', serif;
        font-weight: 300;
    }}

    .unknown-badge {{
        display: inline-block;
        background: {p['unknown_bg']};
        color: {p['brown']};
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 0.78rem;
        font-family: 'Fraunces', serif;
        font-weight: 400;
    }}

    .step-card {{
        background: {p['white']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 1.1rem 1.25rem;
        height: 100%;
    }}
    .step-card-num {{
        font-size: 0.72rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: {p['terracotta']};
        margin-bottom: 0.3rem;
        font-family: 'Fraunces', serif;
    }}
    .step-card-title {{
        font-family: 'Sorts Mill Goudy', serif;
        font-size: 1.05rem;
        color: {p['text']};
        margin-bottom: 0.3rem;
    }}
    .step-card-desc {{
        font-size: 0.82rem;
        color: {p['text_muted']};
        font-family: 'Fraunces', serif;
        font-weight: 300;
    }}

    /* ── Task cards — the "what do you want to do?" landing tiles ── */
    .task-card {{
        background: {p['white']};
        border: 1px solid {p['border']};
        border-radius: 14px;
        padding: 1.6rem 1.25rem 1.1rem;
        text-align: center;
        height: 100%;
        position: relative;
        transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
    }}
    .task-card:hover {{
        border-color: {p['terracotta']};
        box-shadow: 0 6px 16px rgba(193, 96, 58, 0.16);
        transform: translateY(-2px);
    }}
    .task-card-link {{
        position: absolute;
        inset: 0;
        z-index: 1;
        border-radius: 14px;
        cursor: pointer;
    }}
    .task-card.disabled {{
        opacity: 0.55;
    }}
    .task-card-icon {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        border-radius: 50%;
        background: {p['pink']};
        color: {p['pink_accent']};
        font-family: 'Sorts Mill Goudy', serif;
        font-style: italic;
        font-size: 1.1rem;
        margin-bottom: 0.6rem;
        position: relative;
    }}
    .task-card-title {{
        font-family: 'Sorts Mill Goudy', serif;
        font-size: 1.2rem;
        color: {p['text']};
        margin-bottom: 0.35rem;
    }}
    .task-card-desc {{
        font-size: 0.86rem;
        color: {p['text_muted']};
        font-family: 'Fraunces', serif;
        font-weight: 300;
        margin-bottom: 0.9rem;
        min-height: 2.6rem;
    }}

    /* ── Receipt — the price breakdown on the Quote page, in her words ── */
    .receipt-box {{
        background: {p['white']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 1.25rem 1.5rem 1.4rem;
    }}
    .receipt-line {{
        display: flex;
        justify-content: space-between;
        padding: 0.3rem 0;
        font-size: 0.98rem;
        color: {p['text']};
        font-family: 'Fraunces', serif;
        font-weight: 300;
    }}
    .receipt-line.muted {{ color: {p['text_muted']}; font-size: 0.86rem; }}
    .receipt-line.total {{
        border-top: 1px solid {p['border']};
        margin-top: 0.5rem;
        padding-top: 0.7rem;
        font-size: 1.15rem;
        font-weight: 400;
        font-family: 'Sorts Mill Goudy', serif;
    }}
    .receipt-charge {{
        font-family: 'Sorts Mill Goudy', serif;
        font-size: 2.6rem;
        color: {p['text']};
        text-align: center;
        margin: 0.2rem 0 0.9rem;
    }}
    .receipt-charge-label {{
        text-align: center;
        color: {p['text_muted']};
        font-size: 0.82rem;
        font-family: 'Fraunces', serif;
        margin-top: -0.6rem;
        margin-bottom: 1rem;
    }}
    .makes-note {{
        background: {p['bg_secondary']};
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-size: 0.92rem;
        color: {p['brown']};
        font-family: 'Fraunces', serif;
        margin-bottom: 0.8rem;
    }}
    """


def _page_url_slug(path: str) -> str:
    """Mirrors how Streamlit turns a pages/ filename into a URL path segment:
    the .py extension drops and a leading run of digits+underscore (the
    ordering prefix, e.g. "3_") strips off. The bare root page has no slug
    at all — it's just "/"."""
    if path == "app.py":
        return ""
    fname = path.rsplit("/", 1)[-1]
    if fname.endswith(".py"):
        fname = fname[:-3]
    i = 0
    while i < len(fname) and fname[i].isdigit():
        i += 1
    if i < len(fname) and fname[i] == "_":
        fname = fname[i + 1:]
    return fname


def apply_page_style(current_file: str) -> None:
    """Call once per page, right after st.set_page_config(). Renders theme + top nav only."""
    st.markdown(f"<style>{_base_css()}</style>", unsafe_allow_html=True)

    tabs_html = []
    for path, label in PAGES:
        fname = path.rsplit("/", 1)[-1]
        is_active = fname == current_file or path == current_file
        href = "/" + _page_url_slug(path)
        cls = "main-nav-tab active" if is_active else "main-nav-tab"
        tabs_html.append(f"<a class='{cls}' href='{href}' target='_self'>{label}</a>")
    st.markdown(f"<nav class='main-nav'>{''.join(tabs_html)}</nav>", unsafe_allow_html=True)


def render_footer(current_file: str) -> None:
    """Call once at the very end of a page. Holds the export/backup action —
    deliberately out of the way of the main task flow, not competing with nav."""
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1, 1, 1])
    with f2:
        _render_export_button(key_suffix=current_file)


def _render_export_button(key_suffix: str = "default") -> None:
    from export import build_export_workbook
    try:
        data = build_export_workbook()
        st.download_button(
            "Export to Excel",
            data=data,
            file_name="baker_backup.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"export_btn_{key_suffix}",
        )
    except Exception as e:
        st.button("Export to Excel", disabled=True, use_container_width=True,
                   key=f"export_btn_disabled_{key_suffix}",
                   help=f"Export unavailable: {e}")