"""Integração com a API Gemini (Google AI Studio) via SDK google-genai.

A IA é usada como parceira de pareamento: ela EXPLICA e RESUME os números
calculados pelo Python, mas não é a fonte desses números.
"""
from __future__ import annotations

import os
import re
import time

# Ordem: rápido e bom primeiro. O gemini-2.5-* não está mais disponível para contas novas.
MODELOS_PADRAO = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]

INSTRUCAO = (
    "Você é um auditor de Teste de Software ajudando estudantes de Engenharia de Software "
    "(disciplina Teste de Software I, referência: Delamaro, Maldonado e Jino, 2007). "
    "Responda em português do Brasil, com linguagem clara e objetiva, em Markdown. "
    "Use SOMENTE os números e tabelas fornecidos no pedido: não invente valores, não "
    "recalcule de outro jeito e não crie casos de teste novos que não estejam nos dados. "
    "Se notar algo estranho nos dados, aponte como observação."
)


class ErroGemini(Exception):
    pass


def chave_do_ambiente() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def _cliente(api_key: str):
    try:
        from google import genai
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ErroGemini("SDK não instalado. Rode: pip install -U google-genai") from exc
    if not api_key:
        raise ErroGemini("Informe a Gemini API Key na barra lateral (aistudio.google.com).")
    from google.genai import types

    # modelos novos podem demorar ~2 min no Free Tier; poucas re-tentativas internas para
    # poder trocar de modelo em vez de ficar preso num servidor ocupado
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(
        timeout=150_000, retry_options=types.HttpRetryOptions(attempts=2)))


def listar_modelos(api_key: str) -> list[str]:
    cli = _cliente(api_key)
    nomes = []
    for m in cli.models.list():
        acoes = getattr(m, "supported_actions", None) or []
        if "generateContent" in acoes and "gemini" in m.name:
            nomes.append(m.name.removeprefix("models/"))
    # recomendados primeiro (o primeiro da lista vira o padrão na tela)
    preferidos = [m for m in MODELOS_PADRAO if m in nomes]
    outros = [m for m in sorted(nomes) if m not in preferidos and not any(
        x in m for x in ("tts", "image", "computer-use", "transcribe", "robotics", "banana"))]
    return preferidos + outros


def gerar(api_key: str, modelo: str, prompt: str) -> str:
    return gerar_com_modelo(api_key, modelo, prompt)[0]


def gerar_com_modelo(api_key: str, modelo: str, prompt: str) -> tuple[str, str]:
    """Gera o texto e devolve (texto, modelo que respondeu).

    Se o modelo escolhido foi descontinuado (404), está sobrecarregado (503) ou
    estourou o tempo (504), tenta o substituto indicado pela API e depois os
    modelos recomendados, nessa ordem.
    """
    from google.genai import errors, types

    cli = _cliente(api_key)
    config = types.GenerateContentConfig(system_instruction=INSTRUCAO, temperature=0.3)
    fila = [modelo] + [m for m in MODELOS_PADRAO if m != modelo]
    tentados: list[str] = []
    esperas_429 = 0
    ultimo = None
    while fila:
        atual = fila.pop(0)
        if atual in tentados:
            continue
        try:
            resp = cli.models.generate_content(model=atual, contents=prompt, config=config)
            return (resp.text or "").strip() or "_O modelo não devolveu texto._", atual
        except errors.APIError as exc:
            codigo = getattr(exc, "code", None)
            ultimo = exc
            if codigo in (400, 403) and "API key" in str(exc):
                raise ErroGemini("API Key inválida ou sem permissão (API_KEY_INVALID).") from exc
            if codigo == 429 and esperas_429 < 2:
                esperas_429 += 1
                time.sleep(8 * esperas_429)  # limite de requisições por minuto do Free Tier
                fila.insert(0, atual)
                continue
            tentados.append(atual)
            if codigo == 404:
                # a própria API indica o substituto ("use models/gemini-x")
                sugerido = re.search(r"use models/([\w.\-]+)", str(exc))
                if sugerido:
                    fila.insert(0, sugerido.group(1))
                continue
            if codigo in (500, 503, 504):
                continue  # modelo ocupado ou lento: tenta o próximo
            raise ErroGemini(f"Erro da API Gemini ({codigo}): {exc}") from exc
        except Exception as exc:  # rede, DNS etc.
            raise ErroGemini(f"Falha ao chamar o Gemini: {exc}") from exc
    codigo = getattr(ultimo, "code", None)
    if codigo == 429:
        raise ErroGemini("Limite do Free Tier atingido (HTTP 429). Aguarde um minuto e tente de novo.")
    raise ErroGemini(f"Nenhum modelo respondeu (tentados: {', '.join(tentados)}). "
                     f"Último erro: {codigo}. Os servidores do Gemini podem estar ocupados; tente de novo em instantes.")


