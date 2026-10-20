"""TestingStudio Web — Auditoria automatizada de testes do CAD0001.

Teste de Software I (Ementa 62371) — Prof. Frank Piffer — 2026.2
Execute com:  streamlit run app.py
"""
from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from core import analise, gemini, gfc, graficos, mutacao, oraculo, relatorio, tabelas, tema, validacao
from core.fonte4gl import ErroSintaxe, fmt_brl, listar_funcoes

st.set_page_config(page_title="Auditoria do CAD0001", page_icon="🧪", layout="wide")

FONTES = {
    "cad0001_item_calculo.txt — versão do manual (com regra de negativos)": analise.ARQ_MANUAL,
    "cad0001_item_calculo.txt — arquivo entregue pelo professor": analise.ARQ_ORIGINAL,
    "Enviar outro arquivo .txt/.4gl": None,
}


PX_POR_CARACTERE = 7.4  # medido: "ESTOURO em l_val_calculado (DECIMAL(12,2))" = 42 caracteres, ~304 px


def larguras_pelo_conteudo(linhas, fixar=None) -> dict:
    """Largura de cada coluna = texto mais longo (valor ou título) + respiro, para nada ser cortado.

    `fixar` mantém a coluna de identificação visível quando a tabela precisa rolar na horizontal.
    """
    config = {}
    for col in linhas[0]:
        maior = max(len(str(col)), *(len(str(l.get(col, ""))) for l in linhas))
        largura = int(min(max(maior * PX_POR_CARACTERE + 22, 56), 400))
        config[col] = st.column_config.Column(width=largura, pinned=True if col == fixar else None)
    return config


def tabela(linhas, altura="auto", colunas=None, ajustar=False, fixar=None):
    if not linhas:
        st.caption("Sem linhas.")
        return
    if ajustar:
        colunas = larguras_pelo_conteudo(linhas, fixar)
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch", height=altura, column_config=colunas)


@st.cache_data(show_spinner="Executando as 4 Sprints sobre o fonte...", max_entries=20)
def rodar(codigo: str, funcao: str, agrupar: bool, modo: str, operadores: tuple, equivalentes: frozenset):
    op = analise.Opcoes(agrupar, modo, operadores, equivalentes)
    return analise.analisar(codigo, funcao, op)


@st.cache_data(show_spinner=False, max_entries=40)
def figura_gfc(_g, chave: str, destaque: tuple, escuro: bool):
    return graficos.png(graficos.desenhar_gfc(_g, list(destaque), tema=tema.paleta(escuro)))


def _marcar_operadores(valor: bool):
    for sigla in mutacao.OPERADORES:
        st.session_state[f"op_{sigla}"] = valor


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

with st.sidebar:
    escuro = st.toggle("🌙 Modo escuro", key="modo_escuro")
    st.markdown(tema.css(escuro), unsafe_allow_html=True)
    COR = tema.paleta(escuro)  # paleta passada aos gráficos e ao grafo

    st.header("🔑 Autenticação")
    api_key = st.text_input("Gemini API Key (aistudio.google.com):", type="password",
                            value=gemini.chave_do_ambiente(),
                            help="Também pode ser definida na variável de ambiente GEMINI_API_KEY.")
    modelos = st.session_state.get("modelos") or gemini.MODELOS_PADRAO
    modelo = st.selectbox("Modelo Gemini", modelos, index=0)
    if st.button("Listar modelos da minha conta", width="stretch"):
        try:
            with st.spinner("Buscando modelos da sua conta..."):
                lista = gemini.listar_modelos(api_key)
            if lista:
                st.session_state["modelos"] = lista
                st.session_state["modelos_aviso"] = (f"{len(lista)} modelos encontrados. "
                                                     "Abra a caixa **Modelo Gemini** para escolher.")
                st.rerun()
            else:
                st.warning("Nenhum modelo de texto disponível para esta chave.")
        except gemini.ErroGemini as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001
            st.error(f"Não foi possível listar: {e}")
    if aviso := st.session_state.pop("modelos_aviso", None):
        st.success(aviso)

    st.header("👥 Identificação")
    autores = st.text_input("Aluno(s) / Equipe", placeholder="Nome completo dos integrantes")

    st.header("📄 Fonte do CAD0001")
    origem = st.radio("Origem do código", list(FONTES), index=0, label_visibility="collapsed")
    enviado = None
    if FONTES[origem] is None:
        enviado = st.file_uploader("Arquivo 4GL", type=["txt", "4gl", "per"])

    st.header("⚙️ Opções de análise")
    agrupar = st.checkbox("Agrupar comandos sequenciais em blocos (nós indivisíveis)", value=False,
                          help="Desligado: um comando por nó, como no exemplo da Sprint 2.")
    modo_du = st.radio("GFC usado no fluxo de dados", ["GFC 1 — comandos IF", "GFC 2 — condições simples"],
                       index=0)
    for sigla in mutacao.OPERADORES:
        st.session_state.setdefault(f"op_{sigla}", True)
    ativos = sum(st.session_state[f"op_{s}"] for s in mutacao.OPERADORES)
    with st.expander(f"Operadores de mutação ({ativos} de {len(mutacao.OPERADORES)} ativos)", expanded=True):
        with st.container(key="ops_botoes"):
            b_todos, b_limpar = st.columns(2)
            b_todos.button("Marcar todos", on_click=_marcar_operadores, args=(True,), width="stretch")
            b_limpar.button("Limpar", on_click=_marcar_operadores, args=(False,), width="stretch")
        with st.container(key="ops_lista"):
            for sigla, descricao in mutacao.OPERADORES.items():
                st.checkbox(f"**{sigla}** :small[{descricao}]", key=f"op_{sigla}")
        if not ativos:
            st.caption("Nenhum operador ativo: a mutação não vai gerar mutantes.")
    ops = [s for s in mutacao.OPERADORES if st.session_state[f"op_{s}"]]

