"""
Módulo para geração de Grafos Interativos de Relacionamento Societário e Contatos (Vis.js).
Funcionalidades:
- Sinalização visual explícita de Contadores / Escritórios Contábeis (nós 🧮 em Teal)
- Exclusão e filtragem de nós (contadores / ruído de rede)
- Centralização e auto-enquadramento automáticos
- Movimentação livre de nós (sem efeito elástico de retorno)
- Inserção manual de Pessoas Físicas e Jurídicas com vínculos customizados
- Destaque visual de Risco / Irregularidades Cadastrais (Inapta, Baixada, Suspensa)
- Mapeamento de Endereços Compartilhados (nós 📍)
- Destaque do Beneficiário Final (UBO 👑)
- Detecção e arestas de Parentesco / Grupos Familiares
- Ferramentas de Enquadramento, Tela Cheia (Maximizar) e Exportação PNG
- Expansão dinâmica e recursiva de relações (Sócios, Empresas, Telefones, E-mails)
"""
import os
import json
from typing import Tuple, List, Dict, Set, Optional, Any
import streamlit.components.v1 as components

# Registro do Custom Component Streamlit com comunicação bidirecional
_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "components", "vis_graph")
_vis_graph_component = components.declare_component("interactive_network", path=_COMPONENT_DIR)

# Cores e Estilos dos Nós
COLOR_EMPRESA_ROOT = "#0D47A1"   # Azul Royal Escuro
COLOR_EMPRESA_LINK = "#1976D2"   # Azul Médio
COLOR_EMPRESA_RISK = "#D32F2F"   # Vermelho Alerta (Inapta/Baixada/Suspensa)
COLOR_SOCIO = "#E65100"          # Laranja
COLOR_UBO = "#FBC02D"            # Dourado (Beneficiário Final)
COLOR_CONTADOR = "#00897B"       # Verde Petróleo / Teal (Contador / Contabilidade)
COLOR_CONTADOR_BORDER = "#004D40"# Verde Petróleo Escuro
COLOR_EMAIL = "#2E7D32"          # Verde Floresta
COLOR_TELEFONE = "#7B1FA2"       # Roxo
COLOR_ENDERECO = "#00838F"       # Ciano / Turquesa (Endereço Compartilhado)
COLOR_MANUAL_PF = "#D81B60"      # Magenta Neon
COLOR_MANUAL_PJ = "#880E4F"      # Vinho / Magenta Escuro

# Cores e Estilos das Arestas
COLOR_EDGE_AUTO = "#90A4AE"      # Cinza azulado
COLOR_EDGE_MANUAL = "#D50000"    # Vermelho Neon
COLOR_EDGE_FAMILY = "#8E24AA"    # Púrpura (Parentesco)
COLOR_EDGE_ENDERECO = "#00ACC1"  # Ciano suave (Endereço)

TERMOS_CONTABILIDADE = [
    "contab", "contabil", "contabilidade", "assessoria", "consultoria",
    "fiscal@", "dp@", "escritorio", "cont@be", "contar", "auditoria", "contador"
]

CNAES_CONTABILIDADE = ["6920601", "6920602", "6920-6/01", "6920-6/02"]

def is_probable_accountant(label: str = "", title: str = "", cnae: str = "") -> bool:
    """Verifica se o nó possui termos ou CNAE característicos de escritório de contabilidade / contador."""
    content = f"{label} {title}".lower()
    for termo in TERMOS_CONTABILIDADE:
        if termo in content:
            return True
    cnae_clean = str(cnae or "").replace(".", "").replace("-", "").replace("/", "").strip()
    if cnae_clean in ("6920601", "6920602"):
        return True
    return False

