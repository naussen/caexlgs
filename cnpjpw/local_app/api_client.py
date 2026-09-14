import os
import requests
import urllib3

try:
    import bigquery_client
except ImportError:
    from cnpjpw.local_app import bigquery_client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_PUBLIC_URL = "https://api.cnpj.pw"
DEFAULT_LOCAL_URL = "http://localhost:8000"

BASE_URL = os.getenv("CNPJ_API_URL", DEFAULT_PUBLIC_URL).rstrip("/")
ENGINE_MODE = "AUTO"  # "AUTO", "BIGQUERY" ou "API"
_last_error = None

def get_engine_mode() -> str:
    global ENGINE_MODE
    return ENGINE_MODE

def set_engine_mode(mode: str):
    global ENGINE_MODE
    ENGINE_MODE = mode

def is_bigquery_available() -> bool:
    """Verifica se o SDK do BigQuery e credenciais válidas estão configurados."""
    if not getattr(bigquery_client, "HAS_BIGQUERY", False):
        return False
    cred_path = bigquery_client.get_credentials_path()
    has_creds = bool(
        (cred_path and os.path.exists(cred_path))
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    )
    return has_creds

def is_bigquery_mode() -> bool:
    if ENGINE_MODE == "API":
        return False
    if ENGINE_MODE == "BIGQUERY":
        return is_bigquery_available()
    return is_bigquery_available()

def get_base_url() -> str:
    global BASE_URL
    return BASE_URL

def set_base_url(url: str):
    global BASE_URL
    BASE_URL = url.rstrip("/")

def get_last_error():
    global _last_error
    if is_bigquery_mode():
        return bigquery_client.get_last_error() or _last_error
    return _last_error

def clear_last_error():
    global _last_error
    _last_error = None
    bigquery_client.clear_last_error()

def is_public_api() -> bool:
    if is_bigquery_mode():
        return False
    return "cnpj.pw" in BASE_URL

def get_cnpj(cnpj: str):
    global _last_error
    _last_error = None

    if is_bigquery_mode():
        try:
            res = bigquery_client.get_cnpj(cnpj)
            if res and not res.get('erro'):
                return res
        except Exception as e:
            _last_error = f"BigQuery falhou ({str(e)}), utilizando fallback HTTP API..."

    try:
        res = requests.get(f"{BASE_URL}/cnpj/{cnpj}", verify=False, timeout=15)
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 404:
            _last_error = f"CNPJ {cnpj} não encontrado na base de dados."
        else:
            _last_error = f"Erro ao consultar CNPJ ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        _last_error = f"Não foi possível conectar à API em {BASE_URL}. Verifique se o servidor está ativo."
    except Exception as e:
        _last_error = f"Erro na requisição: {str(e)}"
    return None

def buscar_razao_social(razao: str):
    global _last_error
    _last_error = None

    if is_bigquery_mode():
        try:
            res = bigquery_client.buscar_razao_social(razao)
            if res:
                return res
        except Exception as e:
            _last_error = f"BigQuery falhou ({str(e)}), utilizando fallback HTTP API..."

    try:
        res = requests.get(f"{BASE_URL}/razao_social/{razao}", verify=False, timeout=15)
        if res.status_code == 200:
            return res.json().get('resultados_paginacao', [])
        else:
            _last_error = f"Erro na busca por Razão Social ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        _last_error = f"Não foi possível conectar à API em {BASE_URL}. Verifique se o servidor está ativo."
    except Exception as e:
        _last_error = f"Erro na requisição: {str(e)}"
    return []

def buscar_socio(doc: str):
    global _last_error
    _last_error = None

    if is_bigquery_mode():
        try:
            res = bigquery_client.buscar_empresas_do_socio("", doc_socio=doc)
            if res:
                return res
        except Exception as e:
            _last_error = f"BigQuery falhou ({str(e)}), utilizando fallback HTTP API..."

    try:
        res = requests.get(f"{BASE_URL}/socio/{doc}", verify=False, timeout=15)
        if res.status_code == 200:
            return res.json().get('resultados_paginacao', [])
        else:
            _last_error = f"Erro na busca por Sócio ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        _last_error = f"Não foi possível conectar à API em {BASE_URL}. Verifique se o servidor está ativo."
    except Exception as e:
        _last_error = f"Erro na requisição: {str(e)}"
    return []