# ---------------------------------------------------------------------------
# Cabeçalho e fonte
# ---------------------------------------------------------------------------

st.title("🧪 Auditoria do CAD0001")
st.caption("Disciplina: Teste de Software I (Ementa 62371) | Prof. Frank Piffer | Python + Streamlit + Gemini")

if FONTES[origem] is not None:
    padrao = FONTES[origem].read_text(encoding="utf-8")
    nome_origem = FONTES[origem].name if "entregue" in origem else "cad0001_item_calculo.txt (versão do manual)"
elif enviado is not None:
    padrao = enviado.getvalue().decode("utf-8", errors="replace")
    nome_origem = enviado.name
else:
    st.info("Envie um arquivo na barra lateral.")
    st.stop()

if "entregue" in origem:
    st.warning("O arquivo entregue **não tem** a regra de negócio de negativos (`RETURN -1`) que o manual "
               "especifica. Os testes de caixa-preta vão acusar a diferença — veja a Sprint 4 (Validação).")

# altura acompanha o fonte: ~22 px por linha (0,86rem × 1,55) + ~80 px de borda e espaçamento
# interno do campo; teto para arquivos longos (o .txt entregue tem ~200 linhas)
altura_editor = min(max(22 * len(padrao.splitlines()) + 80, 260), 760)
codigo = st.text_area("Fonte CAD0001 (edite à vontade — tudo é recalculado):", value=padrao, height=altura_editor,
                      key=f"codigo::{origem}")

try:
    funcoes = listar_funcoes(codigo)
except ErroSintaxe as e:
    st.error(f"Erro de leitura do fonte: {e}")
    st.stop()
if not funcoes:
    st.error("Nenhuma FUNCTION encontrada no código.")
    st.stop()
padrao_fn = funcoes.index("cad0001_calcula_valor") if "cad0001_calcula_valor" in funcoes else 0
funcao = st.selectbox("Função sob teste", funcoes, index=padrao_fn)

st.session_state.setdefault("equivalentes", set())
try:
    A = rodar(codigo, funcao, agrupar, gfc.COMPOSTO if modo_du.startswith("GFC 1") else gfc.SIMPLES,
              tuple(ops), frozenset(st.session_state["equivalentes"]))
except ErroSintaxe as e:
    st.error(f"Erro de sintaxe no 4GL: {e}")
    st.stop()
except Exception as e:  # noqa: BLE001
    st.error(f"Não foi possível analisar a função: {e}")
    st.stop()

st.success(f"Código lido de **{nome_origem}** — FUNCTION `{A['funcao'].nome}({', '.join(A['funcao'].params)})`.")

# textos do Gemini valem só para este código
chave_codigo = hashlib.sha1(f"{codigo}|{funcao}".encode()).hexdigest()
if st.session_state.get("ia_chave") != chave_codigo:
    st.session_state["ia_chave"] = chave_codigo
    st.session_state["ia"] = {}
    st.session_state.pop("pytest", None)
    st.session_state.pop("pdf", None)
