import streamlit as st
import yfinance as yf
import numpy as np

# Função para calcular a média e a mediana dos preços de fechamento dos últimos 5 anos
def calcular_media_mediana(ticker):
    ativo = yf.Ticker(ticker)
    historico = ativo.history(period="5y")['Close']
    media = historico.mean()
    mediana = historico.median()
    return media, mediana

# Função para calcular o Beta, a volatilidade e o dividend yield
def obter_beta_volatilidade_dividend_yield(ticker, benchmark='^BVSP'):
    ativo = yf.Ticker(ticker)
    benchmark_ativo = yf.Ticker(benchmark)
    historico_ativo = ativo.history(period="1y")['Close']
    historico_benchmark = benchmark_ativo.history(period="1y")['Close']
    retornos_ativo = historico_ativo.pct_change().dropna()
    retornos_benchmark = historico_benchmark.pct_change().dropna()
    cov_matrix = np.cov(retornos_ativo, retornos_benchmark)
    beta = cov_matrix[0, 1] / cov_matrix[1, 1]
    volatilidade = retornos_ativo.std() * np.sqrt(252)
    dividendos = ativo.dividends[-252:].sum()
    preco_atual = ativo.history(period="1d")['Close'].iloc[0]
    dividend_yield = dividendos / preco_atual if preco_atual else None
    return beta, volatilidade, dividend_yield, dividendos

# Função principal da aplicação
def app():
    st.title('Analisador de Ações - Indicadores Financeiros')

    # Entrada de ticker
    ticker = st.text_input('Digite o ticker da ação (ex: PETR4.SA):')

    if ticker:
        ativo = yf.Ticker(ticker)
        preco_atual = ativo.history(period="1d")['Close'].iloc[0]
        media, mediana = calcular_media_mediana(ticker)

        # Indicadores Históricos
        st.markdown("### Indicadores")
        col1, col2, col3 = st.columns(3)
        col1.metric(label="Preço Atual", value=f"R$ {preco_atual:.2f}")
        col2.metric(label="Média (5 anos)", value=f"R$ {media:.2f}")
        col3.metric(label="Mediana (5 anos)", value=f"R$ {mediana:.2f}")

        beta, volatilidade, dividend_yield, dividendos = obter_beta_volatilidade_dividend_yield(ticker)
        col1, col2, col3 = st.columns(3)
        col1.metric(label="Beta (1 ano)", value=f"{beta:.2f}")
        col2.metric(label="Volatilidade (1 ano)", value=f"{volatilidade:.2%}")
        col3.metric(label="Dividend Yield (1 ano)", value=f"{dividend_yield:.2%}" if dividend_yield else "N/A")

        col4, col5 = st.columns(2)
        col4.metric(label="Soma dos Dividendos (12 meses)", value=f"R$ {dividendos:.2f}")
        col5.metric(label="Preço Teto Barsi", value=f"R$ {dividendos / 0.06:.2f}" if dividendos else "N/A")
        
        
        # Entrada do LPA e VPA
        col1, col2 = st.columns(2)
        with col1:
            lpa = st.number_input("Informe o LPA (Lucro por Ação):", value=0.0, step=0.01)
        with col2:
            vpa = st.number_input("Informe o VPA (Valor Patrimonial por Ação):", value=0.0, step=0.01)
        
        if lpa > 0 and vpa > 0:
            preco_justo = np.sqrt(lpa * vpa * 22.5)
        else:
            preco_justo = None
            
        # Exibição do Preço Justo Gahan
        if preco_justo:
            st.markdown("### Preço Justo (Graham)")
            st.metric(label="Preço Justo Gahan", value=f"R$ {preco_justo:.2f}")


if __name__ == "__main__":
    app()
