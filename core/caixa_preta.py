"""Sprint 1 — Caixa-Preta: PCE, AVL e cálculo algorítmico do Épsilon."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import oraculo
from .fonte4gl import Funcao, Interpretador, Let, Tipo, Var, fmt_brl, percorrer


@dataclass
class CasoTeste:
    id: str
    grupo: str
    descricao: str
    args: tuple
    esperado: object = None
    obtido: str = ""
    ok: bool | None = None
    requisitos: list[str] = field(default_factory=list)
    trilha: list[int] = field(default_factory=list)

    @property
    def esperado_txt(self) -> str:
        if isinstance(self.esperado, Decimal):
            return fmt_brl(self.esperado)
        return str(self.esperado)

    def args_txt(self) -> list[str]:
        return [fmt_brl(Decimal(str(a))) if a is not None else "NULL" for a in self.args]


# ---------------------------------------------------------------------------
# Épsilon
# ---------------------------------------------------------------------------


def tipo_dos_parametros(f: Funcao) -> Tipo:
    """Descobre o tipo numérico dos parâmetros.

    Se o parâmetro não foi declarado com DEFINE (caso do manual), usa o tipo
    da variável que recebe o parâmetro em um LET (ex.: LET p_val1 = val_param1).
    """
    for p in f.params:
        if p in f.tipos:
            return f.tipos[p]
    for no in percorrer(f.corpo):
        if isinstance(no, Let) and isinstance(no.expr, Var) and no.expr.nome in f.params:
            if no.alvo in f.tipos:
                return f.tipos[no.alvo]
    for t in f.tipos.values():
        if t.decimal or t.inteiro:
            return t
    return Tipo("DECIMAL", 12, 2)


def calcular_epsilon(tipo: Tipo) -> tuple[Decimal, str]:
    """Menor variação física possível para o tipo de dado."""
    if tipo.decimal:
        escala = tipo.escala if tipo.escala is not None else 2
        eps = Decimal(1).scaleb(-escala)
        return eps, (
            f"{tipo} guarda {escala} casa(s) decimal(is); a menor variação representável é "
            f"10^-{escala} = {fmt_brl(eps, escala)}. Para valores em Reais isso é 1 centavo."
        )
    if tipo.inteiro:
        return Decimal(1), f"{tipo} só guarda inteiros, então ε = 1."
    return Decimal("0.000001"), (
        f"{tipo} é ponto flutuante; adotou-se ε = 0,000001 como tolerância de comparação."
    )


def maximo_do_tipo(tipo: Tipo) -> Decimal:
    if tipo.decimal and tipo.precisao:
        escala = tipo.escala or 0
        return Decimal(10) ** (tipo.precisao - escala) - Decimal(1).scaleb(-escala)
    if tipo.nome == "SMALLINT":
        return Decimal(2**15 - 1)
    if tipo.inteiro:
        return Decimal(2**31 - 1)
    return oraculo.MAXIMO


# ---------------------------------------------------------------------------
# Rastreabilidade (RTM) de cada caso
# ---------------------------------------------------------------------------


def requisitos_do_caso(args, esperado, descricao: str = "") -> list[str]:
    reqs = []
    vals = [None if a is None else Decimal(str(a)) for a in args]
    if esperado == "ESTOURO" or any(v is not None and abs(v) >= oraculo.MAXIMO for v in vals):
        reqs.append("REQ05")
    elif all(v is None or v >= 0 for v in vals):
        reqs.append("REQ01")
    if any(v is None for v in vals):
        reqs.append("REQ02")
    if any(v is not None and v < 0 for v in vals):
        reqs.append("REQ03")
    d = descricao.lower()
    fronteira_inferior = ("on-point" in d or "off-point" in d) and "sup." not in d
    if fronteira_inferior or "arredond" in d or "zerados" in d or any(v == -oraculo.EPSILON for v in vals if v is not None):
        reqs.append("REQ04")
    return sorted(set(reqs))


def avaliar(f: Funcao, casos: list[CasoTeste]) -> list[CasoTeste]:
    """Executa cada caso no programa e compara com o oráculo."""
    exe = Interpretador(f)
    for c in casos:
        c.esperado = oraculo.esperado(*c.args[:3])
        r = exe.executar(c.args)
        c.obtido = r.texto
        c.ok = oraculo.confere(r, c.esperado)
        c.requisitos = requisitos_do_caso(c.args, c.esperado, c.descricao)
    return casos


# ---------------------------------------------------------------------------
# PCE
# ---------------------------------------------------------------------------


def tabela_pce(params: list[str], maximo: Decimal, eps: Decimal) -> list[dict]:
    linhas = []
    for p in params:
        linhas += [
            {"Parâmetro": p, "Classe": "CV1 — Válida", "Domínio": f"0,00 até {fmt_brl(maximo)}",
             "Representante": "100,00", "Comportamento": "Faz o cálculo"},
            {"Parâmetro": p, "Classe": "CI1 — Inválida", "Domínio": "Menor que 0,00",
             "Representante": "-100,00", "Comportamento": "Retorna -1"},
            {"Parâmetro": p, "Classe": "CV2 — NULL", "Domínio": "NULL",
             "Representante": "NULL", "Comportamento": "Converte em 0,00 e calcula"},
            {"Parâmetro": p, "Classe": "CI2 — Inválida", "Domínio": f"Maior que {fmt_brl(maximo)}",
             "Representante": fmt_brl(maximo + eps), "Comportamento": "Estouro do tipo DECIMAL(12,2)"},
        ]
    return linhas


def _neutros(n: int, i: int, valor) -> tuple:
    """Fixa os outros parâmetros em valores neutros: multiplicador 1 e parcela 0.

    Assim o resultado do cálculo é o próprio valor testado.
    """
    if n < 3:
        base = [Decimal(1)] * n
    else:
        base = [Decimal(1), Decimal(1), Decimal(0)] + [Decimal(0)] * (n - 3)
        if i == 2:
            base[1] = Decimal(0)
    base[i] = valor
    return tuple(base)


def casos_pce(params: list[str], maximo: Decimal, eps: Decimal) -> list[CasoTeste]:
    casos = []
    n = len(params)
    for i, p in enumerate(params):
        for classe, valor in (("CV1", Decimal("100.00")), ("CI1", Decimal("-100.00")),
                              ("CV2", None), ("CI2", maximo + eps)):
            casos.append(CasoTeste(
                f"PCE-{p}-{classe}", "PCE", f"{p}: classe {classe}", _neutros(n, i, valor)))
    return casos


# ---------------------------------------------------------------------------
# AVL
# ---------------------------------------------------------------------------


def casos_avl(params: list[str], eps: Decimal, maximo: Decimal, superior: bool = True) -> list[CasoTeste]:
    pontos = [
        ("On-point", Decimal("0.00"), "Exatamente na fronteira válida"),
        ("Off-point", Decimal("0.00") - eps, "Primeiro ponto fora (0,00 − ε)"),
        ("Interior", Decimal("100.00"), "Profundamente na região válida"),
        ("Exterior", Decimal("-100.00"), "Profundamente na região inválida"),
    ]
    if superior:
        pontos += [
            ("On-point sup.", maximo, "Maior valor do tipo"),
            ("Off-point sup.", maximo + eps, "Primeiro valor acima do máximo (máx + ε)"),
        ]
    casos = []
    for i, p in enumerate(params):
        for nome, valor, desc in pontos:
            casos.append(CasoTeste(f"AVL-{p}-{nome}", "AVL", f"{nome} — {desc}",
                                   _neutros(len(params), i, valor)))
    return casos


def casos_combinados() -> list[CasoTeste]:
    D = Decimal
    tabela = [
        ("Todos zerados", (D("0.00"), D("0.00"), D("0.00"))),
        ("Três positivos", (D("2.00"), D("3.00"), D("4.00"))),
        ("p1 negativo", (D("-0.01"), D("2.00"), D("3.00"))),
        ("p2 negativo", (D("2.00"), D("-0.01"), D("3.00"))),
        ("p3 negativo", (D("2.00"), D("3.00"), D("-0.01"))),
        ("p1 NULL", (None, D("2.00"), D("3.00"))),
        ("Todos NULL", (None, None, None)),
        ("Arredondamento de centavos (0,05 × 0,10)", (D("0.05"), D("0.10"), D("0.00"))),
        ("Estouro do resultado (máx × 1 + 0,01)", (oraculo.MAXIMO, D("1.00"), D("0.01"))),
    ]
    return [CasoTeste(f"CMB-{i:02d}", "Combinação", desc, args)
            for i, (desc, args) in enumerate(tabela, start=1)]


def analisar(f: Funcao) -> dict:
    tipo = tipo_dos_parametros(f)
    eps, justificativa = calcular_epsilon(tipo)
    maximo = maximo_do_tipo(tipo)
    params = f.params
    pce = avaliar(f, casos_pce(params, maximo, eps))
    avl = avaliar(f, casos_avl(params, eps, maximo))
    cmb = avaliar(f, casos_combinados()) if len(params) == 3 else []
    return {
        "tipo": tipo,
        "epsilon": eps,
        "justificativa": justificativa,
        "maximo": maximo,
        "tabela_pce": tabela_pce(params, maximo, eps),
        "casos_pce": pce,
        "casos_avl": avl,
        "casos_cmb": cmb,
    }
