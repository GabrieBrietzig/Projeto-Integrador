"""Sprint 4 — Validação: Matriz de Rastreabilidade (RTM), V&V e suíte pytest."""
from __future__ import annotations

import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

from . import oraculo
from .caixa_preta import CasoTeste, avaliar
from .fonte4gl import Funcao

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "saida"

FORA_DO_ESCOPO = {
    "REQ06": "Nível de integração (banco de dados): exige stubs/drivers das tabelas; fora do teste de unidade.",
}


def falha_do_requisito(c: CasoTeste, req: str) -> bool:
    """Atribui a falha ao requisito que de fato foi violado.

    Ex.: o caso (NULL, -0,01, 3) esperava -1. Se falhar, o defeito é da regra de
    negativos (REQ03/REQ04), não da conversão de NULL (REQ02).
    """
    if c.ok or req not in c.requisitos:
        return False
    if c.esperado == Decimal("-1"):
        return req in ("REQ03", "REQ04")
    if c.esperado == "ESTOURO":
        return req == "REQ05"
    return True


def montar_rtm(casos: list[CasoTeste]) -> list[dict]:
    linhas = []
    for req, desc in oraculo.REQUISITOS.items():
        cts = [c for c in casos if req in c.requisitos]
        falhas = [c for c in cts if falha_do_requisito(c, req)]
        if not cts:
            status = "Fora do escopo" if req in FORA_DO_ESCOPO else "Sem caso de teste"
        elif falhas:
            status = "Falhou"
        else:
            status = "Validado"
        linhas.append({
            "Requisito": req, "Descrição": desc, "CTs": len(cts),
            "Passaram": len(cts) - len(falhas), "Falharam": len(falhas),
            "Status": status, "Casos": ", ".join(c.id for c in cts),
            "Observação": FORA_DO_ESCOPO.get(req, ""),
        })
    return linhas


def cobertura_rtm(rtm: list[dict]) -> tuple[int, int]:
    testaveis = [l for l in rtm if l["Status"] != "Fora do escopo"]
    cobertos = [l for l in testaveis if l["CTs"] > 0]
    return len(cobertos), len(testaveis)


def validar_versoes(versoes: dict[str, Funcao], casos_base: list[CasoTeste]) -> dict[str, dict]:
    """Executa a mesma suíte em cada versão do CAD0001 e monta a RTM de cada uma."""
    resultado = {}
    for nome, f in versoes.items():
        casos = [CasoTeste(c.id, c.grupo, c.descricao, c.args) for c in casos_base]
        avaliar(f, casos)
        rtm = montar_rtm(casos)
        resultado[nome] = {
            "casos": casos,
            "rtm": rtm,
            "passaram": sum(1 for c in casos if c.ok),
            "falharam": [c for c in casos if not c.ok],
        }
    return resultado


# ---------------------------------------------------------------------------
# pytest
# ---------------------------------------------------------------------------

_MODELO = '''"""Suíte gerada pelo TestingStudio Web — CAD0001 com rastreabilidade (RTM).

Execute na raiz do projeto:  pytest saida/test_cad0001_rtm.py -v
Filtrar um requisito:        pytest saida/test_cad0001_rtm.py -v -m REQ03
"""
import sys
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core import oraculo  # noqa: E402
from core.fonte4gl import executar, ler_funcao  # noqa: E402

FONTE = Path(__file__).with_name("{fonte}")
FUNCAO = ler_funcao(FONTE.read_text(encoding="utf-8"), "{funcao}")

# (id do caso, requisito, argumentos, resultado esperado pelo oráculo)
CASOS = [
{casos}
]


@pytest.mark.parametrize(
    "cid, req, args, esperado",
    [pytest.param(*c, id=f"{{c[0]}}-{{c[1]}}", marks=[pytest.mark.requisito(c[1]), getattr(pytest.mark, c[1])])
     for c in CASOS],
)
def test_cad0001(cid, req, args, esperado):
    r = executar(FUNCAO, args)
    # Oráculo: regra de negócio do manual, não o próprio código-fonte
    assert oraculo.confere(r, esperado), f"{{cid}} ({{req}}): esperado {{esperado}}, obtido {{r.texto}}"
'''

_INI = """[pytest]
markers =
    requisito(id): rastreia o caso de teste até o requisito (RTM)
{marcadores}
"""


def _lit(v) -> str:
    if v is None:
        return "None"
    if isinstance(v, Decimal):
        return f'Decimal("{v}")'
    return repr(v)


def gerar_pytest(codigo: str, nome_funcao: str, casos: list[CasoTeste],
                 pasta: Path = SAIDA) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    fonte = pasta / "fonte_em_teste.4gl"
    fonte.write_text(codigo, encoding="utf-8")
    linhas = []
    for c in casos:
        for req in c.requisitos or ["REQ01"]:
            args = "(" + ", ".join(_lit(a) for a in c.args) + ("," if len(c.args) == 1 else "") + ")"
            linhas.append(f'    ("{c.id}", "{req}", {args}, {_lit(c.esperado)}),')
    arq = pasta / "test_cad0001_rtm.py"
    arq.write_text(_MODELO.format(fonte=fonte.name, funcao=nome_funcao, casos="\n".join(linhas)),
                   encoding="utf-8")
    marcadores = "\n".join(f"    {r}: {d[:70]}" for r, d in oraculo.REQUISITOS.items())
    (pasta / "pytest.ini").write_text(_INI.format(marcadores=marcadores), encoding="utf-8")
    return arq


def rodar_pytest(arquivo: Path) -> dict:
    cmd = [sys.executable, "-m", "pytest", str(arquivo), "-v", "-p", "no:cacheprovider",
           "--tb=line", "-q", "--no-header", "-rN", "--color=no"]
    proc = subprocess.run(cmd, cwd=arquivo.parent, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)
    saida = proc.stdout + proc.stderr
    resumo = re.findall(r"=+ (.+) in [\d.]+s", saida)
    passou = re.search(r"(\d+) passed", saida)
    falhou = re.search(r"(\d+) failed", saida)
    return {
        "codigo": proc.returncode,
        "saida": saida,
        "resumo": resumo[-1] if resumo else "",
        "passaram": int(passou.group(1)) if passou else 0,
        "falharam": int(falhou.group(1)) if falhou else 0,
    }
