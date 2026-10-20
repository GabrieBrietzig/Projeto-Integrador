"""Sprint 2 — Caixa-Branca: Grafo de Fluxo de Controle e McCabe V(G)."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from decimal import Decimal

from . import oraculo
from .fonte4gl import (Bin, For, Funcao, If, Interpretador, Let, Return, Un, While,
                       fmt_brl, texto)

COMPOSTO = "composto"   # um nó de decisão por IF (o OR conta uma vez)
SIMPLES = "simples"     # um nó por condição simples (curto-circuito)


@dataclass
class NoGrafo:
    id: int
    tipo: str  # inicio | comando | decisao | fim
    rotulos: list[str] = field(default_factory=list)
    cmds: list = field(default_factory=list)  # nós da árvore 4GL ligados a este nó
    linha: int = 0

    @property
    def nome(self) -> str:
        return f"N{self.id}"

    @property
    def rotulo(self) -> str:
        return "\n".join(self.rotulos)


@dataclass
class Grafo:
    modo: str
    nos: dict[int, NoGrafo]
    arestas: list[tuple[int, int, str]]  # (origem, destino, 'V' | 'F' | '')
    inicio: int
    fim: int
    mapa: dict[int, int]  # uid do comando/condição -> id do nó

    # métricas ----------------------------------------------------------------
    @property
    def N(self) -> int:
        return len(self.nos)

    @property
    def E(self) -> int:
        return len(self.arestas)

    def saidas(self, n: int) -> list[tuple[int, int, str]]:
        return [a for a in self.arestas if a[0] == n]

    def entradas(self, n: int) -> list[tuple[int, int, str]]:
        return [a for a in self.arestas if a[1] == n]

    @property
    def predicativos(self) -> list[int]:
        return [n for n in self.nos if len(self.saidas(n)) > 1]

    @property
    def P(self) -> int:
        return len(self.predicativos)

    @property
    def vg_arestas(self) -> int:
        return self.E - self.N + 2

    @property
    def vg_decisoes(self) -> int:
        # nós com k saídas contam k-1 (para IF binário é 1)
        return sum(len(self.saidas(n)) - 1 for n in self.predicativos) + 1

    @property
    def regioes(self) -> int:
        # Fórmula de Euler para grafo planar conexo: R = E - N + 2 (inclui a região externa)
        return self.E - self.N + 2

    def interpretador(self, f: Funcao) -> Interpretador:
        return Interpretador(f, self.mapa, atomico=self.modo == SIMPLES,
                             no_inicio=self.inicio, no_fim=self.fim)

    def arestas_da_trilha(self, trilha: list[int]) -> set[tuple[int, int]]:
        return set(zip(trilha, trilha[1:]))


# ---------------------------------------------------------------------------
# Construção
# ---------------------------------------------------------------------------


class _Construtor:
    def __init__(self, modo: str):
        self.modo = modo
        self.nos: dict[int, NoGrafo] = {}
        self.arestas: list[tuple[int, int, str]] = []
        self.mapa: dict[int, int] = {}
        self.cont = itertools.count(1)
        self.retornos: list[int] = []

    def novo(self, tipo, rotulo, cmd=None, pend=()):
        n = NoGrafo(next(self.cont), tipo, [rotulo], [cmd] if cmd is not None else [],
                    getattr(cmd, "linha", 0))
        self.nos[n.id] = n
        if cmd is not None:
            self.mapa[cmd.uid] = n.id
        for origem, rot in pend:
            self.arestas.append((origem, n.id, rot))
        return n

    def bloco(self, cmds, pend):
        for c in cmds:
            pend = self.cmd(c, pend)
        return pend

    def cmd(self, c, pend):
        if isinstance(c, Return):
            n = self.novo("comando", texto(c), c, pend)
            self.retornos.append(n.id)
            return []
        if isinstance(c, Let):
            n = self.novo("comando", texto(c), c, pend)
            return [(n.id, "")]
        if isinstance(c, If):
            if self.modo == SIMPLES:
                v, f = self.condicao(c.cond, pend)
            else:
                d = self.novo("decisao", texto(c.cond) + " ?", c, pend)
                v, f = [(d.id, "V")], [(d.id, "F")]
            saida = self.bloco(c.entao, v)
            saida += self.bloco(c.senao, f) if c.senao is not None else f
            return saida
        if isinstance(c, While):
            d = self.novo("decisao", f"WHILE {texto(c.cond)} ?", c, pend)
            corpo = self.bloco(c.corpo, [(d.id, "V")])
            for origem, rot in corpo:
                self.arestas.append((origem, d.id, rot))
            return [(d.id, "F")]
        if isinstance(c, For):
            d = self.novo("decisao", f"{texto(c)} ?", c, pend)
            corpo = self.bloco(c.corpo, [(d.id, "V")])
            for origem, rot in corpo:
                self.arestas.append((origem, d.id, rot))
            return [(d.id, "F")]
        raise ValueError(f"Comando não suportado no GFC: {c}")

    def condicao(self, e, pend):
        """Desdobra AND/OR/NOT em nós de condição simples (curto-circuito)."""
        if isinstance(e, Bin) and e.op == "OR":
            ev, ef = self.condicao(e.esq, pend)
            dv, df = self.condicao(e.dir, ef)
            return ev + dv, df
        if isinstance(e, Bin) and e.op == "AND":
            ev, ef = self.condicao(e.esq, pend)
            dv, df = self.condicao(e.dir, ev)
            return dv, ef + df
        if isinstance(e, Un) and e.op == "NOT":
            v, f = self.condicao(e.expr, pend)
            return f, v
        d = self.novo("decisao", texto(e) + " ?", e, pend)
        return [(d.id, "V")], [(d.id, "F")]


def construir(f: Funcao, modo: str = COMPOSTO, agrupar: bool = False) -> Grafo:
    c = _Construtor(modo)
    ini = c.novo("inicio", f"Início ({', '.join(f.params)})")
    pend = c.bloco(f.corpo, [(ini.id, "")])
    fim = c.novo("fim", "Fim", pend=pend + [(r, "") for r in c.retornos])
    g = Grafo(modo, c.nos, c.arestas, ini.id, fim.id, c.mapa)
    if agrupar:
        g = agrupar_blocos(g)
    return g


def agrupar_blocos(g: Grafo) -> Grafo:
    """Funde comandos sequenciais em um único nó (bloco indivisível)."""
    nos = {k: NoGrafo(v.id, v.tipo, list(v.rotulos), list(v.cmds), v.linha) for k, v in g.nos.items()}
    arestas = list(g.arestas)
    mudou = True
    while mudou:
        mudou = False
        for (a, b, rot) in arestas:
            if nos[a].tipo != "comando" or nos[b].tipo != "comando":
                continue
            if sum(1 for x in arestas if x[0] == a) != 1 or sum(1 for x in arestas if x[1] == b) != 1:
                continue
            nos[a].rotulos += nos[b].rotulos
            nos[a].cmds += nos[b].cmds
            arestas = [x for x in arestas if x != (a, b, rot)]
            arestas = [(a if o == b else o, d, r) for (o, d, r) in arestas]
            del nos[b]
            mudou = True
            break
    novo_id = {old: i for i, old in enumerate(sorted(nos), start=1)}
    nos2 = {}
    for old, n in nos.items():
        n.id = novo_id[old]
        nos2[n.id] = n
    mapa = {}
    for n in nos2.values():
        for cmd in n.cmds:
            mapa[cmd.uid] = n.id
    arestas2 = [(novo_id[o], novo_id[d], r) for (o, d, r) in arestas]
    return Grafo(g.modo, dict(sorted(nos2.items())), arestas2, novo_id[g.inicio], novo_id[g.fim], mapa)


# ---------------------------------------------------------------------------
# Caminhos básicos (método da linha de base de McCabe)
# ---------------------------------------------------------------------------


def _seguir(g: Grafo, inicio: int, escolha: dict[int, str], limite: int = 200) -> list[int]:
    caminho = [inicio]
    atual = inicio
    visitas: dict[int, int] = {}
    while atual != g.fim and len(caminho) < limite:
        saidas = g.saidas(atual)
        if not saidas:
            break
        if len(saidas) == 1:
            prox = saidas[0][1]
        else:
            visitas[atual] = visitas.get(atual, 0) + 1
            rot = escolha.get(atual, "F")
            if visitas[atual] > 1 and rot == "V":
                rot = "F"  # sai do laço na segunda passagem
            prox = next((d for (_, d, r) in saidas if r == rot), saidas[0][1])
        caminho.append(prox)
        atual = prox
    return caminho


def caminhos_basicos(g: Grafo) -> list[list[int]]:
    base = _seguir(g, g.inicio, {})
    caminhos = [base]
    vistos = set(g.arestas_da_trilha(base))
    pendentes = [n for n in base if n in g.predicativos]
    feitos = set()
    while pendentes and len(caminhos) < g.vg_decisoes:
        n = pendentes.pop(0)
        if n in feitos:
            continue
        feitos.add(n)
        for (_, d, rot) in g.saidas(n):
            if (n, d) in vistos:
                continue
            ref = next(c for c in caminhos if n in c)
            prefixo = ref[: ref.index(n) + 1]
            resto = _seguir(g, d, {})
            novo = prefixo + resto
            caminhos.append(novo)
            vistos |= g.arestas_da_trilha(novo)
            pendentes += [x for x in resto if x in g.predicativos and x not in feitos]
            if len(caminhos) >= g.vg_decisoes:
                break
    return caminhos


def _candidatos(n: int):
    """Entradas candidatas, das mais "simples" para as mais combinadas."""
    D = Decimal
    base = [D(2 + i) for i in range(n)]
    pool = [None, D("-0.01"), D("0.00"), D("1.00"), D("100.00")]
    yield tuple(base)
    for k in range(1, min(n, 3) + 1):
        for idx in itertools.combinations(range(n), k):
            for vals in itertools.product(pool, repeat=k):
                t = list(base)
                for i, v in zip(idx, vals):
                    t[i] = v
                yield tuple(t)


def derivar_casos(g: Grafo, f: Funcao, caminhos: list[list[int]]) -> list[dict]:
    """Procura, por execução, uma entrada que percorra cada caminho básico."""
    exe = g.interpretador(f)
    achados: dict[int, tuple] = {}
    alvo = {tuple(c): i for i, c in enumerate(caminhos)}
    for args in _candidatos(len(f.params)):
        r = exe.executar(args)
        i = alvo.get(tuple(r.trilha))
        if i is not None and i not in achados:
            achados[i] = (args, r)
            if len(achados) == len(caminhos):
                break
    casos = []
    for i, cam in enumerate(caminhos):
        cid = f"CT{i + 1:02d}"
        if i in achados:
            args, r = achados[i]
            esp = oraculo.esperado(*args[:3]) if len(args) == 3 else r.texto
            casos.append({
                "id": cid, "caminho": cam, "args": args, "obtido": r.texto,
                "esperado": fmt_brl(esp) if isinstance(esp, Decimal) else str(esp),
                "objetivo": objetivo(args), "executavel": True,
            })
        else:
            casos.append({"id": cid, "caminho": cam, "args": None, "obtido": "—",
                          "esperado": "—", "objetivo": "Caminho não executável (infactível)",
                          "executavel": False})
    return casos


def objetivo(args) -> str:
    partes = []
    for i, a in enumerate(args, start=1):
        if a is None:
            partes.append(f"p{i} NULL")
        elif a < 0:
            partes.append(f"p{i} negativo")
    return ", ".join(partes) if partes else "Cálculo normal"


def caminho_txt(g: Grafo, caminho: list[int]) -> str:
    return " → ".join(f"N{n}" for n in caminho)


def analisar(f: Funcao, modo: str, agrupar: bool = False) -> dict:
    g = construir(f, modo, agrupar)
    caminhos = caminhos_basicos(g)
    casos = derivar_casos(g, f, caminhos)
    cobertas = set()
    for c in casos:
        if c["executavel"]:
            cobertas |= g.arestas_da_trilha(c["caminho"])
    nos_cobertos = {n for c in casos if c["executavel"] for n in c["caminho"]}
    return {
        "grafo": g,
        "casos": casos,
        "arestas_cobertas": len(cobertas),
        "nos_cobertos": len(nos_cobertos),
    }


# ---------------------------------------------------------------------------
# Saída em Graphviz DOT (para st.graphviz_chart)
# ---------------------------------------------------------------------------


def dot(g: Grafo, destaque: list[int] | None = None, tema: dict | None = None) -> str:
    from .tema import CLARO

    p = tema or CLARO
    destaque = destaque or []
    arestas_dest = set(zip(destaque, destaque[1:]))
    linhas = [
        "digraph G {",
        f'  graph [rankdir=TB, nodesep=0.35, ranksep=0.35, bgcolor="{p["g-bg"]}", pad=0.2];',
        f'  node [fontname="Helvetica", fontsize=10, style="rounded,filled", fontcolor="{p["g-text"]}", '
        f'fillcolor="{p["g-cmd"]}", color="{p["g-line"]}", penwidth=1.1];',
        f'  edge [fontname="Helvetica", fontsize=9, color="{p["g-line"]}", fontcolor="{p["g-text"]}"];',
    ]
    for n in g.nos.values():
        rot = f"{n.nome}\\n" + "\\n".join(r.replace('"', "'") for r in n.rotulos)
        forma = f'shape=diamond, style="filled", fillcolor="{p["g-dec"]}"' if n.tipo == "decisao" else "shape=box"
        if n.tipo in ("inicio", "fim"):
            forma = f'shape=box, fillcolor="{p["g-term"]}"'
        cor = f', color="{p["verde"]}", penwidth=2.4' if n.id in destaque else ""
        linhas.append(f'  {n.id} [label="{rot}", {forma}{cor}];')
    for (o, d, r) in g.arestas:
        attrs = [f'label=" {r}"'] if r else []
        if (o, d) in arestas_dest:
            attrs += [f'color="{p["verde"]}"', "penwidth=2.6"]
        linhas.append(f"  {o} -> {d} [{', '.join(attrs)}];")
    linhas.append("}")
    return "\n".join(linhas)
