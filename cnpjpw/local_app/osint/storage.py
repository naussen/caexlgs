"""
Camada de armazenamento local (SQLite + Arquivos de Mídia) para o módulo OSINT.
Garante sigilo, integridade forense (SHA-256) e histórico persistente.
"""
import os
import json
import sqlite3
import hashlib
import shutil
import zipfile
from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import PerfilOSINT, PostOSINT, MidiaItem, EvidenciaForense

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_CURRENT_DIR), "data", "osint_vault")
_DB_PATH = os.path.join(_DATA_DIR, "osint_vault.db")
_MEDIA_DIR = os.path.join(_DATA_DIR, "media")
_SNAPSHOTS_DIR = os.path.join(_DATA_DIR, "snapshots")


def ensure_storage_dirs():
    """Garante a existência das pastas necessárias para mídias e banco SQLite."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    os.makedirs(_MEDIA_DIR, exist_ok=True)
    os.makedirs(_SNAPSHOTS_DIR, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    """Retorna uma conexão com o SQLite configurado em modo WAL e tipos nativos."""
    ensure_storage_dirs()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """Inicializa as tabelas do banco de dados SQLite local."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS osint_perfis (
        id TEXT PRIMARY KEY,
        plataforma TEXT NOT NULL,
        username TEXT,
        nome_exibicao TEXT,
        bio_descricao TEXT,
        url_perfil TEXT NOT NULL,
        url_avatar TEXT,
        avatar_local TEXT,
        num_seguidores INTEGER DEFAULT 0,
        num_seguindo INTEGER DEFAULT 0,
        num_posts INTEGER DEFAULT 0,
        verificado INTEGER DEFAULT 0,
        privado INTEGER DEFAULT 0,
        links_externos TEXT,
        data_coleta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        vinculo_cnpj TEXT DEFAULT NULL,
        vinculo_cpf TEXT DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS osint_posts (
        id TEXT PRIMARY KEY,
        perfil_id TEXT,
        plataforma TEXT NOT NULL,
        url_post TEXT,
        conteudo_texto TEXT,
        data_postagem TEXT,
        autor_username TEXT,
        num_likes INTEGER DEFAULT 0,
        num_comentarios INTEGER DEFAULT 0,
        num_compartilhamentos INTEGER DEFAULT 0,
        midias_json TEXT,
        metadados_json TEXT,
        data_coleta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(perfil_id) REFERENCES osint_perfis(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS osint_evidencias (
        id TEXT PRIMARY KEY,
        url_alvo TEXT NOT NULL,
        titulo_pagina TEXT,
        texto_extraido TEXT,
        screenshot_path TEXT,
        html_snapshot_path TEXT,
        hash_sha256 TEXT NOT NULL,
        data_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        observacoes TEXT,
        metadados_json TEXT,
        vinculo_cnpj TEXT DEFAULT NULL,
        vinculo_cpf TEXT DEFAULT NULL
    );
    """)

    conn.commit()
    conn.close()


def calcular_sha256_arquivo(caminho_arquivo: str) -> str:
    """Calcula o Hash SHA-256 de um arquivo para garantir cadeia de custódia forense."""
    if not os.path.exists(caminho_arquivo):
        return ""
    hasher = hashlib.sha256()
    with open(caminho_arquivo, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def salvar_perfil(perfil: PerfilOSINT) -> bool:
    """Salva ou atualiza um perfil e seus posts no banco local."""
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO osint_perfis (
                id, plataforma, username, nome_exibicao, bio_descricao, url_perfil,
                url_avatar, avatar_local, num_seguidores, num_seguindo, num_posts,
                verificado, privado, links_externos, data_coleta, vinculo_cnpj, vinculo_cpf
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            perfil.id,
            perfil.plataforma,
            perfil.username,
            perfil.nome_exibicao,
            perfil.bio_descricao,
            perfil.url_perfil,
            perfil.url_avatar,
            perfil.avatar_local,
            perfil.num_seguidores,
            perfil.num_seguindo,
            perfil.num_posts,
            1 if perfil.verificado else 0,
            1 if perfil.privado else 0,
            json.dumps(perfil.links_externos, ensure_ascii=False),
            perfil.data_coleta,
            perfil.vinculo_cnpj,
            perfil.vinculo_cpf
        ))

        # Salva os posts associados
        for post in perfil.posts_recentes:
            midias_dict = [
                {
                    "tipo": m.tipo,
                    "caminho_local": m.caminho_local,
                    "url_origem": m.url_origem,
                    "tamanho_bytes": m.tamanho_bytes,
                    "hash_sha256": m.hash_sha256
                }
                for m in post.midias
            ]
            cursor.execute("""
                INSERT OR REPLACE INTO osint_posts (
                    id, perfil_id, plataforma, url_post, conteudo_texto, data_postagem,
                    autor_username, num_likes, num_comentarios, num_compartilhamentos,
                    midias_json, metadados_json, data_coleta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post.id,
                perfil.id,
                post.plataforma,
                post.url_post,
                post.conteudo_texto,
                post.data_postagem,
                post.autor_username or perfil.username,
                post.num_likes,
                post.num_comentarios,
                post.num_compartilhamentos,
                json.dumps(midias_dict, ensure_ascii=False),
                json.dumps(post.metadados, ensure_ascii=False),
                post.data_coleta
            ))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Erro ao salvar perfil OSINT no banco: {e}")
        return False
    finally:
        conn.close()


def salvar_evidencia(evidencia: EvidenciaForense) -> bool:
    """Salva uma captura de URL (screenshot/DOM/hash) no banco local."""
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO osint_evidencias (
                id, url_alvo, titulo_pagina, texto_extraido, screenshot_path,
                html_snapshot_path, hash_sha256, data_captura, observacoes,
                metadados_json, vinculo_cnpj, vinculo_cpf
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            evidencia.id,
            evidencia.url_alvo,
            evidencia.titulo_pagina,
            evidencia.texto_extraido,
            evidencia.screenshot_path,
            evidencia.html_snapshot_path,
            evidencia.hash_sha256,
            evidencia.data_captura,
            evidencia.observacoes,
            json.dumps(evidencia.metadados_opengraph, ensure_ascii=False),
            evidencia.vinculo_cnpj,
            evidencia.vinculo_cpf
        ))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Erro ao salvar evidência forense: {e}")
        return False
    finally:
        conn.close()


