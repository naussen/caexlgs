"""
Pacote OSINT (Open Source Intelligence & Fontes Abertas) do POMELO / CAEXLGS.
Ferramentas autohospedadas sem custo de API: Instaloader, snscrape e Playwright Headless.
"""
from .models import PerfilOSINT, PostOSINT, MidiaItem, EvidenciaForense
from .storage import (
    init_db,
    salvar_perfil,
    salvar_evidencia,
    listar_perfis,
    obter_perfil_completo,
    listar_evidencias,
    excluir_perfil,
    excluir_evidencia,
    gerar_pacote_zip_perfil,
    calcular_sha256_arquivo
)
from .instaloader_client import coletar_perfil_instagram, sanitizar_username
from .playwright_client import capturar_evidencia_url
from .snscrape_client import pesquisar_redes_termo
from .osint_service import (
    coletar_instagram,
    capturar_url_forense,
    pesquisar_mencoes,
    listar_perfis_salvos,
    obter_perfil,
    listar_evidencias_salvas,
    gerar_pacote_zip,
    gerar_dossie_pdf_evidencia,
    gerar_dorks_investigativas
)
from .ui import render_osint_screen

__all__ = [
    "render_osint_screen",
    "PerfilOSINT",
    "PostOSINT",
    "MidiaItem",
    "EvidenciaForense",
    "init_db",
    "salvar_perfil",
    "salvar_evidencia",
    "listar_perfis",
    "obter_perfil_completo",
    "listar_evidencias",
    "excluir_perfil",
    "excluir_evidencia",
    "gerar_pacote_zip_perfil",
    "calcular_sha256_arquivo",
    "coletar_perfil_instagram",
    "sanitizar_username",
    "capturar_evidencia_url",
    "pesquisar_redes_termo",
    "coletar_instagram",
    "capturar_url_forense",
    "pesquisar_mencoes",
    "listar_perfis_salvos",
    "obter_perfil",
    "listar_evidencias_salvas",
    "gerar_pacote_zip",
    "gerar_dossie_pdf_evidencia"
]
