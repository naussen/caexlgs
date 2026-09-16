"""
data_service.py — Camada Unificada de Dados e Fallback do POMELO (Fase 5).

Centraliza o acesso a dados cadastrais, societários e de contatos em uma única camada de serviço,
garantindo transparência sobre a origem da consulta (BigQuery, API Local ou API Pública),
executando fallback resiliente e padronizando a estrutura de retorno:

{
    "results": [...] ou {...},
    "source": "BIGQUERY" | "LOCAL_API" | "PUBLIC_API",
    "error": None | str,
    "fallback_used": bool
}
"""

import os
from typing import Dict, Any, List, Optional, Union

try:
    import api_client
    import bigquery_client
    import sanitizers
except ImportError:
    from cnpjpw.local_app import api_client, bigquery_client, sanitizers

SOURCE_BIGQUERY = "BIGQUERY"
SOURCE_LOCAL_API = "LOCAL_API"
SOURCE_PUBLIC_API = "PUBLIC_API"


class QueryResult(dict):
    """
    Estrutura padronizada de resposta de consultas conforme Fase 5.
    Acesso direto por chave (ex: res['results'], res['source'])
    e propriedades convenientes.
    """
    def __init__(
        self,
        results: Union[List[Dict[str, Any]], Dict[str, Any], None],
        source: str,
        error: Optional[str] = None,
        fallback_used: bool = False
    ):
        super().__init__(
            results=results if results is not None else ([] if source != SOURCE_BIGQUERY or not isinstance(results, dict) else None),
            source=source,
            error=error,
            fallback_used=fallback_used
        )

    @property
    def results(self) -> Union[List[Dict[str, Any]], Dict[str, Any], None]:
        return self.get("results")

    @property
    def data(self) -> Union[List[Dict[str, Any]], Dict[str, Any], None]:
        return self.get("results")

    @property
    def source(self) -> str:
        return self.get("source", SOURCE_PUBLIC_API)

    @property
    def error(self) -> Optional[str]:
        return self.get("error")

    @property
    def fallback_used(self) -> bool:
        return self.get("fallback_used", False)

    @property
    def is_success(self) -> bool:
        return self.error is None and bool(self.results)


def is_bigquery_available() -> bool:
    """
    Verifica se o BigQuery possui SDK instalado e credenciais configuradas.
    Considera:
    1. st.secrets["GCP_SERVICE_ACCOUNT_JSON"] ou st.secrets["gcp_service_account"]
    2. Variável de ambiente (GOOGLE_APPLICATION_CREDENTIALS ou GCP_SERVICE_ACCOUNT_JSON)
    3. Arquivo local de credenciais (somente em ambiente local, se o arquivo existir)
    """
    if not getattr(bigquery_client, "HAS_BIGQUERY", False):
        return False

    # 1. Streamlit Secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "GCP_SERVICE_ACCOUNT_JSON" in st.secrets or "gcp_service_account" in st.secrets:
                return True
    except Exception:
        pass

    # 2. Variáveis de ambiente
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GCP_SERVICE_ACCOUNT_JSON"):
        return True

    # 3. Arquivo local (se existir no disco e apontado por credentials_path)
    cred_path = bigquery_client.get_credentials_path()
    if cred_path and os.path.exists(cred_path):
        return True

    return False


def get_api_source() -> str:
    """Identifica se a API HTTP configurada é a pública ou uma API local/privada."""
    base_url = api_client.get_base_url()
    if "cnpj.pw" in base_url:
        return SOURCE_PUBLIC_API
    return SOURCE_LOCAL_API


def should_use_bigquery(operation: str = "") -> bool:
    """Determina se a consulta atual deve priorizar o Google BigQuery."""
    engine_mode = api_client.get_engine_mode()
    if engine_mode == "API":
        return False

    try:
        import streamlit as st
        if hasattr(st, "session_state"):
            if operation in ("telefone", "email") and not st.session_state.get("use_bigquery_for_contacts", True):
                return False
    except Exception:
        pass

    return is_bigquery_available()


def is_privacy_active() -> bool:
    """
    Retorna True se o ambiente opera com Sigilo Total:
    - Consultas executadas via Google BigQuery privado, OU
    - Consultas executadas via API Local / Banco Privado próprio (sem enviar dados para api.cnpj.pw pública).
    """
    if should_use_bigquery():
        return True
    if get_api_source() == SOURCE_LOCAL_API:
        return True
    return False


def get_source_display_name(source: str, fallback_used: bool = False) -> str:
    """Retorna uma descrição amigável da fonte para exibição na UI."""
    mapping = {
        SOURCE_BIGQUERY: "Google BigQuery (Nuvem Privada • Sigilo Total)",
        SOURCE_LOCAL_API: "API Local Privada (Banco Próprio)",
        SOURCE_PUBLIC_API: "API Pública (api.cnpj.pw • Sem Sigilo)"
    }
    desc = mapping.get(source, source)
    if fallback_used:
        desc += " [Contingência / Fallback]"
    return desc


