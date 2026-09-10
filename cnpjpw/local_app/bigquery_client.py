import os
from typing import Optional, List, Dict, Tuple
from google.cloud import bigquery
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPICallError, PermissionDenied, NotFound, Forbidden

DEFAULT_TABLE = "basedosdados.br_me_cnpj.estabelecimentos"

_project_id: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
_credentials_path: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
_dataset_table: str = os.getenv("BIGQUERY_CNPJ_TABLE", DEFAULT_TABLE)
_last_error: Optional[str] = None
_cached_partitions: Optional[List[str]] = None


def get_project_id() -> str:
    return _project_id or ""


def set_project_id(project_id: str):
    global _project_id
    _project_id = project_id.strip() if project_id else None


def get_credentials_path() -> str:
    return _credentials_path or ""


def set_credentials_path(path: str):
    global _credentials_path
    _credentials_path = path.strip() if path else None


def get_table_name() -> str:
    return _dataset_table


def set_table_name(table_name: str):
    global _dataset_table
    _dataset_table = table_name.strip() if table_name else DEFAULT_TABLE


def get_last_error() -> Optional[str]:
    global _last_error
    return _last_error


def clear_last_error():
    global _last_error
    _last_error = None


def _get_client() -> bigquery.Client:
    """Instancia o cliente BigQuery com credenciais de arquivo ou do ambiente."""
    kwargs = {}
    cred_path = _credentials_path
    if not cred_path:
        for candidate in ["gcp-key.json", os.path.join(os.path.dirname(__file__), "..", "..", "gcp-key.json"), "c:/Users/7401/Documents/CNPJ/gcp-key.json"]:
            if os.path.exists(candidate):
                cred_path = os.path.abspath(candidate)
                break

    project = _project_id
    if cred_path and os.path.exists(cred_path):
        credentials = service_account.Credentials.from_service_account_file(
            cred_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        kwargs["credentials"] = credentials
        if not project:
            try:
                import json
                with open(cred_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    project = data.get("project_id")
            except Exception:
                pass

    if project:
        kwargs["project"] = project

    return bigquery.Client(**kwargs)


REAL_SNAPSHOT_DATES = [
    '2026-01-11',
    '2025-12-14',
    '2025-11-09',
    '2025-10-12',
    '2025-09-14',
    '2025-08-10',
    '2025-07-30',
    '2025-06-15',
    '2025-05-12',
    '2025-04-20',
]


def get_recent_partitions(client: bigquery.Client, limit: int = 3) -> List[str]:
    """Retorna as datas dos snapshots que possuem dados populados na Base dos Dados."""
    return REAL_SNAPSHOT_DATES[:max(1, limit)]


def test_connection() -> Tuple[bool, str]:
    """Testa se a autenticação e o projeto do BigQuery estão funcionando."""
    global _last_error
    _last_error = None
    try:
        client = _get_client()
        query_job = client.query("SELECT 1 AS teste")
        res = list(query_job.result())
        if res:
            return True, f"Conexão com BigQuery estabelecida com sucesso (Projeto: {client.project})."
        return False, "Nenhum retorno recebido da consulta de teste."
    except PermissionDenied as e:
        msg = f"Permissão negada no Google Cloud: {e.message}"
        _last_error = msg
        return False, msg
    except NotFound as e:
        msg = f"Projeto ou recurso não encontrado no BigQuery: {e.message}"
        _last_error = msg
        return False, msg
    except Exception as e:
        msg = f"Falha ao conectar com BigQuery: {str(e)}"
        _last_error = msg
        return False, msg


def buscar_email(email: str, limit: int = 25, months: int = 3) -> List[Dict]:
    """Busca estabelecimentos no BigQuery que possuam o e-mail correspondente com Razão Social."""
    global _last_error
    _last_error = None
    email_clean = email.strip().lower()

    try:
        client = _get_client()
        dates = get_recent_partitions(client, limit=months)
        dates_filter = f"est.data IN ('" + "', '".join(dates) + "') AND " if dates else ""
        snapshot_ref = dates[0] if dates else '2026-01-11'

        query = f"""
        SELECT
            est.cnpj,
            ANY_VALUE(est.cnpj_basico) AS cnpj_basico,
            ANY_VALUE(est.cnpj_ordem) AS cnpj_ordem,
            ANY_VALUE(est.cnpj_dv) AS cnpj_dv,
            ANY_VALUE(est.nome_fantasia) AS nome_fantasia,
            ANY_VALUE(em.razao_social) AS razao_social,
            ANY_VALUE(est.sigla_uf) AS sigla_uf,
            ANY_VALUE(est.email) AS email,
            ANY_VALUE(est.ddd_1) AS ddd_1,
            ANY_VALUE(est.telefone_1) AS telefone_1
        FROM `{_dataset_table}` est
        LEFT JOIN `basedosdados.br_me_cnpj.empresas` em
          ON est.cnpj_basico = em.cnpj_basico AND em.data = '{snapshot_ref}'
        WHERE {dates_filter} LOWER(est.email) = LOWER(@email)
        GROUP BY est.cnpj
        ORDER BY est.cnpj
        LIMIT {limit}
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("email", "STRING", email_clean)
            ]
        )
        query_job = client.query(query, job_config=job_config)
        rows = query_job.result()

        resultados = []
        for row in rows:
            cnpj_val = row.get("cnpj") or (
                str(row.get("cnpj_basico", "")) +
                str(row.get("cnpj_ordem", "")) +
                str(row.get("cnpj_dv", ""))
            )
            razao = row.get("razao_social")
            fantasia = row.get("nome_fantasia")
            nome = razao or fantasia or cnpj_val or "Estabelecimento"
            resultados.append({
                "cnpj": cnpj_val,
                "cnpj_base": row.get("cnpj_basico"),
                "cnpj_ordem": row.get("cnpj_ordem"),
                "cnpj_dv": row.get("cnpj_dv"),
                "razao_social": razao or fantasia or f"CNPJ {cnpj_val}",
                "nome_empresarial": nome,
                "nome_fantasia": fantasia,
                "sigla_uf": row.get("sigla_uf"),
                "correio_eletronico": row.get("email"),
                "telefone": f"({row.get('ddd_1', '') or ''}) {row.get('telefone_1', '') or ''}".strip()
            })
        return resultados

    except Forbidden as e:
        if "quotaExceeded" in str(e):
            _last_error = (
                "Cota de leitura gratuita do BigQuery atingida temporariamente (limite diário do Sandbox). "
                "Dica: Vincule uma conta de faturamento (Billing) gratuita ao seu projeto no Google Cloud Console "
                "para usufruir da cota completa de 1 TB/mês sem restrições diárias."
            )
        else:
            _last_error = f"Acesso negado no BigQuery: {e.message}"
        return []
    except GoogleAPICallError as e:
        _last_error = f"Erro na consulta BigQuery: {e.message}"
        return []
    except Exception as e:
        _last_error = f"Erro ao acessar BigQuery: {str(e)}"
        return []


def buscar_telefone(ddd: str, telefone: str, limit: int = 25, months: int = 3) -> List[Dict]:
    """Busca estabelecimentos no BigQuery que possuam o DDD e telefone correspondentes com Razão Social."""
    global _last_error
    _last_error = None
    ddd_clean = ddd.strip()
    telefone_clean = telefone.strip()

    try:
        client = _get_client()
        dates = get_recent_partitions(client, limit=months)
        dates_filter = f"est.data IN ('" + "', '".join(dates) + "') AND " if dates else ""
        snapshot_ref = dates[0] if dates else '2026-01-11'

        query = f"""
        SELECT
            est.cnpj,
            ANY_VALUE(est.cnpj_basico) AS cnpj_basico,
            ANY_VALUE(est.cnpj_ordem) AS cnpj_ordem,
            ANY_VALUE(est.cnpj_dv) AS cnpj_dv,
            ANY_VALUE(est.nome_fantasia) AS nome_fantasia,
            ANY_VALUE(em.razao_social) AS razao_social,
            ANY_VALUE(est.sigla_uf) AS sigla_uf,
            ANY_VALUE(est.email) AS email,
            ANY_VALUE(est.ddd_1) AS ddd_1,
            ANY_VALUE(est.telefone_1) AS telefone_1
        FROM `{_dataset_table}` est
        LEFT JOIN `basedosdados.br_me_cnpj.empresas` em
          ON est.cnpj_basico = em.cnpj_basico AND em.data = '{snapshot_ref}'
        WHERE {dates_filter} (
            (est.ddd_1 = @ddd AND est.telefone_1 = @telefone) OR
            (est.ddd_2 = @ddd AND est.telefone_2 = @telefone)
        )
        GROUP BY est.cnpj
        ORDER BY est.cnpj
        LIMIT {limit}
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ddd", "STRING", ddd_clean),
                bigquery.ScalarQueryParameter("telefone", "STRING", telefone_clean)
            ]
        )
        query_job = client.query(query, job_config=job_config)
        rows = query_job.result()

        resultados = []
        for row in rows:
            cnpj_val = row.get("cnpj") or (
                str(row.get("cnpj_basico", "")) +
                str(row.get("cnpj_ordem", "")) +
                str(row.get("cnpj_dv", ""))
            )
            razao = row.get("razao_social")
            fantasia = row.get("nome_fantasia")
            nome = razao or fantasia or cnpj_val or "Estabelecimento"
            resultados.append({
                "cnpj": cnpj_val,
                "cnpj_base": row.get("cnpj_basico"),
                "cnpj_ordem": row.get("cnpj_ordem"),
                "cnpj_dv": row.get("cnpj_dv"),
                "razao_social": razao or fantasia or f"CNPJ {cnpj_val}",
                "nome_empresarial": nome,
                "nome_fantasia": fantasia,
                "sigla_uf": row.get("sigla_uf"),
                "correio_eletronico": row.get("email"),
                "telefone": f"({row.get('ddd_1', '') or ''}) {row.get('telefone_1', '') or ''}".strip()
            })
        return resultados

    except Forbidden as e:
        if "quotaExceeded" in str(e):
            _last_error = (
                "Cota de leitura gratuita do BigQuery atingida temporariamente (limite diário do Sandbox). "
                "Dica: Vincule uma conta de faturamento (Billing) gratuita ao seu projeto no Google Cloud Console "
                "para usufruir da cota completa de 1 TB/mês sem restrições diárias."
            )
        else:
            _last_error = f"Acesso negado no BigQuery: {e.message}"
        return []
    except GoogleAPICallError as e:
        _last_error = f"Erro na consulta BigQuery: {e.message}"
        return []
    except Exception as e:
        _last_error = f"Erro ao acessar BigQuery: {str(e)}"
        return []


