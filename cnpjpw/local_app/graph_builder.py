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
    height: str = "750px"
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

    ubo_names = {u.get('nome', '').strip().lower() for u in ubos if u.get('nome')}

    nodes_dict = {}
    edges_list = []

    def add_node(node_id: str, label: str, title: str, color: str, size: int, shape: str = "dot", node_type: str = "OUTRO", border_color: str = None):
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
                "_raw_label": label
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
        node_type="EMPRESA_ROOT"
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
            node_type="UBO" if is_ubo else "SOCIO"
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
                        node_type="EMPRESA"
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
            node_type="EMAIL"
        ):
            add_edge(root_id, email_id, label="e-mail")

            # Outras empresas ligadas pelo e-mail
            outras_email = contatos_empresas.get(email_clean, [])
            for emp in outras_email:
                emp_cnpj = emp.get('cnpj') or ""
                emp_nome = emp.get('razao_social') or emp.get('nome_fantasia') or f"CNPJ {emp_cnpj}"
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
                        node_type="EMPRESA"
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
            node_type="TELEFONE"
        ):
            add_edge(root_id, tel_id, label="telefone")

            # Outras empresas ligadas pelo telefone
            outras_tel = contatos_empresas.get(tel1, [])
            for emp in outras_tel:
                emp_cnpj = emp.get('cnpj') or ""
                emp_nome = emp.get('razao_social') or emp.get('nome_fantasia') or f"CNPJ {emp_cnpj}"
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
                        node_type="EMPRESA"
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
            node_type="ENDERECO"
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
            node_type=m_type
        )

    # 7. Vínculos Manuais
    for me in manual_edges:
        src = me.get('from')
        dst = me.get('to')
        lbl = me.get('label', 'Vínculo Manual')
        add_edge(src, dst, label=lbl, manual=True)

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
        #network-container {{
          width: 100%;
          height: calc(100% - 44px);
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          background-color: #ffffff;
        }}
        #toolbar {{
          height: 40px;
          padding: 2px 10px;
          display: flex;
          align-items: center;
          gap: 10px;
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
        <button class="btn" id="fs-toggle" onclick="toggleFullScreen()">⛶ Tela Cheia (Maximizar)</button>
        <button class="btn" onclick="network.fit({{animation: true}})">🔍 Enquadrar</button>
        <button class="btn" id="physics-toggle" onclick="togglePhysics()">⏸️ Pausar</button>
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
      <div id="network-container"></div>

      <script type="text/javascript">
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});

        var container = document.getElementById('network-container');
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
            btn.innerHTML = isFs ? '🗗 Restaurar' : '⛶ Tela Cheia (Maximizar)';
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
        {"id": n["id"], "label": n["_raw_label"], "type": n["_type"]}
        for n in nodes_dict.values()
    ]
    return html_template, available_nodes