# ==========================================
# OPERAÇÕES DE CONSULTA CENTRALIZADAS
# ==========================================

def get_cnpj(cnpj: str) -> QueryResult:
    """Consulta a ficha cadastral completa de uma empresa."""
    cnpj_limpo = sanitizers.adequar_documento(cnpj)
    if len(cnpj_limpo) == 8:
        cnpj_limpo = cnpj_limpo.zfill(14)

    if len(cnpj_limpo) != 14:
        return QueryResult(
            results=None,
            source=get_api_source(),
            error=f"CNPJ inválido: '{cnpj}'. Requer 14 dígitos numéricos.",
            fallback_used=False
        )

    fallback_needed = False
    bq_error_msg = None

    # 1. Tentativa via BigQuery
    if should_use_bigquery("cnpj"):
        try:
            res_bq = bigquery_client.get_cnpj(cnpj_limpo)
            if res_bq and not res_bq.get("erro"):
                return QueryResult(
                    results=res_bq,
                    source=SOURCE_BIGQUERY,
                    error=None,
                    fallback_used=False
                )
            bq_error_msg = bigquery_client.get_last_error() or (res_bq.get("mensagem") if res_bq else "Não encontrado no BigQuery")
        except Exception as e:
            bq_error_msg = str(e)
        fallback_needed = True

    # 2. Execução / Fallback via API HTTP
    api_source = get_api_source()
    try:
        import requests
        base_url = api_client.get_base_url()
        res = requests.get(f"{base_url}/cnpj/{cnpj_limpo}", verify=False, timeout=15)
        if res.status_code == 200:
            data = res.json()
            err_msg = f"BigQuery falhou ({bq_error_msg}), obtido via contingência ({api_source})." if fallback_needed else None
            return QueryResult(
                results=data,
                source=api_source,
                error=err_msg,
                fallback_used=fallback_needed
            )
        elif res.status_code == 404:
            err = f"CNPJ {cnpj_limpo} não encontrado na base de dados."
        else:
            err = f"Erro na consulta do CNPJ ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        err = f"Não foi possível conectar à API em {api_client.get_base_url()}. Servidor indisponível."
    except Exception as e:
        err = f"Erro na requisição: {str(e)}"

    full_err = f"BigQuery ({bq_error_msg}) e API ({err}) falharam." if fallback_needed else err
    return QueryResult(
        results=None,
        source=api_source,
        error=full_err,
        fallback_used=fallback_needed
    )


def buscar_empresas_do_socio(nome: str, doc: str = None) -> QueryResult:
    """Busca todas as empresas vinculadas a um sócio por nome e/ou documento."""
    nome_clean = (nome or "").strip()
    doc_clean = sanitizers.adequar_documento(doc) if doc else ""

    fallback_needed = False
    bq_error_msg = None

    if should_use_bigquery("socio"):
        try:
            res_bq = bigquery_client.buscar_empresas_do_socio(nome_clean, doc_socio=doc_clean if not doc_clean.startswith("***") else None)
            if res_bq:
                return QueryResult(
                    results=res_bq,
                    source=SOURCE_BIGQUERY,
                    error=None,
                    fallback_used=False
                )
            bq_error_msg = bigquery_client.get_last_error()
        except Exception as e:
            bq_error_msg = str(e)
        fallback_needed = True

    api_source = get_api_source()
    params = {}
    if nome_clean:
        params["socio_nome"] = nome_clean
    if doc_clean and not doc_clean.startswith("***"):
        params["socio_doc"] = doc_clean

    try:
        import requests
        base_url = api_client.get_base_url()
        if doc_clean and not doc_clean.startswith("***") and not nome_clean:
            res = requests.get(f"{base_url}/socio/{doc_clean}", verify=False, timeout=15)
        else:
            res = requests.get(f"{base_url}/busca_difusa/", params=params, verify=False, timeout=20)

        if res.status_code == 200:
            lista = res.json().get("resultados_paginacao", [])
            err_msg = f"BigQuery falhou ({bq_error_msg}), obtido via contingência ({api_source})." if fallback_needed else None
            return QueryResult(
                results=lista,
                source=api_source,
                error=err_msg,
                fallback_used=fallback_needed
            )
        else:
            err = f"Erro na busca de sócio ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        err = f"Não foi possível conectar à API em {base_url}."
    except Exception as e:
        err = f"Erro na requisição: {str(e)}"

    full_err = f"BigQuery ({bq_error_msg}) e API ({err}) falharam." if fallback_needed else err
    return QueryResult(
        results=[],
        source=api_source,
        error=full_err,
        fallback_used=fallback_needed
    )