def listar_perfis(limite: int = 50) -> List[Dict[str, Any]]:
    """Retorna a lista de perfis coletados ordenados pelos mais recentes."""
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, plataforma, username, nome_exibicao, bio_descricao, url_perfil,
                   avatar_local, num_seguidores, num_seguindo, num_posts, data_coleta
            FROM osint_perfis
            ORDER BY data_coleta DESC
            LIMIT ?
        """, (limite,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def obter_perfil_completo(perfil_id: str) -> Optional[PerfilOSINT]:
    """Recupera um perfil específico e todos os seus posts salvos."""
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM osint_perfis WHERE id = ?", (perfil_id,))
        row = cursor.fetchone()
        if not row:
            return None

        links = json.loads(row["links_externos"]) if row["links_externos"] else []
        perfil = PerfilOSINT(
            id=row["id"],
            plataforma=row["plataforma"],
            username=row["username"],
            url_perfil=row["url_perfil"],
            nome_exibicao=row["nome_exibicao"] or "",
            bio_descricao=row["bio_descricao"] or "",
            url_avatar=row["url_avatar"],
            avatar_local=row["avatar_local"],
            num_seguidores=row["num_seguidores"] or 0,
            num_seguindo=row["num_seguindo"] or 0,
            num_posts=row["num_posts"] or 0,
            verificado=bool(row["verificado"]),
            privado=bool(row["privado"]),
            links_externos=links,
            data_coleta=row["data_coleta"],
            vinculo_cnpj=row["vinculo_cnpj"],
            vinculo_cpf=row["vinculo_cpf"]
        )

        cursor.execute("SELECT * FROM osint_posts WHERE perfil_id = ? ORDER BY data_postagem DESC", (perfil_id,))
        posts_rows = cursor.fetchall()
        for pr in posts_rows:
            midias_raw = json.loads(pr["midias_json"]) if pr["midias_json"] else []
            midias = [MidiaItem(**m) for m in midias_raw]
            meta = json.loads(pr["metadados_json"]) if pr["metadados_json"] else {}
            post = PostOSINT(
                id=pr["id"],
                plataforma=pr["plataforma"],
                url_post=pr["url_post"] or "",
                conteudo_texto=pr["conteudo_texto"] or "",
                data_postagem=pr["data_postagem"],
                autor_username=pr["autor_username"],
                num_likes=pr["num_likes"] or 0,
                num_comentarios=pr["num_comentarios"] or 0,
                num_compartilhamentos=pr["num_compartilhamentos"] or 0,
                midias=midias,
                metadados=meta,
                data_coleta=pr["data_coleta"]
            )
            perfil.posts_recentes.append(post)

        return perfil
    finally:
        conn.close()


def listar_evidencias(limite: int = 50) -> List[Dict[str, Any]]:
    """Retorna a lista de evidências forenses capturadas."""
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, url_alvo, titulo_pagina, texto_extraido, screenshot_path,
                   html_snapshot_path, hash_sha256, data_captura, observacoes, metadados_json
            FROM osint_evidencias
            ORDER BY data_captura DESC
            LIMIT ?
        """, (limite,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def excluir_evidencia(evidencia_id: str) -> bool:
    """Exclui o registro da evidência e apaga os arquivos de print associados."""
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT screenshot_path, html_snapshot_path FROM osint_evidencias WHERE id = ?", (evidencia_id,))
        row = cursor.fetchone()
        if row:
            for p in [row["screenshot_path"], row["html_snapshot_path"]]:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        cursor.execute("DELETE FROM osint_evidencias WHERE id = ?", (evidencia_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def excluir_perfil(perfil_id: str) -> bool:
    """Exclui o perfil, seus posts e mídias físicas salvas em disco."""
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        perfil = obter_perfil_completo(perfil_id)
        if perfil:
            if perfil.avatar_local and os.path.exists(perfil.avatar_local):
                try:
                    os.remove(perfil.avatar_local)
                except Exception:
                    pass
            for post in perfil.posts_recentes:
                for m in post.midias:
                    if m.caminho_local and os.path.exists(m.caminho_local):
                        try:
                            os.remove(m.caminho_local)
                        except Exception:
                            pass

        cursor.execute("DELETE FROM osint_posts WHERE perfil_id = ?", (perfil_id,))
        cursor.execute("DELETE FROM osint_perfis WHERE id = ?", (perfil_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def gerar_pacote_zip_perfil(perfil_id: str) -> Optional[str]:
    """Compacta todas as fotos, vídeos e metadados de um perfil em um arquivo .zip seguro."""
    perfil = obter_perfil_completo(perfil_id)
    if not perfil:
        return None

    zip_filename = f"evidencia_{perfil.plataforma}_{perfil.username}_{int(datetime.now().timestamp())}.zip"
    zip_path = os.path.join(_DATA_DIR, zip_filename)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Metadados em JSON
        resumo = {
            "plataforma": perfil.plataforma,
            "username": perfil.username,
            "nome": perfil.nome_exibicao,
            "url": perfil.url_perfil,
            "bio": perfil.bio_descricao,
            "seguidores": perfil.num_seguidores,
            "seguindo": perfil.num_seguindo,
            "data_coleta": perfil.data_coleta,
            "posts_coletados": len(perfil.posts_recentes)
        }
        zipf.writestr("metadados_perfil.json", json.dumps(resumo, indent=2, ensure_ascii=False))

        # Avatar
        if perfil.avatar_local and os.path.exists(perfil.avatar_local):
            zipf.write(perfil.avatar_local, arcname=f"avatar_{os.path.basename(perfil.avatar_local)}")

        # Mídias dos posts
        for idx, post in enumerate(perfil.posts_recentes):
            post_txt = f"URL: {post.url_post}\nData: {post.data_postagem}\nLikes: {post.num_likes}\nComentários: {post.num_comentarios}\n\nLegenda:\n{post.conteudo_texto}\n"
            zipf.writestr(f"post_{idx+1}_info.txt", post_txt)
            for m_idx, m in enumerate(post.midias):
                if m.caminho_local and os.path.exists(m.caminho_local):
                    arc = f"post_{idx+1}_midia_{m_idx+1}_{os.path.basename(m.caminho_local)}"
                    zipf.write(m.caminho_local, arcname=arc)

    return zip_path
