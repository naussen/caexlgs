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
import re
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

# CNAEs específicos de contabilidade e perícia contábil (Divisão 69.20)
CNAES_CONTABILIDADE = {"6920601", "6920602", "69206"}

# Termos inequívocos de contabilidade (palavras inteiras ou prefixos estritamente contábeis)
TERMOS_CONTABILIDADE_EXATOS = [
    r"\bcont[aá]b\w*",                                  # contábil, contabilidade, contabilista, contabeis, etc.
    r"\bcontador\w*",                                  # contador, contadora, contadores, contadoras
    r"\bper[ií]c(?:ia|ias)\s+cont[aá]b\w*",             # perícia contábil
    r"\bperit[oa]s?\s+cont[aá]b\w*",                   # perito contábil
    r"\bauditoria\s+(?:cont[aá]b\w*|fiscal|tribut[aá]ri\w*)", # auditoria contábil/fiscal/tributária
    r"\bassessoria\s+(?:cont[aá]b\w*|fiscal|tribut[aá]ri\w*)", # assessoria contábil/fiscal
    r"\bconsultoria\s+(?:cont[aá]b\w*|fiscal|tribut[aá]ri\w*)", # consultoria contábil/fiscal
    r"\bescrit[oó]rio\s+(?:cont[aá]b\w*|de\s+contabilidade)", # escritório contábil
    r"\bservi[cç]os?\s+(?:cont[aá]b\w*|de\s+contabilidade)",  # serviços contábeis
    r"\bcontabilidade\b",
]

# E-mails corporativos contábeis
EMAILS_CONTABILIDADE = [
    r"@.*contab",
    r"contabil(?:idade)?@",
    r"fiscal@.*contab",
]

# Termos que desqualificam categoricamente como contador (falsos positivos comuns como esportes, advocacia, medicina, marketing, etc.)
TERMOS_DESCLASSIFICADORES = [
    r"\bsport\w*", r"\besport\w*", r"\batlet\w*", r"\bfutebol\b", r"\bfitness\b", r"\bgym\b",
    r"\badvoc\w*", r"\badvogad\w*", r"\bjur[ií]dic\w*", r"\boab\b",
    r"\bm[eé]dic\w*", r"\bsa[uú]de\b", r"\bhospital\w*", r"\bcl[ií]nic\w*", r"\bodonto\w*", r"\bfarm[aá]c\w*",
    r"\bimobili[aá]r\w*", r"\bcorretor\w*", r"\bim[oó]ve\w*",
    r"\bviagen\w*", r"\bturism\w*", r"\bhotel\w*", r"\bpousada\w*",
    r"\bimprensa\b", r"\bcomunica[cç][aã]o\b", r"\bmarketing\b", r"\bpublicidade\b", r"\bpropaganda\b",
    r"\bseguran[cç]a\b", r"\bvigil[aâ]ncia\b", r"\blimpeza\b",
    r"\btransporte\w*", r"\blog[ií]stic\w*", r"\bfrete\w*",
    r"\bengenh\w*", r"\barquitet\w*", r"\bconstru[cç][aã]o\b", r"\bobras\b",
    r"\btecnologia\b", r"\bsoftware\b", r"\bsistemas\b", r"\binform[aá]tic\w*",
    r"\brestaurante\w*", r"\bbar\b", r"\blanchonete\w*", r"\baliment\w*",
    r"\bcom[eé]rcio\s+varejista\b", r"\bve[ií]culos\b", r"\bauto\b", r"\boficina\b"
]

