"""
Cliente de raspagem de redes e menções públicas via snscrape e buscas de fontes abertas.
Inclui compatibilidade com Python 3.13 e suporte ao repositório de certificados do Windows.
"""
import importlib.machinery
from typing import List, Tuple, Optional
from datetime import datetime
import urllib.parse
import re

# Injeta suporte a certificados do Windows se truststore estiver disponível
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

# Patch de compatibilidade do Python 3.13 para o carregador dinâmico do snscrape
if not hasattr(importlib.machinery.FileFinder, "find_module"):
    def _patch_find_module(self, fullname):
        spec = self.find_spec(fullname)
        return spec.loader if spec else None
    importlib.machinery.FileFinder.find_module = _patch_find_module

from .models import PostOSINT, MidiaItem


def pesquisar_redes_termo(
    termo: str,
    limite: int = 15,
    plataforma: str = "todas"
) -> Tuple[List[PostOSINT], Optional[str]]:
    """
    Pesquisa postagens, menções ou discussões públicas em redes abertas.
    Suporta Reddit, Telegram público e termos gerais.
    """
    termo = termo.strip()
    if not termo:
        return [], "O termo de pesquisa não pode ser vazio."

    resultados: List[PostOSINT] = []
    erros: List[str] = []

    # 1. Pesquisa no Reddit via snscrape
    if plataforma in ("todas", "reddit"):
        try:
            import snscrape.modules.reddit as snreddit
            scraper = snreddit.RedditSearchScraper(termo)
            cont = 0
            for item in scraper.get_items():
                if cont >= limite:
                    break
                
                # Campos do snscrape reddit
                post_id = f"reddit_{getattr(item, 'id', cont)}"
                url = getattr(item, 'url', '') or getattr(item, 'link', '')
                titulo = getattr(item, 'title', '')
                corpo = getattr(item, 'body', '') or getattr(item, 'selftext', '') or ""
                conteudo = f"{titulo}\n\n{corpo}".strip()
                autor = getattr(item, 'author', 'anônimo')
                dt = getattr(item, 'date', None)
                dt_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                resultados.append(PostOSINT(
                    id=post_id,
                    plataforma="reddit",
                    url_post=url,
                    conteudo_texto=conteudo,
                    data_postagem=dt_str,
                    autor_username=str(autor),
                    num_likes=getattr(item, 'score', 0) or 0,
                    num_comentarios=getattr(item, 'num_comments', 0) or 0,
                    metadados={
                        "subreddit": getattr(item, 'subreddit', ''),
                        "tipo": "post"
                    }
                ))
                cont += 1
        except Exception as e_red:
            erros.append(f"Reddit: {e_red}")

    # 2. Pesquisa no Telegram Público via snscrape
    if plataforma in ("todas", "telegram") and len(resultados) < limite:
        try:
            import snscrape.modules.telegram as sntelegram
            scraper = sntelegram.TelegramChannelScraper(termo)
            cont_tg = 0
            for item in scraper.get_items():
                if cont_tg >= (limite - len(resultados)):
                    break
                post_id = f"tg_{getattr(item, 'id', cont_tg)}"
                conteudo = getattr(item, 'content', '') or getattr(item, 'outlinks', '') or ""
                dt = getattr(item, 'date', None)
                dt_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                resultados.append(PostOSINT(
                    id=post_id,
                    plataforma="telegram",
                    url_post=getattr(item, 'url', ''),
                    conteudo_texto=str(conteudo),
                    data_postagem=dt_str,
                    autor_username=termo,
                    num_likes=0,
                    num_comentarios=0,
                    metadados={}
                ))
                cont_tg += 1
        except Exception as e_tg:
            # Não polui se não for canal válido
            pass

    msg_erro = " | ".join(erros) if erros and not resultados else None
    return resultados, msg_erro
