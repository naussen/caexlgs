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

def generate_excel_dossier(
    root_data: dict,
    all_companies: list[dict],
    socios_list: list[dict],
    risk_info: dict,
    shared_addresses: dict,
    ubos: list[dict],
    manual_nodes: list[dict],
    manual_edges: list[dict],
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

    # Notas do Analista
    if notes:
        story.append(Paragraph("Parecer & Notas do Investigador", sec_style))
        story.append(Paragraph(notes.replace('\n', '<br/>'), body_style))

    doc.build(story)
    return output.getvalue()
