"""
Cliente Playwright Headless para Captura Forense de URLs, Renderização DOM e Extração de Texto.
Executa emulando navegador moderno (Chrome/Edge do sistema), sem necessidade de APIs ou proxies pagos.
"""
import os
import re
import time
from typing import Optional, Tuple, Dict
from playwright.sync_api import sync_playwright
from .models import EvidenciaForense
from .storage import (
    _MEDIA_DIR,
    _SNAPSHOTS_DIR,
    salvar_evidencia,
    calcular_sha256_arquivo,
    ensure_storage_dirs
)


def _obter_canal_navegador() -> Optional[str]:
    """Detecta se Chrome ou Edge estão instalados no sistema operacional."""
    import shutil
    if shutil.which("chrome") or os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe") or os.path.exists(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        return "chrome"
    if shutil.which("msedge") or os.path.exists(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") or os.path.exists(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        return "msedge"
    return None


def capturar_evidencia_url(
    url: str,
    full_page: bool = True,
    wait_seconds: int = 2,
    observacoes: str = ""
) -> Tuple[Optional[EvidenciaForense], Optional[str]]:
    """
    Renderiza uma URL via navegador headless, grava um screenshot de prova forense,
    extrai o texto limpo, metadados OpenGraph e gera o hash criptográfico SHA-256.
    """
    ensure_storage_dirs()

    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    timestamp_id = int(time.time() * 1000)
    evidencia_id = f"evid_{timestamp_id}"
    screenshot_file = f"screenshot_{timestamp_id}.png"
    snapshot_html_file = f"dom_{timestamp_id}.html"

    screenshot_path = os.path.join(_MEDIA_DIR, screenshot_file)
    html_path = os.path.join(_SNAPSHOTS_DIR, snapshot_html_file)

    canal = _obter_canal_navegador()

    try:
        with sync_playwright() as p:
            # Lança navegador com o canal disponível (Chrome do sistema por padrão)
            launch_args = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            }
            if canal:
                launch_args["channel"] = canal

            browser = p.chromium.launch(**launch_args)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="pt-BR"
            )
            page = context.new_page()

            # Navega até a página
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e_nav:
                # Se falhar domcontentloaded estrito, tenta prosseguir se algo foi renderizado
                pass

            # Aguarda carregamento de scripts dinâmicos
            if wait_seconds > 0:
                page.wait_for_timeout(wait_seconds * 1000)

            # Título da página
            titulo = page.title() or "Página sem título"

            # Extração de Metadados OpenGraph / Meta tags
            og_meta: Dict[str, str] = {}
            try:
                metas = page.query_selector_all("meta")
                for m in metas:
                    prop = m.get_attribute("property") or m.get_attribute("name") or ""
                    content = m.get_attribute("content") or ""
                    if prop and content:
                        prop_lower = prop.lower()
                        if prop_lower.startswith("og:") or prop_lower.startswith("twitter:") or prop_lower in ("description", "author", "keywords"):
                            og_meta[prop] = content
            except Exception:
                pass

            # Extração de Texto Limpo do Corpo
            texto_extraido = ""
            try:
                body = page.query_selector("body")
                if body:
                    texto_extraido = body.inner_text()
                    # Normaliza quebras de linha excessivas
                    texto_extraido = re.sub(r"\n{3,}", "\n\n", texto_extraido).strip()
            except Exception:
                texto_extraido = ""

            # Captura de Screenshot Forense
            try:
                page.screenshot(path=screenshot_path, full_page=full_page)
            except Exception as e_shot:
                # Fallback para viewport simples se full_page falhar
                try:
                    page.screenshot(path=screenshot_path, full_page=False)
                except Exception:
                    screenshot_path = None

            # Snapshot do HTML
            try:
                html_content = page.content()
                with open(html_path, "w", encoding="utf-8") as f_html:
                    f_html.write(html_content)
            except Exception:
                html_path = None

            browser.close()

    except Exception as e_browser:
        return None, f"Erro ao executar navegador headless: {e_browser}"

    # Calcula Hash SHA-256 do arquivo de screenshot para garantia de custódia
    sha256_hash = ""
    if screenshot_path and os.path.exists(screenshot_path):
        sha256_hash = calcular_sha256_arquivo(screenshot_path)
    elif html_path and os.path.exists(html_path):
        sha256_hash = calcular_sha256_arquivo(html_path)

    evidencia = EvidenciaForense(
        id=evidencia_id,
        url_alvo=url,
        titulo_pagina=titulo,
        texto_extraido=texto_extraido,
        screenshot_path=screenshot_path,
        html_snapshot_path=html_path,
        hash_sha256=sha256_hash,
        observacoes=observacoes,
        metadados_opengraph=og_meta
    )

    salvar_evidencia(evidencia)

    return evidencia, None
