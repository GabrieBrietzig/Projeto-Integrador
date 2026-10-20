"""Testes do próprio TestingStudio (o auditor também é testado)."""
from decimal import Decimal
from pathlib import Path

import pytest

from core import analise, caixa_preta, fluxo_dados, gfc, mutacao, oraculo, validacao
from core.fonte4gl import ErroSintaxe, executar, ler_funcao, listar_funcoes

DADOS = Path(__file__).resolve().parents[1] / "dados"
MANUAL = (DADOS / "cad0001_manual.4gl").read_text(encoding="utf-8")
ORIGINAL = (DADOS / "cad0001_item_calculo.txt").read_text(encoding="utf-8")
D = Decimal


@pytest.fixture(scope="module")
def f_manual():
    return ler_funcao(MANUAL, "cad0001_calcula_valor")


@pytest.fixture(scope="module")
def f_original():
    return ler_funcao(ORIGINAL, "cad0001_calcula_valor")


# --- leitura e execução do 4GL ----------------------------------------------

def test_lista_funcoes_do_arquivo_original():
    assert listar_funcoes(ORIGINAL) == ["cad0001_main", "cad0001_calcula_valor", "cad0001_incluir",
                                        "cad0001_alterar", "cad0001_excluir"]


@pytest.mark.parametrize("args, esperado", [
    ((D("2"), D("3"), D("4")), D("10.00")),
    ((None, D("3"), D("4")), D("4.00")),
    ((D("-0.01"), D("1"), D("0")), D("-1")),
    ((D("0.05"), D("0.10"), D("0")), D("0.01")),  # arredonda para o centavo
])
def test_interpretador_manual(f_manual, args, esperado):
    assert executar(f_manual, args).valor == esperado


def test_estouro_decimal(f_manual):
    r = executar(f_manual, (oraculo.MAXIMO, D("1"), D("0.01")))
    assert r.erro and "ESTOURO" in r.erro


def test_erro_de_sintaxe():
    with pytest.raises(ErroSintaxe):
        ler_funcao("FUNCTION x(a)\n IF a THEN\n LET b = 1\nEND FUNCTION")


# --- Sprint 1 -------------------------------------------------------------------

def test_epsilon_decimal_12_2(f_manual):
    s1 = caixa_preta.analisar(f_manual)
    assert s1["epsilon"] == D("0.01")
    assert s1["maximo"] == D("9999999999.99")
    assert all(c.ok for c in s1["casos_avl"] + s1["casos_pce"] + s1["casos_cmb"])


def test_oraculo_revela_defeito_no_original(f_original):
    s1 = caixa_preta.analisar(f_original)
    off = next(c for c in s1["casos_avl"] if c.id == "AVL-p_val1-Off-point")
    assert off.obtido == "-0,01" and off.ok is False


# --- Sprint 2 -------------------------------------------------------------------

@pytest.mark.parametrize("modo, N, E, P, VG", [(gfc.COMPOSTO, 15, 18, 4, 5), (gfc.SIMPLES, 17, 22, 6, 7)])
def test_mccabe_igual_ao_exemplo(f_manual, modo, N, E, P, VG):
    a = gfc.analisar(f_manual, modo)
    g = a["grafo"]
    assert (g.N, g.E, g.P) == (N, E, P)
    assert g.vg_arestas == g.vg_decisoes == g.regioes == VG
    assert len(a["casos"]) == VG and all(c["executavel"] for c in a["casos"])
    assert a["arestas_cobertas"] == E


def test_agrupar_blocos_preserva_vg(f_manual):
    g = gfc.construir(f_manual, gfc.COMPOSTO, agrupar=True)
    assert g.N == 14 and g.vg_arestas == 5


def test_laco_while():
    f = ler_funcao("FUNCTION t(n)\n DEFINE i INTEGER\n LET i = 0\n WHILE i < n\n LET i = i + 1\n END WHILE\n RETURN i\nEND FUNCTION")
    g = gfc.construir(f)
    assert g.vg_arestas == 2
    assert executar(f, (D(3),)).valor == D(3)


# --- Sprint 3 -------------------------------------------------------------------

def test_pares_du(f_manual):
    g = gfc.construir(f_manual)
    anot = fluxo_dados.anotar(g, f_manual)
    pares = fluxo_dados.pares_du(g, anot)
    assert len(pares) == 28
    assert any(p.var == "l_val_calculado" and p.defn == 13 and p.uso == 14 for p in pares)


