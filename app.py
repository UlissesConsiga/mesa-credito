import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import matplotlib.pyplot as plt
import time
import bcrypt
from functools import wraps
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    layout="wide",
    initial_sidebar_state="auto",
    page_title="Consiga Empréstimos",
    page_icon="💼"
)

# ==============================
# CONFIGURAÇÕES OTIMIZADAS
# ==============================

# Cache mais longo para reduzir requisições
CACHE_TTL_LONGO = 1800  # 30 minutos
CACHE_TTL_MEDIO = 600   # 10 minutos
CACHE_TTL_CURTO = 180   # 3 minutos

# Controle de rate limiting
MAX_REQUESTS_PER_MINUTE = 30
request_times = []

# Tema removido - usando design profissional fixo

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ============================= */
/* VARIÁVEIS GLOBAIS - TEMA CLARO (padrão) */
/* ============================= */
:root {
    --primary-green: #22c55e;
    --primary-green-dark: #16a34a;
    --primary-green-darker: #15803d;
    --accent-orange: #f97316;
    --accent-orange-dark: #ea580c;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --bg-primary: #ffffff;
    --bg-secondary: #f8fafc;
    --border-color: #e2e8f0;
    --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1);
    --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1);
    --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.15);
    --sidebar-bg: #1a1f2e;
    --sidebar-border: rgba(255,255,255,0.08);
}

/* ============================= */
/* VARIÁVEIS - TEMA ESCURO */
/* ============================= */
@media (prefers-color-scheme: dark) {
    :root {
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --bg-primary: #1e293b;
        --bg-secondary: #0f172a;
        --border-color: #334155;
        --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.3);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.4);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.5);
        --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.6);
    }
}

