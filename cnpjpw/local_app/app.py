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
import ai_grounding
import pandas as pd
import time
import auth
import graph_dispatcher
import data_service
import graph_expansions
import sanitizers
import osint

st.set_page_config(page_title="POMELO — Inteligência Societária", page_icon="🍊", layout="wide")

# ==========================================
# BARREIRA DE AUTENTICAÇÃO OBRIGATÓRIA (FASE 1)
# ==========================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    auth.render_login_screen()
    st.stop()

# Detecta ?cnpj=... ou ?socio=... na URL para abertura direta (útil para links em nova aba)
query_cnpj = st.query_params.get("cnpj")
if query_cnpj:
    query_cnpj = sanitizers.adequar_documento(query_cnpj)
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
        resp_qs = data_service.buscar_empresas_do_socio(query_socio)
        st.session_state.search_results = resp_qs.results
        st.session_state.last_search_source = resp_qs.source
        st.session_state.last_search_fallback = resp_qs.fallback_used
        st.session_state.last_search_error = resp_qs.error


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
if 'graph_false_positive_accountants' not in st.session_state:
    st.session_state.graph_false_positive_accountants = set()
if 'graph_manual_accountants' not in st.session_state:
    st.session_state.graph_manual_accountants = set()
if 'graph_expand_socios' not in st.session_state:
    st.session_state.graph_expand_socios = False
if 'graph_expand_contacts' not in st.session_state:
    st.session_state.graph_expand_contacts = False
if 'graph_expand_socios_summary' not in st.session_state:
    st.session_state.graph_expand_socios_summary = None
if 'graph_expand_contacts_summary' not in st.session_state:
    st.session_state.graph_expand_contacts_summary = None
if 'graph_max_companies_limit' not in st.session_state:
    st.session_state.graph_max_companies_limit = 25
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

def executar_expansao_entidade(ent_type: str, ent_val: str, ent_label: str = ""):
    """Executa a expansão pontual de uma entidade específica (Pessoa Física, Jurídica, Telefone, E-mail)."""
    return graph_dispatcher.executar_expansao_entidade(
        ent_type, ent_val, ent_label, root_id=st.session_state.get('selected_cnpj') or st.session_state.get('current_cnpj')
    )

@st.cache_data(ttl=86400, show_spinner=False)
def obter_cnae_completo(cnae_cod: str, cnae_desc: str = ""):
    """
    Retorna (cnae_formatado, cnae_descricao_oficial).
    Formata o código CNAE (ex: 9312-3/00) e enriquece a descrição textual
    consultando a API pública do IBGE se estiver ausente ou puramente numérica.
    """
    import urllib.request
    import json
    import re

    cnae_limpo = re.sub(r'\D', '', str(cnae_cod or ''))
    if len(cnae_limpo) == 7:
        cnae_fmt = f"{cnae_limpo[:4]}-{cnae_limpo[4]}/{cnae_limpo[5:]}"
    else:
        cnae_fmt = str(cnae_cod or '').strip()

    desc_atual = str(cnae_desc or '').strip()
    if desc_atual and not desc_atual.isdigit() and len(desc_atual) > 3 and desc_atual.lower() != 'não informada':
        return cnae_fmt, desc_atual

    if cnae_limpo:
        try:
            url = f"https://servicodados.ibge.gov.br/api/v2/cnae/subclasses/{cnae_limpo}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if isinstance(data, dict) and 'descricao' in data:
                    return cnae_fmt, str(data['descricao']).strip().upper()
        except Exception:
            pass

    return cnae_fmt, desc_atual or "Atividade econômica não informada"

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
    tel_info = sanitizers.adequar_telefone(f"{ddd}{tel}", default_ddd=ddd)
    d = tel_info.get("ddd") or ddd
    n = tel_info.get("numero") or tel
    months = st.session_state.get('bq_months', 3)
    resp = data_service.buscar_telefone(d, n, months=months)
    origem = data_service.get_source_display_name(resp.source, resp.fallback_used)
    return resp.results, resp.error, origem, resp.source, resp.fallback_used

def executar_busca_email(email: str):
    months = st.session_state.get('bq_months', 3)
    resp = data_service.buscar_email(email, months=months)
    origem = data_service.get_source_display_name(resp.source, resp.fallback_used)
    return resp.results, resp.error, origem, resp.source, resp.fallback_used


# ---- SIDEBAR ----
logo_path = os.path.join(os.path.dirname(__file__), "assets", "pomelo_logo.png")
if os.path.exists(logo_path):
    col_logo, col_txt = st.sidebar.columns([1, 2.2])
    with col_logo:
        st.image(logo_path, width=70)
    with col_txt:
        st.markdown("<h3 style='margin-bottom:0; font-weight:800; color:#1a237e;'>POMELO</h3><span style='font-size:11px; color:#546e7a; font-weight:500;'>Inteligência Societária & Grafos</span>", unsafe_allow_html=True)
else:
    st.sidebar.title("🍊 POMELO")

# Selo de Sigilo Conforme Origem dos Dados (Fase 5)
if data_service.is_privacy_active():
    st.sidebar.markdown(
        "<div style='background:#e8f5e9; border:1px solid #c8e6c9; border-radius:6px; padding:4px 8px; margin: 8px 0 12px 0; font-size:11px; color:#2e7d32; font-weight:600; display:flex; align-items:center; gap:6px;'>"
        "<span>🟢</span> Base CNPJ Conectada • Sigilo Ativo"
        "</div>",
        unsafe_allow_html=True
    )
else:
    st.sidebar.markdown(
        "<div style='background:#fff3e0; border:1px solid #ffe0b2; border-radius:6px; padding:4px 8px; margin: 8px 0 12px 0; font-size:11px; color:#e65100; font-weight:600; display:flex; align-items:center; gap:6px;'>"
        "<span>🟠</span> Base CNPJ Conectada • API Pública (Sem Sigilo)"
        "</div>",
        unsafe_allow_html=True
    )