IA: dict = st.session_state["ia"]

F = A["funcao"]
P = F.params
M = A["metricas"]
tem_oraculo = len(P) == 3
if not tem_oraculo:
    st.warning("O oráculo do manual é para 3 parâmetros (CAD0001). Para outras funções, o 'esperado' "
               "não é avaliado; GFC, fluxo de dados e mutação continuam valendo.")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Casos de teste", M["casos"], f"{M['aprovados']} conferem")
c2.metric("Épsilon (ε)", fmt_brl(M["epsilon"]))
c3.metric("V(G) GFC 1 / 2", f"{M['vg1']} / {M['vg2']}")
c4.metric("Pares Def-Uso", f"{M['pares_du_cobertos']}/{M['pares_du']}")
if M["mutantes"]:
    c5.metric("Escore de Mutação", f"{M['ms'] * 100:.1f}%", f"{M['mortos']}/{M['mutantes']} mortos")
else:  # só exibição: sem mutantes não há escore, então nada de 0,0% com seta verde
    c5.metric("Escore de Mutação", "—", "sem operadores", delta_color="off", delta_arrow="off",
              help="Nenhum operador de mutação selecionado na barra lateral.")
c6.metric("Requisitos com CT", f"{M['rtm'][0]}/{M['rtm'][1]}")


def botao_gemini(chave: str, rotulo: str, montar_prompt):
    if st.button(rotulo, key=f"btn_{chave}", type="primary"):
        if not api_key:
            st.error("Insira sua API Key do Google AI Studio na barra lateral.")
        else:
            with st.spinner(f"Consultando {modelo}... (pode levar de segundos a 2 minutos)"):
                try:
                    IA[chave], IA[f"{chave}_modelo"] = gemini.gerar_com_modelo(api_key, modelo, montar_prompt())
                    st.session_state.pop("pdf", None)  # PDF antigo não tem este texto
                except gemini.ErroGemini as e:
                    st.error(str(e))
    if IA.get(chave):
        st.markdown("#### 🤖 Explicação escrita pelo Gemini")
        with st.container(border=True):
            st.markdown(IA[chave])
        usado = IA.get(f"{chave}_modelo", modelo)
        aviso = f" (o modelo escolhido, {modelo}, não respondeu; usado {usado})" if usado != modelo else ""
        st.caption(f"Gerado com **{usado}**{aviso}. Os números oficiais vêm das funções Python acima; "
                   "o Gemini só explica.")


aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "1️⃣ Caixa-Preta (PCE & AVL)", "2️⃣ Caixa-Branca (GFC & McCabe)", "3️⃣ Dados & Mutantes",
    "4️⃣ Validação & Pitch", "📑 Relatório",
])