def buscar_socio(doc: str) -> QueryResult:
    """Busca empresas por documento específico de sócio (CPF/CNPJ)."""
    return buscar_empresas_do_socio(nome="", doc=sanitizers.adequar_documento(doc))


def buscar_telefone(ddd: str, telefone: str, months: int = 3) -> QueryResult:
    """
    Busca reversa de empresas por telefone.
    Regra 5 da Fase 5: Não executa busca reversa na API pública quando ela não oferece o endpoint.
    Aplica adequação automática de telefone celular (8, 10 ou 11 dígitos) e fixo.
    """
    tel_info = sanitizers.adequar_telefone(f"{ddd}{telefone}", default_ddd=ddd)
    ddd_clean = tel_info.get("ddd") or "".join(filter(str.isdigit, str(ddd or "")))
    tel_clean = tel_info.get("numero") or "".join(filter(str.isdigit, str(telefone or "")))

    if not tel_info.get("valido") and (len(ddd_clean) != 2 or len(tel_clean) < 8):
        return QueryResult(
            results=[],
            source=get_api_source(),
            error=tel_info.get("erro") or f"Telefone inválido: DDD '{ddd}' (2 dígitos) e número '{telefone}' (mínimo 8 dígitos).",
            fallback_used=False
        )

    fallback_needed = False
    bq_error_msg = None

    if should_use_bigquery("telefone"):
        try:
            res_bq = bigquery_client.buscar_telefone(ddd_clean, tel_clean, months=months)
            if res_bq:
                return QueryResult(
                    results=res_bq,
                    source=SOURCE_BIGQUERY,
                    error=None,
                    fallback_used=False
                )
            bq_error_msg = bigquery_client.get_last_error()
        except Exception as e:
            bq_error_msg = str(e)
        fallback_needed = True

    api_source = get_api_source()

    # Regra 5: Bloqueia busca se for API pública
    if api_source == SOURCE_PUBLIC_API:
        msg = "A API pública ('api.cnpj.pw') não possui suporte a buscas reversas por telefone. É necessário ativar o Google BigQuery ou conectar a uma API local com banco próprio."
        if fallback_needed and bq_error_msg:
            msg = f"BigQuery indisponível ({bq_error_msg}). {msg}"
        return QueryResult(
            results=[],
            source=SOURCE_PUBLIC_API,
            error=msg,
            fallback_used=fallback_needed
        )

    try:
        import requests
        base_url = api_client.get_base_url()
        res = requests.get(f"{base_url}/telefone/{ddd_clean}/{tel_clean}", verify=False, timeout=15)
        if res.status_code == 200:
            lista = res.json().get("resultados_paginacao", [])
            err_msg = f"BigQuery falhou ({bq_error_msg}), obtido via contingência local." if fallback_needed else None
            return QueryResult(
                results=lista,
                source=SOURCE_LOCAL_API,
                error=err_msg,
                fallback_used=fallback_needed
            )
        else:
            err = f"Erro na busca por telefone ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        err = f"Não foi possível conectar à API local em {base_url}."
    except Exception as e:
        err = f"Erro na requisição: {str(e)}"

    full_err = f"BigQuery ({bq_error_msg}) e API Local ({err}) falharam." if fallback_needed else err
    return QueryResult(
        results=[],
        source=SOURCE_LOCAL_API,
        error=full_err,
        fallback_used=fallback_needed
    )


