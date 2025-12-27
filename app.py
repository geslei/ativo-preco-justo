import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd

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
    try:
        historico_ativo = ativo.history(period="1y")['Close']
        historico_benchmark = benchmark_ativo.history(period="1y")['Close']
        retornos_ativo = historico_ativo.pct_change().dropna()
        retornos_benchmark = historico_benchmark.pct_change().dropna()
        cov_matrix = np.cov(retornos_ativo, retornos_benchmark)
        beta = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix.shape == (2, 2) else None
        volatilidade = float(retornos_ativo.std() * np.sqrt(252)) if not retornos_ativo.empty else None
    except Exception:
        beta, volatilidade = None, None
    try:
        # Somar dividendos dos últimos 12 meses com base em datas
        div_series = ativo.dividends
        if not div_series.empty:
            try:
                last_date = historico_ativo.index[-1]
            except Exception:
                last_date = pd.Timestamp.today()
            one_year_ago = last_date - pd.Timedelta(days=365)
            dividendos = float(div_series[div_series.index >= one_year_ago].sum())
        else:
            dividendos = 0.0
    except Exception:
        dividendos = 0.0
    try:
        preco_atual = ativo.history(period="1d")['Close'].iloc[0]
    except Exception:
        preco_atual = None
    dividend_yield = (dividendos / preco_atual) if (preco_atual and preco_atual != 0) else None
    return beta, volatilidade, dividend_yield, dividendos


def obter_lpa_vpa(ticker):
    tk = yf.Ticker(ticker)
    lpa = None
    vpa = None
    try:
        info = tk.info
    except Exception:
        info = {}
    try:
        lpa = info.get('trailingEps') or info.get('epsTrailingTwelveMonths')
        if lpa is not None:
            lpa = float(lpa)
    except Exception:
        lpa = None
    try:
        vpa = info.get('bookValue')
        if vpa is not None:
            vpa = float(vpa)
    except Exception:
        vpa = None
    if vpa is None:
        try:
            shares = info.get('sharesOutstanding')
            total_equity = info.get('totalStockholderEquity') or info.get('totalAssets')
            if shares and total_equity:
                vpa = float(total_equity) / float(shares)
        except Exception:
            vpa = None
    if lpa is None:
        try:
            financials = tk.financials
            if 'Net Income' in financials.index:
                net_income = financials.loc['Net Income'].iloc[0]
            else:
                net_income = financials.iloc[0].iloc[0] if not financials.empty else None
            shares = info.get('sharesOutstanding')
            if net_income is not None and shares:
                lpa = float(net_income) / float(shares)
        except Exception:
            lpa = None
    return lpa, vpa

# Função principal da aplicação
def app():
    st.set_page_config(page_title='Ativo - Preço Justo', layout='wide')
    st.title('Analisador de Ações — Indicadores e Preço Justo')

    st.sidebar.header('Configurações')
    ticker = st.sidebar.text_input('Ticker (ex: PETR4.SA)', value='')
    periodo = st.sidebar.selectbox('Período do gráfico', options=['1mo', '3mo', '6mo', '1y', '5y'], index=3)
    usar_auto = st.sidebar.checkbox('Usar LPA/VPA automáticos (se disponíveis)', value=True)

    if not ticker:
        st.info('Digite um ticker na barra lateral para iniciar a análise.')
        return

    ativo = yf.Ticker(ticker)
    try:
        historico = ativo.history(period=periodo)
        df_close = historico['Close']
    except Exception:
        df_close = pd.Series(dtype='float64')

    try:
        preco_atual = float(df_close.iloc[-1]) if not df_close.empty else None
    except Exception:
        preco_atual = None
    media, mediana = calcular_media_mediana(ticker)

    st.markdown('### Visão Geral')
    col1, col2, col3 = st.columns([1.5, 1, 1])
    col1.metric('Preço Atual', f"R$ {preco_atual:.2f}" if preco_atual else 'N/A')
    col2.metric('Média (5 anos)', f"R$ {media:.2f}")
    col3.metric('Mediana (5 anos)', f"R$ {mediana:.2f}")

    beta, volatilidade, dividend_yield, dividendos = obter_beta_volatilidade_dividend_yield(ticker)
    col1, col2, col3 = st.columns(3)
    col1.metric('Beta (1 ano)', f"{beta:.2f}" if beta is not None else 'N/A')
    col2.metric('Volatilidade (1 ano)', f"{volatilidade:.2%}" if volatilidade is not None else 'N/A')
    col3.metric('Dividend Yield (12m)', f"{dividend_yield:.2%}" if dividend_yield else 'N/A')

    col4, col5 = st.columns(2)
    col4.metric('Soma Dividendos (12m)', f"R$ {dividendos:.2f}")
    col5.metric('Preço Teto (Barsi ~ 6%)', f"R$ {dividendos / 0.06:.2f}" if dividendos else 'N/A')

    lpa_auto, vpa_auto = obter_lpa_vpa(ticker)
    st.markdown('### LPA / VPA')
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if usar_auto and lpa_auto:
            lpa = st.number_input('LPA (automático)', value=float(lpa_auto), format='%.4f')
        else:
            lpa = st.number_input('LPA (Informe se não houver automático)', value=float(lpa_auto) if lpa_auto else 0.0, format='%.4f')
    with c2:
        if usar_auto and vpa_auto:
            vpa = st.number_input('VPA (automático)', value=float(vpa_auto), format='%.4f')
        else:
            vpa = st.number_input('VPA (Informe se não houver automático)', value=float(vpa_auto) if vpa_auto else 0.0, format='%.4f')
    with c3:
        st.write('Fonte: yfinance (quando disponível). Você pode ajustar manualmente os valores acima.')

    preco_justo = None
    if lpa and vpa and lpa > 0 and vpa > 0:
        preco_justo = np.sqrt(lpa * vpa * 22.5)

    st.markdown('### Preço Justo (Graham)')
    if preco_justo:
        st.metric('Preço Justo (Graham)', f"R$ {preco_justo:.2f}")
        if preco_atual:
            pct = (preco_atual - preco_justo) / preco_justo
            st.metric('Diferença vs preço atual', f"{pct:.2%}")
    else:
        st.info('LPA ou VPA inválidos para cálculo do preço justo.')

    st.markdown('### Valuation')
    pl = None
    pv = None
    try:
        if lpa and lpa != 0 and preco_atual:
            pl = preco_atual / lpa
    except Exception:
        pl = None
    try:
        if vpa and vpa != 0 and preco_atual:
            pv = preco_atual / vpa
    except Exception:
        pv = None
    ip1, ip2 = st.columns(2)
    ip1.metric('P/L', f"{pl:.2f}" if pl else 'N/A')
    ip2.metric('P/VPA', f"{pv:.2f}" if pv else 'N/A')

    st.markdown('### Gráfico de Preço')
    if not df_close.empty:
        chart_df = pd.DataFrame({'Close': df_close})
        chart_df['SMA20'] = chart_df['Close'].rolling(20).mean()
        chart_df['SMA50'] = chart_df['Close'].rolling(50).mean()
        chart_df['SMA200'] = chart_df['Close'].rolling(200).mean()
        st.line_chart(chart_df)
    else:
        st.warning('Dados históricos insuficientes para construir o gráfico.')


if __name__ == "__main__":
    app()