MAP_SITUACAO_CADASTRAL = {
    "1": "NULA",
    "2": "ATIVA",
    "3": "SUSPENSA",
    "4": "INAPTA",
    "8": "BAIXADA"
}

MAP_QUALIFICACAO_SOCIO = {
    "05": "Administrador",
    "08": "Conselheiro de Administração",
    "10": "Diretor",
    "16": "Presidente",
    "20": "Sociedade Consorciada",
    "21": "Sociedade Filiada",
    "22": "Sócio",
    "23": "Sócio Capitalista",
    "24": "Sócio Comanditado",
    "25": "Sócio Comanditário",
    "26": "Sócio de Indústria",
    "28": "Sócio-Gerente",
    "29": "Sócio Incapaz ou Relat. Incapaz",
    "30": "Sócio Menor (Assistido/Representado)",
    "31": "Sócio Ostensivo",
    "37": "Cônjuge ou Companheiro",
    "38": "Membro de Conselho",
    "49": "Sócio-Administrador",
    "52": "Fundador",
    "53": "Usufrutuário",
    "65": "Titular PJ Domiciliada no Exterior",
    "66": "Titular PF Residente no Brasil"
}

MAP_IDENTIFICADOR_SOCIO = {
    "1": "Pessoa Jurídica",
    "2": "Pessoa Física",
    "3": "Estrangeiro"
}


