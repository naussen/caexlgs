import os
import sys

_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import streamlit as st
import streamlit.components.v1 as components
import urllib.parse
import api_client
import bigquery_client
import graph_builder
import risk_analyzer
import case_manager
import report_generator
import pandas as pd
import time

import judicial
from judicial import (
    JudicialSearchService,
    converter_processos_para_elementos_grafo,
    validar_cpf,
    validar_cnpj,
    formatar_cpf,
    formatar_cnpj,
    limpar_digitos,
    formatar_numero_processo_cnj,
    PoloProcessual,
)

st.set_page_config(page_title="POMELO — Inteligência Societária & Processual", page_icon="🍊", layout="wide")

# Detecta ?cnpj=... ou ?socio=... na URL para abertura direta (útil para links em nova aba)
query_cnpj = st.query_params.get("cnpj")
if query_cnpj and query_cnpj != st.session_state.get('last_loaded_cnpj_query'):
    st.session_state.last_loaded_cnpj_query = query_cnpj
    st.session_state.view = 'DETAILS'
    st.session_state.selected_cnpj = query_cnpj

query_socio = st.query_params.get("socio")
if query_socio and query_socio != st.session_state.get('last_loaded_socio_query'):
    st.session_state.last_loaded_socio_query = query_socio
    st.session_state.view = 'RESULTS'
    st.session_state.search_title = f"Empresas do Sócio: {query_socio}"
    with st.spinner(f"Buscando empresas de {query_socio}..."):
        st.session_state.search_results = api_client.buscar_empresas_do_socio(query_socio)


# Inicializando o state para navegação, histórico e configurações
if 'view' not in st.session_state:
    st.session_state.view = 'HOME'
if 'selected_cnpj' not in st.session_state:
    st.session_state.selected_cnpj = None
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'search_title' not in st.session_state:
    st.session_state.search_title = ""
if 'api_target' not in st.session_state:
    st.session_state.api_target = "Google BigQuery (Sigilo Total & Privado)"
if 'use_bigquery_for_contacts' not in st.session_state:
    st.session_state.use_bigquery_for_contacts = True
if 'bq_project_id' not in st.session_state or not st.session_state.bq_project_id:
    st.session_state.bq_project_id = bigquery_client.get_project_id() or "consulta-cnpj-123456"
if 'bq_credentials_path' not in st.session_state or not st.session_state.bq_credentials_path:
    st.session_state.bq_credentials_path = bigquery_client.get_credentials_path() or "c:/Users/7401/Documents/CNPJ/gcp-key.json"
if 'bq_test_status' not in st.session_state:
    st.session_state.bq_test_status = None
if 'bq_months' not in st.session_state:
    st.session_state.bq_months = 3
if 'history' not in st.session_state:
    st.session_state.history = []

# Estados para o Grafo Interativo de Relacionamento
if 'graph_excluded_nodes' not in st.session_state:
    st.session_state.graph_excluded_nodes = set()
if 'graph_manual_nodes' not in st.session_state:
    st.session_state.graph_manual_nodes = []
if 'graph_manual_edges' not in st.session_state:
    st.session_state.graph_manual_edges = []
if 'graph_auto_filter_accountants' not in st.session_state:
    st.session_state.graph_auto_filter_accountants = False
if 'graph_expand_socios' not in st.session_state:
    st.session_state.graph_expand_socios = False
if 'graph_expand_contacts' not in st.session_state:
    st.session_state.graph_expand_contacts = False
if 'graph_cache_socios_empresas' not in st.session_state:
    st.session_state.graph_cache_socios_empresas = {}
if 'graph_cache_contatos_empresas' not in st.session_state:
    st.session_state.graph_cache_contatos_empresas = {}
if 'multi_expanded_companies' not in st.session_state:
    st.session_state.multi_expanded_companies = {}
if 'multi_expanded_socios' not in st.session_state:
    st.session_state.multi_expanded_socios = {}
if 'multi_expanded_phones' not in st.session_state:
    st.session_state.multi_expanded_phones = {}
if 'multi_expanded_emails' not in st.session_state:
    st.session_state.multi_expanded_emails = {}
if 'investigation_notes' not in st.session_state:
    st.session_state.investigation_notes = ""
if 'enable_risk_highlight' not in st.session_state:
    st.session_state.enable_risk_highlight = True
if 'enable_shared_addresses' not in st.session_state:
    st.session_state.enable_shared_addresses = True
if 'enable_family_detection' not in st.session_state:
    st.session_state.enable_family_detection = True
if 'enable_ubo_detection' not in st.session_state:
    st.session_state.enable_ubo_detection = True
if 'judicial_service' not in st.session_state:
    st.session_state.judicial_service = JudicialSearchService()
if 'judicial_processes' not in st.session_state:
    st.session_state.judicial_processes = {}
if 'judicial_graph_nodes' not in st.session_state:
    st.session_state.judicial_graph_nodes = []
if 'judicial_graph_edges' not in st.session_state:
    st.session_state.judicial_graph_edges = []

def navigate_to(view_name, cnpj=None, title="", results=None):
    """Navega para uma tela guardando o estado anterior no histórico para o botão Voltar."""
    st.session_state.history.append({
        'view': st.session_state.view,
        'selected_cnpj': st.session_state.selected_cnpj,
        'search_title': st.session_state.search_title,
        'search_results': st.session_state.search_results,
        'last_search_error': st.session_state.get('last_search_error')
    })
    st.session_state.view = view_name
    if cnpj is not None:
        st.session_state.selected_cnpj = cnpj
    if title:
        st.session_state.search_title = title
    if results is not None:
        st.session_state.search_results = results
    st.session_state.last_search_error = None

def go_back():
    """Restaura o estado anterior do histórico."""
    if st.session_state.history:
        prev = st.session_state.history.pop()
        st.session_state.view = prev['view']
        st.session_state.selected_cnpj = prev['selected_cnpj']
        st.session_state.search_title = prev['search_title']
        st.session_state.search_results = prev['search_results']
        st.session_state.last_search_error = prev.get('last_search_error')

def render_back_button():
    """Renderiza o botão Voltar se houver histórico disponível."""
    if st.session_state.history:
        col_back, _ = st.columns([1, 5])
        with col_back:
            if st.button("⬅️ Voltar", key=f"btn_back_{st.session_state.view}_{len(st.session_state.history)}"):
                go_back()
                st.rerun()

def executar_busca_telefone(ddd: str, tel: str):
    if st.session_state.use_bigquery_for_contacts:
        months = st.session_state.get('bq_months', 3)
        resultados = bigquery_client.buscar_telefone(ddd, tel, months=months)
        erro = bigquery_client.get_last_error()
        origem = "Google BigQuery (Nuvem)"
    else:
        resultados = api_client.buscar_telefone(ddd, tel)
        erro = api_client.get_last_error()
        origem = "API Local/Pública"
    return resultados, erro, origem

def executar_busca_email(email: str):
    if st.session_state.use_bigquery_for_contacts:
        months = st.session_state.get('bq_months', 3)
        resultados = bigquery_client.buscar_email(email, months=months)
        erro = bigquery_client.get_last_error()
        origem = "Google BigQuery (Nuvem)"
    else:
        resultados = api_client.buscar_email(email)
        erro = api_client.get_last_error()
        origem = "API Local/Pública"
    return resultados, erro, origem


# ---- SIDEBAR ----
logo_path = os.path.join(os.path.dirname(__file__), "assets", "pomelo_logo.png")
if os.path.exists(logo_path):
    col_logo, col_txt = st.sidebar.columns([1, 2])
    with col_logo:
        st.image(logo_path, width=75)
    with col_txt:
        st.markdown("<h3 style='margin-bottom:0;'>POMELO</h3><span style='font-size:11px; color:#666;'>Inteligência Societária & Judicial</span>", unsafe_allow_html=True)
else:
    st.sidebar.title("🍊 POMELO")

st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navegação:",
    ["Busca Simples", "Busca Avançada", "⚖️ Processos Judiciais", "Resultados", "Detalhes CNPJ"],
    index=["HOME", "ADVANCED", "JUDICIAL", "RESULTS", "DETAILS"].index(st.session_state.view) if st.session_state.view in ["HOME", "ADVANCED", "JUDICIAL", "RESULTS", "DETAILS"] else 0
)

