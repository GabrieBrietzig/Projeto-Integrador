# TestingStudio Web — Auditoria do CAD0001

Projeto integrador de **Teste de Software I** (Ementa 62371) — Prof. Frank Piffer — 2026.2.

Aplicação web em **Python + Streamlit + API Gemini** que lê o fonte Informix-4GL do programa
CAD0001 (`cad0001_item_calculo.txt`) e audita a função `cad0001_calcula_valor` em quatro Sprints.
No fim, gera um relatório em PDF (ou Markdown) para enviar ao professor.

| Sprint | Técnica | O que a ferramenta faz |
|---|---|---|
| 1 — Caixa-Preta | PCE e AVL com Épsilon | Classes válidas/inválidas, ε calculado a partir do tipo `DECIMAL(12,2)`, pontos On/Off/Interior/Exterior, gráfico de fronteira |
| 2 — Caixa-Branca | GFC e McCabe V(G) | Desenha o GFC lendo o código (por IF e por condições simples), calcula V(G) pelas 3 fórmulas, gera os caminhos básicos e encontra as entradas que os percorrem |
| 3 — Dados e Mutantes | Pares Def-Uso e Mutação | Anota def/c-uso/p-uso, lista pares DU, mede Todas-Defs/Todos-Usos, gera 73 mutantes (ROR, AOR, COR, NUL, CRP, SDL, LVR) e calcula o Escore de Mutação (MS) |
| 4 — Validação e Pitch | RTM e V&V | Liga requisitos a casos de teste, roda a suíte nas duas versões do CAD0001, gera e executa uma suíte **pytest** com `@pytest.mark.requisito` e monta o pitch |

Os números são calculados pelo Python (o fonte 4GL é executado por um interpretador próprio).
O **Gemini** explica e resume esses números em cada aba (botão "Gerar explicação com Gemini").

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

No Windows também dá para dar dois cliques em `rodar.bat`. O navegador abre em http://localhost:8501.

**Gemini API Key:** crie em https://aistudio.google.com (Get API key) e cole na barra lateral,
ou defina a variável de ambiente `GEMINI_API_KEY` antes de abrir. Sem chave, tudo funciona,
menos os textos escritos pela IA.

## Relatório

Aba **📑 Relatório** → *Montar relatório em PDF* → *Baixar*. O PDF traz capa, as quatro Sprints
(tabelas, grafos, gráficos, RTM, saída do pytest) e os textos do Gemini que já tiverem sido gerados.

## Achado da auditoria

O arquivo `cad0001_item_calculo.txt` entregue **não tem** a regra de negócio
`IF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN RETURN -1` que o manual da Sprint 1 especifica.
Rodando a suíte nele, os casos de negativo falham (ex.: `p1 = -0,01` devolve `-0,01` em vez de `-1`)
→ REQ03 e REQ04 reprovados na Sprint 4. A versão do manual passa em todos os casos.

## Estrutura

```
app.py                 interface Streamlit (5 abas)
core/fonte4gl.py       tokenizador, parser e interpretador do subconjunto 4GL
core/oraculo.py        regra de negócio do manual (oráculo) e requisitos REQ01–REQ06
core/caixa_preta.py    Sprint 1 — PCE, AVL, épsilon
core/gfc.py            Sprint 2 — GFC, McCabe, caminhos básicos
core/fluxo_dados.py    Sprint 3 — pares Def-Uso e critérios de Rapps & Weyuker
core/mutacao.py        Sprint 3 — operadores de mutação e MS
core/validacao.py      Sprint 4 — RTM, validação e geração/execução do pytest
core/gemini.py         integração com a API Gemini (google-genai)
core/relatorio.py      relatório PDF (fpdf2) e Markdown
dados/                 cad0001_item_calculo.txt (entregue) e cad0001_manual.4gl (versão do manual)
tests/                 testes do próprio TestingStudio (pytest)
```

Testes da ferramenta: `pytest -v`
