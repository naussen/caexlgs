"""
Módulo para geração de Grafos Interativos de Relacionamento Societário e Contatos (Vis.js).
Funcionalidades:
- Exclusão de nós (contadores / ruído de rede)
- Inserção manual de Pessoas Físicas e Jurídicas com vínculos customizados
- Destaque visual de Risco / Irregularidades Cadastrais (Inapta, Baixada, Suspensa)
- Mapeamento de Endereços Compartilhados (nós 📍)
- Destaque do Beneficiário Final (UBO 👑)
- Detecção e arestas de Parentesco / Grupos Familiares
- Ferramentas de Enquadramento, Tela Cheia (Maximizar) e Exportação PNG
"""
import json

# Cores e Estilos dos Nós
COLOR_EMPRESA_ROOT = "#0D47A1"   # Azul Royal Escuro
COLOR_EMPRESA_LINK = "#1976D2"   # Azul Médio
COLOR_EMPRESA_RISK = "#D32F2F"   # Vermelho Alerta (Inapta/Baixada/Suspensa)
COLOR_SOCIO = "#E65100"          # Laranja
COLOR_UBO = "#FBC02D"            # Dourado (Beneficiário Final)
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
    "fiscal@", "dp@", "escritorio", "cont@be", "contar", "auditoria"
]

