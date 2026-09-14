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
import auth

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
if 'graph_false_positive_accountants' not in st.session_state:
    st.session_state.graph_false_positive_accountants = set()
if 'graph_manual_accountants' not in st.session_state:
    st.session_state.graph_manual_accountants = set()
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

def executar_expansao_entidade(ent_type: str, ent_val: str, ent_label: str = ""):
    """Executa a expansão pontual de uma entidade específica (Pessoa Física, Jurídica, Telefone, E-mail)."""
    ent_type = (ent_type or '').upper()
    val_str = str(ent_val or '').strip()

    # Sanitização defensiva contra prefixos de node IDs
    if val_str.lower().startswith("socio_"):
        val_str = val_str[6:].strip()
    elif val_str.lower().startswith("cnpj_"):
        val_str = val_str[5:].strip()
    elif val_str.lower().startswith("email_"):
        val_str = val_str[6:].strip()
    elif val_str.lower().startswith("tel_"):
        val_str = val_str[4:].strip()

    if ent_type in ("EMPRESA", "EMPRESA_ROOT") or (val_str.isdigit() and len(val_str) in (8, 14)):
        cnpj_limpo = "".join(filter(str.isdigit, val_str))
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
        socio_nome = val_str.upper()
        if socio_nome:
            if socio_nome not in st.session_state.multi_expanded_socios or not st.session_state.multi_expanded_socios.get(socio_nome):
                with st.spinner(f"Buscando empresas vinculadas ao sócio {socio_nome}..."):
                    res_soc = api_client.buscar_empresas_do_socio(socio_nome)
                    if res_soc:
                        st.session_state.multi_expanded_socios[socio_nome] = res_soc
                        st.toast(f"✅ {len(res_soc)} empresa(s) do sócio {socio_nome} adicionada(s) à rede!")
                    else:
                        st.warning(f"Nenhuma outra empresa encontrada para o sócio {socio_nome}.")
            else:
                st.info("As empresas deste sócio já estão expandidas na rede.")
    elif ent_type == "TELEFONE":
        fone_limpo = "".join(filter(str.isdigit, val_str))
        if len(fone_limpo) >= 8:
            if fone_limpo not in st.session_state.multi_expanded_phones or not st.session_state.multi_expanded_phones.get(fone_limpo):
                if len(fone_limpo) in (10, 11):
                    ddd = fone_limpo[:2]
                    num = fone_limpo[2:]
                else:
                    ddd = "11"
                    num = fone_limpo
                with st.spinner(f"Buscando empresas com telefone ({ddd}) {num}..."):
                    res_tel = api_client.buscar_telefone(ddd, num)
                    if res_tel:
                        st.session_state.multi_expanded_phones[fone_limpo] = res_tel
                        st.toast(f"✅ {len(res_tel)} empresa(s) com telefone ({ddd}) {num} adicionada(s)!")
                    else:
                        st.warning(f"Nenhuma outra empresa encontrada com telefone ({ddd}) {num}.")
            else:
                st.info("As empresas deste telefone já estão expandidas na rede.")
    elif ent_type == "EMAIL":
        em_limpo = val_str.lower()
        if em_limpo:
            if em_limpo not in st.session_state.multi_expanded_emails or not st.session_state.multi_expanded_emails.get(em_limpo):
                with st.spinner(f"Buscando empresas com e-mail {em_limpo}..."):
                    res_em = api_client.buscar_email(em_limpo)
                    if res_em:
                        st.session_state.multi_expanded_emails[em_limpo] = res_em
                        st.toast(f"✅ {len(res_em)} empresa(s) com e-mail {em_limpo} adicionada(s)!")
                    else:
                        st.warning(f"Nenhuma outra empresa encontrada com e-mail {em_limpo}.")
            else:
                st.info("As empresas deste e-mail já estão expandidas na rede.")

# Processa requisições de expansão ou exclusão vindas do grafo ou URL direta
_q_exp_type = st.query_params.get("expand_type")
_q_exp_val = st.query_params.get("expand_val")
_q_exp_lbl = st.query_params.get("expand_label", _q_exp_val)
_q_del_node = st.query_params.get("exclude_node")

