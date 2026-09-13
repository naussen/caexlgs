"""
Cliente Oficial para a API Pública do DataJud (CNJ).
Permite consultar metadados detalhados de processos judiciais de todo o Brasil
utilizando Elasticsearch Query DSL sobre os índices de tribunais estaduais, federais e trabalhistas.
"""
import logging
from typing import Optional, Dict, Any, List
import requests
import urllib3

from .validators import limpar_digitos, formatar_numero_processo_cnj
from .models import ProcessoJudicial, MovimentoProcessual

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("DataJudClient")

DEFAULT_API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
BASE_URL = "https://api-publica.datajud.cnj.jus.br"

# Mapeamento do padrão CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
# J = Ramo da Justiça | TR = Tribunal / Região
MAPA_RAMO_TR = {
    # Justiça Federal (J = 4)
    ("4", "01"): "trf1",
    ("4", "02"): "trf2",
    ("4", "03"): "trf3",
    ("4", "04"): "trf4",
    ("4", "05"): "trf5",
    ("4", "06"): "trf6",
    # Justiça do Trabalho (J = 5)
    ("5", "00"): "tst",
    ("5", "01"): "trt1",
    ("5", "02"): "trt2",
    ("5", "03"): "trt3",
    ("5", "04"): "trt4",
    ("5", "05"): "trt5",
    ("5", "06"): "trt6",
    ("5", "07"): "trt7",
    ("5", "08"): "trt8",
    ("5", "09"): "trt9",
    ("5", "10"): "trt10",
    ("5", "11"): "trt11",
    ("5", "12"): "trt12",
    ("5", "13"): "trt13",
    ("5", "14"): "trt14",
    ("5", "15"): "trt15",
    ("5", "16"): "trt16",
    ("5", "17"): "trt17",
    ("5", "18"): "trt18",
    ("5", "19"): "trt19",
    ("5", "20"): "trt20",
    ("5", "21"): "trt21",
    ("5", "22"): "trt22",
    ("5", "23"): "trt23",
    ("5", "24"): "trt24",
    # Tribunais Superiores
    ("1", "00"): "stf",
    ("2", "00"): "cnj",
    ("3", "00"): "stj",
    # Justiça Estadual (J = 8)
    ("8", "01"): "tjac",
    ("8", "02"): "tjal",
    ("8", "03"): "tjap",
    ("8", "04"): "tjam",
    ("8", "05"): "tjba",
    ("8", "06"): "tjce",
    ("8", "07"): "tjdft",
    ("8", "08"): "tjes",
    ("8", "09"): "tjgo",
    ("8", "10"): "tjma",
    ("8", "11"): "tjmt",
    ("8", "12"): "tjms",
    ("8", "13"): "tjmg",
    ("8", "14"): "tjpa",
    ("8", "15"): "tjpb",
    ("8", "16"): "tjpr",
    ("8", "17"): "tjpe",
    ("8", "18"): "tjpi",
    ("8", "19"): "tjrj",
    ("8", "20"): "tjrn",
    ("8", "21"): "tjrs",
    ("8", "22"): "tjro",
    ("8", "23"): "tjrr",
    ("8", "24"): "tjsc",
    ("8", "25"): "tjse",
    ("8", "26"): "tjsp",
    ("8", "27"): "tjto",
}


def deduzir_tribunal_por_numero_cnj(numero_cnj: str) -> Optional[str]:
    """
    Deduz o índice do tribunal correspondente no DataJud
    a partir da estrutura oficial de numeração CNJ (20 dígitos).
    Estrutura: NNNNNNN-DD.AAAA.J.TR.OOOO -> dígitos 13 (J) e 14-15 (TR)
    """
    d = limpar_digitos(numero_cnj)
    if len(d) == 20:
        ramo = d[13]
        trib = d[14:16]
        return MAPA_RAMO_TR.get((ramo, trib))
    return None


class DataJudClient:
    """Cliente para interagir com a API Pública do DataJud."""

    def __init__(self, api_key: str = DEFAULT_API_KEY, timeout: int = 15):
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"APIKey {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Pomelo-Intelligence/1.0",
        })

    def consultar_processo(self, numero_processo: str, tribunal: Optional[str] = None) -> Optional[ProcessoJudicial]:
        """
        Consulta um processo pelo seu número CNJ único.
        Se a sigla do tribunal não for passada, tenta deduzir automaticamente pelo número CNJ.
        """
        d = limpar_digitos(numero_processo)
        sigla_tribunal = (tribunal or "").strip().lower()

        if not sigla_tribunal:
            sigla_tribunal = deduzir_tribunal_por_numero_cnj(d)

        if not sigla_tribunal:
            logger.warning(f"Não foi possível deduzir o tribunal para o processo {numero_processo}.")
            return None

        # Formato do endpoint: api_publica_{tribunal}/_search
        endpoint = f"{BASE_URL}/api_publica_{sigla_tribunal}/_search"
        payload = {
            "size": 1,
            "query": {
                "match": {
                    "numeroProcesso": d
                }
            }
        }

        try:
            res = self.session.post(endpoint, json=payload, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                hits = data.get("hits", {}).get("hits", [])
                if hits:
                    return self._parsear_hit(hits[0]["_source"])
                return None
            else:
                logger.error(f"Erro ao consultar DataJud ({res.status_code}): {res.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Exceção na consulta DataJud ({endpoint}): {e}")
            return None

    def _parsear_hit(self, src: Dict[str, Any]) -> ProcessoJudicial:
        """Converte o documento retornado pelo Elasticsearch do DataJud para a entidade ProcessoJudicial."""
        num_raw = str(src.get("numeroProcesso", ""))
        num_formatado = formatar_numero_processo_cnj(num_raw)
        tribunal = src.get("tribunal", "")
        grau = src.get("grau")

        classe_info = src.get("classe", {})
        classe_nome = classe_info.get("nome") if isinstance(classe_info, dict) else str(classe_info)

        orgao_info = src.get("orgaoJulgador", {})
        orgao_nome = orgao_info.get("nome") if isinstance(orgao_info, dict) else str(orgao_info)

        assuntos = []
        for ass in src.get("assuntos", []):
            if isinstance(ass, dict) and "nome" in ass:
                assuntos.append(ass["nome"])
            elif isinstance(ass, str):
                assuntos.append(ass)

        movimentos = []
        for mov in src.get("movimentos", []):
            if isinstance(mov, dict):
                movimentos.append(MovimentoProcessual(
                    codigo=mov.get("codigo"),
                    nome=mov.get("nome", ""),
                    data_hora=mov.get("dataHora"),
                    complemento=str(mov.get("complementosTabelados") or "")
                ))

        # Ordena movimentações por data decrescente se disponível
        movimentos.sort(key=lambda x: x.data_hora or "", reverse=True)

        return ProcessoJudicial(
            numero=num_raw,
            numero_formatado=num_formatado,
            tribunal=tribunal,
            grau=grau,
            classe=classe_nome,
            orgao_julgador=orgao_nome,
            data_ajuizamento=src.get("dataAjuizamento"),
            data_ultima_atualizacao=src.get("dataHoraUltimaAtualizacao"),
            assuntos=assuntos,
            movimentos=movimentos,
            origens=["DATAJUD"],
            link_consulta=None
        )