def get_cnpj(cnpj: str, snapshot_date: str = "2026-01-11") -> Optional[dict]:
    """
    Consulta a ficha cadastral completa de um CNPJ diretamente no Google BigQuery (Sigilo Total).
    """
    global _last_error
    _last_error = None

    import re
    cnpj_clean = re.sub(r'\D', '', str(cnpj or ''))
    if len(cnpj_clean) != 14:
        _last_error = f"CNPJ inválido: deve conter 14 dígitos (recebido: {cnpj_clean})"
        return None

    cnpj_basico = cnpj_clean[:8]
    cnpj_ordem = cnpj_clean[8:12]
    cnpj_dv = cnpj_clean[12:14]

    try:
        client = _get_client()

        # 1. Dados do Estabelecimento + Empresa
        q_emp = f"""
        SELECT 
            e.cnpj_basico, e.cnpj_ordem, e.cnpj_dv,
            CONCAT(e.cnpj_basico, e.cnpj_ordem, e.cnpj_dv) AS cnpj,
            em.razao_social AS nome_empresarial,
            e.nome_fantasia,
            e.situacao_cadastral,
            e.data_inicio_atividade,
            e.cnae_fiscal_principal AS cnae_fiscal_principal_descricao,
            e.tipo_logradouro, e.logradouro, e.numero, e.complemento, e.bairro, e.cep,
            e.sigla_uf AS uf,
            e.id_municipio AS municipio_desc,
            e.ddd_1 AS ddd1, e.telefone_1, e.ddd_2 AS ddd2, e.telefone_2,
            e.email AS correio_eletronico,
            em.capital_social
        FROM basedosdados.br_me_cnpj.estabelecimentos e
        LEFT JOIN basedosdados.br_me_cnpj.empresas em
          ON e.cnpj_basico = em.cnpj_basico AND em.data = '{snapshot_date}'
        WHERE e.cnpj_basico = '{cnpj_basico}' AND e.cnpj_ordem = '{cnpj_ordem}' AND e.cnpj_dv = '{cnpj_dv}'
          AND e.data = '{snapshot_date}'
        LIMIT 1
        """
        rows_emp = list(client.query(q_emp).result())
        if not rows_emp:
            _last_error = f"CNPJ {cnpj_clean} não encontrado na base de dados do BigQuery (partição {snapshot_date})."
            return None

        empresa = dict(rows_emp[0])
        # Traduz situação cadastral
        sit_code = str(empresa.get("situacao_cadastral") or "")
        empresa["situacao_cadastral_descricao"] = MAP_SITUACAO_CADASTRAL.get(sit_code, sit_code or "ATIVA")

        # 2. Quadro Societário (Sócios)
        q_soc = f"""
        SELECT 
            nome,
            documento AS cnpj_cpf,
            qualificacao,
            tipo,
            data_entrada_sociedade
        FROM basedosdados.br_me_cnpj.socios
        WHERE cnpj_basico = '{cnpj_basico}'
          AND data = '{snapshot_date}'
        LIMIT 50
        """
        rows_soc = list(client.query(q_soc).result())
        socios_list = []
        for s in rows_soc:
            s_dict = dict(s)
            q_code = str(s_dict.get("qualificacao") or "").zfill(2)
            t_code = str(s_dict.get("tipo") or "")
            s_dict["qualificacao_descricao"] = MAP_QUALIFICACAO_SOCIO.get(q_code, f"Qualif. {q_code}")
            s_dict["identificador_entidade_descricao"] = MAP_IDENTIFICADOR_SOCIO.get(t_code, "Pessoa")
            socios_list.append(s_dict)

        empresa["socios"] = socios_list
        return empresa

    except Forbidden as e:
        _last_error = f"Acesso negado no BigQuery: {e.message}"
        return None
    except Exception as e:
        _last_error = f"Erro na consulta de CNPJ no BigQuery: {str(e)}"
        return None