if _q_exp_type and _q_exp_val:
    executar_expansao_entidade(_q_exp_type, _q_exp_val, _q_exp_lbl)
    st.session_state.view = 'DETAILS'
    if "expand_type" in st.query_params:
        del st.query_params["expand_type"]
    if "expand_val" in st.query_params:
        del st.query_params["expand_val"]
    if "expand_label" in st.query_params:
        del st.query_params["expand_label"]

if _q_del_node:
    st.session_state.graph_excluded_nodes.add(_q_del_node)
    st.session_state.view = 'DETAILS'
    st.toast("✕ Entidade removida da rede.")
    if "exclude_node" in st.query_params:
        del st.query_params["exclude_node"]

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
    col_logo, col_txt = st.sidebar.columns([1, 2.2])
    with col_logo:
        st.image(logo_path, width=70)
    with col_txt:
        st.markdown("<h3 style='margin-bottom:0; font-weight:800; color:#1a237e;'>POMELO</h3><span style='font-size:11px; color:#546e7a; font-weight:500;'>Inteligência Societária & Grafos</span>", unsafe_allow_html=True)
else:
    st.sidebar.title("🍊 POMELO")

st.sidebar.markdown(
    "<div style='background:#e8f5e9; border:1px solid #c8e6c9; border-radius:6px; padding:4px 8px; margin: 8px 0 12px 0; font-size:11px; color:#2e7d32; font-weight:600; display:flex; align-items:center; gap:6px;'>"
    "<span>🟢</span> Base CNPJ Conectada • Sigilo Ativo"
    "</div>",
    unsafe_allow_html=True
)