# Navegação Principal
menu_options = ["🔍 Busca Simples", "⚡ Busca Avançada", "📊 Resultados", "🏢 Dossiê / Grafo", "🌐 Fontes Abertas / OSINT"]
view_map = {
    "🔍 Busca Simples": "HOME",
    "⚡ Busca Avançada": "ADVANCED",
    "📊 Resultados": "RESULTS",
    "🏢 Dossiê / Grafo": "DETAILS",
    "🌐 Fontes Abertas / OSINT": "OSINT"
}
reverse_map = {v: k for k, v in view_map.items()}

current_idx = list(view_map.values()).index(st.session_state.view) if st.session_state.view in view_map.values() else 0
menu = st.sidebar.radio("Navegação:", menu_options, index=current_idx)
target_view = view_map.get(menu, 'HOME')
if target_view != st.session_state.view:
    st.session_state.view = target_view
    st.rerun()

# Inicialização transparente do motor de dados em background (Sigilo Total)
if api_client.is_bigquery_mode() or st.session_state.use_bigquery_for_contacts:
    bigquery_client.set_project_id(st.session_state.bq_project_id)
    bigquery_client.set_credentials_path(st.session_state.bq_credentials_path)

# Painel do Caso em Análise (quando houver empresa ativa)
if st.session_state.get('current_cnpj'):
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### 🏢 Caso em Análise")
    dados_c = st.session_state.get('current_company_data') or {}
    razao_c = dados_c.get('nome_empresarial') or dados_c.get('razao_social') or f"CNPJ {st.session_state.current_cnpj}"
    if len(razao_c) > 26:
        razao_c = razao_c[:24] + "..."
    st.sidebar.markdown(f"**{razao_c}**")
    st.sidebar.caption(f"CNPJ: `{st.session_state.current_cnpj}`")
    
    sit_c = (dados_c.get('situacao_cadastral_descricao') or 'ATIVA').upper()
    cor_sit = "🟢" if sit_c == 'ATIVA' else "🔴"
    st.sidebar.markdown(f"Situação: {cor_sit} **{sit_c}**")
    
    col_sb1, col_sb2 = st.sidebar.columns(2)
    with col_sb1:
        if st.sidebar.button("🕸️ Grafo", key="sb_btn_ir_grafo", use_container_width=True):
            navigate_to('DETAILS', cnpj=st.session_state.current_cnpj)
            st.rerun()
    with col_sb2:
        if st.sidebar.button("📑 Dossiê", key="sb_btn_ir_rep", use_container_width=True):
            navigate_to('DETAILS', cnpj=st.session_state.current_cnpj)
            st.rerun()