def build_graph_elements(
    root_data: dict,
    socios_empresas: dict = None,
    contatos_empresas: dict = None,
    shared_addresses: dict = None,
    family_relationships: list = None,
    ubos: list = None,
    enable_risk_highlight: bool = True,
    excluded_nodes: set = None,
    auto_filter_accountants: bool = False,
    manual_nodes: list = None,
    manual_edges: list = None,
    extra_companies: dict = None
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Processa todos os dados e constrói as listas de nós e arestas para a rede.
    Retorna (nodes_list, edges_list, available_nodes).
    """
    if excluded_nodes is None:
        excluded_nodes = set()
    if socios_empresas is None:
        socios_empresas = {}
    if contatos_empresas is None:
        contatos_empresas = {}
    if shared_addresses is None:
        shared_addresses = {}
    if family_relationships is None:
        family_relationships = []
    if ubos is None:
        ubos = []
    if manual_nodes is None:
        manual_nodes = []
    if manual_edges is None:
        manual_edges = []
    if extra_companies is None:
        extra_companies = {}

    ubo_names = {u.get('nome', '').strip().lower() for u in ubos if u.get('nome')}
    nodes_dict = {}
    edges_list = []

    def add_node(
        node_id: str,
        label: str,
        title: str,
        color: str,
        size: int,
        shape: str = "dot",
        node_type: str = "OUTRO",
        border_color: str = None,
        raw_val: str = "",
        cnae: str = ""
    ):
        if node_id in excluded_nodes:
            return False

        # Verificação e Sinalização de CONTADOR (Requisito 4)
        is_acct = is_probable_accountant(label, title, cnae)
        if auto_filter_accountants and is_acct:
            return False

        display_color = color
        display_border = border_color or color
        display_label = label
        display_title = title

        if is_acct and node_type != "EMPRESA_ROOT":
            display_color = COLOR_CONTADOR
            display_border = COLOR_CONTADOR_BORDER
            if not display_label.startswith("🧮"):
                display_label = f"🧮 {display_label}"
            display_title += "<br><span style='background:#004D40; color:#ffffff; padding:2px 6px; border-radius:3px;'><b>🧮 SINALIZADO COMO CONTADOR / ESCRITÓRIO CONTÁBIL</b></span>"

        if node_id not in nodes_dict:
            nodes_dict[node_id] = {
                "id": node_id,
                "label": display_label,
                "title": display_title,
                "color": {
                    "background": display_color,
                    "border": display_border,
                    "highlight": {"background": "#FFEB3B", "border": "#F57F17"}
                },
                "size": size,
                "shape": shape,
                "font": {"color": "#212121", "size": 12, "face": "Roboto, Segoe UI, sans-serif"},
                "shadow": True,
                "_type": "CONTABILIDADE" if (is_acct and node_type != "EMPRESA_ROOT") else node_type,
                "_raw_label": label,
                "_raw_val": raw_val or node_id,
                "_is_accountant": is_acct
            }
        return True

    def add_edge(src: str, dst: str, label: str = "", manual: bool = False, custom_color: str = None, dashes: bool = False):
        if src in nodes_dict and dst in nodes_dict:
            if manual:
                edges_list.append({
                    "from": src,
                    "to": dst,
                    "label": label,
                    "color": {"color": COLOR_EDGE_MANUAL, "highlight": "#FF1744"},
                    "width": 3,
                    "dashes": [6, 4],
                    "font": {"color": COLOR_EDGE_MANUAL, "size": 11, "bold": True, "align": "middle"}
                })
            elif custom_color:
                edges_list.append({
                    "from": src,
                    "to": dst,
                    "label": label,
                    "color": {"color": custom_color, "highlight": custom_color},
                    "width": 2,
                    "dashes": [4, 4] if dashes else False,
                    "font": {"color": custom_color, "size": 10, "align": "middle"}
                })
            else:
                edges_list.append({
                    "from": src,
                    "to": dst,
                    "label": label,
                    "color": {"color": COLOR_EDGE_AUTO, "highlight": "#37474F"},
                    "width": 1.5,
                    "font": {"color": "#546E7A", "size": 10, "align": "middle"}
                })

    # 1. Empresa Principal (Raiz)
    root_cnpj = root_data.get('cnpj_basico', '')
    if len(root_cnpj) < 14 and 'cnpj_ordem' in root_data and 'cnpj_dv' in root_data:
        root_cnpj = f"{root_cnpj}{root_data['cnpj_ordem']}{root_data['cnpj_dv']}"
    elif not root_cnpj:
        root_cnpj = root_data.get('cnpj', 'EMPRESA_ROOT')

    root_name = root_data.get('nome_empresarial') or root_data.get('razao_social') or f"CNPJ {root_cnpj}"
    root_id = f"cnpj_{root_cnpj}"
    root_sit = (root_data.get('situacao_cadastral_descricao') or 'ATIVA').upper()
    is_root_risk = enable_risk_highlight and (root_sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'))

    root_color = COLOR_EMPRESA_RISK if is_root_risk else COLOR_EMPRESA_ROOT
    root_prefix = "⚠️ " if is_root_risk else ""

    root_tooltip = (
        f"<b>🏢 {root_name}</b><br>"
        f"CNPJ: {root_cnpj}<br>"
        f"Situação: {root_sit}<br>"
        f"CNAE: {root_data.get('cnae_fiscal_principal_descricao', 'N/A')}"
    )
    if is_root_risk:
        root_tooltip += f"<br><font color='#D32F2F'><b>⚠️ ALERTA: Situação {root_sit}</b></font>"

    add_node(
        root_id,
        label=f"{root_prefix}{root_name[:22]}" + ("..." if len(root_name) > 22 else ""),
        title=root_tooltip,
        color=root_color,
        size=36,
        shape="dot",
        node_type="EMPRESA_ROOT",
        raw_val=root_cnpj,
        cnae=root_data.get('cnae_fiscal_principal') or ""
    )

    # 2. Sócios da Raiz
    socios = root_data.get('socios', [])
    for i, s in enumerate(socios):
        nome_socio = (s.get('nome') or f"Sócio {i+1}").strip()
        qualif = s.get('qualificacao_descricao') or s.get('qualificacao_socio_descricao') or "Sócio"
        doc = s.get('cnpj_cpf') or ""
        socio_id = f"socio_{nome_socio.lower()}"

        is_ubo = nome_socio.lower() in ubo_names
        socio_color = COLOR_UBO if is_ubo else COLOR_SOCIO
        socio_prefix = "👑 " if is_ubo else ""

        socio_tooltip = (
            f"<b>👤 {nome_socio}</b><br>"
            f"Qualificação: {qualif}<br>"
            f"Documento: {doc or 'Não informado'}"
        )
        if is_ubo:
            socio_tooltip += "<br><font color='#F57F17'><b>👑 Beneficiário Final Identificado (UBO)</b></font>"

        if add_node(
            socio_id,
            label=f"{socio_prefix}{nome_socio[:18]}" + ("..." if len(nome_socio) > 18 else ""),
            title=socio_tooltip,
            color=socio_color,
            size=24 if is_ubo else 21,
            shape="dot",
            node_type="UBO" if is_ubo else "SOCIO",
            raw_val=nome_socio
        ):
            add_edge(root_id, socio_id, label=qualif[:16])

    # 3. Sócios e Empresas Expandidas (Itera sobre TODOS os sócios em socios_empresas)
    for s_nome, emp_list in socios_empresas.items():
        s_nome_clean = (s_nome or "").strip()
        if not s_nome_clean:
            continue
        s_id = f"socio_{s_nome_clean.lower()}"
        is_ubo = s_nome_clean.lower() in ubo_names
        s_color = COLOR_UBO if is_ubo else COLOR_SOCIO
        s_prefix = "👑 " if is_ubo else ""
        s_tooltip = f"<b>👤 {s_nome_clean}</b><br>Sócio"
        if is_ubo:
            s_tooltip += "<br><font color='#F57F17'><b>👑 Beneficiário Final Identificado (UBO)</b></font>"

        add_node(
            s_id,
            label=f"{s_prefix}{s_nome_clean[:18]}" + ("..." if len(s_nome_clean) > 18 else ""),
            title=s_tooltip,
            color=s_color,
            size=24 if is_ubo else 21,
            shape="dot",
            node_type="UBO" if is_ubo else "SOCIO",
            raw_val=s_nome_clean
        )

        for emp in (emp_list or []):
            emp_cnpj = emp.get('cnpj') or emp.get('cnpj_completo') or emp.get('cnpj_basico') or ""
            emp_nome = emp.get('razao_social') or emp.get('nome_empresarial') or emp.get('nome_fantasia') or f"CNPJ {emp_cnpj}"
            emp_id = f"cnpj_{emp_cnpj}" if emp_cnpj else f"emp_{emp_nome}"

            if emp_id != root_id:
                emp_sit = (emp.get('situacao_cadastral_descricao') or 'ATIVA').upper()
                is_emp_risk = enable_risk_highlight and (emp_sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'))
                emp_color = COLOR_EMPRESA_RISK if is_emp_risk else COLOR_EMPRESA_LINK
                emp_prefix = "⚠️ " if is_emp_risk else ""

                emp_tooltip = (
                    f"<b>🏢 {emp_nome}</b><br>"
                    f"CNPJ: {emp_cnpj}<br>"
                    f"Situação: {emp_sit}<br>"
                    f"Sócio em comum: {s_nome_clean}"
                )
                if is_emp_risk:
                    emp_tooltip += f"<br><font color='#D32F2F'><b>⚠️ ALERTA: Situação {emp_sit}</b></font>"

                if add_node(
                    emp_id,
                    label=f"{emp_prefix}{emp_nome[:18]}" + ("..." if len(emp_nome) > 18 else ""),
                    title=emp_tooltip,
                    color=emp_color,
                    size=24,
                    shape="dot",
                    node_type="EMPRESA",
                    raw_val=emp_cnpj,
                    cnae=emp.get('cnae_fiscal_principal') or ""
                ):
                    add_edge(s_id, emp_id, label="Participação")

    # 4. E-mails e Telefones da Raiz
    email = root_data.get('correio_eletronico')
    if email and "@" in email:
        email_clean = email.strip().lower()
        email_id = f"email_{email_clean}"
        email_tooltip = f"<b>✉️ E-mail:</b> {email_clean}"
        if add_node(
            email_id,
            label=email_clean[:22] + ("..." if len(email_clean) > 22 else ""),
            title=email_tooltip,
            color=COLOR_EMAIL,
            size=18,
            shape="diamond",
            node_type="EMAIL",
            raw_val=email_clean
        ):
            add_edge(root_id, email_id, label="e-mail")

    tel1 = f"{root_data.get('ddd1', '') or ''}{root_data.get('telefone_1', '') or ''}".strip()
    if len(tel1) > 2:
        tel_id = f"tel_{tel1}"
        tel_label = f"({tel1[:2]}) {tel1[2:]}" if len(tel1) >= 10 else tel1
        tel_tooltip = f"<b>📞 Telefone:</b> {tel_label}"
        if add_node(
            tel_id,
            label=tel_label,
            title=tel_tooltip,
            color=COLOR_TELEFONE,
            size=18,
            shape="diamond",
            node_type="TELEFONE",
            raw_val=tel1
        ):
            add_edge(root_id, tel_id, label="telefone")

    # 5. Contatos Expandidos (Itera sobre TODOS os contatos em contatos_empresas)
    for c_key, emp_list in contatos_empresas.items():
        c_str = str(c_key or "").strip()
        if not c_str:
            continue
        if "@" in c_str:
            em_clean = c_str.lower()
            em_id = f"email_{em_clean}"
            add_node(
                em_id,
                label=em_clean[:22] + ("..." if len(em_clean) > 22 else ""),
                title=f"<b>✉️ E-mail:</b> {em_clean}",
                color=COLOR_EMAIL,
                size=18,
                shape="diamond",
                node_type="EMAIL",
                raw_val=em_clean
            )
            for emp in (emp_list or []):
                emp_cnpj = emp.get('cnpj') or emp.get('cnpj_completo') or ""
                emp_nome = emp.get('razao_social') or emp.get('nome_empresarial') or emp.get('nome_fantasia') or f"CNPJ {emp_cnpj}"
                emp_id = f"cnpj_{emp_cnpj}" if emp_cnpj else f"emp_{emp_nome}"
                if emp_id != root_id:
                    emp_sit = (emp.get('situacao_cadastral_descricao') or 'ATIVA').upper()
                    is_emp_risk = enable_risk_highlight and (emp_sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'))
                    emp_color = COLOR_EMPRESA_RISK if is_emp_risk else COLOR_EMPRESA_LINK
                    emp_prefix = "⚠️ " if is_emp_risk else ""
                    emp_tooltip = f"<b>🏢 {emp_nome}</b><br>CNPJ: {emp_cnpj}<br>Mesmo e-mail: {em_clean}"
                    if add_node(
                        emp_id,
                        label=f"{emp_prefix}{emp_nome[:18]}" + ("..." if len(emp_nome) > 18 else ""),
                        title=emp_tooltip,
                        color=emp_color,
                        size=22,
                        shape="dot",
                        node_type="EMPRESA",
                        raw_val=emp_cnpj,
                        cnae=emp.get('cnae_fiscal_principal') or ""
                    ):
                        add_edge(em_id, emp_id, label="mesmo e-mail")
        else:
            digits = "".join(filter(str.isdigit, c_str))
            if len(digits) >= 8:
                tel_id = f"tel_{digits}"
                tel_label = f"({digits[:2]}) {digits[2:]}" if len(digits) >= 10 else digits
                add_node(
                    tel_id,
                    label=tel_label,
                    title=f"<b>📞 Telefone:</b> {tel_label}",
                    color=COLOR_TELEFONE,
                    size=18,
                    shape="diamond",
                    node_type="TELEFONE",
                    raw_val=digits
                )
                for emp in (emp_list or []):
                    emp_cnpj = emp.get('cnpj') or emp.get('cnpj_completo') or ""
                    emp_nome = emp.get('razao_social') or emp.get('nome_empresarial') or emp.get('nome_fantasia') or f"CNPJ {emp_cnpj}"
                    emp_id = f"cnpj_{emp_cnpj}" if emp_cnpj else f"emp_{emp_nome}"
                    if emp_id != root_id:
                        emp_sit = (emp.get('situacao_cadastral_descricao') or 'ATIVA').upper()
                        is_emp_risk = enable_risk_highlight and (emp_sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'))
                        emp_color = COLOR_EMPRESA_RISK if is_emp_risk else COLOR_EMPRESA_LINK
                        emp_prefix = "⚠️ " if is_emp_risk else ""
                        emp_tooltip = f"<b>🏢 {emp_nome}</b><br>CNPJ: {emp_cnpj}<br>Mesmo telefone: {tel_label}"
                        if add_node(
                            emp_id,
                            label=f"{emp_prefix}{emp_nome[:18]}" + ("..." if len(emp_nome) > 18 else ""),
                            title=emp_tooltip,
                            color=emp_color,
                            size=22,
                            shape="dot",
                            node_type="EMPRESA",
                            raw_val=emp_cnpj,
                            cnae=emp.get('cnae_fiscal_principal') or ""
                        ):
                            add_edge(tel_id, emp_id, label="mesmo fone")

    # 6. Endereços Compartilhados
    for addr_key, addr_info in shared_addresses.items():
        addr_id = f"addr_{addr_key}"
        label_addr = addr_info.get('label', '')
        comps = addr_info.get('companies', [])

        addr_tooltip = f"<b>📍 Endereço Compartilhado:</b><br>{label_addr}<br><b>{len(comps)} empresas vinculadas</b>"
        if add_node(
            addr_id,
            label=f"📍 {label_addr[:22]}...",
            title=addr_tooltip,
            color=COLOR_ENDERECO,
            size=22,
            shape="hexagon",
            node_type="ENDERECO",
            raw_val=addr_key
        ):
            for comp in comps:
                c_cnpj = comp.get('cnpj') or comp.get('cnpj_basico') or ''
                c_id = f"cnpj_{c_cnpj}"
                if c_id in nodes_dict:
                    add_edge(addr_id, c_id, label="mesmo endereço", custom_color=COLOR_EDGE_ENDERECO, dashes=True)

    # 7. Vínculos de Parentesco
    for fam in family_relationships:
        s_a = fam.get('socio_a', '').strip().lower()
        s_b = fam.get('socio_b', '').strip().lower()
        id_a = f"socio_{s_a}"
        id_b = f"socio_{s_b}"
        if id_a in nodes_dict and id_b in nodes_dict:
            add_edge(id_a, id_b, label="Parentesco", custom_color=COLOR_EDGE_FAMILY, dashes=True)

    # 8. Nós Manuais
    for mn in manual_nodes:
        m_id = mn.get('id')
        m_label = mn.get('label') or "Manual"
        m_type = mn.get('type', 'MANUAL_PF')
        m_doc = mn.get('doc', '')
        m_obs = mn.get('obs', '')

        is_pf = (m_type == 'MANUAL_PF')
        m_color = COLOR_MANUAL_PF if is_pf else COLOR_MANUAL_PJ
        m_shape = "star" if is_pf else "square"

        m_tooltip = (
            f"<b>⭐ Inserção Manual: {m_label}</b><br>"
            f"Tipo: {'Pessoa Física (PF)' if is_pf else 'Pessoa Jurídica (PJ)'}<br>"
            f"Documento: {m_doc or 'Não informado'}<br>"
            f"Obs: {m_obs or '-'}"
        )

        add_node(
            m_id,
            label=f"⭐ {m_label[:20]}",
            title=m_tooltip,
            color=m_color,
            size=26,
            shape=m_shape,
            node_type=m_type,
            raw_val=m_label
        )

    # 9. Vínculos Manuais
    for me in manual_edges:
        src = me.get('from')
        dst = me.get('to')
        lbl = me.get('label', 'Vínculo Manual')
        add_edge(src, dst, label=lbl, manual=True)

    # 10. Empresas Expandidas Dinamicamente (extra_companies)
    for ext_cnpj, ext_emp in extra_companies.items():
        ext_nome = ext_emp.get('nome_empresarial') or ext_emp.get('razao_social') or f"CNPJ {ext_cnpj}"
        ext_id = f"cnpj_{ext_cnpj}"
        ext_sit = (ext_emp.get('situacao_cadastral_descricao') or 'ATIVA').upper()
        is_ext_risk = enable_risk_highlight and (ext_sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'))
        ext_color = COLOR_EMPRESA_RISK if is_ext_risk else COLOR_EMPRESA_LINK
        ext_prefix = "⚠️ " if is_ext_risk else ""

        ext_tooltip = (
            f"<b>🏢 {ext_nome}</b><br>"
            f"CNPJ: {ext_cnpj}<br>"
            f"Situação: {ext_sit}<br>"
            f"CNAE: {ext_emp.get('cnae_fiscal_principal_descricao', 'N/A')}"
        )
        if is_ext_risk:
            ext_tooltip += f"<br><font color='#D32F2F'><b>⚠️ ALERTA: Situação {ext_sit}</b></font>"

        add_node(
            ext_id,
            label=f"{ext_prefix}{ext_nome[:18]}" + ("..." if len(ext_nome) > 18 else ""),
            title=ext_tooltip,
            color=ext_color,
            size=26,
            shape="dot",
            node_type="EMPRESA",
            raw_val=ext_cnpj,
            cnae=ext_emp.get('cnae_fiscal_principal') or ""
        )

        # Sócios da empresa expandida
        for es in ext_emp.get('socios', []):
            es_nome = (es.get('nome') or "").strip()
            if es_nome:
                es_id = f"socio_{es_nome.lower()}"
                es_qualif = es.get('qualificacao_descricao') or es.get('qualificacao_socio_descricao') or "Sócio"
                es_doc = es.get('cnpj_cpf') or ""
                es_tooltip = f"<b>👤 {es_nome}</b><br>Qualificação: {es_qualif}<br>Documento: {es_doc}"
                if add_node(
                    es_id,
                    label=es_nome[:18] + ("..." if len(es_nome) > 18 else ""),
                    title=es_tooltip,
                    color=COLOR_SOCIO,
                    size=21,
                    shape="dot",
                    node_type="SOCIO",
                    raw_val=es_nome
                ):
                    add_edge(ext_id, es_id, label=es_qualif[:16])

        # E-mail da empresa expandida
        ext_em = ext_emp.get('correio_eletronico')
        if ext_em and "@" in ext_em:
            em_clean = ext_em.strip().lower()
            em_id = f"email_{em_clean}"
            if add_node(em_id, label=em_clean[:20], title=f"<b>✉️ E-mail:</b> {em_clean}", color=COLOR_EMAIL, size=18, shape="diamond", node_type="EMAIL", raw_val=em_clean):
                add_edge(ext_id, em_id, label="e-mail")

        # Telefone da empresa expandida
        ext_tel = f"{ext_emp.get('ddd1', '') or ''}{ext_emp.get('telefone_1', '') or ''}".strip()
        if len(ext_tel) > 2:
            t_id = f"tel_{ext_tel}"
            tel_label = f"({ext_tel[:2]}) {ext_tel[2:]}" if len(ext_tel) >= 10 else ext_tel
            if add_node(t_id, label=tel_label, title=f"<b>📞 Telefone:</b> {tel_label}", color=COLOR_TELEFONE, size=18, shape="diamond", node_type="TELEFONE", raw_val=ext_tel):
                add_edge(ext_id, t_id, label="telefone")

    nodes_list = list(nodes_dict.values())
    available_nodes = [
        {"id": n["id"], "label": n["_raw_label"], "type": n["_type"], "val": n.get("_raw_val", n["id"])}
        for n in nodes_list
    ]
    return nodes_list, edges_list, available_nodes


def render_interactive_graph(
    root_data: dict,
    socios_empresas: dict = None,
    contatos_empresas: dict = None,
    shared_addresses: dict = None,
    family_relationships: list = None,
    ubos: list = None,
    enable_risk_highlight: bool = True,
    excluded_nodes: set = None,
    auto_filter_accountants: bool = False,
    manual_nodes: list = None,
    manual_edges: list = None,
    height: int = 850,
    extra_companies: dict = None,
    key: str = "main_interactive_graph"
) -> Tuple[Optional[Dict[str, Any]], List[Dict]]:
    """
    Renderiza o grafo interativo através do Streamlit Custom Component com suporte
    a cliques nos botões de expansão (+), exclusão (x), movimentação livre e sinalização de contadores.
    """
    nodes_list, edges_list, available_nodes = build_graph_elements(
        root_data=root_data,
        socios_empresas=socios_empresas,
        contatos_empresas=contatos_empresas,
        shared_addresses=shared_addresses,
        family_relationships=family_relationships,
        ubos=ubos,
        enable_risk_highlight=enable_risk_highlight,
        excluded_nodes=excluded_nodes,
        auto_filter_accountants=auto_filter_accountants,
        manual_nodes=manual_nodes,
        manual_edges=manual_edges,
        extra_companies=extra_companies
    )

    comp_value = _vis_graph_component(
        nodes=nodes_list,
        edges=edges_list,
        height=height,
        key=key,
        default=None
    )
    return comp_value, available_nodes


def build_graph_html(
    root_data: dict,
    socios_empresas: dict = None,
    contatos_empresas: dict = None,
    shared_addresses: dict = None,
    family_relationships: list = None,
    ubos: list = None,
    enable_risk_highlight: bool = True,
    excluded_nodes: set = None,
    auto_filter_accountants: bool = False,
    manual_nodes: list = None,
    manual_edges: list = None,
    height: str = "850px",
    extra_companies: dict = None
) -> Tuple[str, List[Dict]]:
    """
    Retorna HTML independente com Vis.js interativo (usado para exportação e fallback).
    """
    nodes_list, edges_list, available_nodes = build_graph_elements(
        root_data=root_data,
        socios_empresas=socios_empresas,
        contatos_empresas=contatos_empresas,
        shared_addresses=shared_addresses,
        family_relationships=family_relationships,
        ubos=ubos,
        enable_risk_highlight=enable_risk_highlight,
        excluded_nodes=excluded_nodes,
        auto_filter_accountants=auto_filter_accountants,
        manual_nodes=manual_nodes,
        manual_edges=manual_edges,
        extra_companies=extra_companies
    )

    nodes_json = json.dumps(nodes_list, ensure_ascii=False)
    edges_json = json.dumps(edges_list, ensure_ascii=False)

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script type="text/javascript" src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
      <style>
        body, html {{
          margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden;
          font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8f9fa;
        }}
        #network-wrapper {{ position: relative; width: 100%; height: calc(100% - 44px); }}
        #network-container {{ width: 100%; height: 100%; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #ffffff; }}
        #toolbar {{ height: 40px; padding: 2px 10px; display: flex; align-items: center; gap: 8px; background: #ffffff; border-bottom: 1px solid #e0e0e0; font-size: 12px; color: #424242; overflow-x: auto; white-space: nowrap; }}
        .btn {{ padding: 4px 10px; border: 1px solid #cfd8dc; border-radius: 4px; background-color: #ffffff; cursor: pointer; font-size: 11px; font-weight: 500; }}
        .btn:hover {{ background-color: #eceff1; }}
        .btn-danger {{ color: #c62828; border-color: #ef9a9a; }}
        .legend-item {{ display: flex; align-items: center; gap: 4px; margin-left: 4px; font-size: 11px; }}
        .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
      </style>
    </head>
    <body>
      <div id="toolbar">
        <button class="btn" onclick="network.fit({{animation: true}})">🔍 Centralizar</button>
        <button class="btn" id="physics-toggle" onclick="togglePhysics()">⏸️ Pausar Física</button>
        <button class="btn btn-danger" onclick="clearGraph()">🧹 Limpar Grafos</button>
        <button class="btn" onclick="exportImage()">📸 Exportar PNG</button>
        <span style="border-left: 1px solid #cfd8dc; height: 18px; margin: 0 2px;"></span>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_ROOT};"></span> Raiz</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_LINK};"></span> Empresa</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_RISK};"></span> ⚠️ Irregular</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_SOCIO};"></span> Sócio</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_UBO};"></span> 👑 UBO</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_CONTADOR};"></span> 🧮 Contador</div>
      </div>
      <div id="network-wrapper">
        <div id="network-container"></div>
      </div>

      <script type="text/javascript">
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});
        var container = document.getElementById('network-container');

        var options = {{
          nodes: {{ font: {{ size: 12, face: 'Roboto, Segoe UI, sans-serif' }}, borderWidth: 2, shadow: true }},
          edges: {{ smooth: {{ type: 'continuous', roundness: 0.25 }}, shadow: false }},
          physics: {{
            enabled: true,
            forceAtlas2Based: {{ gravitationalConstant: -60, centralGravity: 0.01, springLength: 130, springStrength: 0.06, damping: 0.45 }},
            solver: 'forceAtlas2Based',
            stabilization: {{ iterations: 120 }}
          }},
          interaction: {{ hover: true, tooltipDelay: 150, zoomView: true, dragNodes: true, navigationButtons: true }}
        }};

        var network = new vis.Network(container, {{nodes: nodes, edges: edges}}, options);
        var physicsEnabled = true;

        network.once('stabilizationIterationsDone', function() {{
          setTimeout(function() {{ network.fit({{animation: {{duration: 700}}}}); }}, 100);
        }});

        network.on('dragEnd', function(params) {{
          if (params.nodes && params.nodes.length > 0) {{
            params.nodes.forEach(function(nodeId) {{
              var pos = network.getPosition(nodeId);
              nodes.update({{ id: nodeId, x: pos.x, y: pos.y, fixed: {{x: true, y: true}}, physics: false }});
            }});
          }}
        }});

        function togglePhysics() {{
          physicsEnabled = !physicsEnabled;
          network.setOptions({{ physics: {{ enabled: physicsEnabled }} }});
          document.getElementById('physics-toggle').innerHTML = physicsEnabled ? '⏸️ Pausar Física' : '▶️ Ativar Física';
        }}

        function clearGraph() {{
          if (confirm("Limpar nós do grafo?")) {{ nodes.clear(); edges.clear(); }}
        }}

        function exportImage() {{
          network.fit({{ animation: false }});
          setTimeout(function() {{
            var canvas = container.getElementsByTagName('canvas')[0];
            if (canvas) {{
              var link = document.createElement('a');
              link.download = 'grafo_relacionamentos.png';
              link.href = canvas.toDataURL('image/png');
              link.click();
            }}
          }}, 300);
        }}
      </script>
    </body>
    </html>
    """
    return html_template, available_nodes