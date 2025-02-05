import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Função para calcular a média e a mediana dos preços de fechamento dos últimos 5 anos
def calcular_media_mediana(ticker):
    # Obtendo dados históricos dos últimos 5 anos
    ativo = yf.Ticker(ticker)
    historico = ativo.history(period="5y")['Close']
    
    # Calculando média e mediana
    media = historico.mean()
    mediana = historico.median()
    
    return media, mediana

# Função para calcular o Beta, a volatilidade e o dividend yield
def obter_beta_volatilidade_dividend_yield(ticker, benchmark='^BVSP'):
    ativo = yf.Ticker(ticker)
    benchmark_ativo = yf.Ticker(benchmark)

    # Obtendo dados históricos de 1 ano
    historico_ativo = ativo.history(period="1y")['Close']
    historico_benchmark = benchmark_ativo.history(period="1y")['Close']

    # Calculando os retornos diários
    retornos_ativo = historico_ativo.pct_change().dropna()
    retornos_benchmark = historico_benchmark.pct_change().dropna()

    # Calculando o Beta
    cov_matrix = np.cov(retornos_ativo, retornos_benchmark)
    beta = cov_matrix[0, 1] / cov_matrix[1, 1]

    # Calculando a volatilidade
    volatilidade = retornos_ativo.std() * np.sqrt(252)  # Anualizando a volatilidade

    # Calculando o dividend yield como a soma dos dividendos nos últimos 12 meses dividido pelo preço atual
    dividendos = ativo.dividends[-252:].sum()
    preco_atual = ativo.history(period="1d")['Close'].iloc[0]
    dividend_yield = dividendos / preco_atual if preco_atual else None

    return beta, volatilidade, dividend_yield

# Função principal da aplicação
def app():
    st.title('Analisador de Ações - Indicadores Financeiros')

    # Entrada de ticker
    ticker = st.text_input('Digite o ticker da ação (ex: PETR4.SA):')

    if ticker:
        # Exibindo a cotação atual
        ativo = yf.Ticker(ticker)
        preco_atual = ativo.history(period="1d")['Close'].iloc[0]
        
        # Calculando a média e mediana dos preços dos últimos 5 anos
        media, mediana = calcular_media_mediana(ticker)

        # Dividindo a interface em três colunas
        col1, col2, col3 = st.columns(3)
        
        # Exibindo resultados nas colunas
        col1.metric(label=f"Preço Atual para {ticker}", value=f"R${preco_atual:.2f}")
        col2.metric(label=f"Média dos últimos 5 anos para {ticker}", value=f"R${media:.2f}")
        col3.metric(label=f"Mediana dos últimos 5 anos para {ticker}", value=f"R${mediana:.2f}")

        # Obtendo Beta, Volatilidade e Dividend Yield
        beta, volatilidade, dividend_yield = obter_beta_volatilidade_dividend_yield(ticker)

        # Dividindo a interface em três colunas para Beta, Volatilidade e Dividend Yield
        col1, col2, col3 = st.columns(3)
        
        # Exibindo resultados nas colunas
        col1.metric(label=f"Beta (1 ano)", value=f"{beta:.2f}")
        col2.metric(label=f"Volatilidade (1 ano)", value=f"{volatilidade:.2%}")
        if dividend_yield is not None:
            col3.metric(label=f"Dividend Yield (1 ano)", value=f"{dividend_yield:.2%}")
        else:
            col3.metric(label=f"Dividend Yield (1 ano)", value="Dados não disponíveis")

if __name__ == "__main__":
    app()