def is_probable_accountant(label: str, title: str = "") -> bool:
    """Verifica se o nó possui termos característicos de escritório de contabilidade."""
    content = f"{label} {title}".lower()
    for termo in TERMOS_CONTABILIDADE:
        if termo in content:
            return True
    return False

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
    height: str = "750px",
    extra_companies: dict = None
) -> tuple[str, list[dict]]:
    """
    Constrói a rede e retorna o HTML com Vis.js interativo e a lista de nós gerados.
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

    def add_node(node_id: str, label: str, title: str, color: str, size: int, shape: str = "dot", node_type: str = "OUTRO", border_color: str = None, raw_val: str = ""):
        if node_id in excluded_nodes:
            return False
        if auto_filter_accountants and is_probable_accountant(label, title):
            return False
        if node_id not in nodes_dict:
            b_color = border_color or color
            nodes_dict[node_id] = {
                "id": node_id,
                "label": label,
                "title": title,
                "color": {
                    "background": color,
                    "border": b_color,
                    "highlight": {"background": "#FFEB3B", "border": "#F57F17"}
                },
                "size": size,
                "shape": shape,
                "font": {"color": "#212121", "size": 12, "face": "Roboto, Segoe UI, sans-serif"},
                "shadow": True,
                "_type": node_type,
                "_raw_label": label,
                "_raw_val": raw_val or node_id
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

    # 1. Empresa Principal
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
        raw_val=root_cnpj
    )

    # 2. Sócios e Empresas Vinculadas
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

            # Empresas do sócio (2º grau)
            empresas_do_socio = socios_empresas.get(nome_socio, [])
            for emp in empresas_do_socio:
                emp_cnpj = emp.get('cnpj') or emp.get('cnpj_completo') or ""
                emp_nome = emp.get('razao_social') or emp.get('nome_empresarial') or emp.get('nome_fantasia') or f"CNPJ {emp_cnpj}"
                emp_id = f"cnpj_{emp_cnpj}" if emp_cnpj else f"emp_{emp_nome}"

                if emp_id != root_id:
                    emp_sit = (emp.get('situacao_cadastral_descricao') or 'ATIVA').upper()
                    is_emp_risk = enable_risk_highlight and (emp_sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'))
                    emp_color = COLOR_EMPRESA_RISK if is_emp_risk else COLOR_EMPRESA_LINK
                    emp_prefix = "⚠️ " if is_emp_risk else ""

                    emp_tooltip = f"<b>🏢 {emp_nome}</b><br>CNPJ: {emp_cnpj}<br>Situação: {emp_sit}<br>Sócio em comum: {nome_socio}"
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
                        raw_val=emp_cnpj
                    ):
                        add_edge(socio_id, emp_id, label="Participação")

    # 3. E-mails e Telefones
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

            # Outras empresas ligadas pelo e-mail
            outras_email = contatos_empresas.get(email_clean, [])
            for emp in outras_email:
                emp_cnpj = emp.get('cnpj') or ""
                emp_nome = emp.get('razao_social') or emp.get('nome_empresarial') or emp.get('nome_fantasia') or f"CNPJ {emp_cnpj}"
                emp_id = f"cnpj_{emp_cnpj}" if emp_cnpj else f"emp_{emp_nome}"
                if emp_id != root_id:
                    emp_sit = (emp.get('situacao_cadastral_descricao') or 'ATIVA').upper()
                    is_emp_risk = enable_risk_highlight and (emp_sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'))
                    emp_color = COLOR_EMPRESA_RISK if is_emp_risk else COLOR_EMPRESA_LINK
                    emp_prefix = "⚠️ " if is_emp_risk else ""

                    emp_tooltip = f"<b>🏢 {emp_nome}</b><br>CNPJ: {emp_cnpj}<br>Mesmo e-mail: {email_clean}"
                    if add_node(
                        emp_id,
                        label=f"{emp_prefix}{emp_nome[:18]}" + ("..." if len(emp_nome) > 18 else ""),
                        title=emp_tooltip,
                        color=emp_color,
                        size=22,
                        shape="dot",
                        node_type="EMPRESA",
                        raw_val=emp_cnpj
                    ):
                        add_edge(email_id, emp_id, label="mesmo e-mail")

    tel1 = f"{root_data.get('ddd1', '') or ''}{root_data.get('telefone_1', '') or ''}".strip()
    if len(tel1) > 2:
        tel_id = f"tel_{tel1}"
        tel_tooltip = f"<b>📞 Telefone:</b> ({tel1[:2]}) {tel1[2:]}"
        if add_node(
            tel_id,
            label=f"({tel1[:2]}) {tel1[2:]}",
            title=tel_tooltip,
            color=COLOR_TELEFONE,
            size=18,
            shape="diamond",
            node_type="TELEFONE",
            raw_val=tel1
        ):
            add_edge(root_id, tel_id, label="telefone")

            # Outras empresas ligadas pelo telefone
            outras_tel = contatos_empresas.get(tel1, [])
            for emp in outras_tel:
                emp_cnpj = emp.get('cnpj') or ""
                emp_nome = emp.get('razao_social') or emp.get('nome_empresarial') or emp.get('nome_fantasia') or f"CNPJ {emp_cnpj}"
                emp_id = f"cnpj_{emp_cnpj}" if emp_cnpj else f"emp_{emp_nome}"
                if emp_id != root_id:
                    emp_sit = (emp.get('situacao_cadastral_descricao') or 'ATIVA').upper()
                    is_emp_risk = enable_risk_highlight and (emp_sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'))
                    emp_color = COLOR_EMPRESA_RISK if is_emp_risk else COLOR_EMPRESA_LINK
                    emp_prefix = "⚠️ " if is_emp_risk else ""

                    emp_tooltip = f"<b>🏢 {emp_nome}</b><br>CNPJ: {emp_cnpj}<br>Mesmo telefone: {tel1}"
                    if add_node(
                        emp_id,
                        label=f"{emp_prefix}{emp_nome[:18]}" + ("..." if len(emp_nome) > 18 else ""),
                        title=emp_tooltip,
                        color=emp_color,
                        size=22,
                        shape="dot",
                        node_type="EMPRESA",
                        raw_val=emp_cnpj
                    ):
                        add_edge(tel_id, emp_id, label="mesmo fone")

    # 4. Endereços Compartilhados (Mapeamento de Cluster Físico)
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

    # 5. Vínculos de Parentesco (Sobrenomes em Comum)
    for fam in family_relationships:
        s_a = fam.get('socio_a', '').strip().lower()
        s_b = fam.get('socio_b', '').strip().lower()
        id_a = f"socio_{s_a}"
        id_b = f"socio_{s_b}"
        if id_a in nodes_dict and id_b in nodes_dict:
            add_edge(id_a, id_b, label="Parentesco", custom_color=COLOR_EDGE_FAMILY, dashes=True)

    # 6. Nós Manuais
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

    # 7. Vínculos Manuais
    for me in manual_edges:
        src = me.get('from')
        dst = me.get('to')
        lbl = me.get('label', 'Vínculo Manual')
        add_edge(src, dst, label=lbl, manual=True)

    # 8. Empresas Expandidas Dinamicamente (extra_companies)
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
            raw_val=ext_cnpj
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
            if add_node(t_id, label=f"({ext_tel[:2]}) {ext_tel[2:]}", title=f"<b>📞 Telefone:</b> {ext_tel}", color=COLOR_TELEFONE, size=18, shape="diamond", node_type="TELEFONE", raw_val=ext_tel):
                add_edge(ext_id, t_id, label="telefone")

    # Serialização para o template Vis.js
    nodes_json = json.dumps(list(nodes_dict.values()), ensure_ascii=False)
    edges_json = json.dumps(edges_list, ensure_ascii=False)

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
      <style>
        body, html {{
          margin: 0;
          padding: 0;
          width: 100%;
          height: 100%;
          overflow: hidden;
          font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: #f8f9fa;
        }}
        #network-wrapper {{
          position: relative;
          width: 100%;
          height: calc(100% - 44px);
        }}
        #network-container {{
          width: 100%;
          height: 100%;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          background-color: #ffffff;
        }}
        #node-actions-menu {{
          display: none;
          position: absolute;
          gap: 5px;
          align-items: center;
          background: rgba(255, 255, 255, 0.96);
          padding: 3px 6px;
          border-radius: 16px;
          box-shadow: 0 3px 10px rgba(0,0,0,0.3);
          border: 1px solid #b0bec5;
          z-index: 1000;
          user-select: none;
        }}
        .node-action-btn {{
          width: 22px;
          height: 22px;
          border-radius: 50%;
          border: none;
          font-family: Arial, sans-serif;
          font-weight: 900;
          line-height: 22px;
          text-align: center;
          cursor: pointer;
          padding: 0;
          transition: transform 0.15s ease, background-color 0.15s ease;
        }}
        .btn-expand {{
          background-color: #2e7d32;
          color: #ffffff;
          font-size: 14px;
        }}
        .btn-expand:hover {{
          transform: scale(1.22);
          background-color: #1b5e20;
        }}
        .btn-delete {{
          background-color: #d32f2f;
          color: #ffffff;
          font-size: 11px;
        }}
        .btn-delete:hover {{
          transform: scale(1.22);
          background-color: #b71c1c;
        }}
        #toolbar {{
          height: 40px;
          padding: 2px 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          background: #ffffff;
          border-bottom: 1px solid #e0e0e0;
          font-size: 12px;
          color: #424242;
          overflow-x: auto;
          white-space: nowrap;
        }}
        .btn {{
          padding: 4px 10px;
          border: 1px solid #cfd8dc;
          border-radius: 4px;
          background-color: #ffffff;
          cursor: pointer;
          font-size: 11px;
          font-weight: 500;
          transition: background-color 0.15s;
        }}
        .btn:hover {{
          background-color: #eceff1;
        }}
        .btn-danger {{
          color: #c62828;
          border-color: #ef9a9a;
        }}
        .btn-danger:hover {{
          background-color: #ffebee;
        }}
        .legend-item {{
          display: flex;
          align-items: center;
          gap: 4px;
          margin-left: 4px;
          font-size: 11px;
        }}
        .dot {{
          width: 10px;
          height: 10px;
          border-radius: 50%;
          display: inline-block;
        }}
      </style>
    </head>
    <body>
      <div id="toolbar">
        <button class="btn" id="fs-toggle" onclick="toggleFullScreen()">⛶ Maximizar</button>
        <button class="btn" onclick="network.fit({{animation: true}})">🔍 Enquadrar</button>
        <button class="btn" id="physics-toggle" onclick="togglePhysics()">⏸️ Pausar</button>
        <button class="btn btn-danger" onclick="clearGraph()">🧹 Limpar Grafos</button>
        <button class="btn" onclick="exportImage()">📸 Exportar PNG</button>
        <span style="border-left: 1px solid #cfd8dc; height: 18px; margin: 0 2px;"></span>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_ROOT};"></span> Central</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_LINK};"></span> Outra Empresa</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMPRESA_RISK};"></span> ⚠️ Irregular</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_SOCIO};"></span> Sócio</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_UBO};"></span> 👑 UBO</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_ENDERECO};"></span> 📍 Endereço</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_EMAIL};"></span> E-mail</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_TELEFONE};"></span> Fone</div>
        <div class="legend-item"><span class="dot" style="background-color: {COLOR_MANUAL_PF};"></span> Manual</div>
        <div class="legend-item"><span style="display:inline-block; width:12px; border-top: 2px dashed {COLOR_EDGE_MANUAL};"></span> Vínculo Manual</div>
        <div class="legend-item"><span style="display:inline-block; width:12px; border-top: 2px dashed {COLOR_EDGE_FAMILY};"></span> Parentesco</div>
      </div>
      <div id="network-wrapper">
        <div id="network-container"></div>
        <div id="node-actions-menu">
          <button id="node-expand-btn" class="node-action-btn btn-expand" title="Expandir relações desta entidade (+)">✚</button>
          <button id="node-delete-btn" class="node-action-btn btn-delete" title="Excluir este nó da visualização (✕)">✕</button>
        </div>
      </div>

      <script type="text/javascript">
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});

        var container = document.getElementById('network-container');
        var actionMenu = document.getElementById('node-actions-menu');
        var expandBtn = document.getElementById('node-expand-btn');
        var delBtn = document.getElementById('node-delete-btn');
        var activeTargetNode = null;
        var hideTimeout = null;
        var isMouseOverMenu = false;

        var data = {{
          nodes: nodes,
          edges: edges
        }};
        var options = {{
          nodes: {{
            font: {{ size: 12, face: 'Roboto, Segoe UI, sans-serif' }},
            borderWidth: 2,
            shadow: true
          }},
          edges: {{
            smooth: {{ type: 'continuous', roundness: 0.25 }},
            shadow: false
          }},
          physics: {{
            enabled: true,
            forceAtlas2Based: {{
              gravitationalConstant: -65,
              centralGravity: 0.012,
              springLength: 130,
              springStrength: 0.07,
              damping: 0.45
            }},
            solver: 'forceAtlas2Based',
            stabilization: {{ iterations: 120 }}
          }},
          interaction: {{
            hover: true,
            tooltipDelay: 150,
            zoomView: true,
            dragNodes: true,
            navigationButtons: true
          }}
        }};

        var network = new vis.Network(container, data, options);
        var physicsEnabled = true;

        function updateActionMenuPosition(nodeId) {{
          try {{
            var pos = network.getPosition(nodeId);
            var domPos = network.canvasToDOM(pos);
            actionMenu.style.left = (domPos.x - 24) + 'px';
            actionMenu.style.top = (domPos.y - 34) + 'px';
            actionMenu.style.display = 'flex';
          }} catch (e) {{
            actionMenu.style.display = 'none';
          }}
        }}

        network.on('hoverNode', function(params) {{
          clearTimeout(hideTimeout);
          activeTargetNode = params.node;
          updateActionMenuPosition(params.node);
        }});

        network.on('blurNode', function(params) {{
          hideTimeout = setTimeout(function() {{
            if (!isMouseOverMenu) {{
              actionMenu.style.display = 'none';
              activeTargetNode = null;
            }}
          }}, 450);
        }});

        network.on('selectNode', function(params) {{
          if (params.nodes.length > 0) {{
            clearTimeout(hideTimeout);
            activeTargetNode = params.nodes[0];
            updateActionMenuPosition(activeTargetNode);
          }}
        }});

        network.on('deselectNode', function() {{
          actionMenu.style.display = 'none';
          activeTargetNode = null;
        }});

        network.on('dragging', function() {{
          if (activeTargetNode) updateActionMenuPosition(activeTargetNode);
        }});

        network.on('zoom', function() {{
          if (activeTargetNode) updateActionMenuPosition(activeTargetNode);
        }});

        actionMenu.addEventListener('mouseenter', function() {{
          isMouseOverMenu = true;
          clearTimeout(hideTimeout);
        }});

        actionMenu.addEventListener('mouseleave', function() {{
          isMouseOverMenu = false;
          actionMenu.style.display = 'none';
          activeTargetNode = null;
        }});

        expandBtn.addEventListener('click', function(e) {{
          e.stopPropagation();
          if (activeTargetNode) {{
            var nodeObj = nodes.get(activeTargetNode);
            if (nodeObj) {{
              var nType = nodeObj._type || 'OUTRO';
              var nVal = nodeObj._raw_val || nodeObj.id;
              var nLabel = nodeObj.label || nodeObj._raw_label || nVal;
              
              try {{
                var pLoc = window.parent.location;
                var cleanHref = pLoc.href.split('?')[0];
                pLoc.href = cleanHref + '?expand_type=' + encodeURIComponent(nType) + '&expand_val=' + encodeURIComponent(nVal) + '&expand_label=' + encodeURIComponent(nLabel);
              }} catch(err) {{
                window.parent.postMessage({{
                  type: 'streamlit:expand',
                  nodeType: nType,
                  nodeVal: nVal,
                  nodeLabel: nLabel
                }}, '*');
              }}
            }}
            actionMenu.style.display = 'none';
            activeTargetNode = null;
          }}
        }});

        delBtn.addEventListener('click', function(e) {{
          e.stopPropagation();
          if (activeTargetNode) {{
            nodes.remove(activeTargetNode);
            actionMenu.style.display = 'none';
            activeTargetNode = null;
          }}
        }});

        // Teclas Delete e Backspace para remoção de nós selecionados
        document.addEventListener('keydown', function(e) {{
          if (e.key === 'Delete' || e.key === 'Backspace') {{
            var sel = network.getSelectedNodes();
            if (sel && sel.length > 0) {{
              nodes.remove(sel);
              actionMenu.style.display = 'none';
              activeTargetNode = null;
            }}
          }}
        }});

        function clearGraph() {{
          if (confirm("Deseja realmente limpar todos os nós do grafo visual?")) {{
            nodes.clear();
            edges.clear();
            if (actionMenu) actionMenu.style.display = 'none';
          }}
        }}

        function togglePhysics() {{
          physicsEnabled = !physicsEnabled;
          network.setOptions({{ physics: {{ enabled: physicsEnabled }} }});
          var btn = document.getElementById('physics-toggle');
          btn.innerHTML = physicsEnabled ? '⏸️ Pausar' : '▶️ Ativar';
        }}

        function toggleFullScreen() {{
          var elem = document.documentElement;
          if (!document.fullscreenElement && !document.webkitFullscreenElement) {{
            if (elem.requestFullscreen) {{
              elem.requestFullscreen();
            }} else if (elem.webkitRequestFullscreen) {{
              elem.webkitRequestFullscreen();
            }}
          }} else {{
            if (document.exitFullscreen) {{
              document.exitFullscreen();
            }} else if (document.webkitExitFullscreen) {{
              document.webkitExitFullscreen();
            }}
          }}
        }}

        function handleFsChange() {{
          var isFs = !!(document.fullscreenElement || document.webkitFullscreenElement);
          var btn = document.getElementById('fs-toggle');
          if (btn) {{
            btn.innerHTML = isFs ? '🗗 Restaurar' : '⛶ Maximizar';
          }}
          setTimeout(function() {{
            network.fit({{ animation: true }});
          }}, 300);
        }}

        document.addEventListener('fullscreenchange', handleFsChange);
        document.addEventListener('webkitfullscreenchange', handleFsChange);

        function exportImage() {{
          network.fit({{
            animation: false
          }});
          setTimeout(function() {{
            var canvas = container.getElementsByTagName('canvas')[0];
            if (canvas) {{
              var link = document.createElement('a');
              link.download = 'grafo_relacionamentos.png';
              link.href = canvas.toDataURL('image/png');
              link.click();
            }}
          }}, 400);
        }}
      </script>
    </body>
    </html>
    """
    
    available_nodes = [
        {"id": n["id"], "label": n["_raw_label"], "type": n["_type"], "val": n.get("_raw_val", n["id"])}
        for n in nodes_dict.values()
    ]
    return html_template, available_nodes