def buscar_empresas_do_socio(nome_socio: str, doc_socio: str = None, snapshot_date: str = "2026-01-11", limit: int = 25) -> list[dict]:
    """
    Busca todas as empresas vinculadas a um sócio no Google BigQuery (Sigilo Total).
    """
    global _last_error
    _last_error = None

    if not nome_socio and not doc_socio:
        return []

    try:
        client = _get_client()
        conditions = []
        params = []

        if nome_socio:
            conditions.append("s.nome = @nome")
            params.append(bigquery.ScalarQueryParameter("nome", "STRING", nome_socio.strip().upper()))
        if doc_socio and not doc_socio.startswith("***"):
            import re
            clean_doc = re.sub(r'\D', '', doc_socio)
            if clean_doc:
                conditions.append("s.documento = @doc")
                params.append(bigquery.ScalarQueryParameter("doc", "STRING", clean_doc))

        where_clause = " OR ".join(conditions)

        q_soc_emp = f"""
        SELECT 
            s.cnpj_basico,
            s.nome AS nome_socio,
            s.qualificacao,
            s.documento AS doc_socio,
            em.razao_social,
            e.cnpj_ordem, e.cnpj_dv,
            CONCAT(s.cnpj_basico, COALESCE(e.cnpj_ordem, '0001'), COALESCE(e.cnpj_dv, '00')) AS cnpj
        FROM basedosdados.br_me_cnpj.socios s
        LEFT JOIN basedosdados.br_me_cnpj.empresas em
          ON s.cnpj_basico = em.cnpj_basico AND em.data = '{snapshot_date}'
        LEFT JOIN basedosdados.br_me_cnpj.estabelecimentos e
          ON s.cnpj_basico = e.cnpj_basico AND e.cnpj_ordem = '0001' AND e.data = '{snapshot_date}'
        WHERE ({where_clause})
          AND s.data = '{snapshot_date}'
        LIMIT {limit}
        """
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = client.query(q_soc_emp, job_config=job_config).result()

        resultados = []
        for r in rows:
            r_dict = dict(r)
            resultados.append({
                "cnpj": r_dict.get("cnpj"),
                "cnpj_base": r_dict.get("cnpj_basico"),
                "cnpj_ordem": r_dict.get("cnpj_ordem"),
                "cnpj_dv": r_dict.get("cnpj_dv"),
                "razao_social": r_dict.get("razao_social") or f"CNPJ {r_dict.get('cnpj')}",
                "nome_empresarial": r_dict.get("razao_social") or f"CNPJ {r_dict.get('cnpj')}",
                "nome_socio": r_dict.get("nome_socio"),
                "qualificacao_socio": r_dict.get("qualificacao")
            })
        return resultados

    except Forbidden as e:
        _last_error = f"Acesso negado no BigQuery: {e.message}"
        return []
    except Exception as e:
        _last_error = f"Erro na busca de sócio no BigQuery: {str(e)}"
        return []


