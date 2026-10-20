"""Tema visual (claro/escuro) da interface.

Todas as cores ficam aqui: o CSS injetado no Streamlit usa variáveis :root e os
gráficos (matplotlib e Graphviz) recebem a mesma paleta. O relatório PDF sempre
usa o tema claro.
"""
from __future__ import annotations

CLARO = {
    # interface
    "bg": "#F7F8FA", "bg2": "#EEF1F5", "card": "#FFFFFF", "text": "#1F2937", "muted": "#4B5563",
    "border": "#D7DCE3", "accent": "#0F766E", "on-accent": "#FFFFFF", "accent-soft": "#DDEFEC",
    "accent-text": "#0B4F4A",
    "warning-bg": "#FEF6DC", "warning-text": "#5C4300", "warning-border": "#E9C46A",
    "success-bg": "#E3F4EC", "success-text": "#14532D", "success-border": "#9AD5B6",
    "info-bg": "#E6EEF9", "info-text": "#1E3A5F", "info-border": "#A9C3E8",
    "error-bg": "#FDE8E8", "error-text": "#7F1D1D", "error-border": "#F2B4B4",
    "code-bg": "#F1F3F6", "code-text": "#111827",
    "chip-bg": "#DDEFEC", "chip-text": "#0B4F4A",
    # botão primário (contraste 5,47:1), ícone de ajuda, tooltip e trilho do toggle (≥ 3:1)
    "btn-bg": "#0F766E", "btn-text": "#FFFFFF", "btn-hover": "#115E59",
    "help-icon": "#4B5563", "tooltip-bg": "#FFFFFF", "toggle-off": "#717B8A",
    # gráficos e grafos
    "g-bg": "#FFFFFF", "g-text": "#1F2937", "g-line": "#1F2937", "g-muted": "#6B7280", "g-grid": "#D1D5DB",
    "g-cmd": "#EAF2FB", "g-dec": "#FFF1DB", "g-term": "#E5E7EB",
    "verde": "#059669", "vermelho": "#DC2626", "azul": "#2563EB", "ambar": "#D97706",
}

ESCURO = {
    "bg": "#0F1419", "bg2": "#161C23", "card": "#1C232C", "text": "#E6EAF0", "muted": "#A9B4C2",
    "border": "#2E3844", "accent": "#2DD4BF", "on-accent": "#06201D", "accent-soft": "#12403B",
    "accent-text": "#99F6E4",
    "warning-bg": "#3A2F0B", "warning-text": "#FCE7A6", "warning-border": "#8A6D1A",
    "success-bg": "#0F3325", "success-text": "#A7F3D0", "success-border": "#1F6B4C",
    "info-bg": "#13283F", "info-text": "#BFDBFE", "info-border": "#2B4E78",
    "error-bg": "#3B1414", "error-text": "#FECACA", "error-border": "#7A2B2B",
    "code-bg": "#11161C", "code-text": "#E6EAF0",
    "chip-bg": "#12403B", "chip-text": "#99F6E4",
    # texto escuro sobre o verde-água: 7,77:1 (o branco dava 1,86:1)
    "btn-bg": "#2DD4BF", "btn-text": "#042F2E", "btn-hover": "#5EEAD4",
    "help-icon": "#CBD5E1", "tooltip-bg": "#2A3441", "toggle-off": "#6B7685",
    "g-bg": "#1C232C", "g-text": "#E6EAF0", "g-line": "#CBD5E1", "g-muted": "#94A3B8", "g-grid": "#3A4552",
    "g-cmd": "#1E3A5F", "g-dec": "#4A3A12", "g-term": "#2E3844",
    "verde": "#34D399", "vermelho": "#F87171", "azul": "#60A5FA", "ambar": "#FBBF24",
}


def paleta(escuro: bool) -> dict:
    return ESCURO if escuro else CLARO


