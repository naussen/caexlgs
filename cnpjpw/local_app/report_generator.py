"""
Módulo para Geração de Dossiês Consolidados em PDF (reportlab) e Excel (openpyxl).
Compila métricas de risco, quadro societário, empresas vinculadas, endereços compartilhados e anotações.
"""
import io
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def build_argumentative_dossier(
    root_data: dict,
    all_companies: list,
    socios_list: list,
    risk_info: dict,
    shared_addresses: dict,
    ubos: list,
    notes: str = ""
) -> dict:
    """
    Gera a lógica argumentativa estruturada, jurídica e pericial sobre o cluster societário.
    Articula indícios de grupo econômico de fato, confusão patrimonial, promiscuidade operacional,
    blindagem societária e requisitos para desconsideração da personalidade jurídica (Art. 50 do Código Civil).
    """
    root_name = root_data.get('nome_empresarial') or root_data.get('razao_social') or 'EMPRESA ALVO'
    root_cnpj = root_data.get('cnpj') or root_data.get('cnpj_basico') or 'CNPJ NÃO INFORMADO'
    root_sit = (root_data.get('situacao_cadastral_descricao') or root_data.get('situacao_cadastral') or 'ATIVA').upper()

    total_comps = len(all_companies)
    total_socios = len(socios_list)
    risk_level = risk_info.get('risk_level', 'BAIXO')
    risk_score = risk_info.get('risk_score', 0)

    # Beneficiários Finais (UBO)
    ubos_nomes = [u.get('nome') for u in ubos if u.get('nome')]
    ubos_str = ", ".join(ubos_nomes) if ubos_nomes else "Controle pulverizado entre os sócios diretos"

    # Sócios PJ (Holdings interpostas)
    pj_socios = []
    pf_socios = []
    for s in socios_list:
        doc = ''.join(filter(str.isdigit, str(s.get('cnpj_cpf') or s.get('cpf_cnpj') or s.get('doc') or '')))
        nome = s.get('nome') or ''
        if len(doc) == 14 or s.get('identificador_entidade_descricao') == 'PESSOA JURIDICA':
            pj_socios.append(nome)
        else:
            if nome:
                pf_socios.append(nome)

    # Empresas irregulares no cluster
    irreg_comps = []
    for c in all_companies:
        sit = str(c.get('situacao_cadastral_descricao') or c.get('situacao_cadastral') or '').upper()
        if sit in ('INAPTA', 'BAIXADA', 'SUSPENSA', 'NULA'):
            c_name = c.get('nome_empresarial') or c.get('razao_social') or c.get('cnpj') or 'Empresa'
            irreg_comps.append(f"{c_name} ({sit})")

    # Endereços compartilhados
    shared_clusters = []
    for addr_key, addr_info in shared_addresses.items():
        comps = addr_info.get('companies', [])
        lbl = addr_info.get('label') or addr_key
        if len(comps) >= 2:
            shared_clusters.append((lbl, len(comps)))

    # 1. Tese de Grupo Econômico de Fato & Unidade Gerencial
    tese_grupo = (
        f"A análise da malha societária revela a existência de um consistente Grupo Econômico de Fato "
        f"articulado em torno de {root_name} (CNPJ: {root_cnpj}), congregando um cluster com {total_comps} empresas "
        f"e {total_socios} sócios interligados. A identidade ou comunhão do núcleo diretivo e decisório "
        f"evidencia direção unificada e coordenação de interesses operacionais e financeiros comuns, "
        f"ultrapassando os limites da mera autonomia formal de cada pessoa jurídica."
    )

    # 2. Confusão Patrimonial & Promiscuidade Operacional
    if shared_clusters:
        addrs_desc = "; ".join([f"'{lbl}' ({qtd} empresas)" for lbl, qtd in shared_clusters[:3]])
        arg_promiscuidade = (
            f"Restou comprovada severa promiscuidade operacional decorrente do compartilhamento de domicílios "
            f"fiscais entre entidades teórica e formalmente distintas: foram mapeados {len(shared_clusters)} "
            f"estabelecimentos com multiplicidade de pessoas jurídicas cadastradas simultaneamente, destacando-se: {addrs_desc}. "
            f"A concentração de sedes no mesmo endereço físico sem segregação de instalações operacionais "
            f"constitui indício veemente de estabelecimentos de fachada e confusão patrimonial manifesta."
        )
    else:
        arg_promiscuidade = (
            f"As empresas mapeadas na rede apresentam ramificações operacionais distribuídas. "
            f"Recomenda-se a verificação in loco da correspondência dos endereços fáticos perante os registros cadastrais."
        )

    # 3. Engenharia de Blindagem Societária & Beneficiários Finais
    if pj_socios:
        pj_str = ", ".join(pj_socios[:3])
        arg_blindagem = (
            f"Constatou-se a utilização de estruturas societárias em cascata (interposição de pessoas jurídicas como sócias: {pj_str}), "
            f"mecanismo rotineiramente empregado como estratégia de blindagem patrimonial para criar camadas de anteparo "
            f"entre o patrimônio ativo e as pessoas naturais controladoras. No entanto, o rastreamento dos Beneficiários "
            f"Finais (UBO) demonstra que o centro de gravidade do poder decisório e econômico converge para: {ubos_str}."
        )
    else:
        arg_blindagem = (
            f"O quadro de sócios apresenta controle direto por pessoas físicas, convergindo o poder de gestão e "
            f"benefício econômico final prioritariamente para: {ubos_str}."
        )

    # 4. Assimetria Cadastral & Risco de Sucessão Fraudulenta
    if irreg_comps:
        irreg_str = "; ".join(irreg_comps[:4])
        arg_irregularidade = (
            f"Foram identificadas entidades com situação cadastral irregular no mesmo agrupamento sob a gestão "
            f"dos mesmos administradores: {irreg_str}. A coexistência de empresas inaptas ou baixadas "
            f"ao lado de pessoas jurídicas plenamente operantes e ativas sob o mesmo comando configura "
            f"clássico padrão de descarte societário de passivos ('empresa boa versus empresa podre') e "
            f"indício contundente de sucessão empresarial fraudulenta de fato."
        )
    else:
        arg_irregularidade = (
            f"Não foram detectadas baixas cadastrais compulsórias ou inaptidões no núcleo imediato; "
            f"contudo, o volume de relacionamentos e transações exige vigilância quanto à higidez fiscal."
        )

    # 5. Enquadramento Jurídico (Subsunção Legal)
    arg_juridico = (
        f"Diante do arcabouço fático apurado (Score de Risco: {risk_score} pts | Classificação: {risk_level}), "
        f"restam materializados os requisitos autorizadores da Desconsideração da Personalidade Jurídica "
        f"(Art. 50 do Código Civil, com redação da Lei 13.874/2019), especificamente a CONFUSÃO PATRIMONIAL "
        f"(§ 2º, incisos I e III) decorrente do entrelaçamento societário e operacional sem independência fática. "
        f"Subsidiariamente, incidem o Art. 28, § 2º do Código de Defesa do Consumidor (responsabilidade solidária "
        f"de grupos societários de fato) e o Art. 2º, § 2º da CLT (integração e coordenação entre pessoas jurídicas), "
        f"autorizando o redirecionamento de execuções e a constrição patrimonial de todo o conglomerado econômico."
    )

    # 6. Diligências Táticas Recomendadas
    diligencias = [
        "1. SISBAJUD (Teimosinha): Ordem de indisponibilidade de ativos financeiros de forma simultânea em face da empresa central, coligadas e administradores ocultos.",
        "2. RENAJUD & Embarcações/Aeronaves: Consulta integrada para penhora de veículos e ativos móveis de alto valor registrados em nome de qualquer entidade do grupo.",
        "3. CNIB / Cartórios de Imóveis: Expedição de ordem de indisponibilidade perante a Central de Imóveis dos municípios sede e litorâneos vinculados aos sócios.",
        "4. SIMBA / COAF: Requisição de Relatórios de Inteligência Financeira para apuração de movimentações atípicas e fluxo financeiro circular entre as contas das empresas.",
        "5. Mandado de Constatação In Loco: Diligência por Oficial de Justiça nos endereços com multiplicidade cadastral para certificar a existência real de instalações e funcionários."
    ]

    # Texto Integral Consolidado
    paragrafos = [
        f"=== PARECER TÉCNICO & SÍNTESE ARGUMENTATIVA INVESTIGATIVA ===",
        f"Alvo Central: {root_name} | CNPJ: {root_cnpj} | Situação: {root_sit}",
        f"Data da Síntese: {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        "",
        f"1. DA CARACTERIZAÇÃO DO GRUPO ECONÔMICO DE FATO E UNIDADE DE DIREÇÃO:",
        tese_grupo,
        "",
        f"2. DA PROMISCUIDADE OPERACIONAL E CONFUSÃO PATRIMONIAL:",
        arg_promiscuidade,
        "",
        f"3. DA ENGENHARIA SOCIETÁRIA DE BLINDAGEM E BENEFICIÁRIOS FINAIS (UBO):",
        arg_blindagem,
        "",
        f"4. DA ASSIMETRIA CADASTRAL E INDÍCIOS DE SUCESSÃO FRAUDULENTA:",
        arg_irregularidade,
        "",
        f"5. DO ENQUADRAMENTO JURÍDICO (ART. 50 DO CÓDIGO CIVIL E ART. 28 DO CDC):",
        arg_juridico,
        "",
        f"6. PLANO DE DILIGÊNCIAS TÁTICAS RECOMENDADAS:",
        "\n".join(diligencias)
    ]

    if notes and notes.strip():
        paragrafos.extend([
            "",
            f"7. APONTAMENTOS ESPECÍFICOS DO INVESTIGADOR:",
            notes.strip()
        ])

    texto_integral = "\n".join(paragrafos)

    return {
        "tese_grupo": tese_grupo,
        "arg_promiscuidade": arg_promiscuidade,
        "arg_blindagem": arg_blindagem,
        "arg_irregularidade": arg_irregularidade,
        "arg_juridico": arg_juridico,
        "diligencias": diligencias,
        "texto_integral": texto_integral
    }


