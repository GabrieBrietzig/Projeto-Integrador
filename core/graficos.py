"""Figuras em matplotlib usadas na tela e no relatório PDF."""
from __future__ import annotations

import functools
import io
import textwrap
from decimal import Decimal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon  # noqa: E402

from .tema import CLARO

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})


def _rc(p: dict) -> dict:
    """Cores do matplotlib a partir da paleta do tema."""
    return {
        "figure.facecolor": p["g-bg"], "axes.facecolor": p["g-bg"], "savefig.facecolor": p["g-bg"],
        "axes.edgecolor": p["g-grid"], "axes.labelcolor": p["g-text"], "text.color": p["g-text"],
        "xtick.color": p["g-muted"], "ytick.color": p["g-muted"],
        "axes.spines.top": False, "axes.spines.right": False,
    }


def _com_tema(funcao):
    """Aceita `tema=` (paleta de core.tema); sem ele usa o tema claro, como no PDF."""
    @functools.wraps(funcao)
    def envolvida(*args, tema: dict | None = None, **kwargs):
        p = tema or CLARO
        with plt.rc_context(_rc(p)):
            return funcao(*args, p=p, **kwargs)
    return envolvida


def png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Sprint 1 — fronteira da AVL
# ---------------------------------------------------------------------------


@_com_tema
def fronteira_avl(casos, eps: Decimal, p: dict = CLARO):
    """Régua da fronteira inferior + barras com o retorno de cada ponto."""
    pontos = [c for c in casos if "sup." not in c.id][:4]
    ordem = ["Exterior", "Off-point", "On-point", "Interior"]
    pontos.sort(key=lambda c: next((i for i, o in enumerate(ordem) if o in c.id), 9))
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.2, 4.6), gridspec_kw={"height_ratios": [1, 1.6]})

    # régua
    ax1.axvspan(-0.5, 1.5, color=p["vermelho"], alpha=0.08)
    ax1.axvspan(1.5, 3.5, color=p["verde"], alpha=0.08)
    ax1.axhline(0, color=p["g-muted"], lw=1)
    ax1.axvline(1.5, color=p["g-text"], lw=1.2, ls="--")
    ax1.text(0.5, 0.62, "Região inválida (< 0,00)", ha="center", color=p["vermelho"], fontsize=9)
    ax1.text(2.5, 0.62, "Região válida (≥ 0,00)", ha="center", color=p["verde"], fontsize=9)
    ax1.text(1.5, -0.85, f"fronteira 0,00  |  ε = {str(eps).replace('.', ',')}", ha="center",
             color=p["g-text"], fontsize=8)
    for i, c in enumerate(pontos):
        valido = "Off" not in c.id and "Exterior" not in c.id
        ax1.scatter(i, 0, s=90, color=p["verde"] if valido else p["vermelho"], zorder=3, edgecolor=p["g-bg"])
        nome = next((o for o in ordem if o in c.id), c.id)
        ax1.text(i, 0.25, f"{nome}\n{c.args_txt()[0]}", ha="center", fontsize=8, color=p["g-text"])
    ax1.set_xlim(-0.5, 3.5)
    ax1.set_ylim(-1, 1)
    ax1.axis("off")

    # barras com o retorno
    nomes, valores, cores = [], [], []
    for c in pontos:
        nomes.append(next((o for o in ordem if o in c.id), c.id))
        try:
            v = float(c.obtido.replace(".", "").replace(",", "."))
        except ValueError:
            v = 0.0
        valores.append(v)
        cores.append(p["verde"] if c.ok else p["vermelho"])
    barras = ax2.bar(nomes, valores, color=cores, width=0.55)
    ax2.axhline(0, color=p["g-muted"], lw=0.8)
    for b, c in zip(barras, pontos):
        y = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2, y + (4 if y >= 0 else -10), c.obtido,
                 ha="center", fontsize=8, color=p["g-text"])
    ax2.set_ylabel("Retorno da função")
    ax2.set_title("Retorno de cada ponto (verde = confere com o oráculo)", fontsize=9, color=p["g-text"], loc="left")
    ax2.set_ylim(min(-20, min(valores) - 15), max(valores) * 1.2 + 10)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Sprint 2 — desenho do GFC
# ---------------------------------------------------------------------------


def _camadas(g) -> dict[int, int]:
    """Camada de cada nó = maior distância a partir do início (ignorando laços)."""
    ordem, estado, retorno = [], {}, set()

    def dfs(n):
        estado[n] = 1
        for (_, d, _) in g.saidas(n):
            if estado.get(d) == 1:
                retorno.add((n, d))
            elif d not in estado:
                dfs(d)
        estado[n] = 2
        ordem.append(n)

    dfs(g.inicio)
    camada = {n: 0 for n in g.nos}
    for n in reversed(ordem):
        for (_, d, _) in g.saidas(n):
            if (n, d) not in retorno:
                camada[d] = max(camada[d], camada[n] + 1)
    return camada, retorno


