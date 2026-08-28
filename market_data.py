"""
market_data.py
--------------
Busca as cotações das ações no Yahoo Finance.

Regras importantes:
  - os dados são buscados quando alguém abre o app e ficam guardados
    por 15 minutos (cache). Clicar nos botões não faz baixar tudo de novo;
  - se o Yahoo não responder, ou se o código da ação não existir, quem
    chama recebe a informação de forma organizada para mostrar uma
    mensagem amigável — nunca um erro técnico na tela.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st
import yfinance as yf

# Períodos oferecidos nos botões dos gráficos.
# A chave é o "código" que o Yahoo entende; o valor é o texto do botão.
PERIODOS = {
    "1mo": "1 mês",
    "3mo": "3 meses",
    "6mo": "6 meses",
    "ytd": "No ano",
    "1y": "1 ano",
    "max": "Máximo",
}
PERIODO_PADRAO = "ytd"

# Quanto tempo os dados ficam guardados antes de buscar de novo (em segundos).
CACHE_SEGUNDOS = 15 * 60  # 15 minutos


@dataclass
class ResultadoMercado:
    """O que a busca devolve, já organizado para a tela."""
    precos: pd.DataFrame = field(default_factory=pd.DataFrame)  # colunas = tickers
    nao_encontrados: list[str] = field(default_factory=list)     # códigos sem dados
    erro_de_conexao: bool = False                                # Yahoo não respondeu

    @property
    def tem_dados(self) -> bool:
        return not self.precos.empty


def normalizar_ticker(codigo: str) -> str:
    """
    Ajusta o que o usuário digitou para o formato do Yahoo Finance.
    Ex.:  'wege3'  ->  'WEGE3.SA'  |  'PETR4.SA' continua 'PETR4.SA'
    Ações brasileiras (B3) no Yahoo terminam com  .SA
    """
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return ""
    if "." not in codigo:
        codigo += ".SA"
    return codigo


def exibir_ticker(codigo: str) -> str:
    """Versão curta para mostrar na tela: 'PETR4.SA' -> 'PETR4'."""
    return (codigo or "").upper().replace(".SA", "")


@st.cache_data(ttl=CACHE_SEGUNDOS, show_spinner=False)
def buscar_historico(tickers: tuple[str, ...], periodo: str) -> ResultadoMercado:
    """
    Versão com cache (guarda o resultado por 15 minutos).
    O Streamlit usa os argumentos (tickers + período) como "chave" do cache.
    """
    return _buscar_historico_sem_cache(tickers, periodo)


def _buscar_historico_sem_cache(tickers: tuple[str, ...], periodo: str) -> ResultadoMercado:
    """A busca de verdade. Separada para poder ser testada sem o Streamlit."""
    resultado = ResultadoMercado()
    if not tickers:
        return resultado

    series_por_ticker: dict[str, pd.Series] = {}
    houve_excecao = False

    for ticker in tickers:
        try:
            historico = yf.Ticker(ticker).history(
                period=periodo, auto_adjust=True, raise_errors=False
            )
        except Exception:
            # Falha de rede / Yahoo fora do ar para este código.
            houve_excecao = True
            continue

        if historico is None or historico.empty or "Close" not in historico.columns:
            resultado.nao_encontrados.append(exibir_ticker(ticker))
            continue

        fechamento = historico["Close"].dropna()
        if fechamento.empty:
            resultado.nao_encontrados.append(exibir_ticker(ticker))
            continue

        series_por_ticker[ticker] = fechamento

    if series_por_ticker:
        tabela = pd.DataFrame(series_por_ticker)
        # Tira o fuso horário do índice para os gráficos ficarem simples.
        try:
            tabela.index = tabela.index.tz_localize(None)
        except (TypeError, AttributeError):
            pass
        resultado.precos = tabela.dropna(how="all")

    # Se nada deu certo e houve erro de rede (ou simplesmente veio tudo vazio),
    # tratamos como "Yahoo não respondeu".
    if not series_por_ticker and (houve_excecao or not resultado.nao_encontrados):
        resultado.erro_de_conexao = True

    return resultado


def ticker_valido(ticker: str) -> bool:
    """
    Faz uma consulta rápida para saber se um código existe no Yahoo.
    Usada quando o usuário adiciona uma ação à carteira.
    """
    resultado = _buscar_historico_sem_cache((ticker,), "1mo")
    return resultado.tem_dados