def generate_excel_dossier(
    root_data: dict,
    all_companies: list,
    socios_list: list,
    risk_info: dict,
    shared_addresses: dict,
    ubos: list,
    manual_nodes: list,
    manual_edges: list,
    notes: str = ""
) -> bytes:
    """Gera uma pasta de trabalho Excel (.xlsx) com múltiplas abas formatadas."""
    wb = openpyxl.Workbook()
    
    # Estilos padrão
    header_fill = PatternFill(start_color="0D47A1", end_color="0D47A1", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="0D47A1")
    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=11)
    
    # ------------------ Aba 1: Resumo & Risco ------------------
    ws_resumo = wb.active
    ws_resumo.title = "Resumo Executivo"
    
    root_name = root_data.get('nome_empresarial') or root_data.get('razao_social') or ''
    root_cnpj = root_data.get('cnpj') or root_data.get('cnpj_basico') or ''

    ws_resumo.append(["DOSSIÊ DE INTELIGÊNCIA SOCIETÁRIA & COMPLIANCE"])
    ws_resumo["A1"].font = title_font
    ws_resumo.append(["Data de Emissão:", datetime.now().strftime("%d/%m/%Y %H:%M")])
    ws_resumo.append(["Empresa Central:", f"{root_name} (CNPJ: {root_cnpj})"])
    ws_resumo.append([])
    
    # Indicadores de Risco
    ws_resumo.append(["--- INDICADORES DE RISCO & CONFORMIDADE ---"])
    ws_resumo["A5"].font = bold_font
    ws_resumo.append(["Nível de Risco do Grupo:", risk_info.get('risk_level', 'BAIXO')])
    ws_resumo.append(["Score de Risco:", f"{risk_info.get('risk_score', 0)} pontos"])
    ws_resumo.append(["Situação Cadastral Central:", risk_info.get('situacao', 'ATIVA')])
    ws_resumo.append(["Empresa Recente (< 1 ano):", "Sim" if risk_info.get('is_recente') else "Não"])
    
    flags = risk_info.get('risk_flags', [])
    if flags:
        ws_resumo.append(["Alertas Detectados:"])
        for f in flags:
            ws_resumo.append(["", f"⚠️ {f}"])
    else:
        ws_resumo.append(["Alertas Detectados:", "Nenhum alerta crítico encontrado."])
        
    ws_resumo.append([])
    ws_resumo.append(["--- ANOTAÇÕES DA INVESTIGAÇÃO ---"])
    ws_resumo.append(["Notas do Analista:", notes or "Nenhuma nota inserida."])

    # ------------------ Aba 2: Empresas do Grupo ------------------
    ws_emp = wb.create_sheet(title="Empresas Vinculadas")
    headers_emp = ["CNPJ", "Razão Social", "Situação Cadastral", "CNAE Principal", "Município/UF"]
    ws_emp.append(headers_emp)
    for col_idx in range(1, len(headers_emp) + 1):
        cell = ws_emp.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        
    for emp in all_companies:
        cnpj_val = emp.get('cnpj') or emp.get('cnpj_basico') or ''
        razao = emp.get('nome_empresarial') or emp.get('razao_social') or ''
        sit = emp.get('situacao_cadastral_descricao') or 'Ativa'
        cnae = emp.get('cnae_fiscal_principal_descricao') or ''
        mun = f"{emp.get('municipio_desc', '') or ''}/{emp.get('uf', '') or ''}"
        ws_emp.append([cnpj_val, razao, sit, cnae, mun])

    # ------------------ Aba 3: Quadro de Sócios & UBO ------------------
    ws_soc = wb.create_sheet(title="Quadro Societário & UBO")
    headers_soc = ["Nome do Sócio", "Documento", "Qualificação", "Tipo Entidade", "Beneficiário Final (UBO)"]
    ws_soc.append(headers_soc)
    for col_idx in range(1, len(headers_soc) + 1):
        cell = ws_soc.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    ubo_nomes = {u.get('nome') for u in ubos}
    for s in socios_list:
        nome_s = s.get('nome') or ''
        doc_s = s.get('cnpj_cpf') or ''
        qualif_s = s.get('qualificacao_descricao') or ''
        tipo_s = s.get('identificador_entidade_descricao') or ''
        is_ubo = "Sim (UBO)" if nome_s in ubo_nomes else "Sócio Direto"
        ws_soc.append([nome_s, doc_s, qualif_s, tipo_s, is_ubo])

    # ------------------ Aba 4: Endereços Compartilhados ------------------
    ws_end = wb.create_sheet(title="Endereços Compartilhados")
    headers_end = ["Endereço Compartilhado", "Qtd Empresas", "CNPJs no Endereço"]
    ws_end.append(headers_end)
    for col_idx in range(1, len(headers_end) + 1):
        cell = ws_end.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    for addr_key, addr_info in shared_addresses.items():
        label_addr = addr_info.get('label', '')
        comps = addr_info.get('companies', [])
        cnpjs_str = ", ".join([c.get('cnpj') or c.get('cnpj_basico') or '' for c in comps])
        ws_end.append([label_addr, len(comps), cnpjs_str])

    # ------------------ Aba 5: Lógica Argumentativa ------------------
    arg_res = build_argumentative_dossier(
        root_data=root_data,
        all_companies=all_companies,
        socios_list=socios_list,
        risk_info=risk_info,
        shared_addresses=shared_addresses,
        ubos=ubos,
        notes=notes
    )

    ws_arg = wb.create_sheet(title="Lógica Argumentativa")
    headers_arg = ["Eixo Investigativo / Dimensão", "Síntese Argumentativa & Subsunção Fática", "Enquadramento Legal / Diligências"]
    ws_arg.append(headers_arg)
    for col_idx in range(1, len(headers_arg) + 1):
        cell = ws_arg.cell(row=1, column=col_idx)
        cell.fill = PatternFill(start_color="1A237E", end_color="1A237E", fill_type="solid")
        cell.font = header_font

    ws_arg.append(["1. Grupo Econômico de Fato & Unidade de Direção", arg_res.get("tese_grupo", ""), "Art. 2º, § 2º da CLT / Teoria da Unidade Econômica"])
    ws_arg.append(["2. Confusão Patrimonial & Promiscuidade", arg_res.get("arg_promiscuidade", ""), "Art. 50, § 2º, I e III do Código Civil"])
    ws_arg.append(["3. Blindagem Societária & UBO", arg_res.get("arg_blindagem", ""), "Art. 50 do CC / Rastreamento de Beneficiário Final (IN RFB 2.119/2022)"])
    ws_arg.append(["4. Assimetria Cadastral & Sucessão", arg_res.get("arg_irregularidade", ""), "Fraude contra credores / Sucessão empresarial fraudulenta de fato"])
    ws_arg.append(["5. Fundamentação Jurídica Estruturada", arg_res.get("arg_juridico", ""), "Art. 50 do CC / Art. 28 do CDC / Súmula 129 TST"])
    ws_arg.append(["6. Diligências Táticas Sugeridas", "\n".join(arg_res.get("diligencias", [])), "SISBAJUD, RENAJUD, CNIB, SIMBA e Constatação In Loco"])

    if notes and notes.strip():
        ws_arg.append(["7. Anotações Adicionais do Investigador", notes.strip(), "Parecer individualizado do analista"])

    for row in ws_arg.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    # Auto-ajuste da largura das colunas em todas as abas
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                val = str(cell.value or '')
                if len(val) > max_len:
                    max_len = len(val)
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_pdf_dossier(
    root_data: dict,
    all_companies: list[dict],
    socios_list: list[dict],
    risk_info: dict,
    shared_addresses: dict,
    ubos: list[dict],
    notes: str = ""
) -> bytes:
    """Gera um relatório formal em PDF com ReportLab."""
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0D47A1"),
        spaceAfter=6
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#546E7A"),
        spaceAfter=14
    )
    sec_style = ParagraphStyle(
        'DocSec',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1565C0"),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#212121")
    )
    alert_style = ParagraphStyle(
        'DocAlert',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#C62828"),
        bold=True
    )

    story = []

    # Cabeçalho
    story.append(Paragraph("DOSSIÊ DE INTELIGÊNCIA & COMPLIANCE SOCIETÁRIO", title_style))
    dt_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    story.append(Paragraph(f"Emitido em: {dt_str} | Análise Automatizada de Relacionamentos CNPJ", sub_style))

    # Resumo da Empresa Central
    root_name = root_data.get('nome_empresarial') or root_data.get('razao_social') or 'Empresa'
    root_cnpj = root_data.get('cnpj') or root_data.get('cnpj_basico') or ''
    sit_central = root_data.get('situacao_cadastral_descricao') or 'Ativa'
    
    info_table_data = [
        [Paragraph("<b>Empresa Central:</b>", body_style), Paragraph(root_name, body_style)],
        [Paragraph("<b>CNPJ:</b>", body_style), Paragraph(root_cnpj, body_style)],
        [Paragraph("<b>Situação Cadastral:</b>", body_style), Paragraph(sit_central, body_style)],
        [Paragraph("<b>CNAE Principal:</b>", body_style), Paragraph(root_data.get('cnae_fiscal_principal_descricao', 'N/A'), body_style)]
    ]
    t_info = Table(info_table_data, colWidths=[130, 410])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F5F7FA")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CFD8DC")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 10))

    # Box de Risco
    story.append(Paragraph("Avaliação de Risco & Conformidade", sec_style))
    risk_level = risk_info.get('risk_level', 'BAIXO')
    risk_color = colors.HexColor("#2E7D32") if risk_level == "BAIXO" else (colors.HexColor("#F57C00") if risk_level == "MÉDIO" else colors.HexColor("#C62828"))

    risk_table_data = [
        [Paragraph("<b>Nível de Risco do Grupo:</b>", body_style), Paragraph(f"<b>{risk_level}</b> ({risk_info.get('risk_score', 0)} pts)", ParagraphStyle('R', parent=body_style, textColor=risk_color))],
        [Paragraph("<b>Empresas Irregulares no Grupo:</b>", body_style), Paragraph("Identificadas" if risk_info.get('is_irregular') else "Nenhuma detectada", body_style)]
    ]
    flags = risk_info.get('risk_flags', [])
    if flags:
        for f in flags:
            risk_table_data.append([Paragraph("<b>Alerta:</b>", alert_style), Paragraph(f"⚠️ {f}", alert_style)])

    t_risk = Table(risk_table_data, colWidths=[170, 370])
    t_risk.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FFF8E1") if risk_level != "ALTO" else colors.HexColor("#FFEBEE")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#FFE082") if risk_level != "ALTO" else colors.HexColor("#FFCDD2")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_risk)
    story.append(Spacer(1, 10))

    # Seção de Lógica Argumentativa e Parecer Técnico
    arg_res = build_argumentative_dossier(
        root_data=root_data,
        all_companies=all_companies,
        socios_list=socios_list,
        risk_info=risk_info,
        shared_addresses=shared_addresses,
        ubos=ubos,
        notes=notes
    )

    story.append(Paragraph("Parecer Técnico & Lógica Argumentativa Investigativa", sec_style))
    p_arg_intro = Paragraph(
        "A presente síntese técnico-investigativa consolida os vínculos societários, domiciliares e cadastrais "
        "apurados na rede, estabelecendo a fundamentação de fato e de direito para instrução probatória, "
        "desconsideração da personalidade jurídica (Art. 50 do Código Civil) e tutela de recuperação de créditos.",
        body_style
    )
    story.append(p_arg_intro)
    story.append(Spacer(1, 6))

    arg_rows = [
        [Paragraph("<b>1. Grupo Econômico de Fato:</b>", body_style), Paragraph(arg_res.get("tese_grupo", ""), body_style)],
        [Paragraph("<b>2. Confusão Patrimonial & Domicílios:</b>", body_style), Paragraph(arg_res.get("arg_promiscuidade", ""), body_style)],
        [Paragraph("<b>3. Blindagem Societária & UBO:</b>", body_style), Paragraph(arg_res.get("arg_blindagem", ""), body_style)],
        [Paragraph("<b>4. Assimetria Cadastral & Risco:</b>", body_style), Paragraph(arg_res.get("arg_irregularidade", ""), body_style)],
        [Paragraph("<b>5. Fundamentação Jurídica:</b>", body_style), Paragraph(arg_res.get("arg_juridico", ""), body_style)],
        [Paragraph("<b>6. Diligências Sugeridas:</b>", body_style), Paragraph("<br/>".join(arg_res.get("diligencias", [])), body_style)],
    ]

    t_arg = Table(arg_rows, colWidths=[140, 400])
    t_arg.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0F4F8")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#B0BEC5")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_arg)
    story.append(Spacer(1, 10))

    # Quadro Societário
    story.append(Paragraph("Quadro Societário & Beneficiários Finais (UBO)", sec_style))
    soc_table_data = [["Nome", "Documento", "Qualificação", "Tipo"]]
    ubo_nomes = {u.get('nome') for u in ubos}

    for s in socios_list[:15]:  # Primeiros 15 para não estourar
        nome = s.get('nome') or ''
        if nome in ubo_nomes:
            nome = f"👑 {nome} (UBO)"
        soc_table_data.append([
            Paragraph(nome[:30], body_style),
            Paragraph(s.get('cnpj_cpf', '') or '-', body_style),
            Paragraph((s.get('qualificacao_descricao') or '')[:20], body_style),
            Paragraph((s.get('identificador_entidade_descricao') or '')[:15], body_style)
        ])

    t_soc = Table(soc_table_data, colWidths=[200, 100, 140, 100])
    t_soc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0D47A1")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_soc)
    story.append(Spacer(1, 10))

    # Endereços Compartilhados
    if shared_addresses:
        story.append(Paragraph("Endereços Compartilhados (Possível Cluster / Fachada)", sec_style))
        end_data = [["Endereço", "Empresas Vinculadas"]]
        for _, a_info in list(shared_addresses.items())[:5]:
            lbl = a_info.get('label', '')
            qtd = len(a_info.get('companies', []))
            end_data.append([Paragraph(lbl[:50], body_style), Paragraph(f"{qtd} empresas no mesmo local", body_style)])
        t_end = Table(end_data, colWidths=[360, 180])
        t_end.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#00838F")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t_end)
        story.append(Spacer(1, 10))

    # Notas do Analista & Parecer Pericial
    if notes:
        import html
        import re
        story.append(Paragraph("Parecer Técnico & Embasamento Investigativo", sec_style))
        story.append(Spacer(1, 4))
        for line in notes.split('\n'):
            line_str = line.strip()
            if not line_str:
                story.append(Spacer(1, 3))
                continue
            
            # Escapar caracteres HTML/XML para proteger o parser do ReportLab
            safe_text = html.escape(line_str)
            # Converter **negrito** para <b>negrito</b>
            safe_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe_text)
            
            if safe_text.startswith('#'):
                header_text = safe_text.lstrip('#').strip()
                story.append(Spacer(1, 5))
                story.append(Paragraph(f"<b>{header_text}</b>", body_style))
            elif safe_text.startswith('- ') or safe_text.startswith('* '):
                bullet_content = safe_text[2:].strip()
                story.append(Paragraph(f"&bull; {bullet_content}", body_style))
            else:
                story.append(Paragraph(safe_text, body_style))
        story.append(Spacer(1, 10))

    doc.build(story)
    return output.getvalue()
