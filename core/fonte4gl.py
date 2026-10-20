"""Leitura e execução de um subconjunto de Informix-4GL.

O TestingStudio precisa "ler o código por dentro": o mesmo parser alimenta o
Grafo de Fluxo de Controle (Sprint 2), os pares Def-Uso e os mutantes
(Sprint 3) e a execução dos casos de teste (Sprints 1 e 4).

Comandos suportados dentro de uma FUNCTION: DEFINE, LET, IF/ELSE/END IF,
RETURN, WHILE/END WHILE e FOR/END FOR. Expressões: + - * /, comparações
(= <> != < <= > >=), IS [NOT] NULL, AND, OR, NOT e parênteses.
"""
from __future__ import annotations

import copy
import itertools
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------------


class ErroSintaxe(Exception):
    pass


class ErroExecucao(Exception):
    pass


class Estouro(ErroExecucao):
    """Valor não cabe no tipo DECIMAL(p,s) da variável."""


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

_TOKEN = re.compile(
    r"""
    (?P<num>\d+(?:\.\d+)?)
  | (?P<id>[A-Za-z_]\w*(?:\.(?:\w+|\*))*)
  | (?P<op><=|>=|<>|!=|[=<>+\-*/(),])
  | (?P<str>"[^"]*"|'[^']*')
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    tipo: str
    texto: str
    linha: int

    @property
    def up(self) -> str:
        return self.texto.upper()


def _sem_comentarios(linha: str) -> str:
    dentro, aspas = False, ""
    for i, c in enumerate(linha):
        if dentro:
            if c == aspas:
                dentro = False
            continue
        if c in "\"'":
            dentro, aspas = True, c
        elif c == "#" or linha.startswith("--", i):
            return linha[:i]
    return linha


def tokenizar(codigo: str) -> list[Token]:
    tokens: list[Token] = []
    for n, linha in enumerate(codigo.splitlines(), start=1):
        texto = _sem_comentarios(linha)
        pos = 0
        while pos < len(texto):
            if texto[pos].isspace():
                pos += 1
                continue
            m = _TOKEN.match(texto, pos)
            if not m:
                raise ErroSintaxe(f"Caractere inesperado '{texto[pos]}' na linha {n}")
            tokens.append(Token(m.lastgroup, m.group(), n))
            pos = m.end()
    return tokens


# ---------------------------------------------------------------------------
# Árvore sintática
# ---------------------------------------------------------------------------

_uid = itertools.count(1)


@dataclass(eq=False)
class No:
    uid: int = field(default_factory=lambda: next(_uid), init=False)
    linha: int = field(default=0, kw_only=True)


@dataclass(eq=False)
class Num(No):
    valor: Decimal


@dataclass(eq=False)
class Nulo(No):
    pass


@dataclass(eq=False)
class Var(No):
    nome: str


@dataclass(eq=False)
class Bin(No):
    op: str
    esq: No
    dir: No


@dataclass(eq=False)
class Un(No):
    op: str  # '-' ou 'NOT'
    expr: No


@dataclass(eq=False)
class EhNulo(No):
    expr: No
    negado: bool = False


@dataclass(eq=False)
class Let(No):
    alvo: str
    expr: No


@dataclass(eq=False)
class Return(No):
    exprs: list


@dataclass(eq=False)
class If(No):
    cond: No
    entao: list
    senao: list | None


@dataclass(eq=False)
class While(No):
    cond: No
    corpo: list


@dataclass(eq=False)
class For(No):
    var: str
    inicio: No
    fim: No
    corpo: list


@dataclass
class Tipo:
    nome: str
    precisao: int | None = None
    escala: int | None = None

    def __str__(self) -> str:
        if self.precisao is None:
            return self.nome
        if self.escala is None:
            return f"{self.nome}({self.precisao})"
        return f"{self.nome}({self.precisao},{self.escala})"

    @property
    def decimal(self) -> bool:
        return self.nome in ("DECIMAL", "DEC", "NUMERIC", "MONEY")

    @property
    def inteiro(self) -> bool:
        return self.nome in ("INTEGER", "INT", "SMALLINT", "SERIAL", "BIGINT")


@dataclass
class Funcao:
    nome: str
    params: list[str]
    tipos: dict[str, Tipo]
    corpo: list
    linha: int = 0


RELACIONAIS = ("=", "<>", "<", "<=", ">", ">=")
ARITMETICOS = ("+", "-", "*", "/")
LOGICOS = ("AND", "OR")

_TIPOS = {
    "DECIMAL", "DEC", "NUMERIC", "MONEY", "INTEGER", "INT", "SMALLINT", "SERIAL",
    "BIGINT", "FLOAT", "SMALLFLOAT", "REAL", "CHAR", "CHARACTER", "VARCHAR",
    "DATE", "DATETIME", "LIKE", "RECORD",
}
_FIM_BLOCO = {"ELSE", "END"}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.t = tokens
        self.i = 0

    # utilidades ------------------------------------------------------------
    def ver(self, k: int = 0) -> Token | None:
        j = self.i + k
        return self.t[j] if j < len(self.t) else None

    def eh(self, *textos: str, k: int = 0) -> bool:
        tok = self.ver(k)
        return tok is not None and tok.up in textos

    def pegar(self, *textos: str) -> Token:
        tok = self.ver()
        if tok is None:
            raise ErroSintaxe(f"Fim inesperado do código; esperado {' ou '.join(textos)}")
        if textos and tok.up not in textos:
            raise ErroSintaxe(
                f"Linha {tok.linha}: esperado {' ou '.join(textos)}, encontrado '{tok.texto}'"
            )
        self.i += 1
        return tok

    def ident(self) -> Token:
        tok = self.pegar()
        if tok.tipo != "id":
            raise ErroSintaxe(f"Linha {tok.linha}: esperado um identificador, encontrado '{tok.texto}'")
        return tok

    # função ----------------------------------------------------------------
    def funcao(self) -> Funcao:
        ini = self.pegar("FUNCTION")
        nome = self.ident().texto
        params: list[str] = []
        self.pegar("(")
        while not self.eh(")"):
            params.append(self.ident().texto.lower())
            if self.eh(","):
                self.pegar(",")
        self.pegar(")")
        tipos: dict[str, Tipo] = {}
        corpo = self.bloco(tipos)
        self.pegar("END")
        self.pegar("FUNCTION")
        return Funcao(nome, params, tipos, corpo, ini.linha)

    def define(self, tipos: dict[str, Tipo]) -> None:
        self.pegar("DEFINE")
        pendentes: list[str] = []
        while True:
            tok = self.ver()
            if tok is None:
                break
            if tok.up in _TIPOS and pendentes:
                tipo = self.tipo()
                for nome in pendentes:
                    tipos[nome] = tipo
                pendentes = []
                if self.eh(","):
                    self.pegar(",")
                    continue
                break
            if tok.tipo != "id":
                raise ErroSintaxe(f"Linha {tok.linha}: DEFINE mal formado perto de '{tok.texto}'")
            pendentes.append(self.ident().texto.lower())
            if self.eh(","):
                self.pegar(",")
        if pendentes:
            raise ErroSintaxe(f"DEFINE sem tipo para: {', '.join(pendentes)}")

    def tipo(self) -> Tipo:
        nome = self.pegar().up
        if nome == "LIKE":
            self.ident()
            return Tipo("LIKE")
        if nome == "RECORD":
            while not (self.eh("END") and self.eh("RECORD", k=1)):
                self.pegar()
            self.pegar("END")
            self.pegar("RECORD")
            return Tipo("RECORD")
        if self.eh("("):
            self.pegar("(")
            p = int(self.pegar().texto)
            s = None
            if self.eh(","):
                self.pegar(",")
                s = int(self.pegar().texto)
            self.pegar(")")
            if nome in ("DECIMAL", "DEC", "NUMERIC", "MONEY") and s is None:
                s = 0 if nome != "MONEY" else 2
            return Tipo(nome, p, s)
        if nome == "MONEY":
            return Tipo(nome, 16, 2)
        return Tipo(nome)

    # comandos --------------------------------------------------------------
    def bloco(self, tipos: dict[str, Tipo]) -> list:
        cmds: list = []
        while self.ver() is not None and not self.eh(*_FIM_BLOCO):
            if self.eh("DEFINE"):
                self.define(tipos)
                continue
            cmds.append(self.comando(tipos))
        return cmds

    def comando(self, tipos: dict[str, Tipo]) -> No:
        tok = self.ver()
        up = tok.up
        if up == "LET":
            self.pegar()
            alvo = self.ident().texto.lower()
            self.pegar("=")
            return Let(alvo, self.expr(), linha=tok.linha)
        if up == "RETURN":
            self.pegar()
            exprs = []
            if self._inicia_expr():
                exprs.append(self.expr())
                while self.eh(","):
                    self.pegar(",")
                    exprs.append(self.expr())
            return Return(exprs, linha=tok.linha)
        if up == "IF":
            self.pegar()
            cond = self.expr()
            self.pegar("THEN")
            entao = self.bloco(tipos)
            senao = None
            if self.eh("ELSE"):
                self.pegar()
                senao = self.bloco(tipos)
            self.pegar("END")
            self.pegar("IF")
            return If(cond, entao, senao, linha=tok.linha)
        if up == "WHILE":
            self.pegar()
            cond = self.expr()
            corpo = self.bloco(tipos)
            self.pegar("END")
            self.pegar("WHILE")
            return While(cond, corpo, linha=tok.linha)
        if up == "FOR":
            self.pegar()
            var = self.ident().texto.lower()
            self.pegar("=")
            ini = self.expr()
            self.pegar("TO")
            fim = self.expr()
            corpo = self.bloco(tipos)
            self.pegar("END")
            self.pegar("FOR")
            return For(var, ini, fim, corpo, linha=tok.linha)
        raise ErroSintaxe(
            f"Linha {tok.linha}: comando '{tok.texto}' não é suportado pelo analisador "
            "(use LET, IF, RETURN, WHILE ou FOR)"
        )

    def _inicia_expr(self) -> bool:
        tok = self.ver()
        if tok is None:
            return False
        if tok.tipo in ("num", "str"):
            return True
        if tok.texto in ("(", "-"):
            return True
        return tok.tipo == "id" and tok.up not in {
            "END", "ELSE", "LET", "IF", "RETURN", "WHILE", "FOR", "DEFINE", "THEN"
        }

    # expressões ------------------------------------------------------------
    def expr(self) -> No:
        return self.ou()

    def ou(self) -> No:
        esq = self.e()
        while self.eh("OR"):
            tok = self.pegar()
            esq = Bin("OR", esq, self.e(), linha=tok.linha)
        return esq

    def e(self) -> No:
        esq = self.nao()
        while self.eh("AND"):
            tok = self.pegar()
            esq = Bin("AND", esq, self.nao(), linha=tok.linha)
        return esq

    def nao(self) -> No:
        if self.eh("NOT"):
            tok = self.pegar()
            return Un("NOT", self.nao(), linha=tok.linha)
        return self.comparacao()

    def comparacao(self) -> No:
        esq = self.soma()
        tok = self.ver()
        if tok is not None and tok.texto in ("=", "<>", "!=", "<", "<=", ">", ">="):
            self.pegar()
            op = "<>" if tok.texto == "!=" else tok.texto
            return Bin(op, esq, self.soma(), linha=tok.linha)
        if self.eh("IS"):
            tok = self.pegar()
            negado = False
            if self.eh("NOT"):
                self.pegar()
                negado = True
            self.pegar("NULL")
            return EhNulo(esq, negado, linha=tok.linha)
        return esq

    def soma(self) -> No:
        esq = self.produto()
        while self.ver() is not None and self.ver().texto in ("+", "-"):
            tok = self.pegar()
            esq = Bin(tok.texto, esq, self.produto(), linha=tok.linha)
        return esq

    def produto(self) -> No:
        esq = self.unario()
        while self.ver() is not None and self.ver().texto in ("*", "/"):
            tok = self.pegar()
            esq = Bin(tok.texto, esq, self.unario(), linha=tok.linha)
        return esq

    def unario(self) -> No:
        if self.eh("-"):
            tok = self.pegar()
            alvo = self.unario()
            if isinstance(alvo, Num):
                return Num(-alvo.valor, linha=tok.linha)
            return Un("-", alvo, linha=tok.linha)
        return self.primario()

    def primario(self) -> No:
        tok = self.pegar()
        if tok.tipo == "num":
            return Num(Decimal(tok.texto), linha=tok.linha)
        if tok.texto == "(":
            e = self.expr()
            self.pegar(")")
            return e
        if tok.up == "NULL":
            return Nulo(linha=tok.linha)
        if tok.tipo == "id":
            return Var(tok.texto.lower(), linha=tok.linha)
        raise ErroSintaxe(f"Linha {tok.linha}: expressão inválida perto de '{tok.texto}'")


def listar_funcoes(codigo: str) -> list[str]:
    """Nomes das FUNCTIONs presentes no código, na ordem em que aparecem."""
    tokens = tokenizar(codigo)
    nomes = []
    for i, tok in enumerate(tokens):
        if tok.up == "FUNCTION" and (i == 0 or tokens[i - 1].up != "END") and i + 1 < len(tokens):
            nomes.append(tokens[i + 1].texto)
    return nomes


def ler_funcao(codigo: str, nome: str | None = None) -> Funcao:
    """Analisa apenas a FUNCTION pedida (as demais podem ter SQL não suportado)."""
    tokens = tokenizar(codigo)
    inicios = [
        i for i, tok in enumerate(tokens)
        if tok.up == "FUNCTION" and (i == 0 or tokens[i - 1].up != "END")
    ]
    if not inicios:
        raise ErroSintaxe("Nenhuma FUNCTION encontrada no código.")
    escolhido = inicios[0]
    if nome:
        for i in inicios:
            if i + 1 < len(tokens) and tokens[i + 1].texto.lower() == nome.lower():
                escolhido = i
                break
        else:
            raise ErroSintaxe(f"FUNCTION {nome} não encontrada.")
    p = _Parser(tokens)
    p.i = escolhido
    return p.funcao()


# ---------------------------------------------------------------------------
# Impressão de volta em 4GL
# ---------------------------------------------------------------------------

_PRIOR = {"OR": 1, "AND": 2, "NOT": 3, **{op: 4 for op in RELACIONAIS}, "+": 5, "-": 5, "*": 6, "/": 6}


def fmt_num(v: Decimal) -> str:
    return format(v, "f")


def texto(no: No, pai: int = 0) -> str:
    if isinstance(no, Num):
        return fmt_num(no.valor)
    if isinstance(no, Nulo):
        return "NULL"
    if isinstance(no, Var):
        return no.nome
    if isinstance(no, EhNulo):
        return f"{texto(no.expr, 4)} IS {'NOT ' if no.negado else ''}NULL"
    if isinstance(no, Un):
        s = f"NOT {texto(no.expr, 3)}" if no.op == "NOT" else f"-{texto(no.expr, 7)}"
        return f"({s})" if pai > 3 and no.op == "NOT" else s
    if isinstance(no, Bin):
        p = _PRIOR[no.op]
        s = f"{texto(no.esq, p)} {no.op} {texto(no.dir, p + 1)}"
        return f"({s})" if p < pai else s
    if isinstance(no, Let):
        return f"LET {no.alvo} = {texto(no.expr)}"
    if isinstance(no, Return):
        return "RETURN " + ", ".join(texto(e) for e in no.exprs)
    if isinstance(no, If):
        return f"IF {texto(no.cond)} THEN"
    if isinstance(no, While):
        return f"WHILE {texto(no.cond)}"
    if isinstance(no, For):
        return f"FOR {no.var} = {texto(no.inicio)} TO {texto(no.fim)}"
    return "?"


def texto_funcao(f: Funcao) -> str:
    linhas = [f"FUNCTION {f.nome}({', '.join(f.params)})"]
    for nome, tipo in f.tipos.items():
        linhas.append(f"    DEFINE {nome} {tipo}")

    def bloco(cmds, nivel):
        pad = "    " * nivel
        for c in cmds:
            if isinstance(c, If):
                linhas.append(pad + texto(c))
                bloco(c.entao, nivel + 1)
                if c.senao is not None:
                    linhas.append(pad + "ELSE")
                    bloco(c.senao, nivel + 1)
                linhas.append(pad + "END IF")
            elif isinstance(c, While):
                linhas.append(pad + texto(c))
                bloco(c.corpo, nivel + 1)
                linhas.append(pad + "END WHILE")
            elif isinstance(c, For):
                linhas.append(pad + texto(c))
                bloco(c.corpo, nivel + 1)
                linhas.append(pad + "END FOR")
            else:
                linhas.append(pad + texto(c))

    bloco(f.corpo, 1)
    linhas.append("END FUNCTION")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Percursos na árvore
# ---------------------------------------------------------------------------


def filhos(no) -> list:
    if isinstance(no, Bin):
        return [no.esq, no.dir]
    if isinstance(no, (Un, EhNulo)):
        return [no.expr]
    if isinstance(no, Let):
        return [no.expr]
    if isinstance(no, Return):
        return list(no.exprs)
    if isinstance(no, If):
        return [no.cond, *no.entao, *(no.senao or [])]
    if isinstance(no, While):
        return [no.cond, *no.corpo]
    if isinstance(no, For):
        return [no.inicio, no.fim, *no.corpo]
    return []


def percorrer(raiz):
    """Gera todos os nós da árvore (pré-ordem)."""
    pilha = list(reversed(raiz)) if isinstance(raiz, list) else [raiz]
    while pilha:
        no = pilha.pop()
        yield no
        pilha.extend(reversed(filhos(no)))


def variaveis(expr: No) -> list[str]:
    vistos: list[str] = []
    for no in percorrer(expr):
        if isinstance(no, Var) and no.nome not in vistos:
            vistos.append(no.nome)
    return vistos


def clonar(f: Funcao) -> Funcao:
    return copy.deepcopy(f)


# ---------------------------------------------------------------------------
# Interpretador
# ---------------------------------------------------------------------------


@dataclass
class Resultado:
    valor: Decimal | None = None
    erro: str | None = None
    trilha: list[int] = field(default_factory=list)

    @property
    def texto(self) -> str:
        if self.erro:
            return self.erro
        return "NULL" if self.valor is None else fmt_brl(self.valor)

    def chave(self):
        """Valor usado para comparar saídas (morte de mutantes, oráculo)."""
        return ("ERRO", self.erro) if self.erro else ("OK", self.valor)


def fmt_brl(v: Decimal | None, casas: int = 2) -> str:
    if v is None:
        return "NULL"
    q = Decimal(1).scaleb(-casas)
    s = f"{v.quantize(q, rounding=ROUND_HALF_UP):,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


class _Retorno(Exception):
    def __init__(self, valor):
        self.valor = valor


def _ajustar(valor, tipo: Tipo | None, nome: str):
    if valor is None or tipo is None or isinstance(valor, bool):
        return valor
    if tipo.decimal and tipo.precisao is not None:
        escala = tipo.escala or 0
        try:
            v = Decimal(valor).quantize(Decimal(1).scaleb(-escala), rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise Estouro(f"ESTOURO em {nome}") from exc
        limite = Decimal(10) ** (tipo.precisao - escala)
        if abs(v) >= limite:
            raise Estouro(f"ESTOURO em {nome} ({tipo})")
        return v
    if tipo.inteiro:
        v = int(Decimal(valor).to_integral_value(rounding=ROUND_HALF_UP))
        lim = 2**15 if tipo.nome == "SMALLINT" else 2**31
        if abs(v) >= lim:
            raise Estouro(f"ESTOURO em {nome} ({tipo})")
        return Decimal(v)
    return valor


def _verdade(v) -> bool:
    return bool(v) if v is not None else False


class Interpretador:
    """Executa a função registrando os nós do GFC percorridos (trilha).

    `mapa` liga o uid de cada comando/condição ao número do nó no grafo.
    `atomico=True` registra cada condição simples (GFC 2); senão registra o IF inteiro.
    """

    LIMITE_PASSOS = 10_000

    def __init__(self, f: Funcao, mapa: dict[int, int] | None = None, atomico: bool = False,
                 no_inicio: int | None = None, no_fim: int | None = None):
        self.f = f
        self.mapa = mapa or {}
        self.atomico = atomico
        self.no_inicio = no_inicio
        self.no_fim = no_fim

    def executar(self, args) -> Resultado:
        if isinstance(args, dict):
            args = [args.get(p) for p in self.f.params]
        args = list(args) + [None] * (len(self.f.params) - len(args))
        self.env: dict = {}
        self.trilha: list[int] = []
        self.passos = 0
        if self.no_inicio is not None:
            self.trilha.append(self.no_inicio)
        res = Resultado()
        try:
            for nome, v in zip(self.f.params, args):
                v = None if v is None else Decimal(str(v))
                self.env[nome] = _ajustar(v, self.f.tipos.get(nome), nome)
            self.bloco(self.f.corpo)
        except _Retorno as r:
            res.valor = r.valor
        except ErroExecucao as e:
            res.erro = str(e)
        if self.no_fim is not None:
            self.marcar_no(self.no_fim)
        res.trilha = self.trilha
        return res

    def marcar_no(self, n):
        if n is not None and (not self.trilha or self.trilha[-1] != n):
            self.trilha.append(n)

    def marcar(self, no):
        self.marcar_no(self.mapa.get(no.uid))

    def passo(self):
        self.passos += 1
        if self.passos > self.LIMITE_PASSOS:
            raise ErroExecucao("LAÇO INFINITO (limite de passos)")

    def bloco(self, cmds):
        for c in cmds:
            self.passo()
            self.cmd(c)

    def cmd(self, c):
        if isinstance(c, Let):
            self.marcar(c)
            self.env[c.alvo] = _ajustar(self.val(c.expr), self.f.tipos.get(c.alvo), c.alvo)
        elif isinstance(c, Return):
            self.marcar(c)
            valores = [self.val(e) for e in c.exprs]
            v = valores[0] if valores else None
            raise _Retorno(None if isinstance(v, bool) else v)
        elif isinstance(c, If):
            if self.cond(c):
                self.bloco(c.entao)
            elif c.senao is not None:
                self.bloco(c.senao)
        elif isinstance(c, While):
            while self.cond(c):
                self.passo()
                self.bloco(c.corpo)
        elif isinstance(c, For):
            self.marcar(c)
            ini, fim = self.val(c.inicio), self.val(c.fim)
            self.env[c.var] = ini
            while True:
                self.passo()
                self.marcar(c)
                if self.env[c.var] is None or fim is None or self.env[c.var] > fim:
                    break
                self.bloco(c.corpo)
                self.env[c.var] = self.env[c.var] + 1

    def cond(self, c) -> bool:
        if not self.atomico:
            self.marcar(c)
            return _verdade(self.val(c.cond))
        return self.cond_atomica(c.cond)

    def cond_atomica(self, e) -> bool:
        if isinstance(e, Bin) and e.op == "OR":
            return self.cond_atomica(e.esq) or self.cond_atomica(e.dir)
        if isinstance(e, Bin) and e.op == "AND":
            return self.cond_atomica(e.esq) and self.cond_atomica(e.dir)
        if isinstance(e, Un) and e.op == "NOT":
            return not self.cond_atomica(e.expr)
        self.marcar(e)
        return _verdade(self.val(e))

    def val(self, e):
        if isinstance(e, Num):
            return e.valor
        if isinstance(e, Nulo):
            return None
        if isinstance(e, Var):
            return self.env.get(e.nome)
        if isinstance(e, EhNulo):
            r = self.val(e.expr) is None
            return not r if e.negado else r
        if isinstance(e, Un):
            v = self.val(e.expr)
            if e.op == "NOT":
                return None if v is None else not _verdade(v)
            return None if v is None else -v
        if isinstance(e, Bin):
            if e.op == "OR":
                return _verdade(self.val(e.esq)) or _verdade(self.val(e.dir))
            if e.op == "AND":
                return _verdade(self.val(e.esq)) and _verdade(self.val(e.dir))
            a, b = self.val(e.esq), self.val(e.dir)
            if a is None or b is None:
                return None
            if e.op == "+":
                return a + b
            if e.op == "-":
                return a - b
            if e.op == "*":
                return a * b
            if e.op == "/":
                if b == 0:
                    raise ErroExecucao("DIVISÃO POR ZERO")
                return a / b
            return {
                "=": a == b, "<>": a != b, "<": a < b,
                "<=": a <= b, ">": a > b, ">=": a >= b,
            }[e.op]
        raise ErroExecucao(f"Expressão não suportada: {type(e).__name__}")


def executar(f: Funcao, args) -> Resultado:
    """Execução simples, sem registro de trilha."""
    return Interpretador(f).executar(args)
