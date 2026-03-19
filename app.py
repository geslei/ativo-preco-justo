import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd

# Função para calcular a média e a mediana dos preços de fechamento
def calcular_media_mediana(ticker, periodo="5y"):
    ativo = yf.Ticker(ticker)
    historico = ativo.history(period=periodo)['Close']
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

# Função para calcular preço justo usando adaptação de Graham para o Brasil
def calcular_preco_justo_graham_brasil(lpa, vpa):
    """
    Calcula o preço justo usando a fórmula de Benjamin Graham adaptada para a realidade brasileira.
    
    Fórmula: Valor intrínseco = √(10 × VPA × LPA)
    
    Argumento para adaptação:
    - Nos EUA (época de Graham): P/L máx. de 15 × P/VP máx. de 1,5 = 22,5
    - No Brasil (juros altos, inflação, risco maior): P/L máx. de 8 × P/VP máx. de 1,25 = 10
    
    Margem de segurança recomendada: 20% de desconto sobre o valor calculado
    """
    if not lpa or not vpa or lpa <= 0 or vpa <= 0:
        return None, None
    
    # Fórmula adaptada para Brasil: √(10 × VPA × LPA)
    valor_intrinseco = np.sqrt(10 * vpa * lpa)
    
    # Aplicando margem de segurança de 20%
    valor_com_margem = valor_intrinseco * 0.80
    
    return valor_intrinseco, valor_com_margem

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
    media_5y, mediana_5y = calcular_media_mediana(ticker, "5y")
    media_10y, mediana_10y = calcular_media_mediana(ticker, "10y")

    # LINHA 01: PREÇO ATUAL / MEDIA 5 ANOS / MÉDIA 10 ANOS / MEDIANA 5 ANOS / MEDIANA 10 ANOS
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric('Preço Atual', f"R$ {preco_atual:.2f}" if preco_atual else 'N/A')
    col2.metric('Média (5 anos)', f"R$ {media_5y:.2f}")
    col3.metric('Média (10 anos)', f"R$ {media_10y:.2f}")
    col4.metric('Mediana (5 anos)', f"R$ {mediana_5y:.2f}")
    col5.metric('Mediana (10 anos)', f"R$ {mediana_10y:.2f}")

    # LINHA 02: BETA / VOLATILIDADE / DIVIDEND YIELD / SOMA DE DIVIDENDOS
    beta, volatilidade, dividend_yield, dividendos = obter_beta_volatilidade_dividend_yield(ticker)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Beta (1 ano)', f"{beta:.2f}" if beta is not None else 'N/A')
    col2.metric('Volatilidade (1 ano)', f"{volatilidade:.2%}" if volatilidade is not None else 'N/A')
    col3.metric('Dividend Yield (12m)', f"{dividend_yield:.2%}" if dividend_yield else 'N/A')
    col4.metric('Soma Dividendos (12m)', f"R$ {dividendos:.2f}")

    lpa_auto, vpa_auto = obter_lpa_vpa(ticker)
    st.markdown('---')
    st.markdown('### Inputs LPA / VPA')
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
    
    st.markdown('---')

    # Calcular preço justo (Graham original)
    preco_justo_graham = None
    if lpa and vpa and lpa > 0 and vpa > 0:
        preco_justo_graham = np.sqrt(lpa * vpa * 22.5)
    
    # Calcular preço justo (Graham adaptado para Brasil)
    valor_intrinseco_brasil = None
    valor_com_margem_brasil = None
    if lpa and vpa and lpa > 0 and vpa > 0:
        valor_intrinseco_brasil, valor_com_margem_brasil = calcular_preco_justo_graham_brasil(lpa, vpa)
    
    # Calcular P/L e P/VPA
    pl = None
    pvpa = None
    try:
        if lpa and lpa != 0 and preco_atual:
            pl = preco_atual / lpa
    except Exception:
        pl = None
    try:
        if vpa and vpa != 0 and preco_atual:
            pvpa = preco_atual / vpa
    except Exception:
        pvpa = None
    
    # Calcular Preço Teto (Barsi ~ 6%)
    preco_barsi = None
    if dividendos and dividendos > 0:
        preco_barsi = dividendos / 0.06
    
    # LINHA 03: LPA / VPA / PL / PVPA
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('LPA', f"R$ {lpa:.4f}" if lpa else 'N/A')
    col2.metric('VPA', f"R$ {vpa:.4f}" if vpa else 'N/A')
    col3.metric('P/L', f"{pl:.2f}" if pl else 'N/A')
    col4.metric('P/VPA', f"{pvpa:.2f}" if pvpa else 'N/A')
    
    st.markdown('---')
    
    # LINHA 04: PREÇO JUSTO BARSI / PREÇO JUSTO GRAHAM / PREÇO JUSTO BRASIL / PREÇO JUSTO BRASIL COM 20%
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        col1.metric('Preço Justo (Barsi 6%)', f"R$ {preco_barsi:.2f}" if preco_barsi else 'N/A')
    with col2:
        col2.metric('Preço Justo (Graham)', f"R$ {preco_justo_graham:.2f}" if preco_justo_graham else 'N/A')
    with col3:
        if valor_intrinseco_brasil:
            col3.metric('Preço Justo (Brasil)', f"R$ {valor_intrinseco_brasil:.2f}")
        else:
            col3.metric('Preço Justo (Brasil)', 'N/A')
    with col4:
        if valor_com_margem_brasil:
            col4.metric('Preço Justo (Brasil - 20%)', f"R$ {valor_com_margem_brasil:.2f}")
        else:
            col4.metric('Preço Justo (Brasil - 20%)', 'N/A')
    
    # LINHA 05: UPSIDE PREÇO JUSTO BARSI / UPSIDE PREÇO JUSTO GRAHAM / UPSIDE BRASIL / UPSIDE BRASIL COM 20%
    # Upside mostra o potencial de alta/baixa: (Preço Justo - Preço Atual) / Preço Justo
    upside_barsi = None
    upside_graham = None
    upside_brasil = None
    upside_brasil_20 = None
    if preco_barsi and preco_atual:
        upside_barsi = (preco_barsi - preco_atual) / preco_barsi
    if preco_justo_graham and preco_atual:
        upside_graham = (preco_justo_graham - preco_atual) / preco_justo_graham
    if valor_intrinseco_brasil and preco_atual:
        upside_brasil = (valor_intrinseco_brasil - preco_atual) / valor_intrinseco_brasil
    if valor_com_margem_brasil and preco_atual:
        upside_brasil_20 = (valor_com_margem_brasil - preco_atual) / valor_com_margem_brasil
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        col1.metric('Upside Barsi 6%', f"{upside_barsi:.2%}" if upside_barsi is not None else 'N/A')
    with col2:
        col2.metric('Upside Graham', f"{upside_graham:.2%}" if upside_graham is not None else 'N/A')
    with col3:
        col3.metric('Upside Brasil (s/ 20%)', f"{upside_brasil:.2%}" if upside_brasil is not None else 'N/A')
    with col4:
        col4.metric('Upside Brasil (c/ 20%)', f"{upside_brasil_20:.2%}" if upside_brasil_20 is not None else 'N/A')
    
    st.markdown('---')
    
    # Informações adicionais sobre a fórmula de Graham Brasil
    with st.expander('ℹ️ Explicação da Fórmula de Graham (Adaptação Brasil)'):
        st.markdown("""
        **Fórmula adaptada para o Brasil:**
        
        Valor Intrínseco = √(10 × VPA × LPA)
        Preço Sugerido = Valor Intrínseco × 0,80 (margem de segurança 20%)
        
        **Rationale da adaptação:**
        - **Nos EUA (Graham original):** P/L máximo de 15 × P/VP máximo de 1,5 = 22,5
        - **No Brasil (realidade local):** P/L máximo de 8 × P/VP máximo de 1,25 = 10
          - P/L de 8: recuperação do capital em até 8 anos
          - P/VP de 1,25: mais conservador dado juros altos, inflação e risco maior
        
        **Margem de Segurança:** 20% de desconto sobre o valor intrínseco
        - Recomenda-se comprar apenas com essa margem de segurança
        
        **Limitações:** Não é recomendado para setores como tecnologia, bancos e seguros
        """)

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
