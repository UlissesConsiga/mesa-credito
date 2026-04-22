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

st.set_page_config(layout="wide")

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

if "tema" not in st.session_state:
    st.session_state.tema = "auto"

st.markdown("""
<style>

/* ============================= */
/* TEMA CLARO AUTOMÁTICO */
/* ============================= */

@media (prefers-color-scheme: light) {

    .stApp {
        background-color: #f4f6f9;
        color: #000000;
    }

    h1, h2, h3 {
        color: #0d3b66;
    }

    label {
        color: #1f2937 !important;
        font-weight: 600;
    }

    .stButton>button {
        background-color: #0d3b66;
        color: white;
        border-radius: 8px;
        padding: 8px 16px;
    }

}


/* ============================= */
/* TEMA ESCURO AUTOMÁTICO */
/* ============================= */

@media (prefers-color-scheme: dark) {

    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }

    h1, h2, h3 {
        color: #79c0ff;
    }

    label {
        color: #f0f6fc !important;
        font-weight: 600;
    }

    input, textarea {
        color: #ffffff !important;
    }

    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea {
        background-color: #161b22 !important;
        color: #ffffff !important;
        border: 1px solid #30363d !important;
    }

    .stSelectbox div[data-baseweb="select"] {
        background-color: #161b22 !important;
        color: #ffffff !important;
    }

    .stSelectbox div {
        color: #ffffff !important;
    }

    .stButton>button {
        background-color: #238636;
        color: white;
        border-radius: 8px;
        padding: 8px 16px;
    }

}

</style>
""", unsafe_allow_html=True)

st.write("SISTEMA DE CONTROLE DE ANÁLISE DE CRÉDITO ECONSIGNADO")

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
                        st.error("⚠️ Erro ao conectar com Google Sheets. Tente novamente em alguns segundos.")
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
    st.error("⚠️ Erro ao carregar credenciais do Google. Verifique a variável GOOGLE_CREDENTIALS.")
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
        st.error("⚠️ Erro ao conectar com Google Sheets. Verifique as credenciais e nome da planilha.")
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
            return "⚠️ Esta CCB já foi finalizada."
        
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
    st.title("🔐 Login - Mesa de Crédito")
    
    user = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        try:
            usuarios = carregar_usuarios()
            
            if user in usuarios and verificar_senha(password, usuarios[user]["senha"]):
                st.session_state["user"] = user
                st.session_state["perfil"] = usuarios[user]["perfil"]
                logger.info(f"Login bem-sucedido: {user}")
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")
                logger.warning(f"Tentativa de login falhou para usuário: {user}")
        except Exception as e:
            st.error("⚠️ Erro ao fazer login. Tente novamente.")
            logger.error(f"Erro no login: {e}")

if "user" not in st.session_state:
    login()
    st.stop()

analista = st.session_state["user"]

# ==============================
# MENU LATERAL
# ==============================

opcoes_menu = ["📋 Operação", "📊 Acompanhamento"]

if st.session_state["perfil"] == "Supervisor":
    opcoes_menu.append("🔐 Administração")

menu = st.sidebar.selectbox("Menu", opcoes_menu)

st.sidebar.markdown("---")
st.sidebar.write(f"👤 Usuário: **{analista}**")
st.sidebar.write(f"🔑 Perfil: **{st.session_state['perfil']}**")

# Botão de atualização manual
if st.sidebar.button("🔄 Atualizar Dados"):
    carregar_base.clear()
    st.rerun()

# BOTÃO DE TROCA DE TEMA
if st.session_state.tema == "claro":
    if st.sidebar.button("🌙 Modo Escuro"):
        st.session_state.tema = "escuro"
        st.rerun()
else:
    if st.sidebar.button("☀️ Modo Claro"):
        st.session_state.tema = "claro"
        st.rerun()

# ==============================
# 📋 OPERAÇÃO
# ==============================

if menu == "📋 Operação":
    
    st.title("📋 Mesa de Análise CCB")
    
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
                f"📌 CCB já existente  \n"
                f"👤 Analista: {info['Analista']}  \n"
                f"📊 Status: {info['Status Analista']}"
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
                st.success("✅ CCB criada e assumida com sucesso!")
                st.rerun()
            elif resposta == "CONTINUAR":
                st.success("✅ Retomando análise desta CCB.")
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
                        st.success("✅ Análise finalizada com sucesso!")
                        del st.session_state["ccb_ativa"]
                        st.rerun()
                    else:
                        st.error(resultado_final)
    
    # ==============================
    # 📊 PAINEL GERAL
    # ==============================
    
    st.divider()
    st.subheader("📊 Painel Geral")
    
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
# 📊 ACOMPANHAMENTO
# ==============================

if menu == "📊 Acompanhamento":
    
    st.title("📊 Acompanhamento")
    
    df = carregar_base().copy()
    
    if not df.empty:
        
        df["Data da Análise"] = pd.to_datetime(df["Data da Análise"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Data da Análise"])
        
        st.divider()
        st.subheader("📈 Resumo do Mês Atual")
        
        mes_atual = datetime.now().strftime("%m/%Y")
        df["MesAno"] = df["Data da Análise"].dt.strftime("%m/%Y")
        df_mes_atual = df[df["MesAno"] == mes_atual]
        
        if not df_mes_atual.empty:
            
            pendentes = df_mes_atual[df_mes_atual["Status Analista"] == "Análise Pendente"].shape[0]
            aprovadas = df_mes_atual[df_mes_atual["Status Analista"] == "Análise Aprovada"].shape[0]
            reprovadas = df_mes_atual[df_mes_atual["Status Analista"] == "Análise Reprovada"].shape[0]
            total = df_mes_atual.shape[0]
            
            # Métricas visuais
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📋 Total", total)
            col2.metric("⏳ Pendentes", pendentes)
            col3.metric("✅ Aprovadas", aprovadas)
            col4.metric("❌ Reprovadas", reprovadas)
            
            # Gráfico
            resumo_mes = pd.DataFrame({
                "Status": [
                    "Propostas Pendentes",
                    "Propostas Aprovadas",
                    "Propostas Reprovadas"
                ],
                "Quantidade": [
                    pendentes,
                    aprovadas,
                    reprovadas
                ]
            })
            
            fig, ax = plt.subplots(figsize=(10, 6))
            barras = ax.bar(resumo_mes["Status"], resumo_mes["Quantidade"], color=['#FFA500', '#28a745', '#dc3545'])
            
            for barra in barras:
                altura = barra.get_height()
                ax.text(
                    barra.get_x() + barra.get_width() / 2,
                    altura,
                    f'{int(altura)}',
                    ha='center',
                    va='bottom',
                    fontsize=12,
                    fontweight='bold'
                )
            
            plt.xticks(rotation=45, ha='right')
            plt.ylabel('Quantidade')
            plt.title(f'Resumo de Propostas - {mes_atual}')
            plt.tight_layout()
            st.pyplot(fig)
            
        else:
            st.info("Nenhuma proposta encontrada no mês atual.")
        
        st.divider()
        st.subheader("👤 Dashboard por Analista")
        
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

# ==============================
# 🔐 ADMINISTRAÇÃO
# ==============================

if menu == "🔐 Administração":
    
    if st.session_state["perfil"] != "Supervisor":
        st.warning("Acesso restrito a Supervisores.")
        st.stop()
    
    st.title("🔐 Administração de Usuários")
    
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
                    st.success("✅ Usuário cadastrado com sucesso!")
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
                    st.success("✅ Usuário excluído com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao excluir usuário.")