def test_mutacao_ms_completo(f_manual):
    a = analise.analisar(MANUAL, "cad0001_calcula_valor")
    assert a["mutacao"]["total"] == 73
    assert a["mutacao"]["ms"] == 1.0
    so_avl = next(l for l in a["ms_suites"] if l["Suíte"] == "Só AVL")
    assert so_avl["MS"] < 1.0  # AVL sozinha não mata a troca de * por /


def test_mutante_ror_morto_pelo_on_point(f_manual):
    ms = [m for m in mutacao.gerar(f_manual, ("ROR",)) if "p_val1 <= 0" in m.mutado]
    assert len(ms) == 1
    mutacao.executar(f_manual, ms, {"interior": (D("100"), D("1"), D("0"))})
    assert ms[0].status == "Vivo"  # só o interior não distingue < de <=
    mutacao.executar(f_manual, ms, {"on-point": (D("0"), D("1"), D("0"))})
    assert ms[0].status == "Morto"  # o on-point 0,00 mata


# --- Sprint 4 -------------------------------------------------------------------

def test_rtm_valida_manual_e_reprova_original():
    a = analise.analisar(MANUAL, "cad0001_calcula_valor")
    status = {n: {l["Requisito"]: l["Status"] for l in v["rtm"]} for n, v in a["validacao"].items()}
    assert set(status["Fonte em análise"].values()) <= {"Validado", "Fora do escopo"}
    orig = status["Fonte original (cad0001_item_calculo.txt)"]
    assert orig["REQ03"] == "Falhou" and orig["REQ02"] == "Validado"


def test_pytest_gerado_roda(tmp_path):
    a = analise.analisar(MANUAL, "cad0001_calcula_valor")
    arq = validacao.gerar_pytest(MANUAL, "cad0001_calcula_valor", a["suite"], tmp_path)
    # o arquivo gerado usa parents[1] como raiz; aqui só validamos a sintaxe gerada
    compile(arq.read_text(encoding="utf-8"), str(arq), "exec")


# --- interface: gráficos nos dois temas ---------------------------------------------

@pytest.mark.parametrize("escuro", [False, True])
def test_graficos_nos_dois_temas(escuro):
    from core import graficos, tema

    a = analise.analisar(MANUAL, "cad0001_calcula_valor")
    p = tema.paleta(escuro)
    figuras = [
        graficos.fronteira_avl(a["s1"]["casos_avl"][:4], a["s1"]["epsilon"], tema=p),
        graficos.desenhar_gfc(a["g2"]["grafo"], tema=p),
        graficos.criterios_du(a["du"]["criterios"], tema=p),
        graficos.ms_por_suite(a["ms_suites"], tema=p),
    ]
    assert all(graficos.png(fig).startswith(b"\x89PNG") for fig in figuras)
    assert f'bgcolor="{p["g-bg"]}"' in gfc.dot(a["g1"]["grafo"], tema=p)


# --- textos do Gemini no PDF e prompts ------------------------------------------------

def test_latex_vira_texto_no_pdf():
    from core.relatorio import _preparar_md_pdf

    bruto = (r"Temos $V(G) = E - N + 2$ e $\varepsilon = 0{,}01$." "\n---\n"
             r"$$MS = \frac{mortos}{total - equivalentes} = 100\%$$ --- e $p_{val1} \geq 0$")
    limpo = _preparar_md_pdf(bruto)
    assert "$" not in limpo and "\\" not in limpo and "---" not in limpo
    assert "ε = 0,01" in limpo and "mortos / (total - equivalentes)" in limpo and "p_val1 ≥ 0" in limpo


def test_prompts_sem_tuplas_nem_floats():
    from core import gemini

    a = analise.analisar(MANUAL, "cad0001_calcula_valor")
    texto = gemini.metricas_texto(a["metricas"])
    assert "(5, 5)" not in texto and "5 de 5" in texto and "100,0%" in texto and "1.0" not in texto


def test_vivos_da_suite_avl_sao_do_tratamento_de_null():
    a = analise.analisar(MANUAL, "cad0001_calcula_valor")
    avl = next(s for s in a["ms_suites"] if s["Suíte"] == "Só AVL")
    assert avl["Vivos"] == len(avl["_vivos"]) == 15
    assert all("IS NULL" in m.original or m.original.endswith("= 0") for m in avl["_vivos"])
