"""Relatório final das Sprints em PDF (fpdf2) e Markdown."""
from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

import matplotlib
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from PIL import Image

from . import graficos, oraculo, tabelas
from .validacao import falha_do_requisito
from .fonte4gl import fmt_brl
from .gfc import caminho_txt

FONTES = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
AZUL_ESCURO = (31, 41, 55)
CINZA = (107, 114, 128)
CABECALHO = (234, 242, 251)


# ---------------------------------------------------------------------------
# Blocos de conteúdo (independentes do formato)
# ---------------------------------------------------------------------------


def _h1(t):
    return ("h1", t)


def _h2(t):
    return ("h2", t)


def _p(t):
    return ("p", t)


def _code(t):
    return ("code", t)


def _tab(linhas, larguras=None, fonte=7.5):
    return ("table", linhas, larguras, fonte)


def _img(png, largura=170, legenda=""):
    return ("img", png, largura, legenda)


def _md(t, titulo="Explicação escrita pelo Gemini", modelo=""):
    return ("md", t, titulo, modelo)


def _modelo_txt(textos_ia: dict, chave: str) -> str:
    """Legenda com o modelo que gerou o texto (e o pedido, se houve troca automática)."""
    usado = textos_ia.get(f"{chave}_modelo")
    if not usado:
        return ""
    pedido = textos_ia.get(f"{chave}_pedido")
    if pedido and pedido != usado:
        return (f"Texto gerado pelo modelo {usado} (troca automática: o modelo escolhido, "
                f"{pedido}, não respondeu).")
    return f"Texto gerado pelo modelo {usado}."


LARG_CASOS = [26, 34, 16, 16, 16, 18, 20, 13, 19]
LARG_CAMINHOS = [12, 24, 17, 17, 17, 17, 17, 57]