# Histórico de Consultas Recentes
if st.session_state.get('history'):
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### 🕒 Consultas Recentes")
    for idx_h, hist_item in enumerate(reversed(st.session_state.history[-5:])):
        t_hist = hist_item.get('tipo', 'CNPJ')
        v_hist = hist_item.get('valor', '')
        lbl_btn = f"{t_hist}: {v_hist}"
        if len(lbl_btn) > 24:
            lbl_btn = lbl_btn[:22] + "..."
        if st.sidebar.button(f"🔍 {lbl_btn}", key=f"hist_btn_{idx_h}_{v_hist}", use_container_width=True):
            if t_hist == 'CNPJ':
                navigate_to('DETAILS', cnpj=v_hist)
            else:
                navigate_to('RESULTS', title=f"Histórico: {v_hist}", results=[])
            st.rerun()

    if st.sidebar.button("🧹 Limpar Histórico", key="sb_clear_history", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# Encerramento de Sessão
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sair", key="sb_btn_logout", use_container_width=True):
    st.session_state.authenticated = False
    for k in list(st.session_state.keys()):
        if k.startswith("login_") or k in ("auth_error", "selected_cnpj", "current_cnpj"):
            st.session_state.pop(k, None)
    st.rerun()

# Rodapé Institucional
st.sidebar.markdown("---")
if data_service.is_privacy_active():
    st.sidebar.caption("🔒 **Ambiente Seguro & Sigiloso**")
else:
    st.sidebar.caption("🌐 **Ambiente Conectado à API Pública**")
st.sidebar.caption("POMELO Intelligence • v2.5")


# ---- VIEWS ----

if st.session_state.view == 'HOME':
    st.title("Busca Simples")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Por CNPJ")
        cnpj_input = st.text_input("Digite o CNPJ:", placeholder="Ex: 21.807.980/0001-09 ou 21807980000109")
        if st.button("Buscar CNPJ", key="btn_busca_cnpj"):
            if cnpj_input:
                cnpj_adequado = sanitizers.adequar_documento(cnpj_input)
                navigate_to('DETAILS', cnpj=cnpj_adequado)
                st.rerun()

    with col2:
        st.subheader("Por Razão Social")
        razao_input = st.text_input("Digite a Razão Social:")
        if st.button("Buscar Razão Social", key="btn_busca_razao"):
            if razao_input:
                with st.spinner("Consultando Razão Social..."):
                    resp = data_service.buscar_razao_social(razao_input)
                    resultados = resp.results
                    st.session_state.last_search_source = resp.source
                    st.session_state.last_search_fallback = resp.fallback_used
                    st.session_state.last_search_error = resp.error
                navigate_to('RESULTS', title=f"Resultados para Razão Social: {razao_input}", results=resultados)
                st.rerun()

    st.divider()
    
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Por Sócio")
        socio_doc = st.text_input("Documento (CPF/CNPJ):", placeholder="Ex: 123.456.789-01 ou 21.807.980/0001-09")
        socio_nome = st.text_input("Nome do Sócio (opcional):")
        if st.button("Buscar Sócio", key="btn_busca_socio"):
            doc_adequado = sanitizers.adequar_documento(socio_doc)
            with st.spinner("Consultando empresas do sócio..."):
                if doc_adequado and not socio_nome:
                    resp = data_service.buscar_socio(doc_adequado)
                    titulo = f"Resultados para Sócio Doc: {doc_adequado}"
                elif socio_nome:
                    resp = data_service.buscar_empresas_do_socio(socio_nome, doc_adequado)
                    titulo = f"Empresas do Sócio Nome: {socio_nome}"
                else:
                    resp = data_service.QueryResult(results=[], source=data_service.get_api_source(), error=None)
                    titulo = "Busca de Sócios"
                resultados = resp.results
                st.session_state.last_search_source = resp.source
                st.session_state.last_search_fallback = resp.fallback_used
                st.session_state.last_search_error = resp.error
            navigate_to('RESULTS', title=titulo, results=resultados)
            st.rerun()
                
    with col4:
        st.subheader("Por Telefone / E-mail")
        tipo_contato = st.selectbox("Buscar por", ["Telefone", "Email"])
        if tipo_contato == "Telefone":
            telefone_input = st.text_input("Digite o DDD + Telefone:", placeholder="Ex: (11) 98765-4321 ou (11) 8765-4321")
            if st.button("Buscar Telefone", key="btn_busca_tel"):
                tel_info = sanitizers.adequar_telefone(telefone_input)
                if tel_info["valido"]:
                    ddd = tel_info["ddd"]
                    tel = tel_info["numero"]
                    if tel_info.get("ajuste_realizado"):
                        st.toast(f"ℹ️ {tel_info['ajuste_realizado']}")
                    with st.spinner(f"Buscando empresas por telefone ({ddd}) {tel}..."):
                        resultados, erro, origem, src, fb = executar_busca_telefone(ddd, tel)
                        st.session_state.last_search_source = src
                        st.session_state.last_search_fallback = fb
                        st.session_state.last_search_error = erro
                    navigate_to('RESULTS', title=f"Resultados para Telefone: ({ddd}) {tel}", results=resultados)
                    st.rerun()
                else:
                    st.error(tel_info.get("erro") or "Informe DDD (2 dígitos) e telefone (8 ou 9 dígitos).")
        else:
            email_input = st.text_input("Digite o Email")
            if st.button("Buscar Email", key="btn_busca_email"):
                if email_input:
                    with st.spinner("Buscando empresas por e-mail..."):
                        resultados, erro, origem, src, fb = executar_busca_email(email_input)
                        st.session_state.last_search_source = src
                        st.session_state.last_search_fallback = fb
                        st.session_state.last_search_error = erro
                    navigate_to('RESULTS', title=f"Resultados para E-mail: {email_input}", results=resultados)
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
                resp = data_service.busca_difusa(params)
                resultados = resp.results
                st.session_state.last_search_source = resp.source
                st.session_state.last_search_fallback = resp.fallback_used
                st.session_state.last_search_error = resp.error
            navigate_to('RESULTS', title="Resultados da Busca Avançada", results=resultados)
            st.rerun()

elif st.session_state.view == 'RESULTS':
    render_back_button()
    st.title(st.session_state.search_title or "Resultados da Busca")
    
    # Exibe erro detalhado se houver
    erro = st.session_state.get('last_search_error') or api_client.get_last_error() or bigquery_client.get_last_error()
    if erro:
        st.error(erro)

    # Exibe a origem real da consulta na interface (Regra 6 e 7 da Fase 5)
    src_code = st.session_state.get('last_search_source')
    fallback_used = st.session_state.get('last_search_fallback', False)
    if src_code:
        src_label = data_service.get_source_display_name(src_code, fallback_used)
        st.caption(f"🔍 **Origem dos dados:** {src_label}")
    if fallback_used:
        st.info("ℹ️ **Aviso de Fallback:** A consulta primária via BigQuery falhou. Os dados foram obtidos via API de contingência.")
    
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
            resp_det = data_service.get_cnpj(cnpj)
            dados = resp_det.results
            st.session_state.last_search_source = resp_det.source
            st.session_state.last_search_fallback = resp_det.fallback_used
            
        if not dados:
            erro = resp_det.error or api_client.get_last_error() or f"CNPJ {cnpj} não encontrado ou erro na API."
            st.error(erro)
        else:
            st.session_state.current_cnpj = cnpj
            st.session_state.current_company_data = dados
            col_title, col_newtab = st.columns([5, 1])
            with col_title:
                st.header(dados.get('nome_empresarial', ''))
                st.subheader(f"CNPJ: {cnpj}")
                origem_det = data_service.get_source_display_name(resp_det.source, resp_det.fallback_used)
                st.caption(f"🔍 **Origem dos dados:** {origem_det}")
                if resp_det.fallback_used:
                    st.info(f"ℹ️ **Aviso de Fallback:** {resp_det.error}")
            with col_newtab:
                st.link_button("↗️ Abrir em Nova Aba", f"?cnpj={cnpj}", help="Abre esta empresa em uma nova aba independente do navegador")
            
            tab_grafo, tab_ficha = st.tabs(["🕸️ Grafo de Relacionamentos", "📄 Ficha Cadastral"])

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
                                resultados, erro, origem, src, fb = executar_busca_telefone(tel1[:2], tel1[2:])
                            st.session_state.last_search_source = src
                            st.session_state.last_search_fallback = fb
                            st.session_state.last_search_error = erro
                            navigate_to('RESULTS', title=f"Empresas com o Telefone {tel1}", results=resultados)
                            st.rerun()
                    else:
                        st.write("*Telefone 1 não informado*")

                    if len(tel2) > 2:
                        if st.button(f"📞 {tel2}", key="btn_tel2"):
                            with st.spinner(f"Buscando empresas com telefone {tel2}..."):
                                resultados, erro, origem, src, fb = executar_busca_telefone(tel2[:2], tel2[2:])
                            st.session_state.last_search_source = src
                            st.session_state.last_search_fallback = fb
                            st.session_state.last_search_error = erro
                            navigate_to('RESULTS', title=f"Empresas com o Telefone {tel2}", results=resultados)
                            st.rerun()
                
                with col2:
                    st.write("**E-mail:**")
                    email = dados.get('correio_eletronico')
                    if email:
                        if st.button(f"✉️ {email}", key="btn_email"):
                            with st.spinner(f"Buscando empresas com e-mail {email}..."):
                                resultados, erro, origem, src, fb = executar_busca_email(email)
                            st.session_state.last_search_source = src
                            st.session_state.last_search_fallback = fb
                            st.session_state.last_search_error = erro
                            navigate_to('RESULTS', title=f"Empresas com o E-mail {email}", results=resultados)
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
                                            resp_soc = data_service.buscar_empresas_do_socio(nome_socio, doc_socio)
                                            resultados = resp_soc.results
                                            erro = resp_soc.error
                                        st.session_state.last_search_source = resp_soc.source
                                        st.session_state.last_search_fallback = resp_soc.fallback_used
                                        if erro:
                                            st.session_state.last_search_error = erro
                                        navigate_to(
                                            'RESULTS',
                                            title=f"Empresas do Sócio: {nome_socio}",
                                            results=resultados
                                        )
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
                
                # Atividade Principal
                st.divider()
                st.write("### 💼 Atividade Principal")
                cnae_raw_cod = dados.get('cnae_fiscal_principal') or dados.get('cnae_fiscal_principal_descricao') or ''
                cnae_raw_desc = dados.get('cnae_fiscal_principal_descricao') or ''
                cnae_fmt, cnae_desc_txt = obter_cnae_completo(cnae_raw_cod, cnae_raw_desc)
                if cnae_desc_txt and cnae_desc_txt != "Atividade econômica não informada":
                    dados['cnae_fiscal_principal_descricao'] = f"{cnae_fmt} — {cnae_desc_txt}" if cnae_fmt else cnae_desc_txt
                    dados['cnae_fiscal_principal'] = cnae_fmt
                    st.markdown(f"**`{cnae_fmt}`** — **{cnae_desc_txt}**")
                elif cnae_fmt:
                    st.markdown(f"**`{cnae_fmt}`**")
                else:
                    st.write("Atividade econômica não informada.")

            with tab_grafo:
                st.write("### 🕸️ Grafo Interativo de Relacionamentos")
                st.caption(
                    "Todos os controles, expansões e filtros estão integrados diretamente na barra superior da janela do grafo. "
                    "Arraste entidades livremente para organizar (elas ficam onde você soltar sem voltar), passe o mouse para ver ações (botão **✚** para expandir, **✕** para excluir), "
                    "ou utilize o seletor rápido abaixo."
                )

                # 1. Expansão sob demanda: Sócios 2º Grau (Fase 6)
                if st.session_state.get('graph_expand_socios', False):
                    with st.spinner("Expandindo empresas vinculadas aos sócios da raiz (Grau 2)..."):
                        limit = st.session_state.get('graph_max_companies_limit', 25)
                        updated_cache, soc_summary = graph_expansions.expand_socios_grau2(
                            root_data=dados,
                            max_per_partner=limit,
                            cache=st.session_state.graph_cache_socios_empresas
                        )
                        st.session_state.graph_cache_socios_empresas = updated_cache
                        st.session_state.graph_expand_socios_summary = soc_summary

                # 2. Coleta de Empresas Visíveis na Rede para Expansão de Contatos e Inteligência
                visible_cluster_companies = [dados] + list(st.session_state.multi_expanded_companies.values())
                if st.session_state.get('graph_expand_socios'):
                    for comp_list in st.session_state.graph_cache_socios_empresas.values():
                        visible_cluster_companies.extend(comp_list)
                for comp_list in st.session_state.multi_expanded_socios.values():
                    visible_cluster_companies.extend(comp_list)

                # 3. Expansão sob demanda: Contatos da Rede (Fase 6)
                if st.session_state.get('graph_expand_contacts', False):
                    with st.spinner(f"Buscando empresas com contatos compartilhados na rede ({len(visible_cluster_companies)} empresas analisadas)..."):
                        limit = st.session_state.get('graph_max_companies_limit', 25)
                        months = st.session_state.get('bq_months', 3)
                        updated_cache, cont_summary = graph_expansions.expand_contacts_network(
                            visible_companies=visible_cluster_companies,
                            max_per_contact=limit,
                            cache=st.session_state.graph_cache_contatos_empresas,
                            months=months
                        )
                        st.session_state.graph_cache_contatos_empresas = updated_cache
                        st.session_state.graph_expand_contacts_summary = cont_summary

                # Compilação Completa das Empresas da Rede para Inteligência
                all_cluster_companies = list(visible_cluster_companies)
                if st.session_state.get('graph_expand_contacts'):
                    for comp_list in st.session_state.graph_cache_contatos_empresas.values():
                        all_cluster_companies.extend(comp_list)
                for comp_list in st.session_state.multi_expanded_phones.values():
                    all_cluster_companies.extend(comp_list)
                for comp_list in st.session_state.multi_expanded_emails.values():
                    all_cluster_companies.extend(comp_list)

                # Banners informativos dos resumos auditáveis de expansão global
                if st.session_state.get('graph_expand_socios') and st.session_state.get('graph_expand_socios_summary'):
                    s = st.session_state.graph_expand_socios_summary
                    st.info(
                        f"👥 **Expansão de Sócios (Grau 2) Ativa:** {s.get('socios_consultados', 0)} sócios consultados "
                        f"({s.get('total_socios_raiz', 0)} sócios diretos na raiz) • "
                        f"{s.get('empresas_adicionadas', 0)} empresas conectadas • "
                        f"{s.get('duplicatas_removidas', 0)} descartadas (raiz/repetidas/teto {st.session_state.get('graph_max_companies_limit', 25)})"
                        + (f" • ⚠️ {s.get('falhas')} falhas" if s.get('falhas') else "")
                    )

                if st.session_state.get('graph_expand_contacts') and st.session_state.get('graph_expand_contacts_summary'):
                    c = st.session_state.graph_expand_contacts_summary
                    c_msg = (
                        f"📞 **Expansão de Contatos da Rede Ativa:** {c.get('empresas_analisadas', 0)} empresas analisadas • "
                        f"{c.get('contatos_unicos', 0)} contatos únicos ({c.get('telefones', 0)} telefones, {c.get('emails', 0)} e-mails) • "
                        f"{c.get('empresas_adicionadas', 0)} empresas conectadas • "
                        f"{c.get('duplicatas_removidas', 0)} descartadas"
                    )
                    if c.get("avisos_erros"):
                        st.warning(c_msg + f" • ℹ️ Observações ({len(c['avisos_erros'])}): " + "; ".join(c['avisos_erros'][:2]))
                    else:
                        st.info(c_msg)

                # Execução dos Motores de Inteligência (com cache por CNPJ para alta performance)
                if st.session_state.get('last_analyzed_cnpj') != cnpj:
                    st.session_state.cached_risk_info = risk_analyzer.analyze_company_risk(dados)
                    st.session_state.cached_family_rel = risk_analyzer.detect_family_relationships(dados.get('socios', []))
                    st.session_state.cached_ubo_result = risk_analyzer.trace_ultimate_beneficial_owners(cnpj, dados, api_client)
                    st.session_state.last_analyzed_cnpj = cnpj

                risk_info = st.session_state.cached_risk_info
                family_relationships = st.session_state.cached_family_rel
                ubo_result = st.session_state.cached_ubo_result
                ubos = ubo_result.get('ubos', [])
                shared_addresses = risk_analyzer.detect_shared_addresses(all_cluster_companies)

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

                # Barra rápida de controles de expansão da rede com status inequívoco
                c_btn_exp1, c_btn_exp2, c_btn_exp3 = st.columns([1.6, 1.6, 1.8])
                with c_btn_exp1:
                    soc_ativo = st.session_state.get('graph_expand_socios', False)
                    status_soc = "🟢 EXIBIDOS" if soc_ativo else "⚪ OCULTOS"
                    lbl_soc = "❌ CLIQUE P/ OCULTAR Sócios (2º Grau)" if soc_ativo else "➕ CLIQUE P/ EXIBIR Sócios (2º Grau)"
                    st.caption(f"Sócios 2º Grau: **{status_soc}**")
                    if st.button(lbl_soc, key="btn_toggle_expand_socios", use_container_width=True, help="Alterna a exibição das empresas vinculadas aos sócios diretos da raiz (Grau 2)"):
                        graph_dispatcher.handle_graph_action({
                            "action": "toggle_feature",
                            "feature": "expand_socios",
                            "nonce": f"ext_toggle_socios_{time.time()}"
                        })
                        st.rerun()

                with c_btn_exp2:
                    cont_ativo = st.session_state.get('graph_expand_contacts', False)
                    status_cont = "🟢 EXIBIDOS" if cont_ativo else "⚪ OCULTOS"
                    lbl_cont = "❌ CLIQUE P/ OCULTAR Contatos da Rede" if cont_ativo else "➕ CLIQUE P/ EXIBIR Contatos da Rede"
                    st.caption(f"Contatos da Rede: **{status_cont}**")
                    if st.button(lbl_cont, key="btn_toggle_expand_contacts", use_container_width=True, help="Alterna a exibição de empresas que compartilham telefones ou e-mails na rede"):
                        graph_dispatcher.handle_graph_action({
                            "action": "toggle_feature",
                            "feature": "expand_contacts",
                            "nonce": f"ext_toggle_contacts_{time.time()}"
                        })
                        st.rerun()

                with c_btn_exp3:
                    st.caption("Ação Rápida:")
                    if st.button("🧹 Limpar Relações Expandidas", key="btn_clear_graph_exp", use_container_width=True, help="Reinicia a visualização mantendo apenas a empresa raiz e seus vínculos diretos"):
                        graph_dispatcher.handle_graph_action({
                            "action": "clear",
                            "nonce": f"ext_clear_{time.time()}"
                        })
                        st.rerun()

                # Card de entidade clicada no Grafo (Cópia automática e Link para Nova Aba sem fechar o grafo)
                sel_ev = st.session_state.get('selected_graph_node')
                if sel_ev and isinstance(sel_ev, dict):
                    sel_lbl = sel_ev.get('entity_label') or sel_ev.get('node_id') or ''
                    sel_val = sel_ev.get('entity_value') or ''
                    sel_type = str(sel_ev.get('entity_type') or '').upper()
                    link_url = None
                    if 'EMPRESA' in sel_type:
                        c_dig = "".join(filter(str.isdigit, str(sel_val)))
                        if len(c_dig) >= 8:
                            link_url = f"?cnpj={c_dig}"
                    elif 'SOCIO' in sel_type or 'UBO' in sel_type:
                        l_clean = sel_lbl.replace("👑", "").replace("👤", "").strip()
                        if l_clean:
                            link_url = f"?socio={urllib.parse.quote(l_clean)}"

                    c_info1, c_info2 = st.columns([3.2, 1.3])
                    with c_info1:
                        st.info(f"🎯 Entidade Clicada: **{sel_lbl}** • Dado copiado automaticamente para a área de transferência!")
                    with c_info2:
                        if link_url:
                            st.markdown(
                                f'<a href="{link_url}" target="_blank" style="display:inline-block; width:100%; text-align:center; padding:9px 12px; background:#1565c0; color:#ffffff; border-radius:6px; font-weight:700; text-decoration:none; margin-top:2px; font-size:13px;">↗️ Abrir em Nova Aba</a>',
                                unsafe_allow_html=True
                            )

                # Renderização oficial via Streamlit Custom Component (Fase 2)
                comp_event, nos_atuais = graph_builder.render_interactive_graph(
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
                    key=f"pomelo_graph_comp_{cnpj}",
                    false_positive_accountants=st.session_state.graph_false_positive_accountants,
                    manual_accountants=st.session_state.graph_manual_accountants
                )

                # Despacho unificado de eventos do componente interativo (Fase 3)
                if comp_event and isinstance(comp_event, dict):
                    if comp_event.get("action") == "select_node":
                        st.session_state.selected_graph_node = comp_event
                        if comp_event.get("copied_value"):
                            st.toast(f"📋 Copiado: {comp_event['copied_value']}")
                    if graph_dispatcher.handle_graph_action(
                        comp_event,
                        expand_fn=executar_expansao_entidade,
                        root_id=cnpj
                    ):
                        st.rerun()

                # Seletor Pontual de Expansão / Exclusão de Entidades
                cnpj_digits = "".join(filter(str.isdigit, str(cnpj or "")))
                opcoes_nos = {
                    n["id"]: f"{'👤' if n['type'] in ('SOCIO','UBO') else '🏢' if 'EMPRESA' in n['type'] else '📞' if n['type']=='TELEFONE' else '✉️' if n['type']=='EMAIL' else '📌'} {n['label']} ({n['type']})"
                    for n in (nos_atuais or [])
                    if n["id"] not in st.session_state.graph_excluded_nodes
                }
                if opcoes_nos:
                    c_sel_ent, c_act_exp, c_act_del = st.columns([3.2, 1.2, 0.9])
                    with c_sel_ent:
                        sel_node_id = st.selectbox(
                            "🎯 Entidade Selecionada para Expansão / Exclusão:",
                            options=list(opcoes_nos.keys()),
                            format_func=lambda nid: opcoes_nos.get(nid, nid),
                            key="sel_node_action_box",
                            label_visibility="collapsed"
                        )
                    with c_act_exp:
                        if st.button("✚ Expandir Nó", key="btn_act_expand_node", use_container_width=True, help="Busca e adiciona à rede todas as empresas e conexões vinculadas a esta entidade"):
                            target_n = next((n for n in nos_atuais if n["id"] == sel_node_id), None)
                            if target_n:
                                graph_dispatcher.handle_graph_action({
                                    "action": "expand",
                                    "node_id": target_n["id"],
                                    "entity_type": target_n["type"],
                                    "entity_value": target_n["val"],
                                    "entity_label": target_n["label"],
                                    "nonce": f"ext_expand_{time.time()}"
                                }, expand_fn=executar_expansao_entidade, root_id=cnpj)
                                st.rerun()
                    with c_act_del:
                        is_sel_root = bool(
                            sel_node_id and (
                                sel_node_id == cnpj or
                                sel_node_id == f"cnpj_{cnpj}" or
                                (cnpj_digits and "".join(filter(str.isdigit, str(sel_node_id))) == cnpj_digits) or
                                str(sel_node_id).lower() == "empresa_root"
                            )
                        )
                        if st.button("✕ Remover Nó", key="btn_act_del_node", use_container_width=True, disabled=is_sel_root, help="Remove temporariamente esta entidade e suas arestas do grafo"):
                            target_n = next((n for n in nos_atuais if n["id"] == sel_node_id), None)
                            if sel_node_id:
                                graph_dispatcher.handle_graph_action({
                                    "action": "delete",
                                    "node_id": sel_node_id,
                                    "entity_label": target_n["label"] if target_n else sel_node_id,
                                    "nonce": f"ext_delete_{time.time()}"
                                }, root_id=cnpj)
                                st.rerun()

                st.divider()

                # Painel de Dossiês, Relatórios e Persistência
                tab_rep, tab_case, tab_timeline, tab_acct, tab_excl, tab_manual = st.tabs([
                    "📑 Dossiê & Relatórios",
                    "💾 Salvar/Carregar Projeto",
                    "⏱️ Linha do Tempo Societária",
                    "🧮 Contadores & Falsos Positivos",
                    "🚫 Gerenciar Exclusões",
                    "➕ Inserção Manual"
                ])

                with tab_rep:
                    st.write("#### 📑 Emissão de Relatório e Dossiê Consolidado")
                    st.caption("Exporte todos os vínculos, indicadores de risco, quadro societário e fundamentação pericial em formato profissional.")
                    
                    with st.expander("⚙️ Configurações do Assistente de IA Pericial (API Grátis)", expanded=False):
                        st.markdown("""
                        O assistente opera sob diretrizes **estritamente técnicas, assépticas e pragmáticas (sem adjetivos valorativos ou juízos preliminares)**, 
                        estruturando inferências analíticas com base em grandezas quantitativas (empresas vinculadas, sócios, temporalidade, coincidência de domicílios) 
                        e subsunção normativa hipotética (**Art. 50 do Código Civil, Lei 13.874/19, CPC arts. 133 a 137 e Art. 28 do CDC**).
                        
                        **Opções de API 100% Gratuitas:**
                        * 🌟 **Google Gemini Free Tier (Recomendado):** [Obter Chave Grátis no Google AI Studio](https://aistudio.google.com/app/apikey) (15 req/min sem custo).
                        * 🚀 **Groq Cloud Free Tier (Llama 3.3 70B):** [Obter Chave Grátis no Groq Console](https://console.groq.com/keys) (Ultra-rápido).
                        * 🌐 **OpenRouter Free:** [Obter Chave no OpenRouter](https://openrouter.ai/keys) (Modelos livres).
                        * 🛡️ *Modo Offline / Sem Chave:* Se nenhuma chave for informada, o sistema aciona o motor pericial determinístico local automaticamente.
                        """)
                        c_ai_prov, c_ai_key = st.columns([1, 2])
                        with c_ai_prov:
                            ai_provider_sel = st.selectbox(
                                "Provedor de IA:",
                                options=["auto", "gemini", "groq", "openrouter"],
                                format_func=lambda x: {
                                    "auto": "⚡ Automático (Melhor Disponível)",
                                    "gemini": "🌟 Google Gemini (gemini-1.5-flash)",
                                    "groq": "🚀 Groq Cloud (llama-3.3-70b)",
                                    "openrouter": "🌐 OpenRouter (Modelos Free)"
                                }.get(x, x),
                                key="sel_ai_provider"
                            )
                        with c_ai_key:
                            custom_key = st.text_input(
                                "Chave de API Gratuita (opcional se configurada no ambiente):",
                                type="password",
                                placeholder="Cole sua chave API gratuita aqui...",
                                key="input_ai_key",
                                value=st.session_state.get("custom_ai_api_key", "")
                            )
                            st.session_state.custom_ai_api_key = custom_key

                    col_arg1, col_arg2 = st.columns([3, 2])
                    with col_arg1:
                        st.session_state.investigation_notes = st.text_area(
                            "Laudo Técnico-Relacional & Inferências Investigativas:",
                            value=st.session_state.investigation_notes,
                            placeholder="Insira aqui as anotações do caso ou acione os botões ao lado para gerar o laudo relacional e subsunção normativa fundamentada em dados quantitativos...",
                            height=160
                        )
                    with col_arg2:
                        st.write("")
                        if st.button("🤖 Gerar Laudo Relacional & Hipóteses com IA", key="btn_gen_ai_dossier", use_container_width=True, type="primary"):
                            with st.spinner("Analisando malha societária, cruzando correlações quantitativas e elaborando laudo pericial com IA..."):
                                ai_res = ai_grounding.gerar_fundamentacao_dossie_ia(
                                    root_data=dados,
                                    all_companies=all_cluster_companies,
                                    socios_list=dados.get('socios', []),
                                    risk_info=risk_info,
                                    shared_addresses=shared_addresses,
                                    ubos=ubos,
                                    existing_notes=st.session_state.investigation_notes,
                                    provider=st.session_state.get("sel_ai_provider", "auto"),
                                    custom_api_key=st.session_state.get("custom_ai_api_key", "")
                                )
                                st.session_state.investigation_notes = ai_res.get("texto_integral", "")
                                if ai_res.get("used_ai"):
                                    st.success(f"Laudo técnico elaborado com sucesso via {ai_res.get('provider')}!")
                                else:
                                    st.info(f"Laudo gerado via {ai_res.get('provider')}. {ai_res.get('fallback_reason', '')}")
                                st.rerun()

                        if st.button("⚖️ Minuta Técnica Local (Sem IA)", key="btn_gen_arg_logic", use_container_width=True):
                            with st.spinner("Estruturando análise técnica relacional determinística..."):
                                arg_dict = report_generator.build_argumentative_dossier(
                                    root_data=dados,
                                    all_companies=all_cluster_companies,
                                    socios_list=dados.get('socios', []),
                                    risk_info=risk_info,
                                    shared_addresses=shared_addresses,
                                    ubos=ubos,
                                    notes=st.session_state.investigation_notes
                                )
                                st.session_state.investigation_notes = arg_dict.get('texto_integral', '')
                                st.success("Lógica argumentativa gerada!")
                                st.rerun()

                    c_rep1, c_rep2 = st.columns(2)
                    with c_rep1:
                        if st.button("📑 Compilar Dossiê Completo (PDF)", key="btn_compile_pdf", use_container_width=True):
                            with st.spinner("Gerando Dossiê em PDF..."):
                                st.session_state[f"pdf_{cnpj}"] = report_generator.generate_pdf_dossier(
                                    root_data=dados,
                                    all_companies=all_cluster_companies,
                                    socios_list=dados.get('socios', []),
                                    risk_info=risk_info,
                                    shared_addresses=shared_addresses,
                                    ubos=ubos,
                                    notes=st.session_state.investigation_notes
                                )
                        if st.session_state.get(f"pdf_{cnpj}"):
                            st.download_button(
                                "📥 Baixar Dossiê Completo (PDF)",
                                data=st.session_state[f"pdf_{cnpj}"],
                                file_name=f"dossie_investigativo_{cnpj}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                    with c_rep2:
                        if st.button("📊 Compilar Planilha Consolidada (Excel)", key="btn_compile_excel", use_container_width=True):
                            with st.spinner("Gerando Planilha Excel..."):
                                st.session_state[f"excel_{cnpj}"] = report_generator.generate_excel_dossier(
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
                        if st.session_state.get(f"excel_{cnpj}"):
                            st.download_button(
                                "📥 Baixar Planilha Consolidada (Excel)",
                                data=st.session_state[f"excel_{cnpj}"],
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
                            },
                            accountant_false_positives=st.session_state.graph_false_positive_accountants,
                            accountant_manual_nodes=st.session_state.graph_manual_accountants
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
                                    st.session_state.graph_false_positive_accountants = loaded.get('accountant_false_positives', set())
                                    st.session_state.graph_manual_accountants = loaded.get('accountant_manual_nodes', set())
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

                with tab_acct:
                    st.write("#### 🧮 Gestão de Contadores & Correção de Falsos Positivos")
                    st.caption(
                        "O sistema classifica automaticamente entidades contábeis pelo CNAE 69.20 e termos específicos. "
                        "Se uma entidade foi sinalizada indevidamente como contador (falso positivo), desmarque-a aqui com 1 clique."
                    )
                    
                    col_ac1, col_ac2 = st.columns([1.6, 1.1])
                    with col_ac1:
                        st.markdown("##### 📌 Entidades Atualmente Sinalizadas como Contador (`🧮`)")
                        contadores_atuais = [n for n in (nos_atuais or []) if n.get("is_accountant")]
                        if contadores_atuais:
                            for cnt in contadores_atuais:
                                c_lbl, c_btn = st.columns([2.8, 1.4])
                                with c_lbl:
                                    origem = "Inserção Manual" if cnt.get('id') in st.session_state.graph_manual_accountants else "Detecção Automática"
                                    st.markdown(f"🧮 **{cnt.get('label')}** ({cnt.get('type')})")
                                    st.caption(f"ID: `{cnt.get('id')}` • Origem: *{origem}*")
                                with c_btn:
                                    if st.button("🛡️ Falso Positivo", key=f"btn_fp_{cnt.get('id')}", help="Remover marcação de contador desta entidade"):
                                        st.session_state.graph_false_positive_accountants.add(cnt.get('id'))
                                        st.session_state.graph_manual_accountants.discard(cnt.get('id'))
                                        st.toast(f"✅ {cnt.get('label')} desmarcado como contador!")
                                        st.rerun()
                                st.divider()
                        else:
                            st.info("Nenhuma entidade na rede está sinalizada como contador no momento.")

                        st.markdown("##### ➕ Marcar Entidade Manualmente como Contador")
                        candidatos_contador = {
                            f"{n['label']} [{n['type']}]": n['id']
                            for n in (nos_atuais or [])
                            if not n.get('is_accountant') and not n['id'].startswith('cnpj_' + str(cnpj))
                        }
                        if candidatos_contador:
                            c_sel_acct = st.selectbox(
                                "Selecione uma entidade para sinalizar como Contador:",
                                options=list(candidatos_contador.keys()),
                                key="sel_manual_acct"
                            )
                            if st.button("🧮 Sinalizar como Contador", key="btn_add_manual_acct"):
                                node_id_acct = candidatos_contador[c_sel_acct]
                                st.session_state.graph_manual_accountants.add(node_id_acct)
                                st.session_state.graph_false_positive_accountants.discard(node_id_acct)
                                st.toast("🧮 Entidade sinalizada como contador com sucesso!")
                                st.rerun()

                    with col_ac2:
                        st.markdown("##### ↺ Falsos Positivos Desmarcados")
                        if st.session_state.graph_false_positive_accountants:
                            st.caption("Entidades com sinalização de contador removida pelo analista:")
                            for fp_id in list(st.session_state.graph_false_positive_accountants):
                                c_fp_lbl, c_fp_btn = st.columns([2.5, 1])
                                node_match = next((n for n in (nos_atuais or []) if n['id'] == fp_id), None)
                                nome_fp = node_match.get('label') if node_match else fp_id
                                with c_fp_lbl:
                                    st.write(f"• **{nome_fp}**")
                                    st.caption(f"`{fp_id}`")
                                with c_fp_btn:
                                    if st.button("↺ Restaurar", key=f"btn_undo_fp_{fp_id}", help="Voltar a considerar como contador"):
                                        st.session_state.graph_false_positive_accountants.remove(fp_id)
                                        st.rerun()
                            if st.button("Limpar Todos os Falsos Positivos", key="btn_clear_all_fps"):
                                st.session_state.graph_false_positive_accountants = set()
                                st.rerun()
                        else:
                            st.caption("Nenhum falso positivo registrado até agora.")

                with tab_excl:
                    st.write("#### 🚫 Gerenciar Exclusão de Nós (Contadores e Ruídos)")
                    col_ex1, col_ex2 = st.columns([3, 2])
                    with col_ex1:
                        cnpj_digits = "".join(filter(str.isdigit, str(cnpj or "")))
                        opcoes_excluir = {
                            f"{n['label']} [{n['type']}]": n['id']
                            for n in (nos_atuais or [])
                            if not (
                                n['type'] == 'EMPRESA_ROOT' or
                                n['id'].startswith('cnpj_' + str(cnpj)) or
                                (cnpj_digits and "".join(filter(str.isdigit, str(n['id']))) == cnpj_digits) or
                                str(n['id']).lower() in ("empresa_root", "root")
                            )
                        }
                        if opcoes_excluir:
                            selecionados = st.multiselect(
                                "Selecione nó(s) para remover do grafo:",
                                options=list(opcoes_excluir.keys()),
                                key="multi_excluir_nos"
                            )
                            if st.button("❌ Remover Nó(s) Selecionado(s)", disabled=not selecionados):
                                for sel in selecionados:
                                    graph_dispatcher.exclude_graph_node(opcoes_excluir[sel], label=sel, root_id=cnpj)
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
                                        graph_dispatcher.restore_graph_node(ex_id)
                                        st.rerun()
                            if st.button("Restaurar Todos os Nós", key="rst_all_nodes"):
                                graph_dispatcher.restore_all_graph_nodes()
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
                                'doc': sanitizers.adequar_documento(m_doc),
                                'obs': m_obs.strip()
                            })
                            st.success(f"Nó '{m_nome.strip()}' adicionado ao grafo!")
                            st.rerun()

                    with sub_tm2:
                        st.caption("Conecte dois nós do grafo com uma aresta destacada (vermelho neon / tracejada).")
                        todos_nos_map = {f"{n['label']} [{n['type']}]": n['id'] for n in (nos_atuais or [])}
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

elif st.session_state.view == 'OSINT':
    render_back_button()
    osint.render_osint_screen()
