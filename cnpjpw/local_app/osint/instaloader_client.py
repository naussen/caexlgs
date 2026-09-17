"""
Cliente para coleta de perfis públicos e postagens do Instagram via Instaloader.
Autohospedado, sem custo de API, com download de mídias e geração de metadados.
"""
import os
import re
import time
import urllib.request
from datetime import datetime
from typing import Optional, Tuple
import instaloader
# Injeta suporte a certificados do Windows se truststore estiver disponível
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .models import PerfilOSINT, PostOSINT, MidiaItem
from .storage import (
    _MEDIA_DIR,
    salvar_perfil,
    calcular_sha256_arquivo,
    ensure_storage_dirs
)


def sanitizar_username(username_ou_url: str) -> str:
    """Extrai o @username limpo a partir de texto digitado ou URL completa do Instagram."""
    u = username_ou_url.strip()
    # Se for URL: https://www.instagram.com/usuario/ ou instagram.com/p/...
    if "instagram.com" in u:
        match = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", u)
        if match:
            u = match.group(1)
    # Remove @ inicial se houver
    u = u.lstrip("@").strip().rstrip("/")
    return u


def coletar_perfil_instagram(
    alvo: str,
    max_posts: int = 6,
    download_midias: bool = True,
    sessionid: Optional[str] = None
) -> Tuple[Optional[PerfilOSINT], Optional[str]]:
    """
    Coleta os metadados de um perfil do Instagram e suas postagens recentes.
    Suporta autenticação via cookie 'sessionid' para evitar bloqueios de 401/Login da Meta.
    Salva localmente as fotos e cria registros com hash de integridade SHA-256.
    """
    ensure_storage_dirs()
    username = sanitizar_username(alvo)
    if not username:
        return None, "Nome de usuário do Instagram inválido ou vazio."

    # Configuração do Instaloader
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    # Configuração de sessão e SSL tolerante para proxies corporativos
    try:
        L.context._session.verify = False
    except Exception:
        pass

    # Injeção de sessão logada se fornecida
    if sessionid and str(sessionid).strip():
        sid_clean = str(sessionid).strip()
        L.context._session.cookies.set("sessionid", sid_clean, domain=".instagram.com")
        L.context._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "X-IG-App-ID": "936619743392459"
        })

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.ProfileNotExistsException:
        return None, f"O perfil '@{username}' não foi encontrado no Instagram."
    except instaloader.LoginRequiredException:
        return None, (
            f"O Instagram bloqueou o acesso anônimo ao perfil '@{username}'. "
            "A Meta exige login para ler perfis via API. Insira seu cookie 'sessionid' "
            "na barra de autenticação ou utilize a 'Captura Forense (Playwright)' para capturar a página diretamente."
        )
    except instaloader.ConnectionException as ce:
        ce_str = str(ce)
        if "401" in ce_str or "require_login" in ce_str or "wait a few minutes" in ce_str:
            return None, (
                f"O Instagram exigiu login para o perfil '@{username}' (Bloqueio 401 da Meta). "
                "Para coletar via Instaloader, forneça o cookie 'sessionid' de uma conta de auditoria, "
                "ou utilize a aba 'Captura Forense (Playwright)' que renderiza o navegador real sem bloqueio de API."
            )
        return None, f"Erro de conexão com o Instagram: {ce}"
    except Exception as e:
        return None, f"Falha ao consultar perfil '@{username}': {e}"

    # Salva foto do avatar
    avatar_local_path = None
    avatar_url = profile.profile_pic_url
    if avatar_url:
        try:
            avatar_filename = f"avatar_insta_{username}_{int(time.time())}.jpg"
            avatar_local_path = os.path.join(_MEDIA_DIR, avatar_filename)
            req = urllib.request.Request(avatar_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp, open(avatar_local_path, "wb") as f:
                f.write(resp.read())
        except Exception:
            avatar_local_path = None

    links = []
    if profile.external_url:
        links.append(profile.external_url)

    perfil_obj = PerfilOSINT(
        id=f"insta_{username}_{int(time.time())}",
        plataforma="instagram",
        username=username,
        url_perfil=f"https://www.instagram.com/{username}/",
        nome_exibicao=profile.full_name or "",
        bio_descricao=profile.biography or "",
        url_avatar=avatar_url,
        avatar_local=avatar_local_path,
        num_seguidores=profile.followers or 0,
        num_seguindo=profile.followees or 0,
        num_posts=profile.mediacount or 0,
        verificado=bool(profile.is_verified),
        privado=bool(profile.is_private),
        links_externos=links,
        posts_recentes=[]
    )

    # Se perfil for privado e não logado, não há como baixar os posts
    if profile.is_private:
        salvar_perfil(perfil_obj)
        return perfil_obj, "Perfil privado. Apenas dados cadastrais públicos e bio foram capturados."

    # Itera sobre os posts mais recentes
    posts_contados = 0
    try:
        for post in profile.get_posts():
            if posts_contados >= max_posts:
                break

            post_id = f"insta_post_{post.shortcode}_{int(time.time())}"
            post_url = f"https://www.instagram.com/p/{post.shortcode}/"
            post_date_str = post.date_utc.strftime("%Y-%m-%d %H:%M:%S") if post.date_utc else ""

            midias_coletadas = []

            # Baixar imagem principal do post se solicitado
            if download_midias and post.url:
                try:
                    ext = "jpg"
                    img_filename = f"post_{username}_{post.shortcode}_{posts_contados+1}.{ext}"
                    img_path = os.path.join(_MEDIA_DIR, img_filename)
                    req_img = urllib.request.Request(post.url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req_img, timeout=10) as r_img, open(img_path, "wb") as f_img:
                        f_img.write(r_img.read())

                    sha = calcular_sha256_arquivo(img_path)
                    tam = os.path.getsize(img_path)
                    midias_coletadas.append(MidiaItem(
                        tipo="video_thumb" if post.is_video else "imagem",
                        caminho_local=img_path,
                        url_origem=post.url,
                        tamanho_bytes=tam,
                        hash_sha256=sha
                    ))
                except Exception as ex_dl:
                    print(f"Erro ao baixar mídia do post {post.shortcode}: {ex_dl}")

            post_obj = PostOSINT(
                id=post_id,
                plataforma="instagram",
                url_post=post_url,
                conteudo_texto=post.caption or "",
                data_postagem=post_date_str,
                autor_username=username,
                num_likes=post.likes or 0,
                num_comentarios=post.comments or 0,
                num_compartilhamentos=0,
                midias=midias_coletadas,
                metadados={
                    "shortcode": post.shortcode,
                    "is_video": post.is_video,
                    "video_view_count": getattr(post, "video_view_count", 0)
                }
            )

            perfil_obj.posts_recentes.append(post_obj)
            posts_contados += 1
            # Pausa suave de cortesia
            time.sleep(0.5)

    except Exception as e_posts:
        print(f"Aviso ao iterar posts de @{username}: {e_posts}")

    # Salva tudo no cofre SQLite local
    salvar_perfil(perfil_obj)

    return perfil_obj, None
