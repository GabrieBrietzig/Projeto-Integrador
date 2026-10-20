"""Executa as quatro Sprints sobre um código-fonte e reúne tudo em um dicionário."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import caixa_preta, fluxo_dados, gfc, mutacao, validacao
from .caixa_preta import CasoTeste
from .fonte4gl import ler_funcao

DADOS = Path(__file__).resolve().parents[1] / "dados"
ARQ_ORIGINAL = DADOS / "cad0001_item_calculo.txt"
ARQ_MANUAL = DADOS / "cad0001_manual.4gl"


@dataclass(frozen=True)
class Opcoes:
    agrupar_blocos: bool = False
    modo_fluxo: str = gfc.COMPOSTO
    operadores: tuple = tuple(mutacao.OPERADORES)
    equivalentes: frozenset = frozenset()


def versoes_referencia() -> dict[str, str]:
    refs = {}
    if ARQ_MANUAL.exists():
        refs["Especificação do manual (Sprint 1)"] = ARQ_MANUAL.read_text(encoding="utf-8")
    if ARQ_ORIGINAL.exists():
        refs["Fonte original (cad0001_item_calculo.txt)"] = ARQ_ORIGINAL.read_text(encoding="utf-8")
    return refs


def _caso_de_caminho(prefixo: str, grupo: str, c: dict) -> CasoTeste:
    return CasoTeste(f"{prefixo}-{c['id']}", grupo, c["objetivo"], c["args"])


def analisar(codigo: str, nome_funcao: str | None, op: Opcoes = Opcoes()) -> dict:
    f = ler_funcao(codigo, nome_funcao)

    # Sprint 1 ---------------------------------------------------------------
    s1 = caixa_preta.analisar(f)

    # Sprint 2 ---------------------------------------------------------------
    g1 = gfc.analisar(f, gfc.COMPOSTO, op.agrupar_blocos)
    g2 = gfc.analisar(f, gfc.SIMPLES, op.agrupar_blocos)

    casos_g1 = [_caso_de_caminho("GFC1", "Caminhos GFC 1", c) for c in g1["casos"] if c["executavel"]]
    casos_g2 = [_caso_de_caminho("GFC2", "Caminhos GFC 2", c) for c in g2["casos"] if c["executavel"]]
    suite: list[CasoTeste] = s1["casos_pce"] + s1["casos_avl"] + s1["casos_cmb"]
    if len(f.params) == 3:
        caixa_preta.avaliar(f, casos_g1 + casos_g2)
    suite += casos_g1 + casos_g2

    # Sprint 3 — fluxo de dados -----------------------------------------------
    gd = g1 if op.modo_fluxo == gfc.COMPOSTO else g2
    exe = gd["grafo"].interpretador(f)
    trilhas = {c.id: exe.executar(c.args).trilha for c in suite}
    s3_du = fluxo_dados.analisar(gd["grafo"], f, trilhas)
    casos_du = [CasoTeste(s["id"], "Fluxo de dados", s["objetivo"] + " — cobre " + "; ".join(s["pares"]), s["args"])
                for s in s3_du["sugestoes"]]
    if casos_du and len(f.params) == 3:
        caixa_preta.avaliar(f, casos_du)
        for c in casos_du:
            trilhas[c.id] = exe.executar(c.args).trilha
        s3_du = fluxo_dados.analisar(gd["grafo"], f, trilhas)
        s3_du["sugestoes_aplicadas"] = casos_du
    suite += casos_du

    # Sprint 3 — mutação ---------------------------------------------------------
    mutantes = mutacao.gerar(f, op.operadores)
    todos = {c.id: c.args for c in suite}
    resumo_mut = mutacao.executar(f, mutantes, todos, set(op.equivalentes))
    suites = {
        "Só AVL": {c.id: c.args for c in s1["casos_avl"]},
        "Só PCE": {c.id: c.args for c in s1["casos_pce"]},
        "Caminhos GFC 1": {c.id: c.args for c in casos_g1},
        "Caminhos GFC 2": {c.id: c.args for c in casos_g2},
        "Suíte completa": todos,
    }
    ms_suites = mutacao.ms_por_suite(f, mutantes, suites, set(op.equivalentes))

    # Sprint 4 — validação -------------------------------------------------------
    versoes = {"Fonte em análise": f}
    for nome, cod in versoes_referencia().items():
        if cod.strip() != codigo.strip():
            try:
                versoes[nome] = ler_funcao(cod, nome_funcao)
            except Exception:
                pass
    val = validacao.validar_versoes(versoes, suite) if len(f.params) == 3 else {}
    rtm = validacao.montar_rtm(suite)

    metricas = {
        "casos": len(suite),
        "aprovados": sum(1 for c in suite if c.ok),
        "epsilon": s1["epsilon"],
        "vg1": g1["grafo"].vg_arestas,
        "vg2": g2["grafo"].vg_arestas,
        "pares_du": len(s3_du["pares"]),
        "pares_du_cobertos": sum(1 for p in s3_du["pares"] if p.coberto),
        "mutantes": resumo_mut["total"],
        "mortos": resumo_mut["mortos"],
        "ms": resumo_mut["ms"],
        "rtm": validacao.cobertura_rtm(rtm),
    }
    return {
        "funcao": f, "codigo": codigo, "opcoes": op,
        "s1": s1, "g1": g1, "g2": g2,
        "du": s3_du, "grafo_du": gd["grafo"],
        "mutantes": mutantes, "mutacao": resumo_mut, "ms_suites": ms_suites,
        "suite": suite, "rtm": rtm, "validacao": val, "metricas": metricas,
    }