# Navegação Principal
menu_options = ["🔍 Busca Simples", "⚡ Busca Avançada", "📊 Resultados", "🏢 Dossiê / Grafo"]
view_map = {
    "🔍 Busca Simples": "HOME",
    "⚡ Busca Avançada": "ADVANCED",
    "📊 Resultados": "RESULTS",
    "🏢 Dossiê / Grafo": "DETAILS"
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
st.sidebar.caption("🔒 **Ambiente Seguro & Sigiloso**")
st.sidebar.caption("POMELO Intelligence • v2.5")


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

                # Barra rápida de controles de expansão da rede
                c_btn_exp1, c_btn_exp2, c_btn_exp3 = st.columns([1.5, 1.5, 2])
                with c_btn_exp1:
                    lbl_soc = "👥 Ocultar Sócios (2º Grau)" if st.session_state.get('graph_expand_socios') else "👥 Expandir Sócios (2º Grau)"
                    if st.button(lbl_soc, key="btn_toggle_expand_socios", use_container_width=True):
                        st.session_state.graph_expand_socios = not st.session_state.get('graph_expand_socios', False)
                        st.rerun()
                with c_btn_exp2:
                    lbl_cont = "📞 Ocultar Contatos" if st.session_state.get('graph_expand_contacts') else "📞 Expandir Contatos"
                    if st.button(lbl_cont, key="btn_toggle_expand_contacts", use_container_width=True):
                        st.session_state.graph_expand_contacts = not st.session_state.get('graph_expand_contacts', False)
                        st.rerun()
                with c_btn_exp3:
                    if st.button("🧹 Limpar Relações Expandidas", key="btn_clear_graph_exp", use_container_width=True):
                        st.session_state.graph_excluded_nodes = set()
                        st.session_state.graph_false_positive_accountants = set()
                        st.session_state.graph_manual_accountants = set()
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
                        st.toast("🧹 Grafo reiniciado para a empresa raiz.")
                        st.rerun()

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
                    key=f"pomelo_graph_comp_{st.session_state.get('current_cnpj')}",
                    false_positive_accountants=st.session_state.graph_false_positive_accountants,
                    manual_accountants=st.session_state.graph_manual_accountants
                )

                # Processamento seguro de eventos do Custom Component (um por nonce)
                if 'last_processed_graph_nonce' not in st.session_state:
                    st.session_state.last_processed_graph_nonce = None

                if comp_event and isinstance(comp_event, dict):
                    ev_nonce = comp_event.get("nonce")
                    if ev_nonce and ev_nonce != st.session_state.last_processed_graph_nonce:
                        st.session_state.last_processed_graph_nonce = ev_nonce
                        ev_act = comp_event.get("action")
                        if ev_act == "expand":
                            ev_type = comp_event.get("entity_type") or comp_event.get("type")
                            ev_val = comp_event.get("entity_value") or comp_event.get("val")
                            ev_lbl = comp_event.get("entity_label") or comp_event.get("label") or ev_val
                            if ev_type and ev_val:
                                executar_expansao_entidade(ev_type, ev_val, ev_lbl)
                                st.rerun()
                        elif ev_act == "delete":
                            ev_nid = comp_event.get("node_id") or comp_event.get("id")
                            if ev_nid:
                                st.session_state.graph_excluded_nodes.add(ev_nid)
                                ev_lbl = comp_event.get("entity_label") or ev_nid
                                st.toast(f"✕ Entidade '{ev_lbl}' removida da rede.")
                                st.rerun()
                        elif ev_act == "toggle_feature":
                            ev_feat = comp_event.get("feature")
                            if ev_feat == "expand_socios":
                                st.session_state.graph_expand_socios = not st.session_state.get('graph_expand_socios', False)
                                st.rerun()
                            elif ev_feat == "expand_contacts":
                                st.session_state.graph_expand_contacts = not st.session_state.get('graph_expand_contacts', False)
                                st.rerun()
                        elif ev_act == "clear":
                            st.session_state.graph_excluded_nodes = set()
                            st.session_state.graph_false_positive_accountants = set()
                            st.session_state.graph_manual_accountants = set()
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
                            st.toast("🧹 Grafo reiniciado para a empresa raiz.")
                            st.rerun()

                # Seletor Pontual de Expansão / Exclusão de Entidades
                opcoes_nos = {
                    n["id"]: f"{'👤' if n['type'] in ('SOCIO','UBO') else '🏢' if 'EMPRESA' in n['type'] else '📞' if n['type']=='TELEFONE' else '✉️' if n['type']=='EMAIL' else '📌'} {n['label']} ({n['type']})"
                    for n in (nos_atuais or [])
                    if n["id"] not in st.session_state.graph_excluded_nodes
                }
                if opcoes_nos:
                    c_sel_ent, c_act_exp, c_act_del = st.columns([3.2, 1.2, 0.9])
                    with c_sel_ent:
                        sel_node_id = st.selectbox(
                            "🎯 Entidade Selecionada para Expansão:",
                            options=list(opcoes_nos.keys()),
                            format_func=lambda nid: opcoes_nos.get(nid, nid),
                            key="sel_node_action_box",
                            label_visibility="collapsed"
                        )
                    with c_act_exp:
                        if st.button("✚ Expandir Nó", key="btn_act_expand_node", use_container_width=True, help="Busca e adiciona à rede todas as empresas e conexões vinculadas a esta entidade"):
                            target_n = next((n for n in nos_atuais if n["id"] == sel_node_id), None)
                            if target_n:
                                executar_expansao_entidade(target_n["type"], target_n["val"], target_n["label"])
                                st.rerun()
                    with c_act_del:
                        if st.button("✕ Remover Nó", key="btn_act_del_node", use_container_width=True, help="Remove temporariamente esta entidade do grafo"):
                            if sel_node_id:
                                st.session_state.graph_excluded_nodes.add(sel_node_id)
                                st.toast("✕ Entidade removida do grafo.")
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
                    st.caption("Exporte todos os vínculos, indicadores de risco, quadro societário e anotações em formato profissional.")
                    
                    st.session_state.investigation_notes = st.text_area(
                        "Parecer / Notas da Investigação:",
                        value=st.session_state.investigation_notes,
                        placeholder="Insira aqui as conclusões, observações patrimoniais ou apontamentos do analista que constarão no relatório...",
                        height=100
                    )

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
                        opcoes_excluir = {
                            f"{n['label']} [{n['type']}]": n['id']
                            for n in (nos_atuais or [])
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