/* ============================= */
/* BASE */
/* ============================= */
* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ============================= */
/* BACKGROUND - TEMA CLARO */
/* ============================= */
@media (prefers-color-scheme: light) {
    .stApp, [data-testid="stAppViewContainer"] {
        background: #f0fdf4 !important;
    }
    h1, h2, h3 { color: var(--primary-green-darker) !important; }
    p, span, div, label { color: var(--text-primary) !important; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background-color: #ffffff !important;
        border: 2px solid var(--border-color) !important;
        color: var(--text-primary) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
        border-color: var(--primary-green) !important;
        box-shadow: 0 0 0 3px rgba(34,197,94,0.12) !important;
    }
    .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important;
        border: 2px solid var(--border-color) !important;
    }
    [data-testid="stDataFrame"] table { background-color: #ffffff !important; }
    [data-testid="stDataFrame"] tbody tr:nth-child(even) { background-color: #f8fafc !important; }
    [data-testid="stDataFrame"] tbody tr:hover { background-color: #dcfce7 !important; }
}

/* ============================= */
/* BACKGROUND - TEMA ESCURO */
/* ============================= */
@media (prefers-color-scheme: dark) {
    .stApp, [data-testid="stAppViewContainer"] {
        background: linear-gradient(160deg, #0f172a 0%, #1e293b 100%) !important;
    }
    h1, h2, h3 { color: var(--primary-green) !important; }
    p, span, div, label { color: var(--text-primary) !important; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background-color: var(--bg-primary) !important;
        border: 2px solid var(--border-color) !important;
        color: var(--text-primary) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
        border-color: var(--primary-green) !important;
        box-shadow: 0 0 0 3px rgba(34,197,94,0.2) !important;
    }
    .stSelectbox div[data-baseweb="select"] {
        background-color: var(--bg-primary) !important;
        border: 2px solid var(--border-color) !important;
    }
    [data-testid="stDataFrame"] table { background-color: var(--bg-primary) !important; }
    [data-testid="stDataFrame"] tbody tr:nth-child(even) { background-color: var(--bg-secondary) !important; }
    [data-testid="stDataFrame"] tbody tr:hover { background-color: #14532d !important; }
}

/* ============================= */
/* TÍTULOS */
/* ============================= */
h1 {
    font-weight: 800 !important;
    font-size: 2.5rem !important;
    margin-bottom: 1.5rem !important;
    letter-spacing: -0.025em !important;
}

h2 {
    font-weight: 700 !important;
    font-size: 1.875rem !important;
    margin-top: 2rem !important;
    margin-bottom: 1rem !important;
    letter-spacing: -0.025em !important;
}

h3 {
    font-weight: 600 !important;
    font-size: 1.5rem !important;
    letter-spacing: -0.025em !important;
}

/* ============================= */
/* LABELS */
/* ============================= */
label {
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 0.5rem !important;
}

/* ============================= */
/* INPUTS */
/* ============================= */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    border-radius: 12px !important;
    padding: 14px 18px !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.stTextInput input::placeholder,
.stNumberInput input::placeholder,
.stTextArea textarea::placeholder {
    color: var(--text-secondary) !important;
    opacity: 0.6 !important;
}

/* ============================= */
/* SELECTBOX */
/* ============================= */
.stSelectbox div[data-baseweb="select"] {
    border-radius: 12px !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.stSelectbox div[data-baseweb="select"]:hover {
    border-color: var(--primary-green) !important;
}

/* ============================= */
/* BOTÕES */
/* ============================= */
.stButton>button {
    background: linear-gradient(135deg, var(--primary-green) 0%, var(--primary-green-dark) 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 28px !important;
    font-size: 0.9375rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.025em !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: var(--shadow-md) !important;
}

.stButton>button:hover {
    background: linear-gradient(135deg, var(--primary-green-dark) 0%, var(--primary-green-darker) 100%) !important;
    box-shadow: var(--shadow-lg) !important;
    transform: translateY(-1px) !important;
}

.stButton>button:active {
    transform: translateY(0) !important;
    box-shadow: var(--shadow-sm) !important;
}

.stButton>button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent-orange) 0%, var(--accent-orange-dark) 100%) !important;
}

.stButton>button[kind="primary"]:hover {
    background: linear-gradient(135deg, var(--accent-orange-dark) 0%, #c2410c 100%) !important;
}

/* ============================= */
/* SIDEBAR - azul-escuro neutro */
/* ============================= */
[data-testid="stSidebar"] {
    background: #1a1f2e !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    box-shadow: 4px 0 24px rgba(0,0,0,0.3) !important;
}

[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

[data-testid="stSidebar"] label {
    color: #94a3b8 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
    background-color: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
}

[data-testid="stSidebar"] .stButton>button {
    background: rgba(34,197,94,0.15) !important;
    border: 1px solid rgba(34,197,94,0.3) !important;
    color: #22c55e !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}

[data-testid="stSidebar"] .stButton>button:hover {
    background: rgba(34,197,94,0.25) !important;
    border-color: rgba(34,197,94,0.5) !important;
}

/* Logo na sidebar */
[data-testid="stSidebar"] img {
    border-radius: 10px !important;
    background: #ffffff !important;
    padding: 6px !important;
    display: block !important;
    margin: 0 auto !important;
}

/* Botão de colapsar/expandir sidebar — SEMPRE visível */
[data-testid="collapsedControl"] {
    display: flex !important;
    background: #1a1f2e !important;
    color: #e2e8f0 !important;
}

[data-testid="collapsedControl"] svg {
    fill: #e2e8f0 !important;
    color: #e2e8f0 !important;
}

/* ============================= */
/* MÉTRICAS */
/* ============================= */
[data-testid="stMetricValue"] {
    color: var(--primary-green) !important;
    font-size: 2.25rem !important;
    font-weight: 800 !important;
}

[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    font-size: 0.75rem !important;
}

/* ============================= */
/* DATAFRAMES */
/* ============================= */
[data-testid="stDataFrame"] {
    border-radius: 16px !important;
    overflow: hidden !important;
    box-shadow: var(--shadow-lg) !important;
}

[data-testid="stDataFrame"] thead tr th {
    background: linear-gradient(135deg, var(--primary-green) 0%, var(--primary-green-dark) 100%) !important;
    color: white !important;
    font-weight: 700 !important;
    padding: 16px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    font-size: 0.75rem !important;
    border: none !important;
}

[data-testid="stDataFrame"] tbody td {
    padding: 14px 16px !important;
    font-weight: 500 !important;
}

/* ============================= */
/* ALERTAS */
/* ============================= */
.stSuccess {
    background-color: #dcfce7 !important;
    border-left: 5px solid #22c55e !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    color: #14532d !important;
    font-weight: 500 !important;
}

.stError {
    background-color: #fee2e2 !important;
    border-left: 5px solid #ef4444 !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    color: #7f1d1d !important;
    font-weight: 500 !important;
}

.stWarning {
    background-color: #fef3c7 !important;
    border-left: 5px solid #f59e0b !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    color: #78350f !important;
    font-weight: 500 !important;
}

.stInfo {
    background-color: #dbeafe !important;
    border-left: 5px solid #3b82f6 !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    color: #1e3a8a !important;
    font-weight: 500 !important;
}

/* ============================= */
/* DIVISORES */
/* ============================= */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, var(--border-color), transparent) !important;
    margin: 2.5rem 0 !important;
}

/* ============================= */
/* RADIO BUTTONS */
/* ============================= */
.stRadio > label {
    font-weight: 600 !important;
}

/* ============================= */
/* SPINNER */
/* ============================= */
.stSpinner > div {
    border-top-color: var(--primary-green) !important;
}

/* ============================= */
/* LOGIN - centralizado, sem elementos flutuantes */
/* ============================= */

/* Esconde header e toolbar do Streamlit em toda a app */
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
#MainMenu { display: none !important; }
footer { display: none !important; }

/* Na tela de login: esconde sidebar E o botão de expandir */
.login-page [data-testid="stSidebar"] { display: none !important; }
.login-page [data-testid="collapsedControl"] { display: none !important; }

/* Card de login */
.login-card {
    width: 100%;
    max-width: 420px;
    margin: 0 auto;
    background: var(--bg-primary);
    border-radius: 20px;
    padding: 2.5rem 2.5rem 2rem;
    box-shadow: 0 25px 50px rgba(0,0,0,0.15);
    border: 1px solid var(--border-color);
}

.login-header {
    text-align: center;
    margin-bottom: 2rem;
}

/* Área da logo — fundo branco para a imagem aparecer */
.login-logo-area {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1.5rem;
}

.login-logo-area img {
    max-width: 200px;
    height: auto;
}

/* Fallback texto quando não há imagem */
.login-logo-text-block {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    background: linear-gradient(135deg, #22c55e, #16a34a);
    border-radius: 14px;
    padding: 1rem 2rem;
    box-shadow: 0 8px 24px rgba(34,197,94,0.3);
}

.login-logo-name {
    font-size: 1.75rem;
    font-weight: 800;
    color: #ffffff !important;
    letter-spacing: 0.06em;
    line-height: 1;
}

.login-logo-sub {
    font-size: 0.75rem;
    font-weight: 600;
    color: #fbbf24 !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 4px;
}

.login-title {
    font-size: 1.375rem;
    font-weight: 700;
    color: var(--text-primary) !important;
    margin: 0 0 4px;
}

.login-subtitle {
    font-size: 0.875rem;
    color: var(--text-secondary) !important;
    font-weight: 400;
    margin: 0;
}

</style>
""", unsafe_allow_html=True)

# Header removido - design profissional aplicado

# ==============================
# FUNÇÕES DE UTILIDADE
# ==============================

def rate_limit_check():
    """Controla o rate limiting de requisições"""
    global request_times
    now = time.time()
    # Remove requisições antigas (mais de 1 minuto)
    request_times = [t for t in request_times if now - t < 60]
    
    if len(request_times) >= MAX_REQUESTS_PER_MINUTE:
        wait_time = 60 - (now - request_times[0])
        if wait_time > 0:
            logger.warning(f"Rate limit atingido. Aguardando {wait_time:.1f}s")
            time.sleep(wait_time)
            request_times = []
    
    request_times.append(now)

def retry_on_failure(max_retries=3, delay=2):
    """Decorator para retry automático em caso de falha"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    rate_limit_check()
                    return func(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    logger.error(f"Erro API Google Sheets (tentativa {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))  # Backoff exponencial
                    else:
                        st.error("⚠ Erro ao conectar com Google Sheets. Tente novamente em alguns segundos.")
                        raise
                except Exception as e:
                    logger.error(f"Erro inesperado: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        raise
            return None
        return wrapper
    return decorator

def hash_senha(senha):
    """Criptografa senha usando bcrypt"""
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha, hash_armazenado):
    """Verifica se a senha corresponde ao hash"""
    try:
        return bcrypt.checkpw(senha.encode('utf-8'), hash_armazenado.encode('utf-8'))
    except:
        # Fallback para senhas antigas em texto plano
        return senha == hash_armazenado

# ==============================
# CONEXÃO COM GOOGLE SHEETS
# ==============================

SHEET_NAME = os.environ.get("SHEET_NAME", "")
google_creds_str = os.environ.get("GOOGLE_CREDENTIALS", "{}")

try:
    google_creds = json.loads(google_creds_str)
except json.JSONDecodeError:
    st.error("⚠ Erro ao carregar credenciais do Google. Verifique a variável GOOGLE_CREDENTIALS.")
    st.stop()

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource(ttl=3600)  # Cache de 1 hora para conexão
def conectar_google():
    """Conecta ao Google Sheets com tratamento de erros"""
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
        client = gspread.authorize(creds)
        planilha = client.open(SHEET_NAME)
        sheet = planilha.worksheet("BASE_CONTROLE")
        sheet_usuarios = planilha.worksheet("USUARIOS")
        logger.info("Conexão com Google Sheets estabelecida com sucesso")
        return sheet, sheet_usuarios
    except Exception as e:
        logger.error(f"Erro ao conectar com Google Sheets: {e}")
        st.error("⚠ Erro ao conectar com Google Sheets. Verifique as credenciais e nome da planilha.")
        st.stop()

sheet, sheet_usuarios = conectar_google()

# ==============================
# FUNÇÕES DE DADOS OTIMIZADAS
# ==============================

@st.cache_data(ttl=CACHE_TTL_LONGO)
@retry_on_failure(max_retries=3)
def carregar_usuarios():
    """Carrega usuários com cache longo (raramente mudam)"""
    logger.info("Carregando usuários do Google Sheets")
    dados = sheet_usuarios.get_all_values()
    
    usuarios_dict = {}
    if len(dados) > 1:
        for linha in dados[1:]:
            if len(linha) >= 3:
                usuarios_dict[linha[0]] = {
                    "senha": linha[1],
                    "perfil": linha[2]
                }
    
    return usuarios_dict

@st.cache_data(ttl=CACHE_TTL_CURTO)
@retry_on_failure(max_retries=3)
def carregar_base():
    """Carrega base de dados com cache otimizado"""
    logger.info("Carregando base de dados do Google Sheets")
    dados = sheet.get_all_values()
    
    # Se não tem dados ou só tem cabeçalho, retorna DataFrame vazio com colunas corretas
    if len(dados) == 0:
        return pd.DataFrame(columns=["CCB", "Valor", "Parceiro", "Data da Análise", "Status Bankerize", "Status Analista", "Analista", "Anotações"])
    
    if len(dados) == 1:
        # Só tem cabeçalho, retorna DataFrame vazio mas com as colunas do cabeçalho
        return pd.DataFrame(columns=dados[0])
    
    header = dados[0]
    registros = dados[1:]
    df = pd.DataFrame(registros, columns=header)
    
    return df

def buscar_ccb_local(ccb, df=None):
    """Busca CCB no DataFrame local (sem acessar Google Sheets)"""
    if df is None:
        df = carregar_base()
    
    if df.empty:
        return None
    
    resultado = df[df["CCB"] == str(ccb)]
    
    if resultado.empty:
        return None
    
    return resultado.iloc[0]

@retry_on_failure(max_retries=3)
def assumir_ccb(ccb, valor, parceiro, analista, status_bankerize):
    """Assume CCB com validações e tratamento de erros"""
    if not ccb:
        return "Informe a CCB."
    
    # Busca no cache primeiro
    df = carregar_base()
    registro = df[df["CCB"] == str(ccb)]
    
    if not registro.empty:
        status = registro.iloc[0]["Status Analista"]
        
        if status in ["Análise Aprovada", "Análise Reprovada"]:
            return "⚠ Esta CCB já foi finalizada."
        
        if status in ["Em Análise", "Análise Pendente"]:
            st.session_state["ccb_ativa"] = ccb
            return "CONTINUAR"
    
    # Adiciona nova linha
    nova_linha = [
        ccb,
        valor,
        parceiro,
        datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S"),
        status_bankerize,
        "Em Análise",
        analista,
        ""
    ]
    
    try:
        sheet.append_row(nova_linha)
        # Limpa apenas o cache da base, não todos os caches
        carregar_base.clear()
        st.session_state["ccb_ativa"] = ccb
        logger.info(f"CCB {ccb} assumida por {analista}")
        return "OK"
    except Exception as e:
        logger.error(f"Erro ao assumir CCB: {e}")
        return f"Erro ao salvar: {str(e)}"

@retry_on_failure(max_retries=3)
def finalizar_ccb(ccb, resultado, anotacoes, status_bankerize):
    """Finaliza CCB usando batch update para melhor performance"""
    df = carregar_base()
    
    for idx, linha in df.iterrows():
        if str(linha["CCB"]) == str(ccb):
            linha_real = idx + 2
            
            try:
                # Usa batch update para reduzir requisições
                updates = [
                    {
                        'range': f'E{linha_real}',
                        'values': [[status_bankerize]]
                    },
                    {
                        'range': f'F{linha_real}',
                        'values': [[resultado]]
                    },
                    {
                        'range': f'H{linha_real}',
                        'values': [[anotacoes]]
                    }
                ]
                
                sheet.batch_update(updates)
                carregar_base.clear()
                logger.info(f"CCB {ccb} finalizada com status {resultado}")
                return "Finalizado"
            except Exception as e:
                logger.error(f"Erro ao finalizar CCB: {e}")
                return f"Erro ao finalizar: {str(e)}"
    
    return "CCB não encontrada."

@retry_on_failure(max_retries=3)
def adicionar_usuario(usuario, senha, perfil):
    """Adiciona usuário com senha criptografada"""
    try:
        senha_hash = hash_senha(senha)
        sheet_usuarios.append_row([usuario, senha_hash, perfil])
        carregar_usuarios.clear()
        logger.info(f"Usuário {usuario} adicionado com perfil {perfil}")
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar usuário: {e}")
        return False

@retry_on_failure(max_retries=3)
def excluir_usuario(usuario):
    """Exclui usuário da planilha"""
    try:
        dados = sheet_usuarios.get_all_values()
        
        for idx, linha in enumerate(dados[1:], start=2):
            if linha[0] == usuario:
                sheet_usuarios.delete_rows(idx)
                carregar_usuarios.clear()
                logger.info(f"Usuário {usuario} excluído")
                return True
        return False
    except Exception as e:
        logger.error(f"Erro ao excluir usuário: {e}")
        return False

# ==============================
# LOGIN
# ==============================

def login():
    st.markdown("""
    <style>
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"] { display: none !important; }
    .main .block-container {
        max-width: 460px !important;
        padding: 10vh 1rem 4rem !important;
        margin: 0 auto !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Logo: usa base64 para funcionar no Render sem depender de path relativo
    import base64
    logo_html = ""
    try:
        with open("Logo Principal.png", "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="max-width:200px;height:auto;border-radius:10px;margin:0 auto 1.25rem;display:block;" />'
    except Exception:
        logo_html = """
        <div style="display:inline-flex;flex-direction:column;align-items:center;
            background:linear-gradient(135deg,#22c55e,#16a34a);border-radius:14px;
            padding:1rem 2rem;margin:0 auto 1.25rem;width:fit-content;
            box-shadow:0 8px 24px rgba(34,197,94,0.3);">
            <span style="font-size:1.75rem;font-weight:800;color:#fff;letter-spacing:0.06em;line-height:1;">CONSIGA</span>
            <span style="font-size:0.75rem;font-weight:600;color:#fbbf24;letter-spacing:0.12em;text-transform:uppercase;margin-top:4px;">Empréstimos</span>
        </div>"""

    st.markdown(f"""
    <div style="background:var(--bg-primary);border-radius:20px;padding:2.5rem 2.5rem 2rem;
        box-shadow:0 25px 50px rgba(0,0,0,0.18);border:1px solid var(--border-color);text-align:center;margin-bottom:1.5rem;">
        {logo_html}
        <p style="font-size:1.375rem;font-weight:700;margin:0 0 4px;">Bem-vindo</p>
        <p style="font-size:0.875rem;font-weight:400;margin:0;opacity:0.7;">Sistema de Controle de Análise de Crédito</p>
    </div>
    """, unsafe_allow_html=True)

    user     = st.text_input("Usuário", placeholder="Digite seu usuário",  key="login_user")
    password = st.text_input("Senha",   placeholder="Digite sua senha",    key="login_pass", type="password")

    if st.button("Entrar", use_container_width=True, key="login_btn"):
        try:
            usuarios = carregar_usuarios()
            if user in usuarios and verificar_senha(password, usuarios[user]["senha"]):
                st.session_state["user"]   = user
                st.session_state["perfil"] = usuarios[user]["perfil"]
                logger.info(f"Login bem-sucedido: {user}")
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")
                logger.warning(f"Tentativa de login falhou: {user}")
        except Exception as e:
            st.error("Erro ao fazer login. Tente novamente.")
            logger.error(f"Erro no login: {e}")


if "user" not in st.session_state:
    login()
    st.stop()

# Após login: restaura layout normal e garante sidebar visível
st.markdown("""
<style>
[data-testid="stSidebar"],
[data-testid="collapsedControl"] { display: flex !important; }

.main .block-container {
    max-width: 100% !important;
    padding: 2rem 2rem 4rem !important;
}
</style>
""", unsafe_allow_html=True)

analista = st.session_state["user"]

# ==============================
# MENU LATERAL
# ==============================

opcoes_menu = ["Operação", "Acompanhamento"]

if st.session_state["perfil"] == "Supervisor":
    opcoes_menu.append("Administração")

# Logo na sidebar com base64 (funciona no Render)
import base64 as _b64
try:
    with open("Logo Principal.png", "rb") as _f:
        _logo_b64 = _b64.b64encode(_f.read()).decode()
    st.sidebar.markdown(f"""
    <div style="padding:1.25rem 0.5rem 0.5rem;text-align:center;">
        <img src="data:image/png;base64,{_logo_b64}"
             style="max-width:160px;width:100%;height:auto;border-radius:10px;background:#fff;padding:6px;display:block;margin:0 auto;" />
    </div>
    """, unsafe_allow_html=True)
except Exception:
    st.sidebar.markdown("""
    <div style="padding:1.25rem 0.5rem 0.5rem;text-align:center;">
        <div style="display:inline-flex;flex-direction:column;align-items:center;
            background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.3);
            border-radius:12px;padding:0.75rem 1.25rem;">
            <span style="font-size:1.2rem;font-weight:800;color:#fff;letter-spacing:0.06em;">CONSIGA</span>
            <span style="font-size:0.65rem;font-weight:600;color:#fb923c;letter-spacing:0.1em;text-transform:uppercase;margin-top:2px;">Empréstimos</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")
menu = st.sidebar.selectbox("Navegação", opcoes_menu, label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Usuário:** {analista}")
st.sidebar.markdown(f"**Perfil:** {st.session_state['perfil']}")
st.sidebar.markdown("")

# Botão de atualização manual
if st.sidebar.button("Atualizar Dados", use_container_width=True):
    carregar_base.clear()
    st.rerun()

# ==============================
# OPERAÇÃO
# ==============================

if menu == "Operação":
    
    st.title("Mesa de Análise CCB")
    
    ccb_input = st.text_input("Número da CCB")
    valor = st.text_input("Valor Líquido")
    parceiro = st.text_input("Parceiro")
    
    status_bankerize = st.selectbox(
        "Status Bankerize",
        [
            "Aguardando Análise da Assinatura",
            "Aguardando Análise de Risco",
            "Aguardando Análise Manual da Assinatura",
            "Assinatura Reprovada",
            "Pendente"
        ],
        key="status_bankerize_select"
    )
    
    # Busca local (sem acessar Google Sheets novamente)
    if ccb_input:
        df_cache = carregar_base()
        info = buscar_ccb_local(ccb_input, df_cache)
        
        if info is not None:
            st.info(
                f"CCB já existente  \n"
                f"Analista: {info['Analista']}  \n"
                f"Status: {info['Status Analista']}"
            )
    
    if st.button("Assumir Análise"):
        with st.spinner("Processando..."):
            resposta = assumir_ccb(
                ccb_input,
                valor,
                parceiro,
                analista,
                status_bankerize
            )
            
            if resposta == "OK":
                st.success("CCB criada e assumida com sucesso")
                st.rerun()
            elif resposta == "CONTINUAR":
                st.success("Retomando análise desta CCB")
            else:
                st.error(resposta)
    
    if "ccb_ativa" in st.session_state:
        st.divider()
        st.subheader(f"Finalizando CCB {st.session_state['ccb_ativa']}")
        
        resultado = st.radio(
            "Resultado",
            ["Análise Pendente", "Análise Aprovada", "Análise Reprovada"]
        )
        anotacoes = st.text_area("Anotações")
        
        if st.button("Finalizar Análise"):
            if resultado == "Análise Pendente" and not anotacoes:
                st.error("Para Análise Pendente é obrigatório preencher Anotações.")
            else:
                with st.spinner("Finalizando..."):
                    resultado_final = finalizar_ccb(
                        st.session_state["ccb_ativa"],
                        resultado,
                        anotacoes,
                        status_bankerize
                    )
                    
                    if resultado_final == "Finalizado":
                        st.success("Análise finalizada com sucesso")
                        del st.session_state["ccb_ativa"]
                        st.rerun()
                    else:
                        st.error(resultado_final)
    
    # ==============================
    # PAINEL GERAL
    # ==============================
    
    st.divider()
    st.subheader("Painel Geral")
    
    df = carregar_base().copy()
    
    if not df.empty:
        df["Data da Análise"] = pd.to_datetime(
            df["Data da Análise"],
            dayfirst=True,
            errors="coerce"
        )
        
        df = df.dropna(subset=["Data da Análise"])
        df = df.sort_values(by="Data da Análise", ascending=False)
        
        # FORMATO BRASILEIRO
        df["Data da Análise"] = df["Data da Análise"].dt.strftime("%d/%m/%Y %H:%M:%S")
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum registro encontrado.")

# ==============================
# ACOMPANHAMENTO
# ==============================

if menu == "Acompanhamento":
    
    st.title("Acompanhamento")
    
    df = carregar_base().copy()
    
    if not df.empty:
        
        df["Data da Análise"] = pd.to_datetime(df["Data da Análise"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Data da Análise"])
        
        # ==============================
        # RESUMO DO MÊS ATUAL
        # ==============================
        st.subheader("Resumo do Mês Atual")
        
        mes_atual = datetime.now().strftime("%m/%Y")
        df["MesAno"] = df["Data da Análise"].dt.strftime("%m/%Y")
        df_mes_atual = df[df["MesAno"] == mes_atual]
        
        if not df_mes_atual.empty:
            
            pendentes  = df_mes_atual[df_mes_atual["Status Analista"] == "Análise Pendente"].shape[0]
            aprovadas  = df_mes_atual[df_mes_atual["Status Analista"] == "Análise Aprovada"].shape[0]
            reprovadas = df_mes_atual[df_mes_atual["Status Analista"] == "Análise Reprovada"].shape[0]
            total      = df_mes_atual.shape[0]
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total", total)
            col2.metric("Pendentes", pendentes)
            col3.metric("Aprovadas", aprovadas)
            col4.metric("Reprovadas", reprovadas)
            
            fig, ax = plt.subplots(figsize=(10, 5))
            barras = ax.bar(
                ["Pendentes", "Aprovadas", "Reprovadas"],
                [pendentes, aprovadas, reprovadas],
                color=["#f97316", "#22c55e", "#ef4444"],
                width=0.5,
                edgecolor="none"
            )
            for barra in barras:
                h = barra.get_height()
                ax.text(barra.get_x() + barra.get_width()/2, h + 0.1,
                        f'{int(h)}', ha='center', va='bottom', fontsize=13, fontweight='bold')
            ax.set_ylabel("Quantidade", fontsize=11)
            ax.set_title(f"Propostas — {mes_atual}", fontsize=13, fontweight='bold', pad=15)
            ax.spines[['top','right']].set_visible(False)
            ax.set_axisbelow(True)
            ax.yaxis.grid(True, linestyle='--', alpha=0.5)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)
            
        else:
            st.info("Nenhuma proposta encontrada no mês atual.")

        st.divider()

        # ==============================
        # RESUMO DA SEMANA ATUAL
        # ==============================
        st.subheader("Resumo da Semana Atual")

        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        # Segunda-feira da semana atual
        inicio_semana = hoje - pd.Timedelta(days=hoje.weekday())
        # Domingo da semana atual
        fim_semana    = inicio_semana + pd.Timedelta(days=6)

        df["Data_date"] = df["Data da Análise"].dt.date
        df_semana = df[(df["Data_date"] >= inicio_semana) & (df["Data_date"] <= fim_semana)]

        st.caption(f"Período: {inicio_semana.strftime('%d/%m/%Y')} (Seg) até {fim_semana.strftime('%d/%m/%Y')} (Dom)")

        if not df_semana.empty:
            pend_s  = df_semana[df_semana["Status Analista"] == "Análise Pendente"].shape[0]
            aprov_s = df_semana[df_semana["Status Analista"] == "Análise Aprovada"].shape[0]
            reprov_s= df_semana[df_semana["Status Analista"] == "Análise Reprovada"].shape[0]
            total_s = df_semana.shape[0]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total", total_s)
            col2.metric("Pendentes", pend_s)
            col3.metric("Aprovadas", aprov_s)
            col4.metric("Reprovadas", reprov_s)

            # Gráfico por dia da semana
            dias_pt = {0:"Seg", 1:"Ter", 2:"Qua", 3:"Qui", 4:"Sex", 5:"Sáb", 6:"Dom"}
            df_semana = df_semana.copy()
            df_semana["DiaSemana"] = df_semana["Data da Análise"].dt.weekday
            df_semana["DiaLabel"]  = df_semana["DiaSemana"].map(dias_pt)

            por_dia = df_semana.groupby(["DiaSemana","DiaLabel","Status Analista"]).size().reset_index(name="Qtd")

            # Pivot para gráfico empilhado
            pivot = por_dia.pivot_table(index=["DiaSemana","DiaLabel"], columns="Status Analista", values="Qtd", fill_value=0).reset_index()
            pivot = pivot.sort_values("DiaSemana")

            dias_labels = pivot["DiaLabel"].tolist()
            x = range(len(dias_labels))
            cores_status = {
                "Análise Aprovada":  "#22c55e",
                "Análise Reprovada": "#ef4444",
                "Análise Pendente":  "#f97316",
                "Em Análise":        "#3b82f6"
            }

            fig2, ax2 = plt.subplots(figsize=(10, 5))
            bottom = [0] * len(dias_labels)
            for status, cor in cores_status.items():
                if status in pivot.columns:
                    vals = pivot[status].tolist()
                    bars = ax2.bar(x, vals, bottom=bottom, label=status, color=cor, width=0.5, edgecolor="none")
                    bottom = [b + v for b, v in zip(bottom, vals)]

            ax2.set_xticks(list(x))
            ax2.set_xticklabels(dias_labels, fontsize=11)
            ax2.set_ylabel("Quantidade", fontsize=11)
            ax2.set_title(f"Propostas por Dia — Semana {inicio_semana.strftime('%d/%m')} a {fim_semana.strftime('%d/%m')}", fontsize=13, fontweight='bold', pad=15)
            ax2.spines[['top','right']].set_visible(False)
            ax2.set_axisbelow(True)
            ax2.yaxis.grid(True, linestyle='--', alpha=0.5)
            ax2.legend(loc='upper right', fontsize=9, framealpha=0.7)
            plt.tight_layout()
            st.pyplot(fig2)
            plt.close(fig2)

            # Tabela por analista na semana
            st.markdown("**Por Analista — Semana Atual**")
            resumo_sem = df_semana.groupby("Analista").agg(
                Total=("Status Analista", "count"),
                Em_Analise=("Status Analista", lambda x: (x == "Em Análise").sum()),
                Pendentes=("Status Analista", lambda x: (x == "Análise Pendente").sum()),
                Aprovadas=("Status Analista", lambda x: (x == "Análise Aprovada").sum()),
                Reprovadas=("Status Analista", lambda x: (x == "Análise Reprovada").sum())
            ).reset_index().sort_values("Total", ascending=False)
            st.dataframe(resumo_sem, use_container_width=True, hide_index=True)

        else:
            st.info("Nenhuma proposta encontrada nesta semana.")

        st.divider()

        # ==============================
        # DASHBOARD POR ANALISTA
        # ==============================
        st.subheader("Dashboard por Analista")
        
        meses = sorted(df["MesAno"].dropna().unique(), reverse=True)
        
        if len(meses) > 0:
            mes_sel = st.selectbox("Selecionar Mês/Ano", meses)
            df_mes = df[df["MesAno"] == mes_sel]
            
            resumo = df_mes.groupby("Analista").agg(
                Total=("Status Analista", "count"),
                Em_Analise=("Status Analista", lambda x: (x == "Em Análise").sum()),
                Pendentes=("Status Analista", lambda x: (x == "Análise Pendente").sum()),
                Aprovadas=("Status Analista", lambda x: (x == "Análise Aprovada").sum()),
                Reprovadas=("Status Analista", lambda x: (x == "Análise Reprovada").sum())
            ).reset_index()
            
            resumo = resumo.sort_values(by="Total", ascending=False)
            st.dataframe(resumo, use_container_width=True, hide_index=True)

    else:
        st.info("Nenhum registro encontrado.")

# ==============================
# ADMINISTRAÇÃO
# ==============================

if menu == "Administração":
    
    if st.session_state["perfil"] != "Supervisor":
        st.warning("Acesso restrito a Supervisores.")
        st.stop()
    
    st.title("Administração de Usuários")
    
    usuarios = carregar_usuarios()
    
    # LISTAR USUÁRIOS
    lista = []
    for nome, dados in usuarios.items():
        lista.append({
            "Usuário": nome,
            "Perfil": dados["perfil"]
        })
    
    df_users = pd.DataFrame(lista)
    st.dataframe(df_users, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # ADICIONAR USUÁRIO
    st.subheader("Adicionar Novo Usuário")
    
    novo_usuario = st.text_input("Nome do Usuário")
    nova_senha = st.text_input("Senha", type="password")
    nova_senha_confirm = st.text_input("Confirmar Senha", type="password")
    novo_perfil = st.selectbox("Perfil", ["Operador", "Supervisor"])
    
    if st.button("Cadastrar Usuário"):
        
        if not novo_usuario or not nova_senha:
            st.error("Preencha todos os campos.")
        elif nova_senha != nova_senha_confirm:
            st.error("As senhas não coincidem.")
        elif novo_usuario in usuarios:
            st.error("Usuário já existe.")
        else:
            with st.spinner("Cadastrando usuário..."):
                if adicionar_usuario(novo_usuario, nova_senha, novo_perfil):
                    st.success("Usuário cadastrado com sucesso")
                    st.rerun()
                else:
                    st.error("Erro ao cadastrar usuário.")
    
    st.divider()
    
    # EXCLUIR USUÁRIO
    st.subheader("Excluir Usuário")
    
    usuario_excluir = st.selectbox(
        "Selecionar Usuário para Excluir",
        list(usuarios.keys())
    )
    
    if st.button("Excluir Usuário", type="primary"):
        if usuario_excluir == analista:
            st.error("Você não pode excluir seu próprio usuário.")
        else:
            with st.spinner("Excluindo usuário..."):
                if excluir_usuario(usuario_excluir):
                    st.success("Usuário excluído com sucesso")
                    st.rerun()
                else:
                    st.error("Erro ao excluir usuário.")