# ---------------------------------------------------------------------------
# Sprint 1
# ---------------------------------------------------------------------------
with aba1:
    S1 = A["s1"]
    st.subheader("Particionamento em Classes de Equivalência (PCE)")
    tabela(S1["tabela_pce"])
    st.caption("NULL é válido no comportamento deste código porque é convertido em 0 antes do teste de "
               "negativos. O texto teórico do manual trata NULL como inválido, mas o fonte faz outra coisa.")
    with st.expander("Casos de teste por classe (executados no fonte)", expanded=False):
        tabela(tabelas.casos(S1["casos_pce"], P), ajustar=True, fixar="Caso")

    st.subheader("Análise do Valor Limite (AVL) e Épsilon")
    e1, e2 = st.columns([1, 2])
    e1.metric("Tipo detectado", str(S1["tipo"]))
    e1.metric("ε calculado", fmt_brl(S1["epsilon"]))
    e1.metric("Maior valor do tipo", fmt_brl(S1["maximo"]))
    e2.info(f"**Cálculo do épsilon:** {S1['justificativa']}\n\n"
            f"On-point = 0,00 · Off-point = 0,00 − ε = {fmt_brl(-S1['epsilon'])} · "
            f"Fronteira superior = {fmt_brl(S1['maximo'])} e máx + ε = {fmt_brl(S1['maximo'] + S1['epsilon'])} (estouro).")

    t_rel, t_graf = st.tabs(["📋 Tabela AVL", "📈 Gráfico de Fronteira"])
    with t_rel:
        param = st.selectbox("Parâmetro variado (os outros ficam neutros: multiplicador 1, parcela 0)", P)
        tabela(tabelas.avl_param(S1["casos_avl"], param, P), ajustar=True, fixar="Ponto")
    with t_graf:
        param_g = st.selectbox("Parâmetro do gráfico", P, key="param_graf")
        casos_g = [c for c in S1["casos_avl"] if f"-{param_g}-" in c.id]
        st.image(graficos.png(graficos.fronteira_avl(casos_g, S1["epsilon"], tema=COR)), width="stretch")
        st.caption("O gráfico mostra o retorno do cálculo, inclusive -1 para os pontos inválidos.")

    if S1["casos_cmb"]:
        st.subheader("Casos combinando os três parâmetros")
        # st.table (HTML) quebra o texto longo de "Obtido" em duas linhas e cabe na largura sem rolar;
        # o st.dataframe desenha em canvas e não quebra linha
        with st.container(key="tabela_cmb"):
            st.table(pd.DataFrame(tabelas.casos(S1["casos_cmb"], P)), hide_index=True, border="horizontal")

    def _p1():
        dados = "\n\n".join([
            "PCE:\n" + tabelas.markdown(S1["tabela_pce"]),
            f"Tipo: {S1['tipo']}; ε = {fmt_brl(S1['epsilon'])}; máximo = {fmt_brl(S1['maximo'])}. {S1['justificativa']}",
            f"AVL ({P[0]}):\n" + tabelas.markdown(tabelas.avl_param(S1["casos_avl"], P[0], P)),
            "Combinações:\n" + tabelas.markdown(tabelas.casos(S1["casos_cmb"], P, False)),
        ])
        return gemini.prompt_sprint1(codigo, dados)

    botao_gemini("s1", "🤖 Gerar explicação com Gemini (PCE & AVL)", _p1)

# ---------------------------------------------------------------------------
# Sprint 2
# ---------------------------------------------------------------------------
with aba2:
    st.markdown("Um nó reúne comandos executados em sequência. As arestas mostram para onde a execução vai. "
                "**V** = verdadeiro, **F** = falso. O grafo é gerado lendo o código acima.")
    escolha = st.radio("Grafo", ["GFC 1 — contagem por comandos IF (o OR é uma decisão)",
                                 "GFC 2 — contagem por condições simples (curto-circuito)"], horizontal=True)
    GA = A["g1"] if escolha.startswith("GFC 1") else A["g2"]
    G = GA["grafo"]
    ids = ["(nenhum)"] + [c["id"] for c in GA["casos"] if c["executavel"]]
    destaque_id = st.selectbox("Destacar o caminho do caso de teste", ids)
    destaque = next((c["caminho"] for c in GA["casos"] if c["id"] == destaque_id), [])

    col_g, col_m = st.columns([3, 2])
    with col_g:
        modo_desenho = st.radio("Desenho", ["Graphviz", "Imagem (igual ao relatório)"], horizontal=True,
                                label_visibility="collapsed")
        if modo_desenho == "Graphviz":
            st.graphviz_chart(gfc.dot(G, destaque, tema=COR), width="stretch")
        else:
            st.image(figura_gfc(G, f"{chave_codigo}{escolha}{agrupar}", tuple(destaque), escuro))
    with col_m:
        m1, m2, m3 = st.columns(3)
        m1.metric("Nós (N)", G.N)
        m2.metric("Arestas (E)", G.E)
        m3.metric("Decisões (P)", G.P)
        st.markdown("**Complexidade Ciclomática de McCabe**")
        tabela(tabelas.metricas_mccabe(G))
        if G.vg_arestas == G.vg_decisoes == G.regioes:
            st.success(f"As três fórmulas batem: V(G) = {G.vg_arestas}. São necessários no mínimo "
                       f"{G.vg_arestas} casos de teste para cobrir os caminhos independentes.")
        else:
            st.warning("As fórmulas divergem — verifique decisões com mais de duas saídas.")
        st.metric("Cobertura de arestas", f"{GA['arestas_cobertas']}/{G.E}")
        with st.expander("Nós e comandos do grafo"):
            tabela(tabelas.nos(G))
        with st.expander("Arestas do grafo"):
            tabela(tabelas.arestas(G))

    st.subheader("Caminhos básicos independentes e seus casos de teste")
    tabela(tabelas.caminhos(G, GA["casos"], P))
    st.caption("As entradas de cada caminho foram encontradas executando o fonte 4GL no interpretador "
               "do TestingStudio e conferindo a trilha de nós percorrida.")

    def _p2():
        partes = []
        for nome, ga in (("GFC 1 (comandos IF)", A["g1"]), ("GFC 2 (condições simples)", A["g2"])):
            g = ga["grafo"]
            partes += [f"### {nome}", f"N={g.N}, E={g.E}, P={g.P}, V(G)={g.vg_arestas}, regiões={g.regioes}",
                       tabelas.markdown(tabelas.nos(g)),
                       tabelas.markdown(tabelas.caminhos(g, ga["casos"], P)),
                       f"Cobertura de arestas: {ga['arestas_cobertas']}/{g.E}"]
        return gemini.prompt_sprint2("\n\n".join(partes))

    botao_gemini("s2", "🤖 Gerar explicação de Caixa-Branca com Gemini", _p2)