if menu == "Busca Simples" and st.session_state.view != 'HOME':
    st.session_state.view = 'HOME'
elif menu == "Busca Avançada" and st.session_state.view != 'ADVANCED':
    st.session_state.view = 'ADVANCED'
elif menu == "⚖️ Processos Judiciais" and st.session_state.view != 'JUDICIAL':
    st.session_state.view = 'JUDICIAL'
elif menu == "Resultados" and st.session_state.view != 'RESULTS':
    st.session_state.view = 'RESULTS'
elif menu == "Detalhes CNPJ" and st.session_state.view != 'DETAILS':
    st.session_state.view = 'DETAILS'

st.sidebar.divider()
st.sidebar.subheader("⚙️ Conexões & Dados")

# Seletor de Motor de Dados (Privacidade & Origem)
target_options = [
    "Google BigQuery (Sigilo Total & Privado)",
    "API Pública (api.cnpj.pw - Terceiros)",
    "API Local (localhost:8000 - PostgreSQL)",
    "Personalizada"
]
current_target_index = target_options.index(st.session_state.api_target) if st.session_state.api_target in target_options else 0

selected_target = st.sidebar.selectbox("Motor de Dados & Privacidade:", target_options, index=current_target_index)
st.session_state.api_target = selected_target

if selected_target == "Google BigQuery (Sigilo Total & Privado)":
    api_client.set_engine_mode("BIGQUERY")
    st.sidebar.success("🔒 **Sigilo Total:** Consultas 100% privadas no seu Google Cloud. Zero requisições enviadas a terceiros.")
elif selected_target == "API Pública (api.cnpj.pw - Terceiros)":
    api_client.set_engine_mode("API")
    api_client.set_base_url("https://api.cnpj.pw")
    st.sidebar.warning("⚠️ **Modo Terceiros:** As consultas são enviadas para o servidor externo api.cnpj.pw.")
elif selected_target == "API Local (localhost:8000 - PostgreSQL)":
    api_client.set_engine_mode("API")
    api_client.set_base_url("http://localhost:8000")
else:
    api_client.set_engine_mode("API")
    custom_url = st.sidebar.text_input("URL da API:", value=api_client.get_base_url())
    if custom_url:
        api_client.set_base_url(custom_url)

# Configuração BigQuery (Integrada e Segura)
st.sidebar.divider()
st.sidebar.subheader("☁️ Google BigQuery")
st.session_state.use_bigquery_for_contacts = st.sidebar.checkbox(
    "Usar BigQuery para busca por e-mail e telefone",
    value=st.session_state.use_bigquery_for_contacts,
    help="Permite buscar empresas por contato diretamente na nuvem do Google sem precisar de banco de dados local."
)

is_bq_active = st.session_state.use_bigquery_for_contacts or api_client.is_bigquery_mode()

if is_bq_active:
    # Garante inicialização das credenciais em segundo plano (integradas com sigilo)
    bigquery_client.set_project_id(st.session_state.bq_project_id)
    bigquery_client.set_credentials_path(st.session_state.bq_credentials_path)
    st.sidebar.caption("🔒 **Credenciais Integradas (Sigilo Total)**")

    bq_months = st.sidebar.select_slider(
        "Janela de busca (meses recentes):",
        options=[1, 3, 6, 12],
        value=st.session_state.get('bq_months', 3),
        help="Define quantos snapshots mensais da base serão consultados. Menor = mais rápido e econômico."
    )
    st.session_state.bq_months = bq_months

    if st.sidebar.button("🔌 Testar Conexão BigQuery"):
        bigquery_client.set_project_id(st.session_state.bq_project_id)
        bigquery_client.set_credentials_path(st.session_state.bq_credentials_path)
        sucesso, msg = bigquery_client.test_connection()
        st.session_state.bq_test_status = (sucesso, msg)

    if st.session_state.bq_test_status:
        sucesso, msg = st.session_state.bq_test_status
        if sucesso:
            st.sidebar.success(f"✅ {msg}")
        else:
            st.sidebar.error(f"❌ {msg}")
else:
    st.sidebar.caption("Buscas de telefone e e-mail serão direcionadas à API HTTP configurada acima.")


# ---- VIEWS ----

if st.session_state.view == 'HOME':
    st.title("Busca Simples")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Por CNPJ")
        cnpj_input = st.text_input("Digite o CNPJ (somente números):")
        if st.button("Buscar CNPJ", key="btn_busca_cnpj"):
            if cnpj_input:
                navigate_to('DETAILS', cnpj=cnpj_input.strip())
                st.rerun()

    with col2:
        st.subheader("Por Razão Social")
        razao_input = st.text_input("Digite a Razão Social:")
        if st.button("Buscar Razão Social", key="btn_busca_razao"):
            if razao_input:
                api_client.clear_last_error()
                with st.spinner("Consultando Razão Social..."):
                    resultados = api_client.buscar_razao_social(razao_input)
                navigate_to('RESULTS', title=f"Resultados para Razão Social: {razao_input}", results=resultados)
                st.rerun()

    st.divider()
    
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Por Sócio")
        socio_doc = st.text_input("Documento (CPF/CNPJ):")
        socio_nome = st.text_input("Nome do Sócio (opcional):")
        if st.button("Buscar Sócio", key="btn_busca_socio"):
            api_client.clear_last_error()
            with st.spinner("Consultando empresas do sócio..."):
                if socio_doc and not socio_nome:
                    resultados = api_client.buscar_socio(socio_doc)
                    titulo = f"Resultados para Sócio Doc: {socio_doc}"
                elif socio_nome:
                    params = {'socio_nome': socio_nome}
                    if socio_doc:
                        params['socio_doc'] = socio_doc
                    resultados = api_client.busca_difusa(params)
                    titulo = f"Empresas do Sócio Nome: {socio_nome}"
                else:
                    resultados = []
                    titulo = "Busca de Sócios"
            navigate_to('RESULTS', title=titulo, results=resultados)
            st.rerun()
                
    with col4:
        st.subheader("Por Telefone / E-mail")
        if st.session_state.use_bigquery_for_contacts:
            st.caption("☁️ *Motor ativo: Google BigQuery (busca na nuvem)*")
        elif api_client.is_public_api():
            st.warning("⚠️ *A API pública (api.cnpj.pw) não suporta busca reversa por contato. Ative o BigQuery na barra lateral ou use a API Local.*")
            
        tipo_contato = st.selectbox("Buscar por", ["Telefone", "Email"])
        if tipo_contato == "Telefone":
            telefone_input = st.text_input("Digite o DDD + Telefone (ex: 11999999999)")
            if st.button("Buscar Telefone", key="btn_busca_tel"):
                if len(telefone_input) >= 10:
                    ddd = telefone_input[:2]
                    tel = telefone_input[2:]
                    with st.spinner("Buscando empresas por telefone..."):
                        resultados, erro, origem = executar_busca_telefone(ddd, tel)
                    navigate_to('RESULTS', title=f"Resultados para Telefone: ({ddd}) {tel}", results=resultados)
                    if erro:
                        st.session_state.last_search_error = erro
                    st.rerun()
                else:
                    st.error("Informe pelo menos 10 dígitos (DDD + Telefone).")
        else:
            email_input = st.text_input("Digite o Email")
            if st.button("Buscar Email", key="btn_busca_email"):
                if email_input:
                    with st.spinner("Buscando empresas por e-mail..."):
                        resultados, erro, origem = executar_busca_email(email_input)
                    navigate_to('RESULTS', title=f"Resultados para E-mail: {email_input}", results=resultados)
                    if erro:
                        st.session_state.last_search_error = erro
                    st.rerun()