def buscar_email(email: str, months: int = 3) -> QueryResult:
    """
    Busca reversa de empresas por e-mail.
    Regra 5 da Fase 5: Não executa busca reversa na API pública quando ela não oferece o endpoint.
    """
    email_clean = str(email or "").strip().lower()
    if "@" not in email_clean or "." not in email_clean.split("@")[-1]:
        return QueryResult(
            results=[],
            source=get_api_source(),
            error=f"E-mail inválido para busca: '{email}'. Formato esperado: usuario@dominio.com.",
            fallback_used=False
        )

    fallback_needed = False
    bq_error_msg = None

    if should_use_bigquery("email"):
        try:
            res_bq = bigquery_client.buscar_email(email_clean, months=months)
            if res_bq:
                return QueryResult(
                    results=res_bq,
                    source=SOURCE_BIGQUERY,
                    error=None,
                    fallback_used=False
                )
            bq_error_msg = bigquery_client.get_last_error()
        except Exception as e:
            bq_error_msg = str(e)
        fallback_needed = True

    api_source = get_api_source()

    # Regra 5: Bloqueia busca se for API pública
    if api_source == SOURCE_PUBLIC_API:
        msg = "A API pública ('api.cnpj.pw') não possui suporte a buscas reversas por e-mail. É necessário ativar o Google BigQuery ou conectar a uma API local com banco próprio."
        if fallback_needed and bq_error_msg:
            msg = f"BigQuery indisponível ({bq_error_msg}). {msg}"
        return QueryResult(
            results=[],
            source=SOURCE_PUBLIC_API,
            error=msg,
            fallback_used=fallback_needed
        )

    try:
        import requests
        base_url = api_client.get_base_url()
        res = requests.get(f"{base_url}/email/{email_clean}", verify=False, timeout=15)
        if res.status_code == 200:
            lista = res.json().get("resultados_paginacao", [])
            err_msg = f"BigQuery falhou ({bq_error_msg}), obtido via contingência local." if fallback_needed else None
            return QueryResult(
                results=lista,
                source=SOURCE_LOCAL_API,
                error=err_msg,
                fallback_used=fallback_needed
            )
        else:
            err = f"Erro na busca por e-mail ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        err = f"Não foi possível conectar à API local em {base_url}."
    except Exception as e:
        err = f"Erro na requisição: {str(e)}"

    full_err = f"BigQuery ({bq_error_msg}) e API Local ({err}) falharam." if fallback_needed else err
    return QueryResult(
        results=[],
        source=SOURCE_LOCAL_API,
        error=full_err,
        fallback_used=fallback_needed
    )


def buscar_razao_social(razao: str) -> QueryResult:
    """Busca empresas por Razão Social."""
    razao_clean = str(razao or "").strip()
    if not razao_clean:
        return QueryResult(results=[], source=get_api_source(), error="Razão Social não informada.", fallback_used=False)

    fallback_needed = False
    bq_error_msg = None

    if should_use_bigquery("razao"):
        try:
            res_bq = bigquery_client.buscar_razao_social(razao_clean)
            if res_bq:
                return QueryResult(results=res_bq, source=SOURCE_BIGQUERY, error=None, fallback_used=False)
            bq_error_msg = bigquery_client.get_last_error()
        except Exception as e:
            bq_error_msg = str(e)
        fallback_needed = True

    api_source = get_api_source()
    try:
        import requests
        base_url = api_client.get_base_url()
        res = requests.get(f"{base_url}/razao_social/{razao_clean}", verify=False, timeout=15)
        if res.status_code == 200:
            lista = res.json().get("resultados_paginacao", [])
            err_msg = f"BigQuery falhou ({bq_error_msg}), obtido via contingência ({api_source})." if fallback_needed else None
            return QueryResult(results=lista, source=api_source, error=err_msg, fallback_used=fallback_needed)
        else:
            err = f"Erro na busca por Razão Social ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        err = f"Não foi possível conectar à API em {api_client.get_base_url()}."
    except Exception as e:
        err = f"Erro na requisição: {str(e)}"

    full_err = f"BigQuery ({bq_error_msg}) e API ({err}) falharam." if fallback_needed else err
    return QueryResult(results=[], source=api_source, error=full_err, fallback_used=fallback_needed)


def busca_difusa(params: dict) -> QueryResult:
    """Executa busca difusa avançada por filtros múltiplos."""
    params_clean = {k: v for k, v in (params or {}).items() if v is not None and v != ""}

    fallback_needed = False
    bq_error_msg = None

    socio_nome = params_clean.get("socio_nome")
    socio_doc = params_clean.get("socio_doc")

    if should_use_bigquery("difusa") and (socio_nome or socio_doc):
        try:
            res_bq = bigquery_client.buscar_empresas_do_socio(socio_nome or "", doc_socio=socio_doc)
            if res_bq:
                return QueryResult(results=res_bq, source=SOURCE_BIGQUERY, error=None, fallback_used=False)
            bq_error_msg = bigquery_client.get_last_error()
        except Exception as e:
            bq_error_msg = str(e)
        fallback_needed = True

    api_source = get_api_source()
    try:
        import requests
        base_url = api_client.get_base_url()
        res = requests.get(f"{base_url}/busca_difusa/", params=params_clean, verify=False, timeout=20)
        if res.status_code == 200:
            lista = res.json().get("resultados_paginacao", [])
            err_msg = f"BigQuery falhou ({bq_error_msg}), obtido via contingência ({api_source})." if fallback_needed else None
            return QueryResult(results=lista, source=api_source, error=err_msg, fallback_used=fallback_needed)
        else:
            err = f"Erro na busca avançada ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        err = f"Não foi possível conectar à API em {api_client.get_base_url()}."
    except Exception as e:
        err = f"Erro na requisição: {str(e)}"

    full_err = f"BigQuery ({bq_error_msg}) e API ({err}) falharam." if fallback_needed else err
    return QueryResult(results=[], source=api_source, error=full_err, fallback_used=fallback_needed)
