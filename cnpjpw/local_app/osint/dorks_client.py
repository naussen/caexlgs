"""
Módulo de Inteligência de Fontes Abertas (OSINT) e Google X-Ray Dorking.
Especializado em mapeamento investigativo de LinkedIn, Facebook e Instagram (Menções Cruzadas).
"""
import urllib.parse
from typing import Dict, List, Any


def sanitizar_termo(termo: str) -> str:
    """Limpa e padroniza termos para operadores booleanos de busca."""
    if not termo:
        return ""
    # Remove aspas repetidas ou caracteres de quebra
    t = termo.strip().replace('"', '').replace("'", "")
    return t


def gerar_dorks_investigativas(
    nome_alvo: str = "",
    empresa: str = "",
    cnpj: str = "",
    cidade: str = "",
    uf: str = ""
) -> Dict[str, List[Dict[str, str]]]:
    """
    Gera um catálogo estruturado de Dorks investigativas categorizadas por plataforma:
    - LinkedIn (Perfis de Sócios, Executivos, Página da Empresa e Vínculos Profissionais)
    - Facebook (Páginas Comerciais, Menções a CNPJs, Perfis Pessoais e Publicações)
    - Instagram (Menções em perfis abertos, tags de terceiros e vínculos indiretos para contas fechadas)
    - Jusbrasil & Diários Oficiais (Processos, Execuções e Editais)
    """
    nome_limpo = sanitizar_termo(nome_alvo)
    empresa_limpa = sanitizar_termo(empresa)
    cnpj_limpo = ''.join(filter(str.isdigit, str(cnpj)))
    cidade_limpa = sanitizar_termo(cidade)
    uf_limpa = sanitizar_termo(uf).upper()

    dorks: Dict[str, List[Dict[str, str]]] = {
        "linkedin": [],
        "facebook": [],
        "instagram_cruzado": [],
        "juridico_oficial": []
    }

    # ==========================================
    # 1. LINKEDIN DORKS
    # ==========================================
    if nome_limpo:
        q_base = f'site:linkedin.com/in/ "{nome_limpo}"'
        dorks["linkedin"].append({
            "titulo": f"Perfil do Sócio/Alvo ({nome_limpo})",
            "descricao": "Localiza perfis pessoais de profissionais com o nome exato do investigado.",
            "query": q_base,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_base)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_base)}"
        })

        if empresa_limpa:
            q_emp = f'site:linkedin.com/in/ "{nome_limpo}" "{empresa_limpa}"'
            dorks["linkedin"].append({
                "titulo": f"Sócio vinculado à Empresa ({empresa_limpa})",
                "descricao": "Cruza a identidade do alvo diretamente com a empresa sob investigação.",
                "query": q_emp,
                "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_emp)}",
                "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_emp)}"
            })

        if cidade_limpa or uf_limpa:
            loc = f"{cidade_limpa} {uf_limpa}".strip()
            q_loc = f'site:linkedin.com/in/ "{nome_limpo}" "{loc}"'
            dorks["linkedin"].append({
                "titulo": f"Sócio por Localização Geográfica ({loc})",
                "descricao": "Refina a pesquisa filtrando pela cidade ou estado de domicílio fiscal.",
                "query": q_loc,
                "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_loc)}",
                "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_loc)}"
            })

    if empresa_limpa:
        q_comp = f'site:linkedin.com/company/ "{empresa_limpa}"'
        dorks["linkedin"].append({
            "titulo": f"Página Oficial da Empresa ({empresa_limpa})",
            "descricao": "Busca a página corporativa oficial da organização, número de funcionários e subsidiárias.",
            "query": q_comp,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_comp)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_comp)}"
        })

        q_cargos = f'site:linkedin.com/in/ ("diretor" OR "socio" OR "administrador" OR "proprietario" OR "gerente" OR "founder") "{empresa_limpa}"'
        dorks["linkedin"].append({
            "titulo": f"Quadro de Sócios e Diretores da Empresa ({empresa_limpa})",
            "descricao": "Mapeia administradores, diretores executivos e sócios ostensivos da sociedade empresária.",
            "query": q_cargos,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_cargos)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_cargos)}"
        })

    # ==========================================
    # 2. FACEBOOK DORKS
    # ==========================================
    if cnpj_limpo:
        q_fb_cnpj = f'site:facebook.com "{cnpj_limpo}"'
        dorks["facebook"].append({
            "titulo": f"Menção Direta ao CNPJ ({cnpj_limpo})",
            "descricao": "Localiza postagens, notas fiscais, páginas ou anúncios contendo o CNPJ exato.",
            "query": q_fb_cnpj,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_fb_cnpj)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_fb_cnpj)}"
        })

    if empresa_limpa:
        q_fb_emp = f'site:facebook.com "{empresa_limpa}"'
        dorks["facebook"].append({
            "titulo": f"Páginas e Publicações da Empresa ({empresa_limpa})",
            "descricao": "Varredura de páginas comerciais, grupos de consumidores e reclamações públicas.",
            "query": q_fb_emp,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_fb_emp)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_fb_emp)}"
        })

    if nome_limpo:
        q_fb_pes = f'site:facebook.com/people/ "{nome_limpo}"'
        dorks["facebook"].append({
            "titulo": f"Perfil de Usuário no Facebook ({nome_limpo})",
            "descricao": "Localiza perfis cadastrados com o nome exato da pessoa física.",
            "query": q_fb_pes,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_fb_pes)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_fb_pes)}"
        })

        if cidade_limpa or uf_limpa:
            loc = f"{cidade_limpa} {uf_limpa}".strip()
            q_fb_loc = f'site:facebook.com "{nome_limpo}" "{loc}"'
            dorks["facebook"].append({
                "titulo": f"Alvo no Facebook por Região ({loc})",
                "descricao": "Cruza o nome do alvo com o município ou estado informado.",
                "query": q_fb_loc,
                "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_fb_loc)}",
                "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_fb_loc)}"
            })

    # ==========================================
    # 3. INSTAGRAM CRUZADO (Especial para Perfis Fechados)
    # ==========================================
    if nome_limpo:
        q_ig_nome = f'site:instagram.com "{nome_limpo}"'
        dorks["instagram_cruzado"].append({
            "titulo": f"Menções e Tags ao Nome ({nome_limpo})",
            "descricao": "Localiza postagens de terceiros e perfis abertos que mencionaram o investigado no texto.",
            "query": q_ig_nome,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_ig_nome)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_ig_nome)}"
        })

    if empresa_limpa:
        q_ig_emp = f'site:instagram.com "{empresa_limpa}"'
        dorks["instagram_cruzado"].append({
            "titulo": f"Publicações Relacionadas à Empresa ({empresa_limpa})",
            "descricao": "Mapeia postagens públicas associadas ao nome da sociedade ou estabelecimento comercial.",
            "query": q_ig_emp,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_ig_emp)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_ig_emp)}"
        })

    # ==========================================
    # 4. FONTES JURÍDICAS E DIÁRIOS OFICIAIS
    # ==========================================
    alvo_termo = nome_limpo or empresa_limpa or cnpj_limpo
    if alvo_termo:
        q_jus = f'site:jusbrasil.com.br "{alvo_termo}"'
        dorks["juridico_oficial"].append({
            "titulo": f"Processos Judiciais & Diários no Jusbrasil ({alvo_termo})",
            "descricao": "Varre processos cíveis, trabalhistas, execuções fiscais e publicações em Diários de Justiça.",
            "query": q_jus,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_jus)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_jus)}"
        })

        q_dou = f'site:in.gov.br "{alvo_termo}"'
        dorks["juridico_oficial"].append({
            "titulo": f"Diário Oficial da União (DOU) ({alvo_termo})",
            "descricao": "Contratos administrativos, penalidades, portarias e atos do Poder Executivo Federal.",
            "query": q_dou,
            "google_url": f"https://www.google.com/search?q={urllib.parse.quote_plus(q_dou)}",
            "bing_url": f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_dou)}"
        })

    return dorks