def montar_blocos(a: dict, textos_ia: dict[str, str], meta: dict) -> list:
    f = a["funcao"]
    params = f.params
    lc = LARG_CASOS if len(params) == 3 else None
    lp = LARG_CAMINHOS if len(params) == 3 else None
    s1, g1, g2, du = a["s1"], a["g1"], a["g2"], a["du"]
    m = a["metricas"]
    B: list = []

    # --- Sprint 1 --------------------------------------------------------------
    B.append(_h1("Sprint 1 — Caixa-Preta: PCE e AVL com Épsilon"))
    B.append(_p(f"Fonte analisado: {meta.get('origem', 'editor')} — FUNCTION {f.nome}({', '.join(params)})."))
    B.append(_code(a["codigo"].strip()))
    B.append(_h2("Particionamento em Classes de Equivalência (PCE)"))
    B.append(_tab(s1["tabela_pce"], [22, 22, 30, 22, 34]))
    B.append(_p("NULL é tratado como classe válida porque o código o converte em 0,00 antes do teste de "
                "negativos. O texto teórico do manual trata NULL como inválido; o fonte faz outra coisa."))
    B.append(_tab(tabelas.casos(s1["casos_pce"], params), lc, fonte=6.5))
    B.append(_h2("Análise do Valor Limite (AVL) e Épsilon"))
    B.append(_p(f"Tipo dos parâmetros: {s1['tipo']}. ε = {fmt_brl(s1['epsilon'])}. {s1['justificativa']} "
                f"Maior valor do tipo: {fmt_brl(s1['maximo'])}."))
    for p in params:
        B.append(_p(f"Pontos de fronteira variando {p} (os outros parâmetros ficam neutros, então o retorno é o próprio valor):"))
        B.append(_tab(tabelas.avl_param(s1["casos_avl"], p, params), fonte=6.8))
    B.append(_img(graficos.png(graficos.fronteira_avl(
        [c for c in s1["casos_avl"] if f"-{params[0]}-" in c.id], s1["epsilon"])), 150,
        f"Pontos On, Off, Interior e Exterior da fronteira 0,00 ({params[0]})."))
    if s1["casos_cmb"]:
        B.append(_h2("Casos combinando os três parâmetros"))
        B.append(_tab(tabelas.casos(s1["casos_cmb"], params), lc, fonte=6.5))
    if textos_ia.get("s1"):
        B.append(_md(textos_ia["s1"], modelo=_modelo_txt(textos_ia, "s1")))

    # --- Sprint 2 --------------------------------------------------------------
    B.append(_h1("Sprint 2 — Caixa-Branca: GFC e Complexidade Ciclomática"))
    B.append(_p("Um nó reúne comandos executados em sequência; decisões (nós predicativos) têm saídas V "
                "(verdadeiro) e F (falso). V(G) = número de caminhos linearmente independentes "
                "(limite superior para cobrir as arestas)."))
    for titulo, ga, desc in (
        ("GFC 1 — contagem por comandos IF", g1, "O IF com OR é uma decisão só."),
        ("GFC 2 — contagem por condições simples", g2, "O OR é desdobrado em condições simples com curto-circuito."),
    ):
        g = ga["grafo"]
        # título, frase e desenho ficam juntos na mesma página
        B.append(("figura_secao", titulo, desc, graficos.png(graficos.desenhar_gfc(g)), 120, f"{titulo}."))
        B.append(_tab(tabelas.nos(g), [16, 120, 40]))
        B.append(_tab(tabelas.arestas(g), [40, 40, 50]))
        B.append(_p(f"Nós (N) = {g.N}, Arestas (E) = {g.E}, Decisões (P) = {g.P}."))
        B.append(_tab(tabelas.metricas_mccabe(g), [70, 60, 30]))
        B.append(_p("As três fórmulas de McCabe batem." if g.vg_arestas == g.vg_decisoes == g.regioes
                    else "Atenção: as fórmulas divergem (grafo com saída múltipla ou desconexo)."))
        B.append(_p("Caminhos básicos independentes e casos de teste (entradas encontradas executando o programa):"))
        B.append(_tab(tabelas.caminhos(g, ga["casos"], params), lp, fonte=6.2))
        B.append(_p(f"Cobertura de arestas pelos casos: {ga['arestas_cobertas']} de {g.E}. "
                    f"Cobertura de nós: {ga['nos_cobertos']} de {g.N}."))
    if textos_ia.get("s2"):
        B.append(_md(textos_ia["s2"], modelo=_modelo_txt(textos_ia, "s2")))

    # --- Sprint 3 --------------------------------------------------------------
    B.append(_h1("Sprint 3 — Fluxo de Dados (Def-Uso) e Teste de Mutação"))
    B.append(_h2("Anotação def / c-uso / p-uso no GFC"))
    B.append(_p(f"Grafo usado: {'GFC 1 (comandos IF)' if a['grafo_du'].modo == 'composto' else 'GFC 2 (condições simples)'}. "
                "Os parâmetros são definidos no nó de início; p-usos ficam nas arestas que saem das decisões."))
    B.append(_tab(tabelas.anotacoes(du["anotacoes"]), [16, 50, 60, 50]))
    B.append(_h2("Pares Def-Uso e cobertura"))
    B.append(_tab(tabelas.pares(du["pares"]), fonte=6.5))
    B.append(_tab(tabelas.criterios(du["criterios"]), [60, 30, 30, 30]))
    B.append(_img(graficos.png(graficos.criterios_du(du["criterios"])), 130))
    if du.get("sugestoes_aplicadas"):
        B.append(_p("Casos acrescentados automaticamente para cobrir pares que a suíte das Sprints 1 e 2 não cobria:"))
        B.append(_tab(tabelas.casos(du["sugestoes_aplicadas"], params), lc, fonte=6.5))
    if du["defs_sem_uso"]:
        B.append(_p("Definições sem uso (anomalia): " + ", ".join(f"{v} em N{d}" for d, v in du["defs_sem_uso"])))
    r = a["mutacao"]
    B.append(_h2("Teste de Mutação"))
    B.append(_p(f"Mutantes gerados: {r['total']}. Mortos: {r['mortos']}. Vivos: {r['vivos']}. "
                f"Equivalentes: {r['equivalentes']}. Escore de Mutação MS = {r['mortos']} / "
                f"({r['total']} − {r['equivalentes']}) = {r['ms'] * 100:.1f}%."))
    B.append(_tab(tabelas.por_operador(r), [25, 25, 25, 25, 30, 25]))
    B.append(_tab(tabelas.ms_suites(a["ms_suites"]), [50, 25, 25, 25, 25]))
    B.append(_img(graficos.png(graficos.ms_por_suite(a["ms_suites"])), 140))
    vivos = [mt for mt in a["mutantes"] if mt.status != "Morto"]
    if vivos:
        B.append(_p("Mutantes que não foram mortos:"))
        B.append(_tab(tabelas.mutantes(vivos), fonte=6.2))
    B.append(_p("Lista completa de mutantes:"))
    B.append(_tab(tabelas.mutantes(a["mutantes"]), [13, 11, 10, 42, 42, 28, 16, 28], fonte=5.8))
    if textos_ia.get("s3"):
        B.append(_md(textos_ia["s3"], modelo=_modelo_txt(textos_ia, "s3")))

    # --- Sprint 4 --------------------------------------------------------------
    B.append(_h1("Sprint 4 — Validação, Rastreabilidade (RTM) e Pitch"))
    B.append(_p("Verificação: estamos construindo o produto da maneira certa? Validação: estamos construindo "
                "o produto certo? A RTM liga cada requisito aos casos de teste (cobertura bidirecional)."))
    B.append(_tab([{"Requisito": k, "Descrição": v} for k, v in oraculo.REQUISITOS.items()], [22, 150]))
    cab, linhas = tabelas.matriz_rtm(a["suite"], list(oraculo.REQUISITOS))
    B.append(_p("Matriz requisito × grupo de casos de teste (quantidade de CTs):"))
    B.append(_tab([dict(zip(cab, l)) for l in linhas], fonte=7))
    for nome, v in a["validacao"].items():
        B.append(_h2(f"Execução da suíte — {nome}"))
        B.append(_p(f"{v['passaram']} de {len(v['casos'])} casos conferem com o oráculo."))
        B.append(_tab(tabelas.rtm(v["rtm"]), [18, 92, 12, 18, 18, 22], fonte=6.8))
        if v["falharam"]:
            B.append(_p("Casos que falharam (defeitos revelados):"))
            B.append(_tab(tabelas.casos(v["falharam"][:25], params), lc, fonte=6.2))
    if meta.get("pytest"):
        pt = meta["pytest"]
        B.append(_h2("Execução automatizada com pytest"))
        B.append(_p(f"Resultado: {pt['resumo'] or pt['codigo']}. Arquivo: saida/test_cad0001_rtm.py "
                    "(cada caso marcado com @pytest.mark.requisito)."))
        # caminhos do Windows vêm com "\"; no PDF ficam com "/"
        ultimas = "\n".join(pt["saida"].strip().splitlines()[-12:]).replace("\\", "/")
        B.append(_code(ultimas))
    B.append(_h2("Painel de métricas"))
    B.append(_tab([
        {"Métrica": "Casos de teste na suíte", "Valor": m["casos"]},
        {"Métrica": "Casos que conferem com o oráculo", "Valor": f"{m['aprovados']} de {m['casos']}"},
        {"Métrica": "Épsilon (ε)", "Valor": fmt_brl(m["epsilon"])},
        {"Métrica": "V(G) GFC 1 / GFC 2", "Valor": f"{m['vg1']} / {m['vg2']}"},
        {"Métrica": "Pares Def-Uso cobertos", "Valor": f"{m['pares_du_cobertos']} de {m['pares_du']}"},
        {"Métrica": "Escore de Mutação (MS)", "Valor": f"{m['ms'] * 100:.1f}% ({m['mortos']}/{m['mutantes']})"},
        {"Métrica": "Requisitos testáveis com CT (RTM)", "Valor": f"{m['rtm'][0]} de {m['rtm'][1]}"},
    ], [100, 70]))
    if textos_ia.get("pitch"):
        B.append(_md(textos_ia["pitch"], "Pitch de validação (gerado com o Gemini)", _modelo_txt(textos_ia, "pitch")))
    elif meta.get("pitch_local"):
        B.append(_md(meta["pitch_local"], "Pitch de validação"))
    return B