def is_probable_accountant(label: str = "", title: str = "", cnae: str = "") -> bool:
    """
    Verifica se a entidade é com alta probabilidade um contador ou escritório de contabilidade.
    Elimina falsos positivos filtrando setores não relacionados e exigindo correlação estrita.
    """
    content = f"{label} {title}".lower()

    # 1. Validação estrita por CNAE oficial (6920-6/01 ou 6920-6/02)
    cnae_clean = re.sub(r"[^\d]", "", str(cnae or "").strip())
    if cnae_clean in CNAES_CONTABILIDADE or any(cnae_clean.startswith(c) for c in ("6920601", "6920602")):
        return True

    # 2. Se possuir termo desclassificador explícito (ex: 'sports', 'médica', 'advocacia'),
    # somente será contador se houver menção inequívoca a contabilidade/contador
    tem_desclassificador = any(re.search(pat, content, re.IGNORECASE) for pat in TERMOS_DESCLASSIFICADORES)
    if tem_desclassificador:
        if not re.search(r"\b(?:contabilidade|contador|contadora|contadores)\b", content, re.IGNORECASE):
            return False

    # 3. Validação por termos de contabilidade com regex
    for pat in TERMOS_CONTABILIDADE_EXATOS:
        if re.search(pat, content, re.IGNORECASE):
            return True

    # 4. Validação por emails contábeis
    for pat in EMAILS_CONTABILIDADE:
        if re.search(pat, content, re.IGNORECASE):
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
    extra_companies: dict = None,
    judicial_nodes: list = None,
    judicial_edges: list = None,
    false_positive_accountants: set = None,
    manual_accountants: set = None
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Processa todos os dados e constrói as listas de nós e arestas para a rede.
    Retorna (nodes_list, edges_list, available_nodes).
    """
    if not root_data:
        return [], [], []

    if excluded_nodes is None:
        excluded_nodes = set()
    if false_positive_accountants is None:
        false_positive_accountants = set()
    if manual_accountants is None:
        manual_accountants = set()
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

        # Verificação e Sinalização de CONTADOR (com tratamento explícito de falso positivo pelo analista)
        if false_positive_accountants and (node_id in false_positive_accountants or raw_val in false_positive_accountants):
            is_acct = False
        elif manual_accountants and (node_id in manual_accountants or raw_val in manual_accountants):
            is_acct = True
        else:
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

    # 11. Processos Judiciais Integrados (DataJud & DJEN)
    if judicial_nodes:
        for jn in judicial_nodes:
            if jn.get("id") not in excluded_nodes:
                nodes_dict[jn["id"]] = {
                    "id": jn["id"],
                    "label": jn.get("label", ""),
                    "title": jn.get("title", ""),
                    "shape": jn.get("shape", "box"),
                    "margin": jn.get("margin", 8),
                    "color": jn.get("color", {"background": "#F3E5F5", "border": "#4A148C"}),
                    "font": jn.get("font", {"size": 11, "color": "#1A237E", "bold": True}),
                    "borderWidth": jn.get("borderWidth", 2),
                    "_type": "PROCESSO",
                    "_raw_label": jn.get("label", ""),
                    "_raw_val": jn.get("id", "")
                }
    if judicial_edges:
        for je in judicial_edges:
            edges_list.append(je)

    nodes_list = list(nodes_dict.values())
    available_nodes = [
        {
            "id": n["id"],
            "label": n["_raw_label"],
            "display_label": n.get("label", n["_raw_label"]),
            "type": n["_type"],
            "val": n.get("_raw_val", n["id"]),
            "is_accountant": n.get("_is_accountant", False)
        }
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
    key: str = "main_interactive_graph",
    judicial_nodes: list = None,
    judicial_edges: list = None
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
        extra_companies=extra_companies,
        judicial_nodes=judicial_nodes,
        judicial_edges=judicial_edges
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
    extra_companies: dict = None,
    judicial_nodes: list = None,
    judicial_edges: list = None,
    false_positive_accountants: set = None,
    manual_accountants: set = None
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
        extra_companies=extra_companies,
        judicial_nodes=judicial_nodes,
        judicial_edges=judicial_edges,
        false_positive_accountants=false_positive_accountants,
        manual_accountants=manual_accountants
    )

    if not nodes_list:
        return (
            f'<div style="display:flex;align-items:center;justify-content:center;height:{height};background:#f8f9fa;border:1px dashed #cfd8dc;border-radius:8px;color:#78909c;font-family:sans-serif;">'
            '<p>ℹ️ Nenhum dado cadastral disponível para gerar o grafo de rede.</p>'
            '</div>',
            []
        )

    nodes_json = json.dumps(nodes_list, ensure_ascii=False)
    edges_json = json.dumps(edges_list, ensure_ascii=False)

    num_nos = len(nodes_list)
    num_arestas = len(edges_list)

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>POMELO Network Graph</title>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js"></script>
      <script>
        if (typeof vis === 'undefined') {{
          document.write('<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"><\\/script>');
        }}
      </script>
      <style>
        * {{ box-sizing: border-box; }}
        body, html {{
          margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: #f8f9fa;
        }}
        #root-graph {{
          display: flex; flex-direction: column; width: 100%; height: 100%;
          border: 1px solid #cfd8dc; border-radius: 8px; background: #ffffff; overflow: hidden;
        }}
        #toolbar {{
          background: #ffffff; border-bottom: 1px solid #e0e0e0; padding: 6px 12px;
          display: flex; align-items: center; gap: 8px; flex-wrap: wrap; z-index: 10;
          box-shadow: 0 1px 3px rgba(0,0,0,0.05); font-size: 12px; color: #37474f;
        }}
        .btn {{
          padding: 4px 10px; border: 1px solid #cfd8dc; border-radius: 6px;
          background-color: #ffffff; color: #37474f; cursor: pointer;
          font-size: 11px; font-weight: 500; display: inline-flex; align-items: center; gap: 4px;
          transition: all 0.15s ease; user-select: none;
        }}
        .btn:hover {{ background-color: #eceff1; border-color: #b0bec5; }}
        .btn-active {{ background-color: #e8f5e9; border-color: #a5d6a7; color: #1b5e20; font-weight: 600; }}
        .toolbar-divider {{ height: 18px; width: 1px; background-color: #cfd8dc; margin: 0 2px; }}
        .legend-bar {{ display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-left: auto; font-size: 11px; color: #546e7a; }}
        .legend-item {{ display: inline-flex; align-items: center; gap: 4px; }}
        .dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
        .status-pill {{ font-size: 11px; font-weight: 600; color: #1565c0; background: #e3f2fd; padding: 2px 8px; border-radius: 12px; }}
        #network-wrapper {{ position: relative; flex: 1; width: 100%; height: calc(100% - 42px); }}
        #network-container {{ width: 100%; height: 100%; }}
        #quick-hint {{
          position: absolute; bottom: 8px; left: 10px; background: rgba(255,255,255,0.92);
          padding: 3px 8px; border-radius: 4px; font-size: 11px; color: #607d8b; border: 1px solid #e0e0e0;
          pointer-events: none; z-index: 5;
        }}
      </style>
    </head>
    <body>
      <div id="root-graph">
        <div id="toolbar">
          <button class="btn" onclick="autoCenter(50)" title="Centralizar e ajustar a escala da visualização">🔍 Centralizar</button>
          <button class="btn" id="btn-physics" onclick="togglePhysics()" title="Pausar ou reativar movimentação física">⏸️ Pausar Física</button>
          <button class="btn" id="btn-contadores" onclick="toggleAccountants()" title="Ocultar ou exibir nós de contabilidade">🧮 Ocultar Contadores</button>
          <button class="btn" onclick="toggleFullScreen()" title="Alternar modo tela cheia">⛶ Tela Cheia</button>
          <button class="btn" onclick="exportImage()" title="Salvar imagem PNG da rede">📸 Salvar PNG</button>
          <span class="status-pill">📊 {num_nos} entidades | {num_arestas} conexões</span>

          <div class="toolbar-divider"></div>

          <div class="legend-bar">
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_ROOT};"></span> Raiz</div>
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_LINK};"></span> Empresa</div>
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_RISK};"></span> ⚠️ Irregular</div>
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_SOCIO};"></span> Sócio</div>
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_UBO};"></span> 👑 UBO</div>
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_CONTADOR}; border: 1px solid {COLOR_CONTADOR_BORDER};"></span> 🧮 Contador</div>
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMAIL};"></span> E-mail</div>
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_TELEFONE};"></span> Telefone</div>
            <div class="legend-item"><span class="dot" style="background-color: {COLOR_ENDERECO};"></span> 📍 Endereço</div>
          </div>
        </div>

        <div id="network-wrapper">
          <div id="network-container"></div>
          <div id="quick-hint">💡 Arraste os nós para organizar livremente (eles permanecem onde você soltar). Dê scroll para zoom.</div>
        </div>
      </div>

      <script type="text/javascript">
        var nodesData = {nodes_json};
        var edgesData = {edges_json};

        var nodes = new vis.DataSet(nodesData);
        var edges = new vis.DataSet(edgesData);
        var container = document.getElementById('network-container');

        var options = {{
          nodes: {{
            font: {{ size: 12, face: 'Roboto, Segoe UI, sans-serif', color: '#263238' }},
            borderWidth: 2,
            shadow: true
          }},
          edges: {{
            smooth: {{ type: 'continuous', roundness: 0.25 }},
            shadow: false,
            color: {{ color: '#90A4AE', highlight: '#0D47A1' }}
          }},
          physics: {{
            enabled: true,
            barnesHut: {{
              gravitationalConstant: -1800,
              centralGravity: 0.25,
              springLength: 95,
              springConstant: 0.04,
              damping: 0.25,
              avoidOverlap: 0.2
            }},
            solver: 'barnesHut',
            stabilization: {{
              enabled: true,
              iterations: 60,
              updateInterval: 15,
              fit: true
            }}
          }},
          interaction: {{
            hover: true,
            tooltipDelay: 100,
            zoomView: true,
            dragNodes: true,
            dragView: true,
            navigationButtons: true,
            keyboard: false
          }}
        }};

        var network = new vis.Network(container, {{ nodes: nodes, edges: edges }}, options);
        var physicsActive = true;
        var accountantsHidden = false;

        // Estabilização inicial com auto-enquadramento e congelamento suave para 0% de CPU
        network.once('stabilizationIterationsDone', function() {{
          network.fit({{ animation: {{ duration: 400, easingFunction: 'easeInOutQuad' }} }});
          setTimeout(function() {{
            network.setOptions({{ physics: {{ enabled: false }} }});
            physicsActive = false;
            var pBtn = document.getElementById('btn-physics');
            if (pBtn) pBtn.innerHTML = '▶️ Ativar Física';
          }}, 600);
        }});

        // Movimentação livre: fixa permanentemente a coordenada onde o usuário soltar o nó
        network.on('dragEnd', function(params) {{
          if (params.nodes && params.nodes.length > 0) {{
            params.nodes.forEach(function(nodeId) {{
              var pos = network.getPosition(nodeId);
              nodes.update({{ id: nodeId, x: pos.x, y: pos.y, fixed: {{ x: true, y: true }}, physics: false }});
            }});
          }}
        }});

        function autoCenter(delay) {{
          setTimeout(function() {{
            if (network) {{
              network.fit({{ animation: {{ duration: 500, easingFunction: 'easeInOutQuad' }} }});
            }}
          }}, delay || 50);
        }}

        function togglePhysics() {{
          physicsActive = !physicsActive;
          network.setOptions({{ physics: {{ enabled: physicsActive }} }});
          var btn = document.getElementById('btn-physics');
          if (btn) {{
            btn.innerHTML = physicsActive ? '⏸️ Pausar Física' : '▶️ Ativar Física';
            btn.classList.toggle('btn-active', physicsActive);
          }}
        }}

        function toggleAccountants() {{
          accountantsHidden = !accountantsHidden;
          var btn = document.getElementById('btn-contadores');
          if (btn) {{
            btn.innerHTML = accountantsHidden ? '🧮 Exibir Contadores' : '🧮 Ocultar Contadores';
            btn.classList.toggle('btn-active', accountantsHidden);
          }}
          var updates = [];
          nodes.forEach(function(n) {{
            if (n._is_accountant || n.node_type === 'CONTADOR') {{
              updates.push({{ id: n.id, hidden: accountantsHidden }});
            }}
          }});
          nodes.update(updates);
          autoCenter(100);
        }}

        function toggleFullScreen() {{
          var elem = document.getElementById('root-graph');
          if (!document.fullscreenElement && !document.webkitFullscreenElement) {{
            if (elem.requestFullscreen) elem.requestFullscreen();
            else if (elem.webkitRequestFullscreen) elem.webkitRequestFullscreen();
          }} else {{
            if (document.exitFullscreen) document.exitFullscreen();
            else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
          }}
          autoCenter(200);
        }}

        function exportImage() {{
          network.fit({{ animation: false }});
          setTimeout(function() {{
            var canvas = container.getElementsByTagName('canvas')[0];
            if (canvas) {{
              var link = document.createElement('a');
              link.download = 'grafo_relacionamentos_pomelo.png';
              link.href = canvas.toDataURL('image/png');
              link.click();
            }}
          }}, 250);
        }}
      </script>
    </body>
    </html>
    """
    return html_template, available_nodes