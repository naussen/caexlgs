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


def _obter_canal_ou_executavel() -> Tuple[Optional[str], Optional[str]]:
    """
    Detecta navegador Chrome/Chromium no sistema operacional (Linux e Windows).
    Retorna (canal, caminho_executavel).
    """
    import shutil

    # 1. Caminhos explícitos comuns no Linux / Debian / Docker
    linux_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium"
    ]
    for lp in linux_paths:
        if os.path.exists(lp):
            return None, lp

    # 2. Caminhos comuns no Windows
    win_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    for wp in win_paths:
        if os.path.exists(wp):
            return None, wp

    # 3. Verificação no PATH via shutil.which
    for b in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        w = shutil.which(b)
        if w:
            return None, w

    for b in ("msedge", "edge"):
        w = shutil.which(b)
        if w:
            return "msedge", None

    return None, None


def _ensure_playwright_chromium_installed() -> bool:
    """Executa 'playwright install chromium' programaticamente caso o binário esteja ausente."""
    import sys
    import subprocess
    try:
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return proc.returncode == 0
    except Exception:
        return False


def _capturar_evidencia_http_fallback(
    url: str,
    timestamp_id: int,
    observacoes: str = ""
) -> Tuple[Optional[EvidenciaForense], Optional[str]]:
    """
    Fallback resiliente: baixa o DOM completo via HTTP, extrai metadados OpenGraph,
    título e texto puro, calcula hash SHA-256 e gera a evidência forense.
    """
    import urllib.request
    from urllib.parse import urlparse

    html_path = os.path.join(_SNAPSHOTS_DIR, f"dom_{timestamp_id}.html")
    evidencia_id = f"evid_{timestamp_id}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_html = resp.read()
            html_text = raw_html.decode("utf-8", errors="replace")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_text)

        # Extração básica de título
        titulo = ""
        m_title = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        if m_title:
            titulo = m_title.group(1).strip()
        if not titulo:
            titulo = urlparse(url).netloc or "Evidência Web Capturada"

        # Extração de meta tags e OpenGraph
        og_meta = {}
        for m in re.finditer(r'<meta\s+[^>]*?(?:property|name)=["\']([^"\']+)["\'][^>]*?content=["\']([^"\']*)["\']', html_text, re.IGNORECASE):
            k, v = m.group(1).lower(), m.group(2)
            if k.startswith("og:") or k.startswith("twitter:") or k in ("description", "author", "keywords"):
                og_meta[k] = v

        # Limpeza simples de tags HTML para texto
        texto_limpo = re.sub(r"<script[^>]*>.*?</script>", " ", html_text, flags=re.DOTALL | re.IGNORECASE)
        texto_limpo = re.sub(r"<style[^>]*>.*?</style>", " ", texto_limpo, flags=re.DOTALL | re.IGNORECASE)
        texto_limpo = re.sub(r"<[^>]+>", " ", texto_limpo)
        texto_limpo = re.sub(r"\s+", " ", texto_limpo).strip()

        sha256_hash = calcular_sha256_arquivo(html_path)

        obs_completa = (observacoes + " [Modo Fallback HTTP: Snapshot DOM & Metadados Forenses]").strip()

        evidencia = EvidenciaForense(
            id=evidencia_id,
            url_alvo=url,
            titulo_pagina=titulo,
            texto_extraido=texto_limpo[:10000],
            screenshot_path=None,
            html_snapshot_path=html_path,
            hash_sha256=sha256_hash,
            observacoes=obs_completa,
            metadados_opengraph=og_meta
        )
        salvar_evidencia(evidencia)
        return evidencia, None
    except Exception as e_http:
        return None, f"Erro ao capturar URL via Playwright e Fallback HTTP: {e_http}"


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

    canal, exec_path = _obter_canal_ou_executavel()

    try:
        with sync_playwright() as p:
            launch_args = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            }
            if exec_path:
                launch_args["executable_path"] = exec_path
            elif canal:
                launch_args["channel"] = canal

            browser = None
            try:
                browser = p.chromium.launch(**launch_args)
            except Exception as e_launch:
                err_str = str(e_launch)
                if "Executable doesn't exist" in err_str or "playwright install" in err_str or "launch" in err_str:
                    installed = _ensure_playwright_chromium_installed()
                    if installed:
                        try:
                            clean_args = dict(launch_args)
                            clean_args.pop("channel", None)
                            clean_args.pop("executable_path", None)
                            browser = p.chromium.launch(**clean_args)
                        except Exception:
                            browser = None

            if not browser:
                return _capturar_evidencia_http_fallback(url, timestamp_id, observacoes=observacoes)

            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="pt-BR"
            )
            page = context.new_page()

            # Navega até a página
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
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
                    texto_extraido = re.sub(r"\n{3,}", "\n\n", texto_extraido).strip()
            except Exception:
                texto_extraido = ""

            # Captura de Screenshot Forense
            try:
                page.screenshot(path=screenshot_path, full_page=full_page)
            except Exception:
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

    except Exception:
        # Em caso de qualquer falha no Playwright, executa fallback gracioso
        return _capturar_evidencia_http_fallback(url, timestamp_id, observacoes=observacoes)

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