# ---------------------------------------------------------------------------
# Sprint 3
# ---------------------------------------------------------------------------
with aba3:
    DU = A["du"]
    st.subheader("Teste de Fluxo de Dados — pares Def-Uso")
    st.caption(f"Grafo usado: {modo_du}. d = definição, c-uso = uso computacional, p-uso = uso predicativo "
               "(fica nas arestas que saem da decisão).")
    st.markdown("**Anotação dos nós**")
    # largura total da página: "val_param1, val_param2, val_param3" mede ~236 px + respiro
    tabela(tabelas.anotacoes(DU["anotacoes"]), colunas={
        "Nó": st.column_config.TextColumn(width=56),
        "def": st.column_config.TextColumn(width=270),
        "c-uso": st.column_config.TextColumn(width=180),
        "p-uso": st.column_config.TextColumn(width=180),
    })
    st.markdown("**Cobertura — hierarquia de Rapps & Weyuker**")
    cA, cB = st.columns([1, 1])
    with cA:
        tabela(tabelas.criterios(DU["criterios"]))
    with cB:
        st.image(graficos.png(graficos.criterios_du(DU["criterios"], tema=COR)), width="stretch")
    filtro = st.radio("Pares", ["Todos", "Só não cobertos", "Só c-uso", "Só p-uso"], horizontal=True)
    lista = DU["pares"]
    if filtro == "Só não cobertos":
        lista = [p for p in lista if not p.coberto]
    elif filtro == "Só c-uso":
        lista = [p for p in lista if p.tipo == "c-uso"]
    elif filtro == "Só p-uso":
        lista = [p for p in lista if p.tipo == "p-uso"]
    tabela(tabelas.pares(lista), altura=320)
    if DU.get("sugestoes_aplicadas"):
        st.info("A suíte das Sprints 1 e 2 deixava pares DU sem cobertura. O TestingStudio procurou, executando o "
                "programa, entradas que os cobrem e as acrescentou à suíte:")
        tabela(tabelas.casos(DU["sugestoes_aplicadas"], P), ajustar=True, fixar="Caso")
    if DU["defs_sem_uso"]:
        st.warning("Definições sem uso (anomalia de fluxo de dados): " +
                   ", ".join(f"`{v}` em N{d}" for d, v in DU["defs_sem_uso"]))

    st.divider()
    st.subheader("Teste de Mutação — Escore de Mutação (MS)")
    R = A["mutacao"]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Mutantes", R["total"])
    k2.metric("Mortos", R["mortos"])
    k3.metric("Vivos", R["vivos"])
    k4.metric("Equivalentes", R["equivalentes"])
    if R["total"]:
        k5.metric("MS", f"{R['ms'] * 100:.1f}%")
        st.latex(rf"MS = \frac{{mortos}}{{total - equivalentes}} = \frac{{{R['mortos']}}}{{{R['total']} - {R['equivalentes']}}}"
                 rf" = {R['ms'] * 100:.1f}\%")
    else:  # só exibição
        k5.metric("MS", "—")
        st.info("Nenhum operador de mutação selecionado: marque pelo menos um na barra lateral para calcular o MS.")
    cm1, cm2 = st.columns(2)
    with cm1:
        st.markdown("**Por operador**")
        tabela(tabelas.por_operador(R))
    with cm2:
        st.markdown("**MS por suíte de testes**")
        tabela(tabelas.ms_suites(A["ms_suites"]))
    st.image(graficos.png(graficos.ms_por_suite(A["ms_suites"], tema=COR)), width="stretch")

    if A["mutantes"]:  # sem operadores ativos não há mutantes para listar nem comparar
        st.markdown("**Mutantes** — marque como *equivalente* um mutante vivo que nenhum teste consegue distinguir.")
        ver = st.radio("Mostrar", ["Todos", "Vivos/Equivalentes", "Mortos"], horizontal=True)
        df = pd.DataFrame(tabelas.mutantes(A["mutantes"]))
        df["Equivalente"] = df["Mutante"].isin(st.session_state["equivalentes"])
        if ver == "Vivos/Equivalentes":
            df = df[df["Status"] != "Morto"]
        elif ver == "Mortos":
            df = df[df["Status"] == "Morto"]
        editado = st.data_editor(df, hide_index=True, width="stretch", height=360,
                                 disabled=[c for c in df.columns if c != "Equivalente"], key=f"mut_{ver}")
        novos = set(st.session_state["equivalentes"])
        for _, linha in editado.iterrows():
            if linha["Equivalente"] and linha["Status"] != "Morto":
                novos.add(linha["Mutante"])
            else:
                novos.discard(linha["Mutante"])
        if novos != st.session_state["equivalentes"]:
            st.session_state["equivalentes"] = novos
            st.rerun()

        escolhido = st.selectbox("Comparar original × mutante", [m.id for m in A["mutantes"]])
        mt = next(m for m in A["mutantes"] if m.id == escolhido)
        d1, d2 = st.columns(2)
        d1.code(f"-- Original (linha {mt.linha})\n{mt.original}", language="sql")
        d2.code(f"-- {mt.id} [{mt.operador}] {mutacao.descricao_acao(mt)}\n{mt.mutado}", language="sql")
        st.caption(f"Status: **{mt.status}**" + (f" — morto por {', '.join(mt.morto_por[:6])}" if mt.morto_por else ""))

    def _p3():
        vivos = [m for m in A["mutantes"] if m.status != "Morto"]
        dados = "\n\n".join([
            "Anotações:\n" + tabelas.markdown(tabelas.anotacoes(DU["anotacoes"])),
            "Pares DU:\n" + tabelas.markdown(tabelas.pares(DU["pares"])),
            "Critérios:\n" + tabelas.markdown(tabelas.criterios(DU["criterios"])),
            f"Mutação: total={R['total']}, mortos={R['mortos']}, vivos={R['vivos']}, "
            f"equivalentes={R['equivalentes']}, MS={R['ms'] * 100:.1f}%",
            "Por operador:\n" + tabelas.markdown(tabelas.por_operador(R)),
            "MS por suíte:\n" + tabelas.markdown(tabelas.ms_suites(A["ms_suites"])),
            "Mutantes vivos:\n" + (tabelas.markdown(tabelas.mutantes(vivos)) if vivos else "nenhum"),
        ])
        return gemini.prompt_sprint3(dados)

    botao_gemini("s3", "🤖 Gerar explicação de Dados & Mutantes com Gemini", _p3)

