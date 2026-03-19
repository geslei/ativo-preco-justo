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


# Função para calcular o PEG Ratio
def calcular_peg_ratio(ticker, pl):
    """
    Calcula o PEG Ratio = P/L / Taxa de Crescimento de Lucros (%)
    
    Busca o crescimento histórico do LPA nos últimos 5 anos.
    Se não conseguir dados, usa uma taxa padrão de 12% (expectativa para Brasil).
    """
    if not pl or pl <= 0:
        return None
    
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        
        # Tentar obter a taxa de crescimento esperado (forward estimate)
        growth_rate = None
        
        # Primeiro, tenta obter do yfinance (earningsGrowth)
        if 'earningsGrowth' in info and info['earningsGrowth'] is not None:
            growth_rate = float(info['earningsGrowth']) * 100
        
        # Se não conseguir, tenta calcular a partir dos históricos de ganhos
        if growth_rate is None or growth_rate == 0:
            try:
                # Obtém os earnings históricos
                financials = tk.quarterly_financials
                if 'Net Income' in financials.index:
                    earnings = financials.loc['Net Income']
                elif not financials.empty:
                    earnings = financials.iloc[0]
                else:
                    earnings = None
                
                if earnings is not None and len(earnings) >= 2:
                    # Calcula a taxa média de crescimento dos últimos trimestres
                    earnings_clean = earnings.dropna()[earnings.dropna() != 0]
                    if len(earnings_clean) >= 2:
                        # CAGR simplificado
                        oldest = earnings_clean.iloc[-1]
                        newest = earnings_clean.iloc[0]
                        if oldest > 0:
                            periods = len(earnings_clean) - 1
                            growth_rate = ((newest / oldest) ** (1/periods) - 1) * 100
            except Exception:
                growth_rate = None
        
        # Se ainda não tiver growth_rate, usa taxa padrão para Brasil
        if growth_rate is None or growth_rate <= 0:
            growth_rate = 12.0  # Taxa padrão de crescimento esperado no Brasil (12%)
        
        # PEG Ratio = P/L / Taxa de Crescimento (%)
        peg_ratio = pl / growth_rate if growth_rate > 0 else None
        
        return peg_ratio, growth_rate
    
    except Exception:
        return None, None

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
    
    # CSS customizado para melhorar o layout
    st.markdown("""
    <style>
        .section-header {
            background: linear-gradient(90deg, #1f77b4 0%, #2ca02c 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            margin-top: 20px;
            margin-bottom: 15px;
            font-size: 18px;
            font-weight: bold;
        }
        .metric-card {
            background: #f0f2f6;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #1f77b4;
        }
        .alert-box {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }
        .success-box {
            background: #d4edda;
            border: 1px solid #28a745;
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }
        .danger-box {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.title('📈 Analisador de Ações — Indicadores e Preço Justo')

    st.sidebar.header('⚙️ Configurações')
    ticker = st.sidebar.text_input('Ticker (ex: PETR4.SA)', value='', placeholder='Digite o ticker')
    periodo = st.sidebar.selectbox('Período do gráfico', options=['1mo', '3mo', '6mo', '1y', '5y'], index=3)
    usar_auto = st.sidebar.checkbox('Usar LPA/VPA automáticos (se disponíveis)', value=True)

    if not ticker:
        st.info('👉 Digite um ticker na barra lateral para iniciar a análise.')
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

    # ============================================
    # SEÇÃO 1: VISÃO GERAL DA AÇÃO
    # ============================================
    st.markdown('<div class="section-header">💰 VISÃO GERAL</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric('🎯 Preço Atual', f"R$ {preco_atual:.2f}" if preco_atual else 'N/A')
    col2.metric('📊 Média (5a)', f"R$ {media_5y:.2f}")
    col3.metric('📊 Média (10a)', f"R$ {media_10y:.2f}")
    col4.metric('📈 Mediana (5a)', f"R$ {mediana_5y:.2f}")
    col5.metric('📈 Mediana (10a)', f"R$ {mediana_10y:.2f}")

    # ============================================
    # SEÇÃO 2: MÉTRICAS DE RISCO E RENDIMENTO
    # ============================================
    st.markdown('<div class="section-header">⚡ RISCO E RENDIMENTO</div>', unsafe_allow_html=True)
    
    beta, volatilidade, dividend_yield, dividendos = obter_beta_volatilidade_dividend_yield(ticker)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('📍 Beta (1a)', f"{beta:.2f}" if beta is not None else 'N/A', 
                delta='Alto risco' if beta and beta > 1 else 'Baixo risco' if beta else None)
    col2.metric('📊 Volatilidade', f"{volatilidade:.2%}" if volatilidade is not None else 'N/A')
    col3.metric('💵 Dividend Yield', f"{dividend_yield:.2%}" if dividend_yield else 'N/A')
    col4.metric('💸 Dividendos (12m)', f"R$ {dividendos:.2f}")

    # ============================================
    # SEÇÃO 3: DADOS DE ENTRADA (LPA/VPA)
    # ============================================
    st.markdown('<div class="section-header">📝 DADOS FUNDAMENTAIS</div>', unsafe_allow_html=True)
    
    lpa_auto, vpa_auto = obter_lpa_vpa(ticker)
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if usar_auto and lpa_auto:
            lpa = st.number_input('LPA (Lucro por Ação)', value=float(lpa_auto), format='%.4f')
        else:
            lpa = st.number_input('LPA (Lucro por Ação)', value=float(lpa_auto) if lpa_auto else 0.0, format='%.4f')
    with c2:
        if usar_auto and vpa_auto:
            vpa = st.number_input('VPA (Valor Patrimonial)', value=float(vpa_auto), format='%.4f')
        else:
            vpa = st.number_input('VPA (Valor Patrimonial)', value=float(vpa_auto) if vpa_auto else 0.0, format='%.4f')
    with c3:
        st.markdown('<p style="color: #666; font-size: 13px; margin-top: 32px;">Fonte: yfinance (quando disponível). Ajuste manualmente se necessário.</p>', 
                   unsafe_allow_html=True)

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
    
    # ============================================
    # SEÇÃO 4: INDICADORES DE VALORAÇÃO
    # ============================================
    st.markdown('<div class="section-header">🎲 INDICADORES DE VALORAÇÃO</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('LPA', f"R$ {lpa:.4f}" if lpa else 'N/A')
    col2.metric('VPA', f"R$ {vpa:.4f}" if vpa else 'N/A')
    col3.metric('P/L (Preço/Lucro)', f"{pl:.2f}x" if pl else 'N/A')
    col4.metric('P/VPA (Preço/Patrimônio)', f"{pvpa:.2f}x" if pvpa else 'N/A')

    # ============================================
    # SEÇÃO 5: PREÇOS JUSTOS
    # ============================================
    st.markdown('<div class="section-header">💎 PREÇOS JUSTOS</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric('Barsi (6%)', f"R$ {preco_barsi:.2f}" if preco_barsi else 'N/A')
    with col2:
        st.metric('Graham (USA)', f"R$ {preco_justo_graham:.2f}" if preco_justo_graham else 'N/A')
    with col3:
        st.metric('Brasil (Puro)', f"R$ {valor_intrinseco_brasil:.2f}" if valor_intrinseco_brasil else 'N/A')
    with col4:
        st.metric('Brasil (- 20%)', f"R$ {valor_com_margem_brasil:.2f}" if valor_com_margem_brasil else 'N/A')

    # Calcular PEG Ratio
    peg_ratio = None
    growth_rate = None
    if pl is not None and pl > 0:
        peg_ratio, growth_rate = calcular_peg_ratio(ticker, pl)
    
    # ============================================
    # SEÇÃO 6: ANÁLISE PEG RATIO
    # ============================================
    st.markdown('<div class="section-header">📊 ANÁLISE PEG RATIO</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric('PEG Ratio', f"{peg_ratio:.2f}" if peg_ratio is not None else 'N/A')
    with col2:
        st.metric('Crescimento LPA', f"{growth_rate:.1f}%" if growth_rate is not None else 'N/A')
    
    # Determinar se está BARATO ou NÃO conforme PEG Ratio
    avaliacao_peg = None
    cor_box = None
    if peg_ratio is not None:
        if peg_ratio < 0.5:
            avaliacao_peg = "🟢 MUITO BARATA"
            cor_box = "success"
        elif peg_ratio < 1.0:
            avaliacao_peg = "🟢 BARATA"
            cor_box = "success"
        elif peg_ratio < 1.5:
            avaliacao_peg = "🟡 PREÇO JUSTO"
            cor_box = "alert"
        elif peg_ratio < 2.0:
            avaliacao_peg = "🔴 CARA"
            cor_box = "danger"
        else:
            avaliacao_peg = "🔴 MUITO CARA"
            cor_box = "danger"
    
    with col3:
        st.metric('Avaliação (PEG)', avaliacao_peg if avaliacao_peg else 'N/A')
    
    # Caixa de avaliação colorida
    if avaliacao_peg:
        if cor_box == "success":
            st.markdown(f'<div class="success-box"><strong>✅ Oportunidade de Compra</strong><br>PEG Ratio de {peg_ratio:.2f} indica que a ação está em bom preço considerando seu crescimento.</div>', unsafe_allow_html=True)
        elif cor_box == "alert":
            st.markdown(f'<div class="alert-box"><strong>⚠️ Preço Equilibrado</strong><br>PEG Ratio de {peg_ratio:.2f} sugere uma valoração justa. Observe outros indicadores.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="danger-box"><strong>⛔ Ação Cara</strong><br>PEG Ratio de {peg_ratio:.2f} indica supervalorização. Cuidado ao investir.</div>', unsafe_allow_html=True)

    # ============================================
    # SEÇÃO 7: POTENCIAL DE UPSIDE
    # ============================================
    st.markdown('<div class="section-header">🚀 POTENCIAL DE ALTA (UPSIDE)</div>', unsafe_allow_html=True)
    
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
    
    # Função auxiliar para colorir upside
    def colorir_upside(value):
        if value is None:
            return 'N/A'
        color = '🟢' if value > 0 else '🔴'
        return f"{color} {value:.2%}"
    
    with col1:
        st.metric('Upside Barsi 6%', colorir_upside(upside_barsi))
    with col2:
        st.metric('Upside Graham', colorir_upside(upside_graham))
    with col3:
        st.metric('Upside Brasil (Puro)', colorir_upside(upside_brasil))
    with col4:
        # Destaque para o upside mais conservador (Brasil - 20%)
        if upside_brasil_20 is not None:
            color = '🟢' if upside_brasil_20 > 0 else '🔴'
            upside_display = f"{color} {upside_brasil_20:.2%}"
            st.metric('Upside Brasil (- 20%)', upside_display)
        else:
            st.metric('Upside Brasil (- 20%)', 'N/A')
    
    # ============================================
    # SEÇÃO 8: GRÁFICO DE PREÇO
    # ============================================
    st.markdown('<div class="section-header">📈 GRÁFICO HISTÓRICO</div>', unsafe_allow_html=True)
    
    if not df_close.empty:
        chart_df = pd.DataFrame({'Close': df_close})
        chart_df['SMA20'] = chart_df['Close'].rolling(20).mean()
        chart_df['SMA50'] = chart_df['Close'].rolling(50).mean()
        chart_df['SMA200'] = chart_df['Close'].rolling(200).mean()
        st.line_chart(chart_df, use_container_width=True)
    else:
        st.warning('⚠️ Dados históricos insuficientes para construir o gráfico.')

    # ============================================
    # SEÇÃO 9: EXPLICAÇÕES E REFERÊNCIAS
    # ============================================
    st.markdown('<div class="section-header">📚 DOCUMENTAÇÃO</div>', unsafe_allow_html=True)
    
    with st.expander('ℹ️ Como Usar - Guia Rápido'):
        st.markdown("""
        **Passo 1:** Digite o ticker da ação (ex: PETR4.SA)
        
        **Passo 2:** Revise os dados de LPA e VPA (se necessário, ajuste manualmente)
        
        **Passo 3:** Analise os indicadores:
        - **Preços Justos:** Compare com o preço atual
        - **PEG Ratio:** Veja se a ação está barata ou cara
        - **Upside:** Potencial de ganho até o preço justo
        
        **Recomendação:** Compre apenas com margem de segurança (Brasil - 20%)
        """)
    
    with st.expander('🎓 Explicação da Fórmula de Graham (Adaptação Brasil)'):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Fórmula:**
            
            Valor Intrínseco = √(10 × VPA × LPA)
            
            Preço com Margem = Valor × 0,80
            """)
        with col2:
            st.markdown("""
            **Por que adaptado para Brasil?**
            
            - **EUA:** P/L máx 15 × P/VP máx 1,5 = 22,5
            - **Brasil:** P/L máx 8 × P/VP máx 1,25 = 10
            
            Mais conservador — juros altos, inflação, risco maior
            """)
        
        st.info("💡 **Margem de Segurança:** 20% de desconto é recomendado antes de comprar")

    with st.expander('📊 Entendendo o PEG Ratio'):
        st.markdown("""
        **O que é PEG Ratio?**
        
        PEG Ratio = P/L ÷ Taxa de Crescimento Esperado (%)
        
        Relaciona preço ao crescimento futuro. Melhor que P/L simples!
        
        **Interpretação:**
        """)
        
        df_peg = pd.DataFrame({
            'PEG Ratio': ['< 0,5', '0,5 - 1,0', '1,0 - 1,5', '1,5 - 2,0', '> 2,0'],
            'Avaliação': ['🟢 MUITO BARATA', '🟢 BARATA', '🟡 PREÇO JUSTO', '🔴 CARA', '🔴 MUITO CARA'],
            'Significado': [
                'Oportunidade excelente',
                'Bom valor, boa compra',
                'Preço apropriado',
                'Um pouco cara',
                'Muito superavaliada'
            ]
        })
        st.table(df_peg)
        
        st.info("💡 **Melhor para:** Empresas em crescimento. Para empresas maduras, use P/L e Dividend Yield")


if __name__ == "__main__":
    app()
