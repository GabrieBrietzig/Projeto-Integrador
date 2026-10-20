"""Sprint 3 (parte 1) — Teste de Fluxo de Dados: pares Def-Uso (Rapps & Weyuker)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .fonte4gl import For, Funcao, If, Let, Return, While, variaveis
from .gfc import Grafo


@dataclass
class Anotacao:
    defs: list[str] = field(default_factory=list)
    cusos: list[str] = field(default_factory=list)
    pusos: list[str] = field(default_factory=list)


@dataclass
class ParDU:
    var: str
    defn: int
    uso: object  # int (c-uso, nó) ou tuple (p-uso, aresta)
    tipo: str    # 'c-uso' | 'p-uso'
    cobertos_por: list[str] = field(default_factory=list)

    @property
    def uso_txt(self) -> str:
        if self.tipo == "p-uso":
            return f"(N{self.uso[0]}, N{self.uso[1]})"
        return f"N{self.uso}"

    @property
    def coberto(self) -> bool:
        return bool(self.cobertos_por)


def anotar(g: Grafo, f: Funcao) -> dict[int, Anotacao]:
    anot = {n: Anotacao() for n in g.nos}
    anot[g.inicio].defs = list(f.params)
    for n, no in g.nos.items():
        a = anot[n]
        definidas: set[str] = set()
        for c in no.cmds:
            if isinstance(c, Let):
                for v in variaveis(c.expr):
                    if v not in definidas and v not in a.cusos:
                        a.cusos.append(v)
                definidas.add(c.alvo)
                if c.alvo not in a.defs:
                    a.defs.append(c.alvo)
            elif isinstance(c, Return):
                for e in c.exprs:
                    for v in variaveis(e):
                        if v not in definidas and v not in a.cusos:
                            a.cusos.append(v)
            elif isinstance(c, (If, While)):
                a.pusos += [v for v in variaveis(c.cond) if v not in a.pusos]
            elif isinstance(c, For):
                a.defs.append(c.var)
                a.cusos += [v for v in variaveis(c.inicio) if v not in a.cusos]
                a.pusos += [v for v in [c.var, *variaveis(c.fim)] if v not in a.pusos]
            else:  # condição simples (GFC por condições)
                a.pusos += [v for v in variaveis(c) if v not in a.pusos]
    return anot


def pares_du(g: Grafo, anot: dict[int, Anotacao]) -> list[ParDU]:
    pares: list[ParDU] = []
    for d in g.nos:
        for v in anot[d].defs:
            vistos: set[int] = set()
            fila = [dst for (_, dst, _) in g.saidas(d)]
            while fila:
                n = fila.pop(0)
                if n in vistos:
                    continue
                vistos.add(n)
                if v in anot[n].cusos:
                    pares.append(ParDU(v, d, n, "c-uso"))
                if v in anot[n].pusos:
                    for (_, m, _) in g.saidas(n):
                        pares.append(ParDU(v, d, (n, m), "p-uso"))
                if v in anot[n].defs:
                    continue  # caminho deixa de ser livre de definição
                fila += [dst for (_, dst, _) in g.saidas(n)]
    pares.sort(key=lambda p: (p.var, p.defn, p.tipo, str(p.uso)))
    return pares


def _cobre(trilha: list[int], par: ParDU, anot) -> bool:
    for i, n in enumerate(trilha):
        if n != par.defn:
            continue
        for j in range(i + 1, len(trilha)):
            atual = trilha[j]
            if par.tipo == "c-uso" and atual == par.uso:
                return True
            if par.tipo == "p-uso" and atual == par.uso[0] and j + 1 < len(trilha) and trilha[j + 1] == par.uso[1]:
                return True
            if par.var in anot[atual].defs:
                break
    return False


def sugerir_casos(g: Grafo, f: Funcao, anot, pares: list[ParDU], limite: int = 20) -> list[dict]:
    """Busca, por execução, entradas que cubram os pares DU ainda não cobertos."""
    from .gfc import _candidatos, objetivo

    faltam = [p for p in pares if not p.coberto]
    if not faltam:
        return []
    exe = g.interpretador(f)
    sugestoes = []
    for args in _candidatos(len(f.params)):
        if not faltam or len(sugestoes) >= limite:
            break
        r = exe.executar(args)
        novos = [p for p in faltam if _cobre(r.trilha, p, anot)]
        if novos:
            cid = f"DU{len(sugestoes) + 1:02d}"
            sugestoes.append({"id": cid, "args": args, "trilha": r.trilha, "obtido": r.texto,
                              "objetivo": objetivo(args),
                              "pares": [f"{p.var}: N{p.defn} → {p.uso_txt}" for p in novos]})
            faltam = [p for p in faltam if p not in novos]
    return sugestoes


def analisar(g: Grafo, f: Funcao, trilhas: dict[str, list[int]]) -> dict:
    anot = anotar(g, f)
    pares = pares_du(g, anot)
    for p in pares:
        p.cobertos_por = [cid for cid, t in trilhas.items() if _cobre(t, p, anot)]

    defs = [(d, v) for d in g.nos for v in anot[d].defs]
    defs_com_par = {(p.defn, p.var) for p in pares}
    defs_cobertas = {(p.defn, p.var) for p in pares if p.coberto}
    sem_uso = [(d, v) for (d, v) in defs if (d, v) not in defs_com_par]

    def pct(itens):
        itens = list(itens)
        return (sum(1 for p in itens if p.coberto), len(itens))

    criterios = {
        "Todas-Definições": (len(defs_cobertas), len(defs_com_par)),
        "Todos-c-Usos": pct(p for p in pares if p.tipo == "c-uso"),
        "Todos-p-Usos": pct(p for p in pares if p.tipo == "p-uso"),
        "Todos-Usos": pct(pares),
    }
    sugestoes = sugerir_casos(g, f, anot, pares)
    return {"anotacoes": anot, "pares": pares, "criterios": criterios,
            "defs_sem_uso": sem_uso, "sugestoes": sugestoes}
