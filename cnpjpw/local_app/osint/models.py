"""
Modelos de dados (Dataclasses) para o módulo OSINT (Fontes Abertas & Redes Sociais).
Projetado para operar de forma autônoma e desacoplada, com suporte nativo a 
vínculos futuros (CNPJ/CPF) quando a funcionalidade for expandida.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class MidiaItem:
    """Representa um arquivo de mídia (foto, vídeo, print) baixado localmente."""
    tipo: str  # 'imagem', 'video', 'screenshot', 'html'
    caminho_local: str
    url_origem: Optional[str] = None
    tamanho_bytes: int = 0
    hash_sha256: Optional[str] = None


@dataclass
class PostOSINT:
    """Representa uma publicação/post raspada de rede social ou fórum."""
    id: str
    plataforma: str  # 'instagram', 'twitter', 'facebook', 'reddit', 'web'
    url_post: str
    conteudo_texto: str
    data_postagem: Optional[str] = None
    autor_username: Optional[str] = None
    num_likes: int = 0
    num_comentarios: int = 0
    num_compartilhamentos: int = 0
    midias: List[MidiaItem] = field(default_factory=list)
    metadados: Dict[str, Any] = field(default_factory=dict)
    data_coleta: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class PerfilOSINT:
    """Representa o perfil público de um indivíduo ou organização em rede social."""
    id: str
    plataforma: str  # 'instagram', 'twitter', 'facebook', 'linkedin', 'web'
    username: str
    url_perfil: str
    nome_exibicao: str = ""
    bio_descricao: str = ""
    url_avatar: Optional[str] = None
    avatar_local: Optional[str] = None
    num_seguidores: int = 0
    num_seguindo: int = 0
    num_posts: int = 0
    verificado: bool = False
    privado: bool = False
    links_externos: List[str] = field(default_factory=list)
    posts_recentes: List[PostOSINT] = field(default_factory=list)
    data_coleta: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    vinculo_cnpj: Optional[str] = None  # Reservado para fase futura
    vinculo_cpf: Optional[str] = None   # Reservado para fase futura


@dataclass
class EvidenciaForense:
    """Representa uma captura forense de página web/post via navegador headless."""
    id: str
    url_alvo: str
    titulo_pagina: str
    texto_extraido: str
    screenshot_path: Optional[str] = None
    html_snapshot_path: Optional[str] = None
    hash_sha256: str = ""
    data_captura: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    observacoes: str = ""
    metadados_opengraph: Dict[str, str] = field(default_factory=dict)
    vinculo_cnpj: Optional[str] = None  # Reservado para fase futura
    vinculo_cpf: Optional[str] = None   # Reservado para fase futura