elif st.session_state.view == 'ADVANCED':
    st.title("Busca Avançada (Filtros)")
    
    with st.form("busca_avancada"):
        col1, col2, col3 = st.columns(3)
        with col1:
            razao = st.text_input("Razão Social")
            fantasia = st.text_input("Nome Fantasia")
            cnae = st.text_input("CNAE Fiscal Principal")
            natureza = st.text_input("Natureza Jurídica (Cód)")
        with col2:
            uf = st.text_input("UF")
            municipio = st.text_input("Município (Cód)")
            bairro = st.text_input("Bairro")
            cep = st.text_input("CEP")
        with col3:
            situacao = st.text_input("Situação Cadastral (Cód)")
            opcao_simples = st.selectbox("Opção Simples", ["", "Sim", "Não"])
            opcao_mei = st.selectbox("Opção MEI", ["", "Sim", "Não"])
            cap_min = st.number_input("Capital Social Mín.", min_value=0.0, step=1000.0)
            
        submitted = st.form_submit_button("Pesquisar")
        if submitted:
            api_client.clear_last_error()
            params = {}
            if razao: params['razao_social'] = razao
            if fantasia: params['nome_fantasia'] = fantasia
            if cnae: params['cnae'] = cnae
            if natureza: params['natureza_juridica'] = natureza
            if uf: params['uf'] = uf
            if municipio: params['municipio'] = municipio
            if bairro: params['bairro'] = bairro
            if cep: params['cep'] = cep
            if situacao: params['situacao_cadastral'] = situacao
            if opcao_simples == "Sim": params['opcao_simples'] = 1
            elif opcao_simples == "Não": params['opcao_simples'] = 0
            if opcao_mei == "Sim": params['opcao_mei'] = 1
            elif opcao_mei == "Não": params['opcao_mei'] = 0
            if cap_min > 0: params['capital_social_min'] = cap_min
            
            with st.spinner("Executando busca avançada..."):
                resultados = api_client.busca_difusa(params)
            navigate_to('RESULTS', title="Resultados da Busca Avançada", results=resultados)
            st.session_state.last_search_error = api_client.get_last_error()
            st.rerun()

elif st.session_state.view == 'RESULTS':
    render_back_button()
    st.title(st.session_state.search_title or "Resultados da Busca")
    
    # Exibe erro detalhado se houver
    erro = st.session_state.get('last_search_error') or api_client.get_last_error() or bigquery_client.get_last_error()
    if erro:
        st.error(erro)
    
    resultados = st.session_state.search_results
    if not resultados:
        if not erro:
            st.warning("Nenhum resultado encontrado.")
    else:
        st.success(f"{len(resultados)} resultado(s) encontrado(s) (limitado à página atual).")
        for i, res in enumerate(resultados):
            cnpj_str = res.get('cnpj') or (str(res.get('cnpj_base', '')) + str(res.get('cnpj_ordem', '')) + str(res.get('cnpj_dv', '')))
            nome = res.get('nome_empresarial') or res.get('nome') or 'Desconhecido'
            
            col1, col2, col3 = st.columns([4, 1.2, 1])
            with col1:
                st.markdown(f"**{nome}**")
                info_pills = [f"CNPJ: `{cnpj_str}`"]
                if res.get('sigla_uf'):
                    info_pills.append(f"UF: {res.get('sigla_uf')}")
                st.write(" • ".join(info_pills))
                if res.get('correio_eletronico') or res.get('email'):
                    st.caption(f"✉️ {res.get('correio_eletronico') or res.get('email')}")
                if res.get('telefone'):
                    st.caption(f"📞 {res.get('telefone')}")
            with col2:
                if st.button("Ver Detalhes", key=f"det_{cnpj_str}_{i}"):
                    navigate_to('DETAILS', cnpj=cnpj_str)
                    st.rerun()
            with col3:
                st.link_button("↗️ Nova Aba", f"?cnpj={cnpj_str}", help="Abre este CNPJ em uma nova aba do navegador")
            st.divider()