_CSS = """
<style>
:root {{
{variaveis}
}}

/* ---------- base ---------- */
body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] {{
    background: var(--bg); color: var(--text);
}}
.stApp p, .stApp li, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
[data-testid="stMarkdownContainer"] {{ color: var(--text); }}
[data-testid="stHeader"] button, [data-testid="stHeader"] svg {{ color: var(--text); fill: var(--text); }}
.stApp a {{ color: var(--accent); }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {{ background: var(--bg2); }}
[data-testid="stSidebar"] [data-testid="stHeading"] h2 {{
    font-size: 1.02rem; font-weight: 700; margin: 0;
    padding: 1.05rem 0 .4rem; border-top: 1px solid var(--border);
}}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-size: .95rem; font-weight: 600; color: var(--text); }}
[data-testid="stSidebar"] [data-testid="stRadio"] label p,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label p {{ font-size: .93rem; color: var(--text); opacity: 1; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: var(--muted); font-size: .9rem; }}
[data-testid="stTooltipIcon"] svg, [data-testid="stTooltipIcon"] svg * {{
    color: var(--help-icon) !important; stroke: var(--help-icon) !important;
}}

/* operadores de mutação */
.st-key-ops_botoes button {{ min-height: 1.9rem; padding: .1rem .55rem; font-size: .82rem; }}
.st-key-ops_lista [data-testid="stCheckbox"] {{ margin-bottom: .15rem; }}
.st-key-ops_lista [data-testid="stCheckbox"] label p {{ line-height: 1.35; }}
.st-key-ops_lista small, .st-key-ops_lista [data-testid="stCheckbox"] label p span {{ color: var(--muted); }}
.st-key-ops_lista strong {{ color: var(--accent-text); letter-spacing: .02em; }}

/* ---------- campos ---------- */
/* No Streamlit 1.66 os campos usam React Aria (role=group / listbox); as regras
   [data-baseweb] cobrem versões anteriores. */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div,
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"],
[data-testid="stSelectbox"] [role="group"], [data-testid="stFileUploaderDropzone"] {{
    background: var(--card) !important; border-color: var(--border) !important;
}}
.stApp input, .stApp textarea {{ color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; }}
/* "Press Enter to apply": por padrão fica dentro do campo, colado no texto/senha;
   passa para logo abaixo da borda, alinhado à direita, com espaço reservado */
[data-testid="stTextInput"]:has([data-testid="InputInstructions"]),
[data-testid="stTextArea"]:has([data-testid="InputInstructions"]) {{ margin-bottom: 1.1rem; }}
[data-testid="stTextInput"] [data-testid="InputInstructions"],
[data-testid="stTextArea"] [data-testid="InputInstructions"] {{
    top: calc(100% + 4px) !important; bottom: auto !important; right: 0 !important;
    font-size: .75rem; color: var(--muted) !important; background: transparent !important;
}}
.stApp input::placeholder, .stApp textarea::placeholder {{ color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; }}
[data-testid="stSelectbox"] [role="group"] * {{ color: var(--text); }}
[data-baseweb="popover"] ul, [data-baseweb="menu"], [data-baseweb="popover"] li,
[role="listbox"], [role="listbox"] [role="option"] {{ background: var(--card) !important; color: var(--text) !important; }}
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"],
[role="listbox"] [role="option"]:hover, [role="listbox"] [role="option"][aria-selected="true"] {{ background: var(--accent-soft) !important; }}
[data-baseweb="tag"] {{ background: var(--chip-bg) !important; color: var(--chip-text) !important; }}
[data-baseweb="tag"] span {{ color: var(--chip-text) !important; }}
[data-baseweb="checkbox"] > div:first-child, [data-baseweb="radio"] > div:first-child {{ border-color: var(--muted); }}
/* rádio e checkbox desmarcados (React Aria): o fundo vinha fixo do tema base */
[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child {{
    background: var(--card) !important; border: 2px solid var(--muted) !important;
}}
[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child > div {{ background: transparent !important; }}
[data-testid="stCheckbox"] label:not([data-selected="true"]):not(:has(input[role="switch"])) > div:first-of-type {{
    background: var(--card) !important; border-color: var(--muted) !important;
}}
[data-testid="stCheckbox"] label:has(input[role="switch"]):not([data-selected="true"]) > div:first-of-type {{
    background: var(--toggle-off) !important;
}}

/* fonte do CAD0001 (editor) e blocos de código */
[class*="st-key-codigo"] textarea {{
    font-family: "JetBrains Mono", "Cascadia Code", Consolas, "Courier New", monospace !important;
    font-size: .86rem !important; line-height: 1.55 !important;
    background: var(--code-bg) !important; color: var(--code-text) !important;
    -webkit-text-fill-color: var(--code-text) !important;
}}
[data-testid="stCode"] pre, [data-testid="stCode"] code {{ background: var(--code-bg) !important; }}
[data-testid="stCode"] code {{ font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace !important; font-size: .85rem; }}
{codigo_escuro}

/* ---------- botões e abas ---------- */
[data-testid="stBaseButton-secondary"] {{ background: var(--card); color: var(--text); border-color: var(--border); }}
[data-testid="stBaseButton-secondary"]:hover {{ border-color: var(--accent); color: var(--accent); }}
[data-testid="stBaseButton-primary"] {{ background: var(--btn-bg) !important; border-color: var(--btn-bg) !important; }}
[data-testid="stBaseButton-primary"]:hover {{ background: var(--btn-hover) !important; border-color: var(--btn-hover) !important; }}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] * {{ color: var(--btn-text) !important; }}
[data-testid="stTab"] p {{ color: var(--muted); }}
[data-testid="stTab"][aria-selected="true"] p {{ color: var(--accent); font-weight: 600; }}

/* ---------- cartões ---------- */
[data-testid="stMetric"] {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: .65rem .85rem;
}}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {{ align-items: stretch; }}
[data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:only-child > [data-testid="stMetric"]) > [data-testid="stVerticalBlock"],
[data-testid="stElementContainer"]:only-child:has(> [data-testid="stMetric"]),
[data-testid="stElementContainer"]:only-child > [data-testid="stMetric"] {{ height: 100%; box-sizing: border-box; }}
[data-testid="stMetricLabel"] p {{ color: var(--muted); }}
[data-testid="stMetricValue"] {{ color: var(--text); }}
.stApp [data-testid="stMetricDelta"], .stApp [data-testid="stMetricDelta"] div {{ color: var(--accent-text) !important; }}
/* delta sem seta (delta_arrow="off") é só uma mensagem: cor neutra, sem fundo verde */
.stApp [data-testid="stMetricDelta"]:not(:has([data-testid^="stMetricDeltaIcon"])),
.stApp [data-testid="stMetricDelta"]:not(:has([data-testid^="stMetricDeltaIcon"])) div {{
    color: var(--muted) !important; background: transparent !important;
}}
[data-testid="stExpander"] details {{ background: var(--card); border-color: var(--border); }}
[data-testid="stExpander"] summary {{ background: var(--card) !important; color: var(--text); }}
[data-testid="stExpander"] summary:hover {{ background: var(--accent-soft) !important; }}
[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary svg {{ color: var(--text); fill: var(--text); }}

/* ---------- avisos ---------- */
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{ background: var(--warning-bg); border: 1px solid var(--warning-border); }}
[data-testid="stAlertContentWarning"] * {{ color: var(--warning-text) !important; }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{ background: var(--success-bg); border: 1px solid var(--success-border); }}
[data-testid="stAlertContentSuccess"] * {{ color: var(--success-text) !important; }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {{ background: var(--info-bg); border: 1px solid var(--info-border); }}
[data-testid="stAlertContentInfo"] * {{ color: var(--info-text) !important; }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{ background: var(--error-bg); border: 1px solid var(--error-border); }}
[data-testid="stAlertContentError"] * {{ color: var(--error-text) !important; }}

/* ---------- elementos flutuantes (portais no <body>, fora do .stApp) ---------- */
[data-testid="stTooltipContent"] {{
    background: var(--tooltip-bg) !important; color: var(--text) !important;
    border: 1px solid var(--border); box-shadow: 0 6px 18px rgba(0, 0, 0, .25);
}}
[data-testid="stTooltipContent"] * {{ color: var(--text) !important; }}
[data-testid="stElementToolbarButtonContainer"] {{
    background: var(--card) !important; border: 1px solid var(--border); border-radius: 8px;
}}
[data-testid="stElementToolbar"] button, [data-testid="stElementToolbar"] [data-testid="stIconMaterial"] {{ color: var(--text) !important; }}
[data-testid="stElementToolbar"] button:hover {{ background: var(--accent-soft) !important; }}
/* menus do st.dataframe: stDataFrameColumnVisibilityMenu (colunas) e menu de cada coluna */
[data-baseweb="popover"] > div, [data-testid="portal"] [role="dialog"], [data-testid="portal"] [role="menu"],
[data-testid^="stDataFrameColumn"][data-testid$="Menu"] {{
    background: var(--card) !important; color: var(--text) !important; border-color: var(--border) !important;
}}
[data-testid="portal"] [role="menu"] *, [data-testid^="stDataFrameColumn"][data-testid$="Menu"] * {{ color: var(--text); }}
[data-testid^="stDataFrameColumn"][data-testid$="Menu"] input[type="checkbox"]:not(:checked):not([aria-checked="mixed"]) + span {{
    background: var(--card) !important; border-color: var(--muted) !important;
}}
[data-testid="portal"] [role="menuitem"]:hover {{ background: var(--accent-soft) !important; }}

/* ---------- tabelas ---------- */
[data-testid="stTable"] table, [data-testid="stTable"] td {{ background: var(--card); color: var(--text); border-color: var(--border) !important; }}
[data-testid="stTable"] th {{ background: var(--bg2); color: var(--muted); border-color: var(--border) !important; }}
/* casos combinados: números e códigos numa linha só; Descrição (2ª) e Obtido (7ª) podem quebrar */
.st-key-tabela_cmb table {{ width: 100%; table-layout: auto; font-size: .88rem; }}
.st-key-tabela_cmb th, .st-key-tabela_cmb td {{ padding: .35rem .5rem; vertical-align: top; }}
.st-key-tabela_cmb td {{ white-space: nowrap !important; }}
.st-key-tabela_cmb td * {{ white-space: inherit !important; }}  /* o <div><p> interno voltava para normal */
.st-key-tabela_cmb td:nth-child(2), .st-key-tabela_cmb td:nth-child(7) {{ white-space: normal !important; min-width: 9rem; }}
{tabela_escuro}
</style>
"""