def pitch_local(a: dict) -> str:
    """Resumo sem IA, para o relatório funcionar mesmo sem API Key."""
    m = a["metricas"]
    defeitos = []
    for nome, v in a["validacao"].items():
        if v["falharam"]:
            reqs = sorted({r for c in v["falharam"] for r in c.requisitos if falha_do_requisito(c, r)})
            defeitos.append(f"- **{nome}**: {len(v['falharam'])} caso(s) falharam ({', '.join(reqs)}).")
    if not defeitos:
        defeitos.append("- Nenhum caso falhou nas versões analisadas.")
    return "\n".join([
        "**O problema:** testar \"mais ou menos\" deixa passar defeitos de fronteira e de lógica.",
        "",
        "**A solução:** o TestingStudio Web lê o fonte 4GL, calcula PCE/AVL com ε, desenha o GFC, "
        "mede V(G), rastreia pares Def-Uso, gera mutantes e liga tudo aos requisitos (RTM).",
        "",
        "**Números que provam:**",
        f"- {m['casos']} casos de teste; ε = {fmt_brl(m['epsilon'])}",
        f"- V(G) = {m['vg1']} (por IF) e {m['vg2']} (por condições simples)",
        f"- {m['pares_du_cobertos']}/{m['pares_du']} pares Def-Uso cobertos",
        f"- MS = {m['ms'] * 100:.1f}% ({m['mortos']} de {m['mutantes']} mutantes mortos)",
        f"- {m['rtm'][0]}/{m['rtm'][1]} requisitos testáveis com caso de teste",
        "",
        "**Defeitos encontrados (Validação):**",
        *defeitos,
        "",
        "**Próximos passos:** stubs/drivers para testar a gravação 1:1 (REQ06); integrar ao CI; "
        "aplicar a ferramenta às listas de exercícios antes da prova.",
    ])


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