elif st.session_state.view == 'DETAILS':
    render_back_button()
    st.title("Detalhes do CNPJ")
    cnpj = st.session_state.selected_cnpj
    
    if not cnpj:
        st.warning("Nenhum CNPJ selecionado.")
    else:
        api_client.clear_last_error()
        with st.spinner(f"Carregando dados do CNPJ {cnpj}..."):
            dados = api_client.get_cnpj(cnpj)
            
        if not dados:
            erro = api_client.get_last_error()
            st.error(erro or f"CNPJ {cnpj} não encontrado ou erro na API.")
        else:
            col_title, col_newtab = st.columns([5, 1])
            with col_title:
                st.header(dados.get('nome_empresarial', ''))
                st.subheader(f"CNPJ: {cnpj}")
            with col_newtab:
                st.link_button("↗️ Abrir em Nova Aba", f"?cnpj={cnpj}", help="Abre esta empresa em uma nova aba independente do navegador")
            
            tab_ficha, tab_grafo, tab_judicial = st.tabs(["📄 Ficha Cadastral", "🕸️ Grafo de Relacionamentos", "⚖️ Processos Judiciais (DataJud & DJEN)"])

            with tab_ficha:
                # Contatos com botões de busca vinculada
                st.write("### 📞 Contatos & Busca Vinculada")
                if st.session_state.use_bigquery_for_contacts:
                    st.caption("☁️ *Clique em um telefone ou e-mail para localizar outras empresas vinculadas (via Google BigQuery).*")
                elif api_client.is_public_api():
                    st.info(
                        "ℹ️ **Modo API Pública:** A busca reversa de outras empresas por e-mail ou telefone requer o **Google BigQuery** "
                        "(ative na barra lateral) ou a **API Local** com banco de dados próprio."
                    )
                else:
                    st.caption("Clique em um telefone ou e-mail para localizar outras empresas vinculadas a este contato.")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Telefones:**")
                    tel1 = f"{dados.get('ddd1', '') or ''}{dados.get('telefone_1', '') or ''}".strip()
                    tel2 = f"{dados.get('ddd2', '') or ''}{dados.get('telefone_2', '') or ''}".strip()
                    
                    if len(tel1) > 2:
                        if st.button(f"📞 {tel1}", key="btn_tel1"):
                            with st.spinner(f"Buscando empresas com telefone {tel1}..."):
                                resultados, erro, origem = executar_busca_telefone(tel1[:2], tel1[2:])
                            navigate_to('RESULTS', title=f"Empresas com o Telefone {tel1}", results=resultados)
                            st.session_state.last_search_error = erro
                            st.rerun()
                    else:
                        st.write("*Telefone 1 não informado*")

                    if len(tel2) > 2:
                        if st.button(f"📞 {tel2}", key="btn_tel2"):
                            with st.spinner(f"Buscando empresas com telefone {tel2}..."):
                                resultados, erro, origem = executar_busca_telefone(tel2[:2], tel2[2:])
                            navigate_to('RESULTS', title=f"Empresas com o Telefone {tel2}", results=resultados)
                            st.session_state.last_search_error = erro
                            st.rerun()
                
                with col2:
                    st.write("**E-mail:**")
                    email = dados.get('correio_eletronico')
                    if email:
                        if st.button(f"✉️ {email}", key="btn_email"):
                            with st.spinner(f"Buscando empresas com e-mail {email}..."):
                                resultados, erro, origem = executar_busca_email(email)
                            navigate_to('RESULTS', title=f"Empresas com o E-mail {email}", results=resultados)
                            st.session_state.last_search_error = erro
                            st.rerun()
                    else:
                        st.write("*E-mail não informado*")
                
                # Quadro Societário com busca vinculada por sócio
                socios = dados.get('socios')
                if socios:
                    st.divider()
                    st.write("### 👥 Quadro Societário & Busca Vinculada por Sócio")
                    st.caption("Clique em **🏢 Ver empresas** para listar todas as empresas em que o sócio possui participação societária.")
                    
                    for i, s in enumerate(socios):
                        nome_socio = s.get('nome') or 'Sem nome'
                        qualificacao = s.get('qualificacao_descricao') or 'Qualificação não informada'
                        doc_socio = s.get('cnpj_cpf') or ''
                        tipo_entidade = s.get('identificador_entidade_descricao') or ''
                        
                        with st.container():
                            col_socio_info, col_socio_btn = st.columns([3, 1.8])
                            with col_socio_info:
                                st.markdown(f"**{nome_socio}** ({qualificacao})")
                                sub_info = []
                                if doc_socio:
                                    sub_info.append(f"Doc: `{doc_socio}`")
                                if tipo_entidade:
                                    sub_info.append(f"Tipo: {tipo_entidade}")
                                if sub_info:
                                    st.caption(" • ".join(sub_info))
                            with col_socio_btn:
                                c_btn1, c_btn2 = st.columns([1.2, 1])
                                with c_btn1:
                                    if st.button("🏢 Empresas", key=f"btn_soc_{i}_{nome_socio[:15]}", help="Ver empresas nesta mesma tela"):
                                        with st.spinner(f"Buscando empresas de {nome_socio}..."):
                                            resultados = api_client.buscar_empresas_do_socio(nome_socio, doc_socio)
                                            erro = api_client.get_last_error()
                                        navigate_to(
                                            'RESULTS',
                                            title=f"Empresas do Sócio: {nome_socio}",
                                            results=resultados
                                        )
                                        if erro:
                                            st.session_state.last_search_error = erro
                                        st.rerun()
                                with c_btn2:
                                    enc_socio = urllib.parse.quote_plus(nome_socio)
                                    st.link_button("↗️ Nova Aba", f"?socio={enc_socio}", help="Abrir lista de empresas em uma nova aba")
                            st.divider()

                # Endereço
                st.divider()
                st.write("### 📍 Endereço")
                tipo_log = dados.get('tipo_logradouro') or ''
                logradouro = dados.get('logradouro') or ''
                numero = dados.get('numero') or 'S/N'
                st.write(f"{tipo_log} {logradouro}, {numero}")
                st.write(f"Bairro: {dados.get('bairro', '') or '-'} - CEP: {dados.get('cep', '') or '-'}")
                st.write(f"{dados.get('municipio_desc', '') or '-'} - {dados.get('uf', '') or '-'}")
                
                # Atividade
                st.divider()
                st.write("### 💼 Atividade Principal")
                st.write(dados.get('cnae_fiscal_principal_descricao', 'Não informada'))

            with tab_grafo:
                # Função para executar expansão de qualquer entidade (Pessoa Física, Jurídica, Telefone, E-mail)
                def executar_expansao_entidade(ent_type: str, ent_val: str, ent_label: str = ""):
                    if ent_type in ("EMPRESA", "EMPRESA_ROOT"):
                        cnpj_limpo = "".join(filter(str.isdigit, str(ent_val or '')))
                        if cnpj_limpo:
                            if cnpj_limpo not in st.session_state.multi_expanded_companies:
                                with st.spinner(f"Consultando dados e conexões da empresa {ent_label or cnpj_limpo}..."):
                                    emp_dados = api_client.get_cnpj(cnpj_limpo)
                                    if emp_dados and not emp_dados.get('erro'):
                                        st.session_state.multi_expanded_companies[cnpj_limpo] = emp_dados
                                        st.toast(f"✅ Relações de {emp_dados.get('nome_empresarial') or cnpj_limpo} expandidas com sucesso!")
                                    else:
                                        st.warning(f"Não foi possível obter dados para o CNPJ {cnpj_limpo}.")
                            else:
                                st.info("As conexões desta empresa já estão expandidas na rede.")
                    elif ent_type in ("SOCIO", "UBO"):
                        socio_nome = str(ent_val or '').strip()
                        if socio_nome:
                            if socio_nome not in st.session_state.multi_expanded_socios:
                                with st.spinner(f"Buscando empresas vinculadas ao sócio {socio_nome}..."):
                                    res_soc = api_client.buscar_empresas_do_socio(socio_nome)
                                    st.session_state.multi_expanded_socios[socio_nome] = res_soc or []
                                    st.toast(f"✅ {len(res_soc or [])} empresa(s) do sócio {socio_nome} adicionada(s) à rede!")
                            else:
                                st.info("As empresas deste sócio já estão expandidas na rede.")
                    elif ent_type == "TELEFONE":
                        fone_limpo = "".join(filter(str.isdigit, str(ent_val or '')))
                        if len(fone_limpo) >= 8:
                            if fone_limpo not in st.session_state.multi_expanded_phones:
                                if len(fone_limpo) in (10, 11):
                                    ddd = fone_limpo[:2]
                                    num = fone_limpo[2:]
                                else:
                                    ddd = str(dados.get('ddd1') or dados.get('ddd_1') or '11')
                                    num = fone_limpo
                                with st.spinner(f"Buscando empresas com telefone ({ddd}) {num}..."):
                                    res_tel = api_client.buscar_telefone(ddd, num)
                                    st.session_state.multi_expanded_phones[fone_limpo] = res_tel or []
                                    st.toast(f"✅ {len(res_tel or [])} empresa(s) com telefone ({ddd}) {num} adicionada(s)!")
                            else:
                                st.info("As empresas deste telefone já estão expandidas na rede.")
                    elif ent_type == "EMAIL":
                        em_limpo = str(ent_val or '').strip().lower()
                        if em_limpo:
                            if em_limpo not in st.session_state.multi_expanded_emails:
                                with st.spinner(f"Buscando empresas com e-mail {em_limpo}..."):
                                    res_em = api_client.buscar_email(em_limpo)
                                    st.session_state.multi_expanded_emails[em_limpo] = res_em or []
                                    st.toast(f"✅ {len(res_em or [])} empresa(s) com e-mail {em_limpo} adicionada(s)!")
                            else:
                                st.info("As empresas deste e-mail já estão expandidas na rede.")

                # Verifica se veio requisição de expansão pela URL (ao clicar no botão ✚ sobre o nó)
                if "expand_type" in st.query_params and "expand_val" in st.query_params:
                    q_type = st.query_params.get("expand_type")
                    q_val = st.query_params.get("expand_val")
                    q_lbl = st.query_params.get("expand_label", q_val)
                    st.query_params.clear()
                    executar_expansao_entidade(q_type, q_val, q_lbl)
                    st.rerun()

                st.write("### 🕸️ Grafo Interativo de Relacionamentos")
                st.caption(
                    "Todos os controles, expansões e filtros estão integrados diretamente na barra superior da janela do grafo. "
                    "Arraste entidades livremente para organizar (elas ficam onde você soltar sem voltar), passe o mouse para ver ações (botão **✚** para expandir, **✕** para excluir), "
                    "ou dê um duplo-clique no nó."
                )

                # Expansão sob demanda: Sócios (acionada via toolbar do grafo)
                if st.session_state.get('graph_expand_socios', False):
                    socios_list = dados.get('socios', [])
                    for s in socios_list:
                        n_socio = s.get('nome')
                        if n_socio and n_socio not in st.session_state.graph_cache_socios_empresas:
                            with st.spinner(f"Carregando empresas do sócio {n_socio}..."):
                                res_soc = api_client.buscar_empresas_do_socio(n_socio, s.get('cnpj_cpf'))
                                st.session_state.graph_cache_socios_empresas[n_socio] = res_soc or []

                # Expansão sob demanda: Contatos (acionada via toolbar do grafo)
                if st.session_state.get('graph_expand_contacts', False):
                    em = dados.get('correio_eletronico')
                    if em and em not in st.session_state.graph_cache_contatos_empresas:
                        with st.spinner(f"Buscando empresas com e-mail {em}..."):
                            res_em = api_client.buscar_email(em)
                            st.session_state.graph_cache_contatos_empresas[em] = res_em or []
                    
                    t1 = f"{dados.get('ddd1', '') or ''}{dados.get('telefone_1', '') or ''}".strip()
                    if len(t1) > 2 and t1 not in st.session_state.graph_cache_contatos_empresas:
                        with st.spinner(f"Buscando empresas com telefone {t1}..."):
                            res_t1 = api_client.buscar_telefone(t1[:2], t1[2:])
                            st.session_state.graph_cache_contatos_empresas[t1] = res_t1 or []

                # Compilação das Empresas da Rede para Inteligência
                all_cluster_companies = [dados] + list(st.session_state.multi_expanded_companies.values())
                if st.session_state.get('graph_expand_socios'):
                    for comp_list in st.session_state.graph_cache_socios_empresas.values():
                        all_cluster_companies.extend(comp_list)
                for comp_list in st.session_state.multi_expanded_socios.values():
                    all_cluster_companies.extend(comp_list)
                if st.session_state.get('graph_expand_contacts'):
                    for comp_list in st.session_state.graph_cache_contatos_empresas.values():
                        all_cluster_companies.extend(comp_list)
                for comp_list in st.session_state.multi_expanded_phones.values():
                    all_cluster_companies.extend(comp_list)
                for comp_list in st.session_state.multi_expanded_emails.values():
                    all_cluster_companies.extend(comp_list)

                # Execução dos Motores de Inteligência
                risk_info = risk_analyzer.analyze_company_risk(dados)
                shared_addresses = risk_analyzer.detect_shared_addresses(all_cluster_companies)
                family_relationships = risk_analyzer.detect_family_relationships(dados.get('socios', []))
                ubo_result = risk_analyzer.trace_ultimate_beneficial_owners(cnpj, dados, api_client)
                ubos = ubo_result.get('ubos', [])

                # Painel Resumo de Inteligência & Compliance
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Risco do Grupo", risk_info['risk_level'], f"{risk_info['risk_score']} pts")
                with m2:
                    st.metric("Beneficiários Finais (UBO)", len(ubos))
                with m3:
                    st.metric("Endereços Compartilhados", len(shared_addresses))
                with m4:
                    st.metric("Relações de Parentesco", len(family_relationships))

                if risk_info.get('risk_flags'):
                    st.warning("⚠️ **Alertas Detectados:** " + " | ".join(risk_info['risk_flags']))

                # Mescla dicionários de sócios e contatos expandidos
                merged_socios = dict(st.session_state.graph_cache_socios_empresas) if st.session_state.get('graph_expand_socios') else {}
                merged_socios.update(st.session_state.multi_expanded_socios)

                merged_contatos = dict(st.session_state.graph_cache_contatos_empresas) if st.session_state.get('graph_expand_contacts') else {}
                merged_contatos.update(st.session_state.multi_expanded_phones)
                merged_contatos.update(st.session_state.multi_expanded_emails)

                # Renderização do Grafo Interativo com Custom Component (Todos os botões integrados na janela)
                try:
                    graph_event, _ = graph_builder.render_interactive_graph(
                        root_data=dados,
                        socios_empresas=merged_socios,
                        contatos_empresas=merged_contatos,
                        shared_addresses=shared_addresses,
                        family_relationships=family_relationships,
                        ubos=ubos,
                        enable_risk_highlight=True,
                        excluded_nodes=st.session_state.graph_excluded_nodes,
                        auto_filter_accountants=False,
                        manual_nodes=st.session_state.graph_manual_nodes,
                        manual_edges=st.session_state.graph_manual_edges,
                        height=850,
                        extra_companies=st.session_state.multi_expanded_companies,
                        key=f"interactive_net_{cnpj}",
                        judicial_nodes=st.session_state.judicial_graph_nodes,
                        judicial_edges=st.session_state.judicial_graph_edges
                    )
                except Exception as comp_err:
                    # Fallback com HTML padrão caso o componente dê erro
                    html_code, _ = graph_builder.build_graph_html(
                        root_data=dados,
                        socios_empresas=merged_socios,
                        contatos_empresas=merged_contatos,
                        shared_addresses=shared_addresses,
                        family_relationships=family_relationships,
                        ubos=ubos,
                        enable_risk_highlight=True,
                        excluded_nodes=st.session_state.graph_excluded_nodes,
                        auto_filter_accountants=False,
                        manual_nodes=st.session_state.graph_manual_nodes,
                        manual_edges=st.session_state.graph_manual_edges,
                        height="850px",
                        extra_companies=st.session_state.multi_expanded_companies,
                        judicial_nodes=st.session_state.judicial_graph_nodes,
                        judicial_edges=st.session_state.judicial_graph_edges
                    )
                    components.html(html_code, height=870, scrolling=False)
                    graph_event = None

                # Processa eventos originados de ações dentro da janela do grafo
                if graph_event and isinstance(graph_event, dict):
                    nonce = graph_event.get("nonce")
                    if nonce and nonce != st.session_state.get("last_graph_action_nonce"):
                        st.session_state.last_graph_action_nonce = nonce
                        act = graph_event.get("action")
                        if act == "expand":
                            executar_expansao_entidade(
                                graph_event.get("type"),
                                graph_event.get("val"),
                                graph_event.get("label", "")
                            )
                            st.rerun()
                        elif act == "delete":
                            node_id = graph_event.get("id")
                            if node_id:
                                st.session_state.graph_excluded_nodes.add(node_id)
                                st.toast("🗑️ Nó removido do grafo.")
                                st.rerun()
                        elif act == "toggle_feature":
                            feat = graph_event.get("feature")
                            if feat == "expand_socios":
                                st.session_state.graph_expand_socios = not st.session_state.get('graph_expand_socios', False)
                                st.toast("👥 Expansão de Sócios (2º Grau) " + ("ativada!" if st.session_state.graph_expand_socios else "desativada."))
                                st.rerun()
                            elif feat == "expand_contacts":
                                st.session_state.graph_expand_contacts = not st.session_state.get('graph_expand_contacts', False)
                                st.toast("📞 Expansão de Contatos " + ("ativada!" if st.session_state.graph_expand_contacts else "desativada."))
                                st.rerun()
                        elif act == "clear":
                            st.session_state.graph_excluded_nodes = set()
                            st.session_state.graph_manual_nodes = []
                            st.session_state.graph_manual_edges = []
                            st.session_state.graph_cache_socios_empresas = {}
                            st.session_state.graph_cache_contatos_empresas = {}
                            st.session_state.multi_expanded_companies = {}
                            st.session_state.multi_expanded_socios = {}
                            st.session_state.multi_expanded_phones = {}
                            st.session_state.multi_expanded_emails = {}
                            st.session_state.graph_expand_socios = False
                            st.session_state.graph_expand_contacts = False
                            st.toast("🧹 Grafos e conexões limpos.")
                            st.rerun()

                st.divider()

                # Painel de Dossiês, Relatórios e Persistência
                tab_rep, tab_case, tab_timeline, tab_excl, tab_manual = st.tabs([
                    "📑 Dossiê & Relatórios",
                    "💾 Salvar/Carregar Projeto",
                    "⏱️ Linha do Tempo Societária",
                    "🚫 Gerenciar Exclusões",
                    "➕ Inserção Manual"
                ])

                with tab_rep:
                    st.write("#### 📑 Emissão de Relatório e Dossiê Consolidado")
                    st.caption("Exporte todos os vínculos, indicadores de risco, quadro societário e anotações em formato profissional.")
                    
                    st.session_state.investigation_notes = st.text_area(
                        "Parecer / Notas da Investigação:",
                        value=st.session_state.investigation_notes,
                        placeholder="Insira aqui as conclusões, observações patrimoniais ou apontamentos do analista que constarão no relatório...",
                        height=100
                    )

                    c_rep1, c_rep2 = st.columns(2)
                    with c_rep1:
                        pdf_data = report_generator.generate_pdf_dossier(
                            root_data=dados,
                            all_companies=all_cluster_companies,
                            socios_list=dados.get('socios', []),
                            risk_info=risk_info,
                            shared_addresses=shared_addresses,
                            ubos=ubos,
                            notes=st.session_state.investigation_notes
                        )
                        st.download_button(
                            "📑 Baixar Dossiê Completo (PDF)",
                            data=pdf_data,
                            file_name=f"dossie_investigativo_{cnpj}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    with c_rep2:
                        excel_data = report_generator.generate_excel_dossier(
                            root_data=dados,
                            all_companies=all_cluster_companies,
                            socios_list=dados.get('socios', []),
                            risk_info=risk_info,
                            shared_addresses=shared_addresses,
                            ubos=ubos,
                            manual_nodes=st.session_state.graph_manual_nodes,
                            manual_edges=st.session_state.graph_manual_edges,
                            notes=st.session_state.investigation_notes
                        )
                        st.download_button(
                            "📊 Baixar Planilha Consolidada (Excel)",
                            data=excel_data,
                            file_name=f"relatorio_societario_{cnpj}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )

                with tab_case:
                    st.write("#### 💾 Salvar e Carregar Projeto de Investigação (.json)")
                    st.caption("Salve todo o estado da análise (nós manuais, contadores excluídos, vínculos e notas) para continuar depois.")
                    
                    col_csave, col_cload = st.columns(2)
                    with col_csave:
                        st.write("**Salvar Caso Atual:**")
                        case_json_content = case_manager.export_case_json(
                            root_cnpj=cnpj,
                            root_name=dados.get('nome_empresarial', ''),
                            manual_nodes=st.session_state.graph_manual_nodes,
                            manual_edges=st.session_state.graph_manual_edges,
                            excluded_nodes=st.session_state.graph_excluded_nodes,
                            investigation_notes=st.session_state.investigation_notes,
                            active_options={
                                "auto_filter_accountants": st.session_state.graph_auto_filter_accountants,
                                "expand_socios": st.session_state.graph_expand_socios,
                                "expand_contacts": st.session_state.graph_expand_contacts
                            }
                        )
                        st.download_button(
                            "📥 Baixar Arquivo do Caso (.json)",
                            data=case_json_content,
                            file_name=f"caso_investigacao_{cnpj}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    with col_cload:
                        st.write("**Carregar Caso Existente:**")
                        up_case = st.file_uploader("Selecione um arquivo .json de caso salvo:", type=["json"], key="up_case_file")
                        if up_case is not None:
                            try:
                                loaded = case_manager.import_case_json(up_case.read().decode('utf-8'))
                                if st.button("🚀 Aplicar Caso ao Grafo", use_container_width=True):
                                    st.session_state.graph_manual_nodes = loaded.get('manual_nodes', [])
                                    st.session_state.graph_manual_edges = loaded.get('manual_edges', [])
                                    st.session_state.graph_excluded_nodes = loaded.get('excluded_nodes', set())
                                    st.session_state.investigation_notes = loaded.get('notes', '')
                                    st.success("Caso carregado com sucesso!")
                                    st.rerun()
                            except Exception as err:
                                st.error(f"Erro ao ler arquivo de caso: {str(err)}")

                with tab_timeline:
                    st.write("#### ⏱️ Linha do Tempo de Entrada de Sócios")
                    st.caption("Histórico cronológico de ingresso de cada administrador ou cotista na empresa.")
                    
                    socios_data = dados.get('socios', [])
                    if socios_data:
                        # Ordena por data de entrada
                        sorted_socios = sorted(
                            socios_data,
                            key=lambda s: s.get('data_entrada_sociedade') or '9999-99-99'
                        )
                        timeline_records = []
                        for s in sorted_socios:
                            dt_in = s.get('data_entrada_sociedade') or 'Data não informada'
                            timeline_records.append({
                                "Data de Ingresso": dt_in,
                                "Nome do Sócio": s.get('nome', ''),
                                "Qualificação": s.get('qualificacao_descricao', ''),
                                "Documento": s.get('cnpj_cpf', '') or '-'
                            })
                        st.dataframe(pd.DataFrame(timeline_records), use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhum sócio registrado nesta empresa.")

                with tab_excl:
                    st.write("#### 🚫 Gerenciar Exclusão de Nós (Contadores e Ruídos)")
                    col_ex1, col_ex2 = st.columns([3, 2])
                    with col_ex1:
                        opcoes_excluir = {
                            f"{n['label']} [{n['type']}]": n['id']
                            for n in nos_atuais
                            if not n['id'].startswith('cnpj_' + str(cnpj))
                        }
                        if opcoes_excluir:
                            selecionados = st.multiselect(
                                "Selecione nó(s) para remover do grafo:",
                                options=list(opcoes_excluir.keys()),
                                key="multi_excluir_nos"
                            )
                            if st.button("❌ Remover Nó(s) Selecionado(s)", disabled=not selecionados):
                                for sel in selecionados:
                                    st.session_state.graph_excluded_nodes.add(opcoes_excluir[sel])
                                st.rerun()
                        else:
                            st.info("Nenhum nó elegível para exclusão no momento.")

                    with col_ex2:
                        st.write("**Nós Atualmente Excluídos:**")
                        if st.session_state.graph_excluded_nodes:
                            for ex_id in list(st.session_state.graph_excluded_nodes):
                                c_lbl, c_btn = st.columns([3, 1])
                                with c_lbl:
                                    st.code(ex_id, language="text")
                                with c_btn:
                                    if st.button("Restaurar", key=f"rst_{ex_id}"):
                                        st.session_state.graph_excluded_nodes.remove(ex_id)
                                        st.rerun()
                            if st.button("Restaurar Todos os Nós", key="rst_all_nodes"):
                                st.session_state.graph_excluded_nodes = set()
                                st.rerun()
                        else:
                            st.caption("Nenhum nó foi excluído manualmente.")

                with tab_manual:
                    st.write("#### ➕ Inserção Manual de Entidade ou Vínculo Gráfico")
                    sub_tm1, sub_tm2 = st.tabs(["👤 Adicionar Pessoa Física / Jurídica", "🔗 Adicionar Vínculo Manual"])

                    with sub_tm1:
                        col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
                        with col_m1:
                            m_nome = st.text_input("Nome da Pessoa / Razão Social:", key="m_nome_input")
                        with col_m2:
                            m_tipo = st.selectbox("Tipo:", ["Pessoa Física (PF)", "Pessoa Jurídica (PJ)"], key="m_tipo_input")
                        with col_m3:
                            m_doc = st.text_input("CPF / CNPJ (Opcional):", key="m_doc_input")
                        
                        m_obs = st.text_input("Observação / Papel:", placeholder="ex: Operador de fato, Familiar, Testa de ferro", key="m_obs_input")
                        if st.button("➕ Inserir Nó Manual no Grafo", disabled=not m_nome.strip()):
                            new_node_id = f"manual_{int(time.time() * 1000)}"
                            tipo_code = 'MANUAL_PF' if 'Física' in m_tipo else 'MANUAL_PJ'
                            st.session_state.graph_manual_nodes.append({
                                'id': new_node_id,
                                'label': m_nome.strip(),
                                'type': tipo_code,
                                'doc': m_doc.strip(),
                                'obs': m_obs.strip()
                            })
                            st.success(f"Nó '{m_nome.strip()}' adicionado ao grafo!")
                            st.rerun()

                    with sub_tm2:
                        st.caption("Conecte dois nós do grafo com uma aresta destacada (vermelho neon / tracejada).")
                        todos_nos_map = {f"{n['label']} [{n['type']}]": n['id'] for n in nos_atuais}
                        if len(todos_nos_map) >= 2:
                            col_e1, col_e2, col_e3 = st.columns([2, 2, 2])
                            with col_e1:
                                src_key = st.selectbox("Nó de Origem:", options=list(todos_nos_map.keys()), key="edge_src_box")
                            with col_e2:
                                dst_key = st.selectbox("Nó de Destino:", options=list(todos_nos_map.keys()), index=1, key="edge_dst_box")
                            with col_e3:
                                edge_label = st.text_input("Rótulo do Vínculo:", value="Vínculo Manual", key="edge_label_input")

                            if st.button("🔗 Criar Vínculo Gráfico"):
                                src_id = todos_nos_map[src_key]
                                dst_id = todos_nos_map[dst_key]
                                if src_id == dst_id:
                                    st.warning("Origem e destino devem ser nós diferentes.")
                                else:
                                    st.session_state.graph_manual_edges.append({
                                        'from': src_id,
                                        'to': dst_id,
                                        'label': edge_label.strip()
                                    })
                                    st.success(f"Vínculo '{edge_label}' adicionado com sucesso!")
                                    st.rerun()
                        else:
                            st.info("É necessário pelo menos 2 nós disponíveis para conectar.")

            with tab_judicial:
                st.subheader("⚖️ Inteligência Forense: Ações e Processos Judiciais")
                st.caption(
                    "Consulta automatizada em tempo real integrando a API Pública do DataJud (CNJ) "
                    "e o Diário de Justiça Eletrônico Nacional (DJEN / ComunicaAPI)."
                )

                razao_empresa = dados.get('nome_empresarial', '') or dados.get('razao_social', '')
                cnpj_clean = limpar_digitos(cnpj)

                col_j1, col_j2 = st.columns([3, 1])
                with col_j1:
                    st.write(f"**Empresa Alvo:** {razao_empresa} (`{formatar_cnpj(cnpj_clean)}`)")
                with col_j2:
                    btn_buscar_judicial = st.button("🔍 Rastrear Processos", key=f"btn_search_jud_{cnpj_clean}", use_container_width=True)

                # Busca automática ou por botão
                if btn_buscar_judicial or (cnpj_clean in st.session_state.judicial_processes):
                    if btn_buscar_judicial or cnpj_clean not in st.session_state.judicial_processes:
                        with st.spinner(f"Consultando bases públicas do Poder Judiciário para o CNPJ {formatar_cnpj(cnpj_clean)}..."):
                            procs_cnpj = st.session_state.judicial_service.consultar_por_cnpj(
                                cnpj=cnpj_clean,
                                razao_social=razao_empresa,
                                max_itens=25,
                                enriquecer_datajud=True,
                            )
                            st.session_state.judicial_processes[cnpj_clean] = procs_cnpj

                    procs_empresa = st.session_state.judicial_processes.get(cnpj_clean, [])
                    vinculos_empresa = st.session_state.judicial_service.obter_vinculos_documento(cnpj_clean)

                    if not procs_empresa:
                        st.info("ℹ️ Nenhuma citação ou processo judicial público localizado para este CNPJ nas bases consultadas.")
                    else:
                        stats = st.session_state.judicial_service.obter_estatisticas_documento(cnpj_clean)
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Total de Ações", stats.get("total_processos", 0))
                        m2.metric("Como Ré / Executada", stats.get("como_reu", 0), help="Polo Passivo (Maior Risco Forense)")
                        m3.metric("Como Autora", stats.get("como_autor", 0), help="Polo Ativo")
                        m4.metric("Tribunais Distintos", len(stats.get("distribuicao_tribunais", {})))

                        col_btn_g, _ = st.columns([2, 3])
                        with col_btn_g:
                            if st.button("🕸️ Conectar Processos ao Grafo Interativo", key=f"btn_add_graph_{cnpj_clean}"):
                                new_nodes, new_edges = converter_processos_para_elementos_grafo(
                                    processos=procs_empresa,
                                    vinculos=vinculos_empresa,
                                    id_no_origem=f"empresa_{cnpj_clean}"
                                )
                                for n in new_nodes:
                                    if not any(x['id'] == n['id'] for x in st.session_state.judicial_graph_nodes):
                                        st.session_state.judicial_graph_nodes.append(n)
                                for e in new_edges:
                                    if not any(x['from'] == e['from'] and x['to'] == e['to'] for x in st.session_state.judicial_graph_edges):
                                        st.session_state.judicial_graph_edges.append(e)
                                st.success(f"{len(new_nodes)} processos vinculados ao Grafo Interativo! Volte na aba 'Grafo de Relacionamentos' para visualizar.")
                                st.rerun()

                        st.markdown("---")
                        st.write("#### 📜 Processos Localizados")

                        for p in procs_empresa:
                            # Identifica o polo da empresa
                            vinc = next((v for v in vinculos_empresa if v.numero_processo == p.numero), None)
                            is_reu = vinc and vinc.polo == PoloProcessual.PASSIVO
                            badge_polo = "🚨 **RÉ / EXECUTADA (POLO PASSIVO)**" if is_reu else "⚖️ **AUTORA (POLO ATIVO)**" if vinc and vinc.polo == PoloProcessual.ATIVO else "📌 **PARTE CADASTRADA**"
                            card_color = "#FFEBEE" if is_reu else "#E8F5E9"

                            with st.expander(f"⚖️ {p.tribunal} | {p.numero_formatado} — {p.classe or 'Processo Judicial'}"):
                                st.markdown(f"**Polo:** {badge_polo}")
                                c_info1, c_info2 = st.columns(2)
                                with c_info1:
                                    st.write(f"**Tribunal:** {p.tribunal} ({p.grau or 'Instância Única'})")
                                    st.write(f"**Órgão Julgador:** {p.orgao_julgador or 'Não informado'}")
                                    st.write(f"**Classe:** {p.classe or 'Não informada'}")
                                with c_info2:
                                    st.write(f"**Data Ajuizamento:** {p.data_ajuizamento or 'N/I'}")
                                    st.write(f"**Última Movimentação / Publicação:** {p.data_ultima_atualizacao or 'N/I'}")
                                    st.write(f"**Origem do Dado:** {', '.join(p.origens)}")

                                if p.assuntos:
                                    st.write(f"**Assuntos:** {', '.join(p.assuntos)}")

                                if p.partes:
                                    st.write("**Partes Envolvidas:**")
                                    for parte in p.partes:
                                        p_icon = "🟢" if parte.polo == PoloProcessual.ATIVO else ("🔴" if parte.polo == PoloProcessual.PASSIVO else "⚪")
                                        advs = f" (Advogados: {', '.join(a.nome for a in parte.advogados)})" if parte.advogados else ""
                                        st.write(f"{p_icon} **{parte.polo.value}:** {parte.nome}{advs}")

                                if p.movimentos:
                                    st.write("**Histórico Recente de Movimentações (DataJud):**")
                                    for mov in p.movimentos[:5]:
                                        st.caption(f"• **{mov.data_hora or ''}** — {mov.nome} {mov.complemento or ''}")

                                if p.link_consulta:
                                    st.link_button("🌐 Acessar Publicação na Íntegra", p.link_consulta)


elif st.session_state.view == 'JUDICIAL':
    render_back_button()
    st.title("⚖️ Centro de Pesquisa Processual & Compliance Judicial")
    st.caption("Investigação e cruzamento de ações judiciais em tempo real via DataJud e DJEN.")

    tab_j_cnpj, tab_j_cpf, tab_j_nome, tab_j_proc, tab_j_repo = st.tabs([
        "🏢 Consulta por CNPJ",
        "👤 Consulta por CPF",
        "🔍 Consulta por Nome / Razão Social",
        "📜 Consulta por Número Único (CNJ)",
        "📊 Vínculos & Dossiê Forense"
    ])

    with tab_j_cnpj:
        st.subheader("Consultar Ações por CNPJ")
        col_c1, col_c2 = st.columns([2, 3])
        with col_c1:
            inp_cnpj = st.text_input("Número do CNPJ:", placeholder="ex: 33.000.167/0001-01", key="search_jud_cnpj_input")
        with col_c2:
            inp_razao = st.text_input("Razão Social (Opcional - refina a busca):", placeholder="ex: PETROLEO BRASILEIRO S A", key="search_jud_razao_input")

        if st.button("🔍 Pesquisar Processos por CNPJ", key="btn_exec_search_jud_cnpj"):
            cnpj_clean = limpar_digitos(inp_cnpj)
            if not validar_cnpj(cnpj_clean):
                st.error("CNPJ inválido. Verifique a digitação dos 14 números.")
            else:
                with st.spinner(f"Consultando processos do CNPJ {formatar_cnpj(cnpj_clean)}..."):
                    procs = st.session_state.judicial_service.consultar_por_cnpj(
                        cnpj=cnpj_clean,
                        razao_social=inp_razao.strip() or None,
                        max_itens=30,
                        enriquecer_datajud=True,
                    )
                    st.session_state.judicial_processes[cnpj_clean] = procs

        if inp_cnpj:
            c_clean = limpar_digitos(inp_cnpj)
            procs = st.session_state.judicial_processes.get(c_clean, [])
            if procs:
                stats = st.session_state.judicial_service.obter_estatisticas_documento(c_clean)
                st.success(f"Encontrados {len(procs)} processos vinculados ao CNPJ {formatar_cnpj(c_clean)}.")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total", stats.get("total_processos", 0))
                m2.metric("Polo Passivo (Ré)", stats.get("como_reu", 0))
                m3.metric("Polo Ativo (Autora)", stats.get("como_autor", 0))
                m4.metric("Tribunais", len(stats.get("distribuicao_tribunais", {})))

                for p in procs:
                    with st.expander(f"⚖️ {p.tribunal} | {p.numero_formatado} — {p.classe or 'Processo Judicial'}"):
                        st.write(f"**Tribunal:** {p.tribunal} | **Órgão Julgador:** {p.orgao_julgador or 'N/I'}")
                        st.write(f"**Data:** {p.data_ultima_atualizacao or p.data_ajuizamento or 'N/I'}")
                        if p.partes:
                            st.write("**Partes:**")
                            for pt in p.partes:
                                st.write(f"• **{pt.polo.value}:** {pt.nome}")
                        if p.link_consulta:
                            st.link_button("🌐 Ver Comunicação Oficial", p.link_consulta)

    with tab_j_cpf:
        st.subheader("Consultar Ações por CPF (Pessoa Física)")
        col_p1, col_p2 = st.columns([2, 3])
        with col_p1:
            inp_cpf = st.text_input("Número do CPF:", placeholder="ex: 111.444.777-35", key="search_jud_cpf_input")
        with col_p2:
            inp_cpf_nome = st.text_input("Nome da Pessoa Física (Opcional):", placeholder="ex: JOAO DA SILVA", key="search_jud_cpf_nome_input")

        if st.button("🔍 Pesquisar Processos por CPF", key="btn_exec_search_jud_cpf"):
            cpf_clean = limpar_digitos(inp_cpf)
            if not validar_cpf(cpf_clean):
                st.error("CPF inválido. Verifique o número digitado.")
            else:
                with st.spinner(f"Consultando processos da Pessoa Física {formatar_cpf(cpf_clean)}..."):
                    procs = st.session_state.judicial_service.consultar_por_cpf(
                        cpf=cpf_clean,
                        nome=inp_cpf_nome.strip() or None,
                        max_itens=30,
                        enriquecer_datajud=True,
                    )
                    st.session_state.judicial_processes[cpf_clean] = procs

        if inp_cpf:
            cpf_clean = limpar_digitos(inp_cpf)
            procs = st.session_state.judicial_processes.get(cpf_clean, [])
            if procs:
                stats = st.session_state.judicial_service.obter_estatisticas_documento(cpf_clean)
                st.success(f"Encontrados {len(procs)} processos vinculados ao CPF {formatar_cpf(cpf_clean)}.")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total", stats.get("total_processos", 0))
                m2.metric("Réu (Polo Passivo)", stats.get("como_reu", 0))
                m3.metric("Autor (Polo Ativo)", stats.get("como_autor", 0))
                m4.metric("Tribunais", len(stats.get("distribuicao_tribunais", {})))

                for p in procs:
                    with st.expander(f"⚖️ {p.tribunal} | {p.numero_formatado} — {p.classe or 'Processo Judicial'}"):
                        st.write(f"**Tribunal:** {p.tribunal} | **Órgão Julgador:** {p.orgao_julgador or 'N/I'}")
                        if p.partes:
                            st.write("**Partes:**")
                            for pt in p.partes:
                                st.write(f"• **{pt.polo.value}:** {pt.nome}")

    with tab_j_nome:
        st.subheader("Consultar por Nome ou Razão Social")
        col_n1, col_n2 = st.columns([3, 1])
        with col_n1:
            inp_nome = st.text_input("Nome da Pessoa ou Empresa:", placeholder="ex: BANCO DO BRASIL SA", key="search_jud_nome_only")
        with col_n2:
            inp_trib = st.text_input("Tribunal (Opcional):", placeholder="ex: TJSP, TRF3, TST", key="search_jud_trib_only")

        if st.button("🔍 Pesquisar por Nome", key="btn_exec_search_jud_nome"):
            if not inp_nome.strip():
                st.warning("Informe um nome para pesquisar.")
            else:
                with st.spinner(f"Consultando processos para '{inp_nome}'..."):
                    procs = st.session_state.judicial_service.consultar_por_nome(
                        nome=inp_nome.strip(),
                        tribunal=inp_trib.strip() or None,
                        max_itens=30,
                        enriquecer_datajud=True,
                    )
                    st.session_state.judicial_processes[inp_nome.strip().upper()] = procs

        nome_key = inp_nome.strip().upper() if inp_nome else None
        if nome_key and nome_key in st.session_state.judicial_processes:
            procs = st.session_state.judicial_processes[nome_key]
            st.success(f"Encontrados {len(procs)} processos para '{nome_key}'.")
            for p in procs:
                with st.expander(f"⚖️ {p.tribunal} | {p.numero_formatado} — {p.classe or 'Processo Judicial'}"):
                    st.write(f"**Tribunal:** {p.tribunal} | **Órgão Julgador:** {p.orgao_julgador or 'N/I'}")
                    if p.partes:
                        st.write("**Partes:**")
                        for pt in p.partes:
                            st.write(f"• **{pt.polo.value}:** {pt.nome}")

    with tab_j_proc:
        st.subheader("Consulta 360º de Processo por Número Único CNJ")
        inp_proc = st.text_input("Número do Processo (20 dígitos com ou sem formatação):", placeholder="ex: 0000290-40.2025.5.08.0018 ou 10334818020238260405", key="search_jud_single_proc")
        if st.button("🔍 Obter Dossiê Completo do Processo", key="btn_exec_search_single_proc"):
            proc_clean = limpar_digitos(inp_proc)
            if not proc_clean:
                st.warning("Informe o número do processo.")
            else:
                with st.spinner(f"Consultando processo {proc_clean} no DataJud e DJEN..."):
                    proc_det = st.session_state.judicial_service.consultar_por_processo(proc_clean)
                    if not proc_det:
                        st.error(f"Processo {proc_clean} não localizado no DataJud ou DJEN.")
                    else:
                        st.success(f"Processo {proc_det.numero_formatado} localizado com sucesso!")
                        c_p1, c_p2 = st.columns(2)
                        with c_p1:
                            st.write(f"**Número Único:** `{proc_det.numero_formatado}`")
                            st.write(f"**Tribunal:** {proc_det.tribunal} ({proc_det.grau or '1º Grau'})")
                            st.write(f"**Órgão Julgador:** {proc_det.orgao_julgador or 'Não informado'}")
                            st.write(f"**Classe TPU:** {proc_det.classe or 'Não informada'}")
                        with c_p2:
                            st.write(f"**Data Ajuizamento:** {proc_det.data_ajuizamento or 'N/I'}")
                            st.write(f"**Última Atualização:** {proc_det.data_ultima_atualizacao or 'N/I'}")
                            st.write(f"**Bases Integradas:** {', '.join(proc_det.origens)}")
                            if proc_det.link_consulta:
                                st.link_button("🌐 Link Oficial de Consulta", proc_det.link_consulta)

                        if proc_det.assuntos:
                            st.write(f"**Assuntos (TPU):** {', '.join(proc_det.assuntos)}")

                        st.markdown("---")
                        st.write("#### 👥 Partes do Processo")
                        if not proc_det.partes:
                            st.caption("Metadados de partes resguardados pelo tribunal de origem.")
                        else:
                            for parte in proc_det.partes:
                                polo_cor = "🟢" if parte.polo == PoloProcessual.ATIVO else ("🔴" if parte.polo == PoloProcessual.PASSIVO else "⚪")
                                st.write(f"{polo_cor} **{parte.polo.value}:** {parte.nome} ({parte.tipo_documento.value})")

                        if proc_det.movimentos:
                            st.markdown("---")
                            st.write(f"#### 📜 Histórico de Movimentações ({len(proc_det.movimentos)} andamentos)")
                            for mov in proc_det.movimentos:
                                st.caption(f"• **{mov.data_hora or ''}** — **{mov.nome}** {f'({mov.complemento})' if mov.complemento else ''}")

    with tab_j_repo:
        st.subheader("📊 Repositório de Vínculos Processuais Registrados")
        vinculos_dict = st.session_state.judicial_service.vinculador.exportar_para_dict()
        if not vinculos_dict:
            st.info("Nenhum vínculo registrado na sessão atual. Execute consultas por CNPJ ou CPF para alimentar a base de inteligência.")
        else:
            total_docs = len(vinculos_dict)
            total_vinc = sum(len(v) for v in vinculos_dict.values())
            st.write(f"**Documentos Investigados:** {total_docs} | **Total de Vínculos Mapeados:** {total_vinc}")

            dados_tabela = []
            for doc, lista in vinculos_dict.items():
                for v in lista:
                    dados_tabela.append({
                        "Documento": v["documento_formatado"],
                        "Nome da Parte": v["nome_parte"],
                        "Processo": v["numero_formatado"],
                        "Tribunal": v["tribunal"],
                        "Polo": v["polo"],
                        "Papel": v["papel"],
                        "Data Vínculo": v.get("data_vinculo"),
                        "Fonte": v.get("fonte"),
                    })

            df_vinculos = pd.DataFrame(dados_tabela)
            st.dataframe(df_vinculos, use_container_width=True)

            # Exportação em JSON
            json_str = df_vinculos.to_json(orient="records", force_ascii=False, indent=2)
            st.download_button(
                "📥 Exportar Dossiê de Vínculos (JSON)",
                data=json_str,
                file_name="pomelo_dossie_vinculos_judiciais.json",
                mime="application/json"
            )