# ---------------------------------------------------------------------------
# Sprint 4
# ---------------------------------------------------------------------------
with aba4:
    st.markdown("**Verificação** — estamos construindo o produto *da maneira certa*? · "
                "**Validação** — estamos construindo *o produto certo*? A RTM liga cada requisito "
                "aos casos de teste (cobertura bidirecional).")
    st.subheader("Requisitos do CAD0001 (extraídos do manual)")
    tabela([{"Requisito": k, "Descrição": v} for k, v in oraculo.REQUISITOS.items()])
    st.subheader("Matriz de Rastreabilidade (requisito × grupo de casos)")
    cab, linhas = tabelas.matriz_rtm(A["suite"], list(oraculo.REQUISITOS))
    tabela([dict(zip(cab, l)) for l in linhas])

    st.subheader("Execução da suíte em cada versão do CAD0001")
    for nome, v in A["validacao"].items():
        ok = not v["falharam"]
        with st.expander(f"{'✅' if ok else '❌'} {nome} — {v['passaram']}/{len(v['casos'])} casos conferem",
                         expanded=not ok):
            tabela(tabelas.rtm(v["rtm"]))
            if v["falharam"]:
                st.error("Defeitos revelados (Erro → Defeito → Falha): a saída obtida difere do oráculo.")
                tabela(tabelas.casos(v["falharam"], P), altura=260, ajustar=True, fixar="Caso")

    st.subheader("Suíte automatizada com pytest")
    st.caption("Gera `saida/test_cad0001_rtm.py` com cada caso marcado por `@pytest.mark.requisito(...)` "
               "e roda o pytest contra o fonte que está no editor.")
    if st.button("🧪 Gerar e executar pytest", disabled=not tem_oraculo):
        arq = validacao.gerar_pytest(codigo, funcao, A["suite"])
        with st.spinner("Rodando pytest..."):
            st.session_state["pytest"] = validacao.rodar_pytest(arq)
    pt = st.session_state.get("pytest")
    if pt:
        (st.success if pt["falharam"] == 0 and pt["codigo"] == 0 else st.error)(
            f"pytest: {pt['resumo'] or 'código ' + str(pt['codigo'])}")
        with st.expander("Saída do pytest"):
            st.code(pt["saida"][-8000:], language="text")
        arq = validacao.SAIDA / "test_cad0001_rtm.py"
        if arq.exists():
            st.download_button("⬇️ Baixar test_cad0001_rtm.py", arq.read_bytes(), "test_cad0001_rtm.py")

    st.subheader("🎤 Pitch de validação")
    if not IA.get("pitch"):
        with st.container(border=True):
            st.markdown(relatorio.pitch_local(A))
        st.caption("Resumo montado sem IA. Use o botão para o Gemini escrever o pitch.")

    def _p4():
        partes = [f"Métricas: {M}"]
        for nome, v in A["validacao"].items():
            partes.append(f"{nome}: {v['passaram']}/{len(v['casos'])} conferem.\n" + tabelas.markdown(tabelas.rtm(v["rtm"])))
        if pt:
            partes.append(f"pytest: {pt['resumo']}")
        return gemini.prompt_pitch("\n\n".join(partes))

    botao_gemini("pitch", "🤖 Gerar pitch com Gemini", _p4)

# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------
with aba5:
    st.subheader("Relatório para o professor")
    st.markdown("O relatório reúne as quatro Sprints: tabelas, grafos, métricas, RTM e os textos do Gemini "
                "que já foram gerados nas abas.")
    estado = {"Sprint 1 (PCE & AVL)": "s1", "Sprint 2 (GFC & McCabe)": "s2",
              "Sprint 3 (Dados & Mutantes)": "s3", "Sprint 4 (Pitch)": "pitch"}
    st.table(pd.DataFrame([{"Texto do Gemini": k, "Situação": "✅ gerado" if IA.get(v) else "— não gerado"}
                           for k, v in estado.items()]))
    if not autores:
        st.warning("Preencha **Aluno(s) / Equipe** na barra lateral para sair na capa.")
    if st.button("🤖 Gerar todos os textos que faltam com Gemini", disabled=not api_key):
        prompts = {"s1": _p1, "s2": _p2, "s3": _p3, "pitch": _p4}
        barra = st.progress(0.0)
        for i, (k, fn) in enumerate(prompts.items(), start=1):
            if not IA.get(k):
                try:
                    IA[k], IA[f"{k}_modelo"] = gemini.gerar_com_modelo(api_key, modelo, fn())
                    st.session_state.pop("pdf", None)
                except gemini.ErroGemini as e:
                    st.error(f"{k}: {e}")
                    break
            barra.progress(i / len(prompts))
        st.rerun()

    usados = sorted({v for k, v in IA.items() if k.endswith("_modelo")})
    meta = {"autores": autores, "origem": nome_origem, "modelo": ", ".join(usados) or "não utilizado",
            "pytest": st.session_state.get("pytest")}
    b1, b2 = st.columns(2)
    with b1:
        if st.button("📄 Montar relatório em PDF", type="primary", width="stretch"):
            with st.spinner("Montando PDF..."):
                st.session_state["pdf"] = relatorio.gerar_pdf(A, IA, meta)
        if st.session_state.get("pdf"):
            st.download_button("⬇️ Baixar relatorio_testingstudio.pdf", st.session_state["pdf"],
                               "relatorio_testingstudio.pdf", "application/pdf", width="stretch")
    with b2:
        st.download_button("⬇️ Baixar relatório em Markdown", relatorio.gerar_markdown(A, IA, meta),
                           "relatorio_testingstudio.md", "text/markdown", width="stretch")
