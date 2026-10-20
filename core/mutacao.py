"""Sprint 3 (parte 2) — Teste de Mutação e Escore de Mutação (MS).

Cada mutante é uma cópia da função com UMA pequena alteração sintática
(hipótese do programador competente). Um mutante é "morto" quando algum caso
de teste produz saída diferente da do programa original.

    MS = mutantes mortos / (total de mutantes − equivalentes)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from .fonte4gl import (ARITMETICOS, RELACIONAIS, Bin, EhNulo, For, Funcao, If, Interpretador,
                       Let, Num, Return, Var, While, clonar, fmt_num, percorrer, texto)

OPERADORES = {
    "ROR": "Relacional (< ↔ <=, >, >=, =, <>)",
    "AOR": "Aritmético (+ ↔ -, *, /)",
    "COR": "Conector lógico (AND ↔ OR)",
    "NUL": "Teste de nulo (IS NULL ↔ IS NOT NULL)",
    "CRP": "Troca de constante (c → c+1, c−1, 0)",
    "SDL": "Remoção de comando (LET/RETURN)",
    "LVR": "Troca de variável local (p_val1 → p_val2)",
}


@dataclass
class Mutante:
    id: str
    operador: str
    linha: int
    original: str
    mutado: str
    uid: int
    acao: tuple
    status: str = "Vivo"
    morto_por: list[str] = field(default_factory=list)
    equivalente: bool = False


def _expressoes(c):
    if isinstance(c, Let):
        return [c.expr]
    if isinstance(c, Return):
        return list(c.exprs)
    if isinstance(c, (If, While)):
        return [c.cond]
    if isinstance(c, For):
        return [c.inicio, c.fim]
    return []


def _comandos(cmds):
    for c in cmds:
        yield c
        if isinstance(c, If):
            yield from _comandos(c.entao)
            yield from _comandos(c.senao or [])
        elif isinstance(c, (While, For)):
            yield from _comandos(c.corpo)


def _familia(nome: str) -> str:
    return re.sub(r"\d+$", "", nome)


def _variaveis_da_funcao(f: Funcao) -> list[str]:
    nomes = list(f.params) + list(f.tipos)
    for n in percorrer(f.corpo):
        if isinstance(n, Let) and n.alvo not in nomes:
            nomes.append(n.alvo)
    return nomes


def _aplicar(f: Funcao, uid: int, acao: tuple) -> Funcao:
    m = clonar(f)
    if acao[0] == "SDL":
        def remover(cmds):
            for i, c in enumerate(cmds):
                if c.uid == uid:
                    del cmds[i]
                    return True
                if isinstance(c, If) and (remover(c.entao) or remover(c.senao or [])):
                    return True
                if isinstance(c, (While, For)) and remover(c.corpo):
                    return True
            return False
        remover(m.corpo)
        return m
    alvo = next(n for n in percorrer(m.corpo) if n.uid == uid)
    tipo, valor = acao
    if tipo == "op":
        alvo.op = valor
    elif tipo == "nulo":
        alvo.negado = not alvo.negado
    elif tipo == "num":
        alvo.valor = valor
    elif tipo == "var":
        alvo.nome = valor
    return m


def _cmd_por_uid(f: Funcao, uid: int):
    return next((c for c in _comandos(f.corpo) if c.uid == uid), None)


def gerar(f: Funcao, operadores=tuple(OPERADORES)) -> list[Mutante]:
    variaveis = _variaveis_da_funcao(f)
    brutos = []  # (operador, comando, uid, acao)
    for c in _comandos(f.corpo):
        if "SDL" in operadores and isinstance(c, (Let, Return)):
            brutos.append(("SDL", c, c.uid, ("SDL", None)))
        for e in _expressoes(c):
            for n in percorrer(e):
                if isinstance(n, Bin) and n.op in RELACIONAIS and "ROR" in operadores:
                    brutos += [("ROR", c, n.uid, ("op", op)) for op in RELACIONAIS if op != n.op]
                elif isinstance(n, Bin) and n.op in ARITMETICOS and "AOR" in operadores:
                    brutos += [("AOR", c, n.uid, ("op", op)) for op in ARITMETICOS if op != n.op]
                elif isinstance(n, Bin) and n.op in ("AND", "OR") and "COR" in operadores:
                    brutos.append(("COR", c, n.uid, ("op", "AND" if n.op == "OR" else "OR")))
                elif isinstance(n, EhNulo) and "NUL" in operadores:
                    brutos.append(("NUL", c, n.uid, ("nulo", None)))
                elif isinstance(n, Num) and "CRP" in operadores:
                    novos = {n.valor + 1, n.valor - 1}
                    if n.valor != 0:
                        novos.add(Decimal(0))
                    brutos += [("CRP", c, n.uid, ("num", v)) for v in sorted(novos)]
                elif isinstance(n, Var) and "LVR" in operadores:
                    fam = _familia(n.nome)
                    for outra in variaveis:
                        if outra != n.nome and _familia(outra) == fam:
                            brutos.append(("LVR", c, n.uid, ("var", outra)))

    mutantes = []
    for i, (op, cmd, uid, acao) in enumerate(brutos, start=1):
        m = _aplicar(f, uid, acao)
        original = texto(cmd)
        novo_cmd = _cmd_por_uid(m, cmd.uid)
        mutado = "(comando removido)" if novo_cmd is None else texto(novo_cmd)
        mutantes.append(Mutante(f"M{i:02d}", op, cmd.linha, original, mutado, uid, acao))
    return mutantes


def executar(f: Funcao, mutantes: list[Mutante], casos: dict[str, tuple],
             equivalentes: set[str] = frozenset()) -> dict:
    """Roda a suíte em cada mutante. `casos` = {id do CT: argumentos}."""
    original = Interpretador(f)
    saidas = {cid: original.executar(args).chave() for cid, args in casos.items()}
    for mt in mutantes:
        exe = Interpretador(_aplicar(f, mt.uid, mt.acao))
        mt.morto_por = [cid for cid, args in casos.items() if exe.executar(args).chave() != saidas[cid]]
        mt.equivalente = mt.id in equivalentes and not mt.morto_por
        mt.status = "Morto" if mt.morto_por else ("Equivalente" if mt.equivalente else "Vivo")
    return resumo(mutantes)


def resumo(mutantes: list[Mutante]) -> dict:
    total = len(mutantes)
    mortos = sum(1 for m in mutantes if m.status == "Morto")
    equiv = sum(1 for m in mutantes if m.status == "Equivalente")
    vivos = total - mortos - equiv
    base = total - equiv
    ms = mortos / base if base else 0.0
    por_op = {}
    for m in mutantes:
        d = por_op.setdefault(m.operador, {"Total": 0, "Mortos": 0, "Vivos": 0, "Equivalentes": 0})
        d["Total"] += 1
        d["Mortos" if m.status == "Morto" else "Equivalentes" if m.status == "Equivalente" else "Vivos"] += 1
    return {"total": total, "mortos": mortos, "vivos": vivos, "equivalentes": equiv,
            "ms": ms, "por_operador": por_op}


def ms_por_suite(f: Funcao, mutantes: list[Mutante], suites: dict[str, dict[str, tuple]],
                 equivalentes: set[str] = frozenset()) -> list[dict]:
    """Mostra como o MS sobe conforme a suíte fica mais rigorosa."""
    linhas = []
    for nome, casos in suites.items():
        copia = [Mutante(m.id, m.operador, m.linha, m.original, m.mutado, m.uid, m.acao) for m in mutantes]
        r = executar(f, copia, casos, equivalentes)
        linhas.append({"Suíte": nome, "Casos": len(casos), "Mortos": r["mortos"],
                       "Vivos": r["vivos"], "MS": r["ms"]})
    return linhas


def descricao_acao(m: Mutante) -> str:
    tipo, valor = m.acao
    if tipo == "num":
        return f"constante → {fmt_num(valor)}"
    if tipo in ("op", "var"):
        return f"→ {valor}"
    if tipo == "nulo":
        return "IS NULL ↔ IS NOT NULL"
    return "remove o comando"
