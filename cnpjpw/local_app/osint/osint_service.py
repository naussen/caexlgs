"""
Orquestrador central do módulo OSINT (Fontes Abertas & Redes Sociais).
Centraliza chamadas dos coletores, persistência forense e relatórios.
"""
import os
import time
from typing import List, Optional, Tuple, Dict, Any
from .models import PerfilOSINT, PostOSINT, EvidenciaForense
from .storage import (
    listar_perfis,
    obter_perfil_completo,
    listar_evidencias,
    excluir_perfil as _storage_excluir_perfil,
    excluir_evidencia as _storage_excluir_evidencia,
    gerar_pacote_zip_perfil,
    _DATA_DIR
)
from .instaloader_client import coletar_perfil_instagram
from .playwright_client import capturar_evidencia_url
from .snscrape_client import pesquisar_redes_termo


def coletar_instagram(
    alvo: str,
    max_posts: int = 6,
    download_midias: bool = True
) -> Tuple[Optional[PerfilOSINT], Optional[str]]:
    """Executa a coleta de perfil e mídias públicas do Instagram."""
    return coletar_perfil_instagram(alvo, max_posts=max_posts, download_midias=download_midias)


def capturar_url_forense(
    url: str,
    full_page: bool = True,
    wait_seconds: int = 2,
    observacoes: str = ""
) -> Tuple[Optional[EvidenciaForense], Optional[str]]:
    """Renderiza a URL no navegador headless, salva screenshot, DOM e hash SHA-256."""
    return capturar_evidencia_url(url, full_page=full_page, wait_seconds=wait_seconds, observacoes=observacoes)


def pesquisar_mencoes(
    termo: str,
    limite: int = 15,
    plataforma: str = "todas"
) -> Tuple[List[PostOSINT], Optional[str]]:
    """Pesquisa menções e discussões públicas em fóruns e redes abertas."""
    return pesquisar_redes_termo(termo, limite=limite, plataforma=plataforma)


def listar_perfis_salvos(limite: int = 50) -> List[Dict[str, Any]]:
    """Retorna histórico de perfis coletados."""
    return listar_perfis(limite=limite)


def obter_perfil(perfil_id: str) -> Optional[PerfilOSINT]:
    """Retorna dados completos de um perfil salvo."""
    return obter_perfil_completo(perfil_id)


def listar_evidencias_salvas(limite: int = 50) -> List[Dict[str, Any]]:
    """Retorna lista de evidências forenses capturadas."""
    return listar_evidencias(limite=limite)


def excluir_perfil(perfil_id: str) -> bool:
    """Exclui perfil e seus arquivos associados."""
    return _storage_excluir_perfil(perfil_id)


def excluir_evidencia(evidencia_id: str) -> bool:
    """Exclui evidência forense e seus prints associados."""
    return _storage_excluir_evidencia(evidencia_id)


def gerar_pacote_zip(perfil_id: str) -> Optional[str]:
    """Gera pacote zip de mídias e metadados do perfil."""
    return gerar_pacote_zip_perfil(perfil_id)


def gerar_dossie_pdf_evidencia(evidencia: EvidenciaForense) -> Optional[str]:
    """
    Gera um relatório forense em PDF contendo o print capturado, hash SHA-256,
    data/hora da captura e metadados OpenGraph.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        pdf_filename = f"dossie_forense_{evidencia.id}.pdf"
        pdf_path = os.path.join(_DATA_DIR, pdf_filename)

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=10
        )
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor('#333333')
        )
        hash_style = ParagraphStyle(
            'HashStyle',
            parent=styles['Code'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#b71c1c')
        )

        elements = []

        # Cabeçalho
        elements.append(Paragraph("🛡️ POMELO — Laudo de Captura Forense Digital (OSINT)", title_style))
        elements.append(Spacer(1, 10))

        # Tabela de Metadados Forenses
        tabela_dados = [
            [Paragraph("<b>URL Alvo:</b>", meta_style), Paragraph(evidencia.url_alvo, meta_style)],
            [Paragraph("<b>Título da Página:</b>", meta_style), Paragraph(evidencia.titulo_pagina or "Não informado", meta_style)],
            [Paragraph("<b>Data/Hora da Captura:</b>", meta_style), Paragraph(evidencia.data_captura, meta_style)],
            [Paragraph("<b>Hash de Integridade (SHA-256):</b>", meta_style), Paragraph(evidencia.hash_sha256 or "N/A", hash_style)],
            [Paragraph("<b>Observações:</b>", meta_style), Paragraph(evidencia.observacoes or "Sem observações adicionais.", meta_style)]
        ]

        t = Table(tabela_dados, colWidths=[160, 380])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))

        # Imagem do Screenshot
        if evidencia.screenshot_path and os.path.exists(evidencia.screenshot_path):
            elements.append(Paragraph("<b>Registro Visual / Screenshot da Evidência:</b>", meta_style))
            elements.append(Spacer(1, 6))
            try:
                # Ajusta tamanho para caber na página
                img = RLImage(evidencia.screenshot_path, width=540, height=360)
                elements.append(img)
            except Exception as e_img:
                elements.append(Paragraph(f"[Não foi possível renderizar a imagem no PDF: {e_img}]", meta_style))

        # Texto Extraído (trecho inicial)
        if evidencia.texto_extraido:
            elements.append(Spacer(1, 15))
            elements.append(Paragraph("<b>Conteúdo Textual Identificado (Amostra Inicial):</b>", meta_style))
            elements.append(Spacer(1, 6))
            trecho = evidencia.texto_extraido[:800] + ("..." if len(evidencia.texto_extraido) > 800 else "")
            trecho_escaped = trecho.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
            elements.append(Paragraph(trecho_escaped, meta_style))

        doc.build(elements)
        return pdf_path
    except Exception as e:
        print(f"Erro ao gerar PDF da evidência: {e}")
        return None