class _PDF(FPDF):
    titulo = "TestingStudio Web — Auditoria do CAD0001"

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("dejavu", "", 7.5)
        self.set_text_color(*CINZA)
        self.cell(0, 5, self.titulo, align="L")
        self.cell(0, 5, "Teste de Software I | Prof. Frank Piffer", align="R",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(220, 224, 230)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_text_color(*AZUL_ESCURO)

    def footer(self):
        self.set_y(-12)
        self.set_font("dejavu", "", 7.5)
        self.set_text_color(*CINZA)
        self.cell(0, 6, f"{self.page_no()}/{{nb}}", align="C")


_SIMBOLOS = {
    "varepsilon": "ε", "epsilon": "ε", "times": "×", "cdot": "·", "leq": "≤", "le": "≤", "geq": "≥",
    "ge": "≥", "neq": "≠", "ne": "≠", "approx": "≈", "rightarrow": "→", "to": "→", "Rightarrow": "⇒",
    "leftarrow": "←", "leftrightarrow": "↔", "Leftrightarrow": "⇔", "implies": "⇒", "iff": "⇔",
    "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "supseteq": "⊇", "in": "∈", "notin": "∉",
    "infty": "∞", "sum": "Σ", "Delta": "Δ", "delta": "δ", "alpha": "α", "beta": "β", "lambda": "λ",
    "pi": "π", "mu": "μ", "sigma": "σ", "pm": "±", "ldots": "…", "dots": "…", "cdots": "…",
    "cup": "∪", "cap": "∩", "forall": "∀", "exists": "∃", "neg": "¬", "lnot": "¬", "land": "∧",
    "lor": "∨", "wedge": "∧", "vee": "∨", "lt": "<", "gt": ">", "quad": " ", "qquad": " ",
    "left": "", "right": "", "displaystyle": "", "big": "", "Big": "",
}
_SOBRESCRITO = str.maketrans("0123456789+-n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ")


def _latex_para_texto(t: str) -> str:
    """Converte LaTeX que o Gemini às vezes escreve ($V(G)$, \\varepsilon, \\frac) em texto Unicode."""
    t = re.sub(r"\\\[|\\\]|\\\(|\\\)", "", t)              # delimitadores \[ \] \( \)
    t = re.sub(r"\$\$(.+?)\$\$", r"\1", t, flags=re.S)       # $$ ... $$
    t = re.sub(r"(?<!\\)\$(.+?)(?<!\\)\$", r"\1", t)           # $ ... $
    for _ in range(4):                                         # \frac{a}{b} (inclusive aninhado)
        t = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}",
                   lambda m: (f"({m[1]})" if re.search(r"[\s+−-]", m[1].strip()) else m[1]) + " / "
                   + (f"({m[2]})" if re.search(r"[\s+−-]", m[2].strip()) else m[2]), t)
    t = re.sub(r"\\(?:text|mathrm|mathbf|mathit|textbf|textit|operatorname|mbox)\s*\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\^\{([0-9+\-n]+)\}", lambda m: m[1].translate(_SOBRESCRITO), t)
    t = re.sub(r"\^([0-9n])", lambda m: m[1].translate(_SOBRESCRITO), t)
    t = re.sub(r"_\{([^{}]*)\}", r"_\1", t)                   # p_{val1} -> p_val1
    t = re.sub(r"\\([%_#&{}$])", r"\1", t)                     # \% \_ etc.
    t = re.sub(r"\\[,;:! ]", " ", t)                           # espaços do LaTeX
    t = re.sub(r"\\\\", " ", t)                                # quebra de linha \\
    t = re.sub(r"\\([A-Za-z]+)", lambda m: _SIMBOLOS.get(m[1], m[1]), t)
    t = t.replace("\\", "")
    t = re.sub(r"(?<=[^\s{])\{([^{}]*)\}", r"\1", t)           # chaves que sobraram de grupos
    return re.sub(r"[ \t]{2,}", " ", t)