@_com_tema
def desenhar_gfc(g, destaque: list[int] | None = None, titulo: str = "", p: dict = CLARO):
    destaque = destaque or []
    arestas_dest = set(zip(destaque, destaque[1:]))
    camada, retorno = _camadas(g)
    por_camada: dict[int, list[int]] = {}
    for n in sorted(g.nos):
        por_camada.setdefault(camada[n], []).append(n)
    largura_max = max(len(v) for v in por_camada.values())
    pos = {}
    for c, nos in por_camada.items():
        for i, n in enumerate(nos):
            pos[n] = ((i - (len(nos) - 1) / 2) * 3.2, -c * 1.5)

    altura = max(4, 1.05 * len(por_camada))
    fig, ax = plt.subplots(figsize=(max(5.5, 2.6 * largura_max + 2), altura))
    ax.set_aspect("equal")
    ax.axis("off")

    def caixa(n):
        no = g.nos[n]
        largura = 24 if no.tipo == "decisao" else 30
        linhas = [ln for r in no.rotulos for ln in textwrap.wrap(r, largura)][:4]
        rot = f"N{n}\n" + "\n".join(linhas)
        x, y = pos[n]
        borda = p["verde"] if n in destaque else p["g-line"]
        lw = 2.2 if n in destaque else 1
        if no.tipo == "decisao":
            w, h = 2.9, 0.95
            ax.add_patch(Polygon([(x - w / 2, y), (x, y + h / 2), (x + w / 2, y), (x, y - h / 2)],
                                 closed=True, fc=p["g-dec"], ec=borda, lw=lw, zorder=2))
        else:
            w, h = 2.6, 0.42 + 0.2 * len(linhas)
            fc = p["g-term"] if no.tipo in ("inicio", "fim") else p["g-cmd"]
            ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.15",
                                        fc=fc, ec=borda, lw=lw, zorder=2))
        ax.text(x, y, rot, ha="center", va="center", fontsize=6.6, color=p["g-text"], zorder=3, linespacing=1.15)
        return w, h

    tamanhos = {n: caixa(n) for n in g.nos}

    for (o, d, r) in g.arestas:
        (x1, y1), (x2, y2) = pos[o], pos[d]
        h1, h2 = tamanhos[o][1], tamanhos[d][1]
        cor = p["verde"] if (o, d) in arestas_dest else p["g-line"]
        lw = 2 if (o, d) in arestas_dest else 0.9
        if (o, d) in retorno:  # aresta de volta do laço
            ax.annotate("", xy=(x2 - 1.4, y2), xytext=(x1 - 1.3, y1),
                        arrowprops=dict(arrowstyle="-|>", color=cor, lw=lw, connectionstyle="arc3,rad=-0.5"))
        else:
            salto = camada[d] - camada[o]
            estilo = "arc3,rad=0" if salto <= 1 else f"arc3,rad={0.35 if x2 <= x1 else -0.35}"
            ax.annotate("", xy=(x2, y2 + h2 / 2), xytext=(x1, y1 - h1 / 2),
                        arrowprops=dict(arrowstyle="-|>", color=cor, lw=lw, shrinkA=0, shrinkB=1,
                                        connectionstyle=estilo))
        if r:
            ax.text(x1 + (x2 - x1) * 0.3 + (0.15 if x2 >= x1 else -0.15), y1 - h1 / 2 + (y2 + h2 / 2 - y1 + h1 / 2) * 0.3,
                    r, fontsize=7, color=p["verde"] if r == "V" else p["vermelho"], fontweight="bold")

    xs = [xy[0] for xy in pos.values()]
    ys = [xy[1] for xy in pos.values()]
    ax.set_xlim(min(xs) - 2.2, max(xs) + 2.2)
    ax.set_ylim(min(ys) - 0.9, max(ys) + 0.9)
    if titulo:
        ax.set_title(titulo, fontsize=10, color=p["g-text"])
    return fig


# ---------------------------------------------------------------------------
# Sprint 3 — cobertura de dados e escore de mutação
# ---------------------------------------------------------------------------


@_com_tema
def criterios_du(criterios: dict[str, tuple[int, int]], p: dict = CLARO):
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    nomes = list(criterios)
    pct = [c / t * 100 if t else 0 for c, t in criterios.values()]
    barras = ax.barh(nomes, pct, color=[p["verde"] if v == 100 else p["ambar"] for v in pct], height=0.5)
    for b, (c, t) in zip(barras, criterios.values()):
        ax.text(b.get_width() + 1, b.get_y() + b.get_height() / 2, f"{c}/{t}", va="center", fontsize=8)
    ax.set_xlim(0, 115)
    ax.invert_yaxis()
    ax.set_xlabel("% de cobertura")
    ax.set_title("Critérios de Rapps & Weyuker", fontsize=9, loc="left", color=p["g-text"])
    fig.tight_layout()
    return fig


@_com_tema
def ms_por_suite(linhas: list[dict], p: dict = CLARO):
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    nomes = [l["Suíte"] for l in linhas]
    vals = [l["MS"] * 100 for l in linhas]
    barras = ax.bar(nomes, vals, color=[p["verde"] if v == 100 else p["azul"] for v in vals], width=0.55)
    for b, v, l in zip(barras, vals, linhas):
        ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.1f}%\n({l['Casos']} CTs)", ha="center", fontsize=7.5)
    ax.set_ylim(0, 125)
    ax.set_ylabel("MS (%)")
    ax.set_title("Escore de Mutação por suíte de testes", fontsize=9, loc="left", color=p["g-text"])
    plt.setp(ax.get_xticklabels(), fontsize=8)
    fig.tight_layout()
    return fig