# ---------------------------------------------------------------------------
# Prompts de cada Sprint
# ---------------------------------------------------------------------------


def prompt_sprint1(codigo: str, dados_md: str) -> str:
    return f"""Analise o programa CAD0001 abaixo com técnicas de Caixa-Preta.

Código-fonte (Informix-4GL):
```
{codigo}
```

Dados calculados pelo TestingStudio (Python):
{dados_md}

Escreva:
1. **Tabela PCE** — explique as classes válidas e inválidas de cada parâmetro (inclua a tabela).
2. **Justificativa do Épsilon** — por que ε = 0,01 para DECIMAL(12,2) e o que isso muda nos testes.
3. **Tabela AVL** — explique os 4 pontos (On, Off, Interior, Exterior) e o limite superior do tipo.
4. **Observações** — diferenças entre o que o manual diz (NULL como inválido) e o que o código faz.
Seja direto (máximo ~450 palavras fora as tabelas)."""


def prompt_sprint2(dados_md: str) -> str:
    return f"""Explique a análise de Caixa-Branca (Grafo de Fluxo de Controle e McCabe) do CAD0001.

Dados calculados pelo TestingStudio (Python):
{dados_md}

Explique, para um estudante:
1. O que são nós, arestas, desvios V/F e caminhos linearmente independentes.
2. Por que o GFC por comandos IF tem um V(G) e o GFC por condições simples tem outro (curto-circuito do OR).
3. Como as três fórmulas de McCabe (E − N + 2, P + 1 e Regiões) chegam ao mesmo número.
4. O que significa a cobertura de arestas obtida pelos casos de teste listados.
Máximo ~400 palavras."""


def prompt_sprint3(dados_md: str) -> str:
    return f"""Explique os resultados de Teste Baseado em Defeitos (Fluxo de Dados e Mutação) do CAD0001.

Dados calculados pelo TestingStudio (Python):
{dados_md}

Escreva:
1. **Fluxo de Dados** — o que são definições, c-usos e p-usos; comente os pares Def-Uso e a cobertura dos critérios de Rapps & Weyuker (Todas-Definições ⊂ Todos-Usos).
2. **Mutação** — explique a hipótese do programador competente, os operadores usados e o Escore de Mutação (MS).
3. **Comparação entre suítes** — por que algumas suítes matam menos mutantes (ex.: só AVL não detecta troca de * por /).
4. **Mutantes vivos** — se houver, diga se parecem equivalentes ou se falta caso de teste.
Máximo ~450 palavras."""


def prompt_pitch(dados_md: str) -> str:
    return f"""Monte o PITCH DE VALIDAÇÃO do TestingStudio Web (projeto integrador da disciplina Teste de Software I).

Métricas e resultados reais da auditoria do CAD0001:
{dados_md}

Estrutura (Markdown, máximo ~350 palavras):
- **O problema** (1 frase)
- **A solução** — o TestingStudio Web: Python + Streamlit + Gemini, 4 sprints
- **Números que provam** — use os números fornecidos (casos de teste, V(G), pares DU, MS, cobertura RTM)
- **Defeitos encontrados** — Verificação × Validação (estamos construindo o produto certo?)
- **Próximos passos** — 2 ou 3 itens
Tom: apresentação curta para banca/professor."""