def buscar_empresas_do_socio(nome: str, doc: str = None):
    """Busca todas as empresas vinculadas a um sócio por nome e/ou documento."""
    global _last_error
    _last_error = None

    if is_bigquery_mode():
        try:
            res = bigquery_client.buscar_empresas_do_socio(nome, doc_socio=doc)
            if res:
                return res
        except Exception as e:
            _last_error = f"BigQuery falhou ({str(e)}), utilizando fallback HTTP API..."

    params = {}
    if nome:
        params['socio_nome'] = nome.strip()
    if doc and not doc.startswith("***"):
        params['socio_doc'] = doc.strip()
    
    resultados = busca_difusa(params)
    if not resultados and doc and not doc.startswith("***"):
        resultados = buscar_socio(doc.strip())
    return resultados or []

def buscar_telefone(ddd: str, telefone: str):
    global _last_error
    _last_error = None

    if is_bigquery_mode():
        try:
            res = bigquery_client.buscar_telefone(ddd, telefone)
            if res:
                return res
        except Exception as e:
            _last_error = f"BigQuery falhou ({str(e)}), utilizando fallback HTTP API..."

    try:
        res = requests.get(f"{BASE_URL}/telefone/{ddd}/{telefone}", verify=False, timeout=15)
        if res.status_code == 200:
            return res.json().get('resultados_paginacao', [])
        elif res.status_code == 404 and is_public_api():
            _last_error = (
                "A API pública ('api.cnpj.pw') não possui suporte a buscas reversas por telefone (retornou HTTP 404)."
            )
        else:
            _last_error = f"Erro na busca por telefone ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        _last_error = f"Não foi possível conectar à API em {BASE_URL}. Verifique se a API local está em execução."
    except Exception as e:
        _last_error = f"Erro na requisição: {str(e)}"
    return []

def buscar_email(email: str):
    global _last_error
    _last_error = None

    if is_bigquery_mode():
        try:
            res = bigquery_client.buscar_email(email)
            if res:
                return res
        except Exception as e:
            _last_error = f"BigQuery falhou ({str(e)}), utilizando fallback HTTP API..."

    try:
        res = requests.get(f"{BASE_URL}/email/{email}", verify=False, timeout=15)
        if res.status_code == 200:
            return res.json().get('resultados_paginacao', [])
        elif res.status_code == 404 and is_public_api():
            _last_error = (
                "A API pública ('api.cnpj.pw') não possui suporte a buscas reversas por e-mail (retornou HTTP 404)."
            )
        else:
            _last_error = f"Erro na busca por e-mail ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        _last_error = f"Não foi possível conectar à API em {BASE_URL}. Verifique se a API local está em execução."
    except Exception as e:
        _last_error = f"Erro na requisição: {str(e)}"
    return []

def busca_difusa(params: dict):
    global _last_error
    _last_error = None

    if is_bigquery_mode():
        socio_nome = params.get('socio_nome')
        socio_doc = params.get('socio_doc')
        try:
            res = bigquery_client.buscar_empresas_do_socio(socio_nome or "", doc_socio=socio_doc)
            if res:
                return res
        except Exception as e:
            _last_error = f"BigQuery falhou ({str(e)}), utilizando fallback HTTP API..."

    params_clean = {k: v for k, v in params.items() if v is not None and v != ""}
    try:
        res = requests.get(f"{BASE_URL}/busca_difusa/", params=params_clean, verify=False, timeout=20)
        if res.status_code == 200:
            return res.json().get('resultados_paginacao', [])
        else:
            _last_error = f"Erro na busca avançada ({res.status_code}): {res.text}"
    except requests.exceptions.ConnectionError:
        _last_error = f"Não foi possível conectar à API em {BASE_URL}. Verifique se o servidor está ativo."
    except Exception as e:
        _last_error = f"Erro na requisição: {str(e)}"
    return []