def _preparar_md_pdf(texto: str) -> str:
    """Texto do Gemini para o PDF: sem LaTeX e sem separadores '---' (na tela fica igual)."""
    linhas = []
    for l in _latex_para_texto(texto).replace("\r", "").split("\n"):
        if re.fullmatch(r"\s*([-*_])(\s*\1){2,}\s*", l):        # linha só com ---, *** ou ___
            continue
        linhas.append(l.replace("---", "—"))
    return "\n".join(linhas)


def _limpar_md(t: str) -> str:
    t = t.replace("`", "")
    t = t.replace("---", "—").replace("--", "–")  # no modo markdown do fpdf2, "--" vira sublinhado
    t = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+)(?<!\*)\*(?!\*)", r"\1", t)  # *itálico* simples
    return t


def _md_tabela(linhas_md: list[str]) -> list[dict]:
    celulas = [[c.strip() for c in l.strip().strip("|").split("|")] for l in linhas_md]
    celulas = [c for c in celulas if not all(re.fullmatch(r":?-{2,}:?", x or "--") for x in c)]
    if not celulas:
        return []
    cab = celulas[0]
    return [dict(zip(cab, l + [""] * (len(cab) - len(l)))) for l in celulas[1:]]


class _Escritor:
    def __init__(self, meta):
        self.pdf = _PDF(format="A4")
        p = self.pdf
        p.add_font("dejavu", "", str(FONTES / "DejaVuSans.ttf"))
        p.add_font("dejavu", "B", str(FONTES / "DejaVuSans-Bold.ttf"))
        p.add_font("dejavu", "I", str(FONTES / "DejaVuSans-Oblique.ttf"))
        p.add_font("mono", "", str(FONTES / "DejaVuSansMono.ttf"))
        p.set_margins(16, 16, 16)
        p.set_auto_page_break(True, 16)
        p.alias_nb_pages()
        self.capa(meta)

    @property
    def largura(self):
        return self.pdf.w - self.pdf.l_margin - self.pdf.r_margin

    def capa(self, meta):
        p = self.pdf
        p.add_page()
        p.ln(40)
        p.set_text_color(5, 150, 105)
        p.set_font("dejavu", "B", 10)
        p.cell(0, 6, "PROJETO INTEGRADOR", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.set_text_color(*AZUL_ESCURO)
        p.set_font("dejavu", "B", 26)
        p.multi_cell(0, 12, "TestingStudio Web\nAuditoria do CAD0001", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.ln(4)
        p.set_font("dejavu", "", 11)
        p.set_text_color(*CINZA)
        p.multi_cell(0, 6, "Relatório das Sprints 1 a 4 — Caixa-Preta, Caixa-Branca, Dados e Mutantes, "
                           "Validação e Pitch", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.ln(16)
        p.set_text_color(*AZUL_ESCURO)
        itens = [
            ("Disciplina", "Teste de Software I (Ementa 62371) — 2026.2"),
            ("Professor", "Frank Piffer"),
            ("Aluno(s) / Equipe", meta.get("autores") or "—"),
            ("Fonte analisado", meta.get("origem") or "—"),
            ("Modelo de IA", meta.get("modelo") or "—"),
            ("Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")),
        ]
        for k, v in itens:
            p.set_font("dejavu", "B", 10)
            p.cell(45, 7, k)
            p.set_font("dejavu", "", 10)
            p.multi_cell(0, 7, v, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.ln(10)
        p.set_font("dejavu", "I", 8.5)
        p.set_text_color(*CINZA)
        p.multi_cell(0, 5, "Os números (classes, pontos limite, V(G), pares Def-Uso, mutantes e RTM) são calculados "
                           "pelo Python do TestingStudio executando o fonte 4GL. Os textos marcados como Gemini "
                           "explicam esses números e foram gerados pela API do Google AI Studio.",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def h1(self, t):
        p = self.pdf
        p.add_page()
        p.set_font("dejavu", "B", 15)
        p.set_text_color(*AZUL_ESCURO)
        p.multi_cell(0, 8, t, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.set_draw_color(5, 150, 105)
        p.set_line_width(0.6)
        p.line(p.l_margin, p.get_y() + 1, p.l_margin + 30, p.get_y() + 1)
        p.set_line_width(0.2)
        p.ln(5)

    def h2(self, t, tamanho=11.5):
        p = self.pdf
        if p.get_y() > p.h - 40:
            p.add_page()
        p.ln(2)
        p.set_font("dejavu", "B", tamanho)
        p.set_text_color(*AZUL_ESCURO)
        p.multi_cell(0, 6.5, t, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.ln(1)

    def par(self, t, md=False):
        p = self.pdf
        p.set_font("dejavu", "", 9)
        p.set_text_color(*AZUL_ESCURO)
        p.multi_cell(0, 4.8, _limpar_md(t) if md else t, markdown=md, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.ln(1.5)

    def codigo(self, t):
        p = self.pdf
        p.set_font("mono", "", 7)
        p.set_fill_color(243, 244, 246)
        p.set_text_color(*AZUL_ESCURO)
        p.multi_cell(0, 3.6, t, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.ln(2)

    def tabela(self, linhas, larguras=None, fonte=7.5):
        if not linhas:
            return
        p = self.pdf
        cab = list(linhas[0])
        if larguras and len(larguras) != len(cab):
            larguras = None
        p.set_font("dejavu", "", fonte)
        p.set_text_color(*AZUL_ESCURO)
        p.set_draw_color(209, 213, 219)
        estilo = FontFace(emphasis="BOLD", fill_color=CABECALHO, color=AZUL_ESCURO)
        with p.table(col_widths=larguras, width=self.largura if not larguras else min(sum(larguras), self.largura),
                     text_align="LEFT", headings_style=estilo, line_height=fonte * 0.55,
                     padding=0.9, first_row_as_headings=True, align="LEFT") as t:
            r = t.row()
            for c in cab:
                r.cell(str(c))
            for l in linhas:
                r = t.row()
                for c in cab:
                    r.cell(str(l.get(c, "")))
        p.ln(3)

    def imagem(self, png, largura, legenda=""):
        p = self.pdf
        w_px, h_px = Image.open(io.BytesIO(png)).size
        largura = min(largura, self.largura)
        altura = largura * h_px / w_px
        maxh = p.h - p.t_margin - p.b_margin - 14
        if altura > maxh:
            altura = maxh
            largura = altura * w_px / h_px
        if p.get_y() + altura > p.h - p.b_margin:
            p.add_page()
        x = p.l_margin + (self.largura - largura) / 2
        p.image(io.BytesIO(png), x=x, w=largura, h=altura)
        if legenda:
            p.set_font("dejavu", "I", 7.5)
            p.set_text_color(*CINZA)
            p.multi_cell(0, 4, legenda, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.ln(3)

    def figura_secao(self, titulo, desc, png, largura, legenda=""):
        """Título + frase + figura sem separar; reduz a figura para caber se necessário."""
        p = self.pdf
        w_px, h_px = Image.open(io.BytesIO(png)).size
        largura = min(largura, self.largura)
        altura = largura * h_px / w_px
        cabecalho = 24  # espaço do título, da frase e da legenda
        altura = min(altura, p.h - p.t_margin - p.b_margin - cabecalho - 8)
        espaco = p.h - p.b_margin - p.get_y() - cabecalho
        if altura > espaco:
            if espaco >= 0.85 * altura:
                altura = espaco
            else:
                p.add_page()
        largura = altura * w_px / h_px
        self.h2(titulo)
        self.par(desc)
        x = p.l_margin + (self.largura - largura) / 2
        p.image(io.BytesIO(png), x=x, w=largura, h=altura)
        if legenda:
            p.set_font("dejavu", "I", 7.5)
            p.set_text_color(*CINZA)
            p.multi_cell(0, 4, legenda, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        p.ln(3)

    def markdown(self, texto, titulo, modelo=""):
        p = self.pdf
        self.h2(titulo)
        p.set_draw_color(37, 99, 235)
        linhas = _preparar_md_pdf(texto).split("\n")
        i = 0
        em_codigo = False
        buf_codigo: list[str] = []
        while i < len(linhas):
            l = linhas[i]
            if l.strip().startswith("```"):
                if em_codigo:
                    self.codigo("\n".join(buf_codigo))
                    buf_codigo = []
                em_codigo = not em_codigo
                i += 1
                continue
            if em_codigo:
                buf_codigo.append(l)
                i += 1
                continue
            if l.strip().startswith("|"):
                bloco = []
                while i < len(linhas) and linhas[i].strip().startswith("|"):
                    bloco.append(linhas[i])
                    i += 1
                self.tabela([{k: _limpar_md(v).replace("**", "") for k, v in d.items()} for d in _md_tabela(bloco)],
                            fonte=7)
                continue
            m = re.match(r"^(#{1,6})\s+(.*)", l)
            if m:
                self.h2(m.group(2).replace("**", ""), 10.5 if len(m.group(1)) <= 2 else 9.8)
            elif re.match(r"^\s*([-*•]|\d+[.)])\s+", l):
                mm = re.match(r"^(\s*)([-*•]|\d+[.)])\s+(.*)", l)
                recuo = 4 + len(mm.group(1)) * 1.5
                marca = "•" if mm.group(2) in "-*•" else mm.group(2)
                p.set_font("dejavu", "", 9)
                p.set_x(p.l_margin + recuo)
                p.cell(5, 4.8, marca)
                p.multi_cell(0, 4.8, _limpar_md(mm.group(3)), markdown=True,
                             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            elif l.strip():
                self.par(l.strip(), md=True)
            else:
                p.ln(1.2)
            i += 1
        if buf_codigo:
            self.codigo("\n".join(buf_codigo))
        if modelo:
            p.ln(1)
            p.set_font("dejavu", "I", 7.8)
            p.set_text_color(*CINZA)
            p.multi_cell(0, 4.2, modelo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            p.set_text_color(*AZUL_ESCURO)
            p.ln(2)

    def escrever(self, blocos):
        for b in blocos:
            tipo = b[0]
            if tipo == "figura_secao":
                self.figura_secao(*b[1:])
            elif tipo == "h1":
                self.h1(b[1])
            elif tipo == "h2":
                self.h2(b[1])
            elif tipo == "p":
                self.par(b[1])
            elif tipo == "code":
                self.codigo(b[1])
            elif tipo == "table":
                self.tabela(b[1], b[2], b[3])
            elif tipo == "img":
                self.imagem(b[1], b[2], b[3])
            elif tipo == "md":
                self.markdown(b[1], b[2], b[3])
        return bytes(self.pdf.output())


def gerar_pdf(a: dict, textos_ia: dict[str, str], meta: dict) -> bytes:
    meta = dict(meta)
    meta.setdefault("pitch_local", pitch_local(a))
    return _Escritor(meta).escrever(montar_blocos(a, textos_ia, meta))


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def gerar_markdown(a: dict, textos_ia: dict[str, str], meta: dict) -> str:
    meta = dict(meta)
    meta.setdefault("pitch_local", pitch_local(a))
    out = [
        "# TestingStudio Web — Auditoria do CAD0001",
        "",
        f"**Disciplina:** Teste de Software I | **Professor:** Frank Piffer | "
        f"**Aluno(s):** {meta.get('autores') or '—'} | **Gerado em:** {datetime.now():%d/%m/%Y %H:%M}",
        "",
    ]
    for b in montar_blocos(a, textos_ia, meta):
        tipo = b[0]
        if tipo == "figura_secao":
            out += ["", f"### {b[1]}", "", b[2], "", f"_Figura: {b[5]} (ver relatório PDF)_", ""]
            continue
        if tipo == "h1":
            out += ["", f"## {b[1]}", ""]
        elif tipo == "h2":
            out += ["", f"### {b[1]}", ""]
        elif tipo == "p":
            out += [b[1], ""]
        elif tipo == "code":
            out += ["```", b[1], "```", ""]
        elif tipo == "table":
            out += [tabelas.markdown(b[1]), ""]
        elif tipo == "img":
            out += [f"_Figura: {b[3] or 'ver relatório PDF'}_", ""]
        elif tipo == "md":
            out += [f"#### {b[2]}", "", b[1], ""] + ([f"_{b[3]}_", ""] if b[3] else [])
    return "\n".join(out)


__all__ = ["gerar_pdf", "gerar_markdown", "pitch_local", "caminho_txt"]