# As tabelas interativas (st.dataframe / st.data_editor) são desenhadas em <canvas>
# com as cores do tema base, então o CSS não alcança as células. No escuro elas
# são invertidas; o hue-rotate devolve os tons originais aos ✔/✘ e cores. Só a grade
# (stDataFrameResizable) é invertida: a barra de ferramentas é irmã dela e usa as variáveis.
_TABELA_ESCURO = """
[data-testid="stDataFrameResizable"] { filter: invert(.9) hue-rotate(180deg); }
/* a busca da tabela fica dentro da grade invertida: o texto precisa ser escuro antes
   da inversão para aparecer claro depois dela */
[data-testid="stDataFrameResizable"] input {
    color: #1F2937 !important; -webkit-text-fill-color: #1F2937 !important;
}
"""

# O realce de sintaxe do st.code usa cores pensadas para fundo claro.
_CODIGO_ESCURO = """
[data-testid="stCode"] code, [data-testid="stCode"] code span { color: var(--code-text) !important; }
"""


def css(escuro: bool) -> str:
    p = paleta(escuro)
    variaveis = "\n".join(f"    --{k}: {v};" for k, v in p.items())
    return _CSS.format(variaveis=variaveis,
                       tabela_escuro=_TABELA_ESCURO if escuro else "",
                       codigo_escuro=_CODIGO_ESCURO if escuro else "")