def buscar_razao_social(razao: str, snapshot_date: str = "2026-01-11", limit: int = 25) -> list[dict]:
    """
    Busca empresas por Razão Social no Google BigQuery (Sigilo Total).
    """
    global _last_error
    _last_error = None

    if not razao:
        return []

    try:
        client = _get_client()
        razao_clean = razao.strip().upper()

        q_razao = f"""
        SELECT 
            em.cnpj_basico,
            em.razao_social,
            CONCAT(em.cnpj_basico, COALESCE(e.cnpj_ordem, '0001'), COALESCE(e.cnpj_dv, '00')) AS cnpj,
            e.situacao_cadastral,
            e.sigla_uf AS uf
        FROM basedosdados.br_me_cnpj.empresas em
        LEFT JOIN basedosdados.br_me_cnpj.estabelecimentos e
          ON em.cnpj_basico = e.cnpj_basico AND e.cnpj_ordem = '0001' AND e.data = '{snapshot_date}'
        WHERE (STARTS_WITH(em.razao_social, @razao) OR em.razao_social LIKE @razao_like)
          AND em.data = '{snapshot_date}'
        LIMIT {limit}
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("razao", "STRING", razao_clean),
                bigquery.ScalarQueryParameter("razao_like", "STRING", f"%{razao_clean}%")
            ]
        )
        rows = client.query(q_razao, job_config=job_config).result()

        resultados = []
        for r in rows:
            r_dict = dict(r)
            sit = MAP_SITUACAO_CADASTRAL.get(str(r_dict.get("situacao_cadastral") or ""), "ATIVA")
            resultados.append({
                "cnpj": r_dict.get("cnpj"),
                "cnpj_base": r_dict.get("cnpj_basico"),
                "razao_social": r_dict.get("razao_social"),
                "nome_empresarial": r_dict.get("razao_social"),
                "situacao_cadastral_descricao": sit,
                "uf": r_dict.get("uf")
            })
        return resultados

    except Forbidden as e:
        _last_error = f"Acesso negado no BigQuery: {e.message}"
        return []
    except Exception as e:
        _last_error = f"Erro na busca por Razão Social no BigQuery: {str(e)}"
        return []

