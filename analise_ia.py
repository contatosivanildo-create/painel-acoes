"""
analise_ia.py
-------------
O "cérebro" da Análise do Dia.

  1. monta um resumo NUMÉRICO da carteira do usuário (montar_resumo);
  2. envia esse resumo ao Claude Haiku 4.5 — o modelo MAIS BARATO da Anthropic —
     e devolve o texto em pedaços, para aparecer "sendo digitado" (gerar_analise);
  3. se a chave faltar, estiver errada, o crédito acabar ou o serviço cair,
     devolve uma MENSAGEM AMIGÁVEL — nunca um erro técnico.

Segredo fora do código: a chave de acesso NUNCA aparece aqui. Ela é lida de
  1. .streamlit/secrets.toml   (no seu computador), ou
  2. variável de ambiente ANTHROPIC_API_KEY   (no servidor / Railway),
exatamente como a senha do primeiro administrador (ver auth._ler_secrets).

As instruções do agente ficam no arquivo  agente_analise_instrucoes.md , separado,
para você ajustar o texto sem mexer neste código.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd

try:  # fuso de Brasília para carimbar a hora da análise
    from zoneinfo import ZoneInfo

    _FUSO_BR = ZoneInfo("America/Sao_Paulo")
except Exception:  # pragma: no cover - ambiente sem base de fusos
    _FUSO_BR = None

# Modelo mais barato da Anthropic: US$ 1 / milhão de tokens de entrada,
# US$ 5 / milhão de saída (confirmado na documentação oficial em ago/2026).
MODELO_IA = "claude-haiku-4-5"

# Quantos tokens, no máximo, a análise pode ter (folga suficiente para o texto).
_MAX_TOKENS_SAIDA = 1200

_ARQ_INSTRUCOES = Path(__file__).with_name("agente_analise_instrucoes.md")

# Nome amigável para as ações mais comuns da B3. Para as demais, usamos o código.
_NOMES_EMPRESAS = {
    "PETR4": "Petrobras (PN)", "PETR3": "Petrobras (ON)",
    "VALE3": "Vale (ON)",
    "ITUB4": "Itaú Unibanco (PN)", "ITSA4": "Itaúsa (PN)",
    "BBDC4": "Bradesco (PN)", "BBAS3": "Banco do Brasil (ON)",
    "SANB11": "Santander Brasil (Unit)",
    "B3SA3": "B3 (ON)", "ABEV3": "Ambev (ON)", "WEGE3": "WEG (ON)",
    "MGLU3": "Magazine Luiza (ON)", "LREN3": "Lojas Renner (ON)",
    "RENT3": "Localiza (ON)", "SUZB3": "Suzano (ON)",
    "PRIO3": "PRIO (ON)", "ELET3": "Eletrobras (ON)", "ELET6": "Eletrobras (PNB)",
    "RADL3": "Raia Drogasil (ON)", "EQTL3": "Equatorial (ON)",
    "GGBR4": "Gerdau (PN)", "CSNA3": "CSN (ON)", "USIM5": "Usiminas (PNA)",
    "VBBR3": "Vibra Energia (ON)", "RAIZ4": "Raízen (PN)",
    "JBSS3": "JBS (ON)", "BRFS3": "BRF (ON)", "HAPV3": "Hapvida (ON)",
    "ITUB3": "Itaú Unibanco (ON)", "BPAC11": "BTG Pactual (Unit)",
}

# --- mensagens amigáveis (nunca erro técnico) ---------------------------------
_MSG_SEM_CHAVE = (
    "A Análise do Dia ainda não está configurada neste servidor. "
    "É preciso cadastrar a chave de acesso da Anthropic (ANTHROPIC_API_KEY). "
    "Se você é o responsável, veja o passo a passo no README."
)
_MSG_CHAVE_INVALIDA = (
    "A chave de acesso da Anthropic não foi aceita. "
    "Confira se ela está correta e completa nas configurações."
)
_MSG_SEM_CREDITO = (
    "O crédito da conta da Anthropic acabou. É preciso adicionar crédito "
    "para gerar novas análises. As cotações e o restante do app continuam normais."
)
_MSG_OCUPADO = (
    "Estamos gerando muitas análises ao mesmo tempo. "
    "Espere um minutinho e tente de novo."
)
_MSG_INDISPONIVEL = (
    "O serviço de análise está indisponível agora. "
    "Isso costuma ser passageiro — tente de novo em alguns minutos."
)
_MSG_SEM_INTERNET = (
    "Não consegui falar com o serviço de análise agora. "
    "Verifique a conexão e tente de novo em alguns minutos."
)


class AnaliseIndisponivel(Exception):
    """Falha que a janela mostra como aviso amigável (nunca um erro técnico)."""


# ---------------------------------------------------------------------------
# Ajudantes
# ---------------------------------------------------------------------------
def agora_brasil() -> datetime:
    """Data e hora de agora no horário de Brasília."""
    if _FUSO_BR is not None:
        return datetime.now(_FUSO_BR)
    return datetime.now()


def _reais(valor) -> str:
    try:
        texto = f"{float(valor):,.2f}"
    except (TypeError, ValueError):
        return "—"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _pct(valor) -> str:
    try:
        return f"{float(valor):+.2f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _data(momento) -> str:
    try:
        return pd.Timestamp(momento).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(momento)


def _nome_empresa(codigo: str) -> str:
    return _NOMES_EMPRESAS.get(codigo.upper(), codigo.upper())


def _limpar(valor) -> str:
    """Tira espaços, quebras de linha e caracteres invisíveis das pontas."""
    return (valor or "").strip().strip(" \t\r\n ​﻿")


def _ler_chave() -> str:
    """Lê ANTHROPIC_API_KEY de .streamlit/secrets.toml ou da variável de ambiente."""
    try:
        import streamlit as st

        if "ANTHROPIC_API_KEY" in st.secrets:
            valor = _limpar(str(st.secrets["ANTHROPIC_API_KEY"]))
            if valor:
                return valor
    except Exception:
        pass
    return _limpar(os.environ.get("ANTHROPIC_API_KEY"))


def chave_configurada() -> bool:
    """True se existe uma chave de acesso da Anthropic configurada."""
    return bool(_ler_chave())


# ---------------------------------------------------------------------------
# 1) Resumo numérico da carteira (é isto que a IA recebe — nunca os gráficos)
# ---------------------------------------------------------------------------
def _metricas_de_uma_acao(serie: pd.Series) -> dict:
    """Calcula os números de UMA ação a partir da série de preços de fechamento."""
    serie = serie.dropna()
    n = len(serie)
    preco_atual = float(serie.iloc[-1])
    preco_inicial = float(serie.iloc[0])
    maximo = float(serie.max())
    minimo = float(serie.min())

    # variação nos últimos 5 pregões (precisa de pelo menos 6 pontos)
    if n >= 6:
        var_5 = (preco_atual / float(serie.iloc[-6]) - 1) * 100
    else:
        var_5 = None

    # tendência: média móvel de 20 dias x média móvel de 50 dias
    if n >= 50:
        mm20 = float(serie.rolling(20).mean().iloc[-1])
        mm50 = float(serie.rolling(50).mean().iloc[-1])
        if mm20 > mm50:
            tendencia = (
                "média de 20 dias ACIMA da média de 50 dias "
                "(tendência de alta no médio prazo)"
            )
        else:
            tendencia = (
                "média de 20 dias ABAIXO da média de 50 dias "
                "(tendência de baixa no médio prazo)"
            )
    else:
        tendencia = "poucos pregões para calcular a tendência de 20/50 dias"

    # volatilidade: desvio-padrão das variações diárias, em %
    retornos = serie.pct_change().dropna()
    volatilidade = float(retornos.std() * 100) if len(retornos) >= 3 else None

    return {
        "pregões": n,
        "preco_atual": preco_atual,
        "data_atual": serie.index[-1],
        "var_periodo": (preco_atual / preco_inicial - 1) * 100,
        "minimo": minimo,
        "data_minimo": serie.idxmin(),
        "maximo": maximo,
        "data_maximo": serie.idxmax(),
        "abaixo_da_maxima": (preco_atual / maximo - 1) * 100,
        "var_5_pregoes": var_5,
        "tendencia": tendencia,
        "volatilidade": volatilidade,
    }


def montar_resumo(
    precos: pd.DataFrame,
    nao_encontrados: list[str],
    periodo_rotulo: str,
    usuario_nome: str,
    quando: datetime | None = None,
) -> str:
    """
    Monta o texto com os NÚMEROS da carteira que a IA vai receber.

      precos          -> DataFrame: uma coluna por ação (ex.: 'PETR4'), linhas por data.
      nao_encontrados -> códigos da carteira que não retornaram dados (ex.: ['ABCD1']).
      periodo_rotulo  -> '1 mês', 'No ano', '1 ano', ...
      usuario_nome    -> nome completo do usuário logado.
    """
    quando = quando or agora_brasil()
    pregoes = len(precos.index)

    linhas: list[str] = [
        "DADOS DA CARTEIRA (use apenas estes números; não busque nada por fora)",
        "",
        f"Data de hoje: {quando.strftime('%d/%m/%Y')}",
        f"Usuário: {usuario_nome}",
        f"Período analisado: {periodo_rotulo}",
        f"Pregões no período (aprox.): {pregoes}",
        "",
    ]

    for codigo in precos.columns:
        m = _metricas_de_uma_acao(precos[codigo])
        if m["var_5_pregoes"] is None:
            var5 = "sem histórico suficiente (menos de 6 pregões)"
        else:
            var5 = _pct(m["var_5_pregoes"])
        if m["volatilidade"] is None:
            vol = "sem histórico suficiente"
        else:
            vol = f"oscila em média {m['volatilidade']:.2f}% por pregão".replace(".", ",")

        linhas += [
            f"Ação {codigo} — {_nome_empresa(codigo)}",
            f"- Preço atual: {_reais(m['preco_atual'])} (pregão de {_data(m['data_atual'])})",
            f"- Variação no período: {_pct(m['var_periodo'])}",
            f"- Mínima do período: {_reais(m['minimo'])} em {_data(m['data_minimo'])}",
            f"- Máxima do período: {_reais(m['maximo'])} em {_data(m['data_maximo'])}",
            f"- Distância da máxima: {_pct(m['abaixo_da_maxima'])} (abaixo da máxima do período)",
            f"- Variação nos últimos 5 pregões: {var5}",
            f"- Tendência: {m['tendencia']}",
            f"- Volatilidade: {vol}",
            "",
        ]

    for codigo in nao_encontrados or []:
        linhas += [
            f"Ação {codigo} — {_nome_empresa(codigo)}",
            "- SEM DADOS no período (ficou de fora da análise)",
            "",
        ]

    return "\n".join(linhas).strip()


# ---------------------------------------------------------------------------
# 2) Chamada à IA, com o texto vindo em pedaços (efeito de digitação)
# ---------------------------------------------------------------------------
def gerar_analise(resumo: str, estado: dict):
    """
    Gerador: entrega o texto da Análise do Dia em pedaços, para o Streamlit
    mostrar "sendo digitado".

      estado -> dicionário mutável. No fim, estado["ok"] = True se a análise foi
                concluída com sucesso (aí a tela pode guardá-la por 15 minutos),
                ou False se caiu numa mensagem amigável.
    """
    estado["ok"] = False

    chave = _ler_chave()
    if not chave:
        yield _MSG_SEM_CHAVE
        return

    try:
        instrucoes = _ARQ_INSTRUCOES.read_text(encoding="utf-8").strip()
    except Exception:
        yield (
            "Não encontrei o arquivo de instruções da análise "
            "(agente_analise_instrucoes.md). Avise o responsável pelo app."
        )
        return

    try:
        import anthropic
    except Exception:
        yield _MSG_INDISPONIVEL
        return

    cliente = anthropic.Anthropic(api_key=chave)
    try:
        with cliente.messages.stream(
            model=MODELO_IA,
            max_tokens=_MAX_TOKENS_SAIDA,
            system=instrucoes,
            messages=[{"role": "user", "content": resumo}],
        ) as fluxo:
            for pedaco in fluxo.text_stream:
                yield pedaco
        estado["ok"] = True
    except anthropic.AuthenticationError:
        yield "\n\n" + _MSG_CHAVE_INVALIDA
    except anthropic.PermissionDeniedError:
        yield "\n\n" + _MSG_CHAVE_INVALIDA
    except anthropic.RateLimitError:
        yield "\n\n" + _MSG_OCUPADO
    except anthropic.BadRequestError as erro:
        texto = (getattr(erro, "message", "") or str(erro)).lower()
        if "credit" in texto or "balance" in texto or "quota" in texto:
            yield "\n\n" + _MSG_SEM_CREDITO
        else:
            yield "\n\n" + _MSG_INDISPONIVEL
    except anthropic.APIConnectionError:
        yield "\n\n" + _MSG_SEM_INTERNET
    except anthropic.APIStatusError:
        yield "\n\n" + _MSG_INDISPONIVEL
    except Exception:
        # Rede de segurança: qualquer outra falha vira aviso amigável.
        yield "\n\n" + _MSG_INDISPONIVEL
