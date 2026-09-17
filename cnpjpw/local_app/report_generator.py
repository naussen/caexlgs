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

    # 1. Inferência de Coordenação e Hipótese de Grupo Econômico
    tese_grupo = (
        f"A correlação da malha societária indica a conformação relacional de grupo econômico "
        f"em torno de {root_name} (CNPJ: {root_cnpj}), integrando {total_comps} pessoas jurídicas "
        f"e {total_socios} pessoas físicas/jurídicas qualificadas no QSA. A identidade quantitativa de integrantes do corpo "
        f"diretivo subsidia a inferência técnica de coordenação administrativa e comunhão de interesses operacionais, "
        f"constituindo hipótese investigativa de atuação sob direção comum."
    )

    # 2. Correlação Espacial de Domicílios Fiscais
    if shared_clusters:
        addrs_desc = "; ".join([f"Logradouro '{lbl}' com registro simultâneo de {qtd} CNPJs" for lbl, qtd in shared_clusters[:3]])
        arg_promiscuidade = (
            f"Registrou-se a coincidência de domicílio fiscal entre entidades formalmente autônomas: "
            f"constam {len(shared_clusters)} estabelecimentos com multiplicidade cadastral de 2 ou mais pessoas jurídicas, "
            f"destacando-se: {addrs_desc}. A sobreposição cadastral de múltiplos CNPJs no mesmo espaço geográfico, "
            f"sem evidência registral de segregação de instalações físicas, subsidia a suposição técnica de confusão patrimonial "
            f"e compartilhamento operacional, a ser constatada in loco."
        )
    else:
        arg_promiscuidade = (
            f"As pessoas jurídicas mapeadas na malha societária possuem endereços cadastrais formalmente distintos. "
            f"Sugere-se averiguação da correspondência empírica das sedes frente aos registros perante os órgãos fazendários."
        )

    # 3. Estruturação em Camadas & Beneficiários Finais (UBO)
    if pj_socios:
        pj_str = ", ".join(pj_socios[:3])
        arg_blindagem = (
            f"Constatou-se a interposição de {len(pj_socios)} pessoa(s) jurídica(s) na composição do QSA ({pj_str}). "
            f"A análise da cadeia de controle societário aponta a convergência da titularidade econômica final (UBO) para: {ubos_str}. "
            f"A presença de camadas societárias intermediárias fundamenta a inferência técnica de fracionamento de titularidade, "
            f"demandando apuração da linha direta de benefício econômico."
        )
    else:
        arg_blindagem = (
            f"O quadro de sócios apresenta controle direto por pessoas físicas, convergindo a administração formal e o "
            f"benefício econômico prioritariamente para: {ubos_str}."
        )

    # 4. Correlação Temporal e Cadastral
    if irreg_comps:
        irreg_str = "; ".join(irreg_comps[:4])
        arg_irregularidade = (
            f"Mapeou-se a coexistência de {len(irreg_comps)} entidade(s) com situação cadastral inativa, suspensa ou baixada correlacionadas aos mesmos administradores: {irreg_str}. "
            f"A concomitância temporal entre cadastros baixados/inaptos e empresas plenamente ativas sob a mesma gestão "
            f"fundamenta a hipótese investigativa de descontinuidade seletiva de passivos e sucessão de fato para apuração probatória."
        )
    else:
        arg_irregularidade = (
            f"Não foram identificadas baixas compulsórias ou declarações de inaptidão no núcleo sob análise. "
            f"Mantém-se a regularidade cadastral formal aparente perante a administração tributária."
        )

    # 5. Hipótese de Subsunção Normativa (Enquadramento Técnico)
    arg_juridico = (
        f"A correlação dos indicadores quantitativos apurados (Score de Risco: {risk_score} pts | Classificação: {risk_level} | "
        f"{total_comps} sociedades correlacionadas | {total_socios} integrantes no QSA) fornece substrato empírico "
        f"para a formulação da hipótese de incidência do Art. 50 do Código Civil (com redação dada pela Lei 13.874/2019), "
        f"especificamente sob a modalidade de confusão patrimonial (§ 2º, incisos I e III), amparada na convergência de domicílios e gestão. "
        f"Subsidia-se, outrossim, o enquadramento hipotético de grupo de fato com esteio no Art. 28, § 2º do CDC, "
        f"Art. 14 da Lei 12.846/2013 e instauração do Incidente de Desconsideração da Personalidade Jurídica (CPC, arts. 133 a 137)."
    )

    # 6. Diligências Pragmáticas Sugeridas
    diligencias = [
        "1. Constatação Física In Loco: Expedição de mandado de constatação nos endereços de multiplicidade cadastral para quantificar instalações físicas, maquinário e quadro de funcionários.",
        "2. Requisição de Vínculos Financeiros (SISBAJUD): Pesquisa quantitativa de relacionamento de contas correntes e aplicações em nome das pessoas jurídicas e dos gestores mapeados.",
        "3. Rastreamento Patrimonial de Bens Móveis e Imóveis (RENAJUD / CNIB): Consulta de ativos registrados em nome de cada entidade componente do agrupamento sob investigação.",
        "4. Fluxo de Movimentação Financeira (SIMBA/COAF): Apuração técnica de eventual trânsito circular de recursos financeiros entre as pessoas jurídicas correlacionadas.",
        "5. Intimação Contábil-Fiscal: Solicitação dos livros contábeis (ECD/ECF) para verificação documental de mútuos intercompany e segregação patrimonial."
    ]

    # Texto Integral Consolidado
    paragrafos = [
        f"=== LAUDO TÉCNICO-INVESTIGATIVO & SÍNTESE RELACIONAL ===",
        f"Alvo Central: {root_name} | CNPJ: {root_cnpj} | Situação Cadastral: {root_sit}",
        f"Data da Síntese: {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        "",
        f"1. DA CORRELAÇÃO DE SOCIEDADES E HIPÓTESE DE GRUPO ECONÔMICO:",
        tese_grupo,
        "",
        f"2. DA SOBREPOSIÇÃO DE DOMICÍLIOS FISCAIS E CONFUSÃO PATRIMONIAL HIPOTÉTICA:",
        arg_promiscuidade,
        "",
        f"3. DA ESTRUTURAÇÃO EM CAMADAS E BENEFICIÁRIOS FINAIS (UBO):",
        arg_blindagem,
        "",
        f"4. DA ASSIMETRIA TEMPORAL E CORRELAÇÕES CADASTRAIS:",
        arg_irregularidade,
        "",
        f"5. DO ENQUADRAMENTO TÉCNICO-NORMATIVO HIPOTÉTICO (ART. 50 CC E CORRELATOS):",
        arg_juridico,
        "",
        f"6. PLANO DE DILIGÊNCIAS PRAGMÁTICAS RECOMENDADAS:",
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

    ws_arg.append(["1. Coordenação e Grupo Econômico Hipotético", arg_res.get("tese_grupo", ""), "Art. 2º, § 2º da CLT / Art. 265 da Lei 6.404/76"])
    ws_arg.append(["2. Coincidência Espacial de Domicílios Fiscais", arg_res.get("arg_promiscuidade", ""), "Art. 50, § 2º, I e III do Código Civil / Confusão Patrimonial"])
    ws_arg.append(["3. Estruturação em Camadas e UBO", arg_res.get("arg_blindagem", ""), "Art. 50 do CC / Rastreamento de Beneficiário Final (IN RFB 2.119/2022)"])
    ws_arg.append(["4. Correlação Temporal e Assimetria Cadastral", arg_res.get("arg_irregularidade", ""), "Hipótese de sucessão empresarial de fato / Art. 1.146 do CC"])
    ws_arg.append(["5. Subsunção Normativa Hipotética", arg_res.get("arg_juridico", ""), "Art. 50 do CC / Art. 28 do CDC / CPC arts. 133 a 137"])
    ws_arg.append(["6. Diligências Pragmáticas Recomendadas", "\n".join(arg_res.get("diligencias", [])), "Constatação In Loco, SISBAJUD, RENAJUD, CNIB e SIMBA"])

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

    story.append(Paragraph("Síntese Técnico-Pericial & Inferências Investigativas", sec_style))
    p_arg_intro = Paragraph(
        "A presente síntese técnico-investigativa consolida correlações cadastrais, societárias e espaciais "
        "apuradas na rede de relacionamentos, estruturando hipóteses fáticas para instrução probatória "
        "e eventual subsunção às hipóteses normativas do Art. 50 do Código Civil e medidas de constrição patrimonial.",
        body_style
    )
    story.append(p_arg_intro)
    story.append(Spacer(1, 6))

    arg_rows = [
        [Paragraph("<b>1. Coordenação & Grupo Econômico:</b>", body_style), Paragraph(arg_res.get("tese_grupo", ""), body_style)],
        [Paragraph("<b>2. Coincidência Espacial de Domicílios:</b>", body_style), Paragraph(arg_res.get("arg_promiscuidade", ""), body_style)],
        [Paragraph("<b>3. Estruturação em Camadas & UBO:</b>", body_style), Paragraph(arg_res.get("arg_blindagem", ""), body_style)],
        [Paragraph("<b>4. Correlação Temporal & Cadastral:</b>", body_style), Paragraph(arg_res.get("arg_irregularidade", ""), body_style)],
        [Paragraph("<b>5. Subsunção Normativa Hipotética:</b>", body_style), Paragraph(arg_res.get("arg_juridico", ""), body_style)],
        [Paragraph("<b>6. Diligências Pragmáticas Sugeridas:</b>", body_style), Paragraph("<br/>".join(arg_res.get("diligencias", [])), body_style)],
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
