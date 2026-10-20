"""Tabelas (listas de dicionários) usadas na tela e no relatório."""
from __future__ import annotations

from .fonte4gl import fmt_brl
from .gfc import Grafo, caminho_txt
from .mutacao import descricao_acao


def _args(args, params):
    return {p: ("NULL" if a is None else fmt_brl(a)) for p, a in zip(params, args)}


def casos(lista, params, com_req: bool = True) -> list[dict]:
    linhas = []
    for c in lista:
        d = {"Caso": c.id, "Descrição": c.descricao, **_args(c.args, params),
             "Esperado (oráculo)": c.esperado_txt, "Obtido": c.obtido,
             "Situação": "✔ OK" if c.ok else "✘ FALHA"}
        if com_req:
            d["Requisitos"] = ", ".join(c.requisitos)
        linhas.append(d)
    return linhas


def avl_param(lista, param, params) -> list[dict]:
    linhas = []
    for c in lista:
        if f"-{param}-" not in c.id:
            continue
        ponto = c.id.split(f"-{param}-", 1)[1]
        linhas.append({"Ponto": ponto, **_args(c.args, params), "Esperado": c.esperado_txt,
                       "Obtido": c.obtido, "Situação": "Cálculo OK" if c.esperado_txt not in ("-1,00", "ESTOURO") else
                       ("Erro (-1)" if c.esperado_txt == "-1,00" else "Estouro do tipo"),
                       "Confere": "✔" if c.ok else "✘"})
    return linhas


def nos(g: Grafo) -> list[dict]:
    tipos = {"inicio": "Início", "comando": "Comando", "decisao": "Decisão (predicativo)", "fim": "Fim"}
    return [{"Nó": n.nome, "Comando(s)": " ; ".join(n.rotulos), "Tipo": tipos[n.tipo]}
            for n in g.nos.values()]


def arestas(g: Grafo) -> list[dict]:
    return [{"Origem": f"N{o}", "Destino": f"N{d}", "Desvio": r or "Sequência"}
            for (o, d, r) in g.arestas]


def metricas_mccabe(g: Grafo) -> list[dict]:
    return [
        {"Fórmula": "V(G) = E − N + 2", "Conta": f"{g.E} − {g.N} + 2", "Resultado": g.vg_arestas},
        {"Fórmula": "V(G) = P + 1", "Conta": f"{g.P} + 1", "Resultado": g.vg_decisoes},
        {"Fórmula": "V(G) = R (regiões, com a externa)", "Conta": f"R = {g.regioes}", "Resultado": g.regioes},
    ]


def caminhos(g: Grafo, lista: list[dict], params) -> list[dict]:
    linhas = []
    for c in lista:
        d = {"Teste": c["id"], "Objetivo": c["objetivo"]}
        if c["args"] is not None:
            d.update(_args(c["args"], params))
        else:
            d.update({p: "—" for p in params})
        d.update({"Esperado": c["esperado"], "Obtido": c["obtido"], "Caminho": caminho_txt(g, c["caminho"])})
        linhas.append(d)
    return linhas


def anotacoes(anot) -> list[dict]:
    return [{"Nó": f"N{n}", "def": ", ".join(a.defs) or "—", "c-uso": ", ".join(a.cusos) or "—",
             "p-uso": ", ".join(a.pusos) or "—"} for n, a in anot.items()]


def pares(lista) -> list[dict]:
    return [{"Variável": p.var, "Def (nó)": f"N{p.defn}", "Uso": p.uso_txt, "Tipo": p.tipo,
             "Coberto": "✔" if p.coberto else "✘",
             "Coberto por": ", ".join(p.cobertos_por[:4]) + (" …" if len(p.cobertos_por) > 4 else "")}
            for p in lista]


def criterios(c: dict) -> list[dict]:
    return [{"Critério": k, "Cobertos": a, "Total": b, "Cobertura": f"{(a / b * 100 if b else 0):.1f}%"}
            for k, (a, b) in c.items()]


def mutantes(lista) -> list[dict]:
    return [{"Mutante": m.id, "Operador": m.operador, "Linha": m.linha, "Original": m.original,
             "Mutante (código)": m.mutado, "Alteração": descricao_acao(m), "Status": m.status,
             "Morto por": ", ".join(m.morto_por[:3]) + (" …" if len(m.morto_por) > 3 else "")}
            for m in lista]


def por_operador(resumo: dict) -> list[dict]:
    linhas = []
    for op, d in sorted(resumo["por_operador"].items()):
        base = d["Total"] - d["Equivalentes"]
        linhas.append({"Operador": op, **d, "MS": f"{(d['Mortos'] / base * 100 if base else 0):.1f}%"})
    return linhas


def ms_suites(linhas) -> list[dict]:
    return [{**l, "MS": f"{l['MS'] * 100:.1f}%"} for l in linhas]


def rtm(linhas) -> list[dict]:
    return [{k: l[k] for k in ("Requisito", "Descrição", "CTs", "Passaram", "Falharam", "Status")}
            for l in linhas]


def matriz_rtm(suite, reqs) -> tuple[list[str], list[list[str]]]:
    """Matriz requisito × grupo de casos (contagem de CTs)."""
    grupos = list(dict.fromkeys(c.grupo for c in suite))
    linhas = []
    for r in reqs:
        linha = [r]
        for gname in grupos:
            n = sum(1 for c in suite if c.grupo == gname and r in c.requisitos)
            linha.append(str(n) if n else "·")
        linhas.append(linha)
    return ["Requisito", *grupos], linhas


def markdown(linhas: list[dict]) -> str:
    if not linhas:
        return "_(sem linhas)_"
    cab = list(linhas[0])
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for l in linhas:
        out.append("| " + " | ".join(str(l[c]).replace("|", "/") for c in cab) + " |")
    return "\n".join(out)
