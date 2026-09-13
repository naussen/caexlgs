"""
Cliente para a ComunicaAPI / Diário de Justiça Eletrônico Nacional (DJEN).
Permite consultas públicas abertas de processos por:
- Nome da Parte (Pessoa Física ou Razão Social Jurídica)
- Texto (Busca por CNPJ ou CPF formatados citados em intimações)
- Número de Processo
Extrai as partes (destinatários), qualificação de Polo (Ativo/Passivo) e Advogados.
"""
import logging
from typing import List, Dict, Any, Optional
import requests
import urllib3

from .validators import (
    limpar_digitos,
    formatar_numero_processo_cnj,
    formatar_cnpj,
    formatar_cpf,
    sanitizar_nome,
)
from .models import (
    ProcessoJudicial,
    ParteProcessual,
    AdvogadoProcessual,
    PoloProcessual,
    TipoDocumento,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("ComunicaClient")

BASE_URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"


class ComunicaClient:
    """Cliente para consultas ao Diário de Justiça Eletrônico Nacional (DJEN / ComunicaAPI)."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Pomelo-Intelligence/1.0",
            "Accept": "application/json",
        })

    def buscar_por_nome(self, nome: str, tribunal: Optional[str] = None, max_itens: int = 20) -> List[ProcessoJudicial]:
        """Busca processos no DJEN pelo nome da parte (Pessoa Física ou Razão Social)."""
        nome_limpo = sanitizar_nome(nome)
        if not nome_limpo:
            return []

        params: Dict[str, Any] = {
            "nomeParte": nome_limpo,
            "itensPorPagina": min(max_itens, 100),
            "pagina": 1,
        }
        if tribunal:
            params["siglaTribunal"] = tribunal.strip().upper()

        return self._executar_busca(params)

    def buscar_por_documento(self, doc: str, tribunal: Optional[str] = None, max_itens: int = 20) -> List[ProcessoJudicial]:
        """
        Busca processos no DJEN buscando o CNPJ ou CPF formatado dentro do texto
        das publicações e intimações judiciais.
        """
        d = limpar_digitos(doc)
        if len(d) == 14:
            doc_formatado = formatar_cnpj(d)
        elif len(d) == 11:
            doc_formatado = formatar_cpf(d)
        else:
            return []

        params: Dict[str, Any] = {
            "texto": doc_formatado,
            "itensPorPagina": min(max_itens, 100),
            "pagina": 1,
        }
        if tribunal:
            params["siglaTribunal"] = tribunal.strip().upper()

        resultados = self._executar_busca(params)

        # Se não encontrou resultados pelo documento formatado, tenta com dígitos puros
        if not resultados:
            params["texto"] = d
            resultados = self._executar_busca(params)

        return resultados

    def buscar_por_processo(self, numero_processo: str) -> List[ProcessoJudicial]:
        """Busca todas as comunicações e partes de um número de processo específico."""
        d = limpar_digitos(numero_processo)
        if not d:
            return []

        params = {
            "numeroProcesso": d,
            "itensPorPagina": 50,
            "pagina": 1,
        }
        return self._executar_busca(params)

    def _executar_busca(self, params: Dict[str, Any]) -> List[ProcessoJudicial]:
        """Executa a requisição HTTP e agrupa os itens por processo judicial."""
        try:
            res = self.session.get(BASE_URL, params=params, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                items = data.get("items", [])
                return self._agrupar_por_processo(items)
            else:
                logger.error(f"Erro na consulta DJEN ({res.status_code}): {res.text[:200]}")
                return []
        except Exception as e:
            logger.error(f"Exceção na consulta DJEN: {e}")
            return []

    def _agrupar_por_processo(self, items: List[Dict[str, Any]]) -> List[ProcessoJudicial]:
        """
        Agrupa múltiplas publicações que pertencem ao mesmo processo judicial,
        consolidando suas partes, advogados, classe e órgão julgador.
        """
        processos_map: Dict[str, ProcessoJudicial] = {}

        for it in items:
            raw_num = str(it.get("numero_processo") or "")
            if not raw_num:
                continue

            num_clean = limpar_digitos(raw_num)
            num_formatado = it.get("numeroprocessocommascara") or formatar_numero_processo_cnj(num_clean)
            tribunal = str(it.get("siglaTribunal") or "").upper()
            classe = it.get("nomeClasse")
            orgao = it.get("nomeOrgao")
            data_disp = it.get("data_disponibilizacao")
            link = it.get("link")

            if num_clean not in processos_map:
                processos_map[num_clean] = ProcessoJudicial(
                    numero=num_clean,
                    numero_formatado=num_formatado,
                    tribunal=tribunal,
                    classe=classe,
                    orgao_julgador=orgao,
                    data_ultima_atualizacao=data_disp,
                    origens=["DJEN"],
                    link_consulta=link,
                    partes=[],
                )

            proc = processos_map[num_clean]
            if not proc.classe and classe:
                proc.classe = classe
            if not proc.orgao_julgador and orgao:
                proc.orgao_julgador = orgao
            if data_disp and (not proc.data_ultima_atualizacao or data_disp > proc.data_ultima_atualizacao):
                proc.data_ultima_atualizacao = data_disp

            # Extração de advogados
            advogados_map: Dict[str, AdvogadoProcessual] = {}
            for adv_raw in it.get("destinatarioadvogados", []):
                adv_info = adv_raw.get("advogado", {})
                adv_nome = sanitizar_nome(adv_info.get("nome"))
                if adv_nome:
                    advogados_map[adv_nome] = AdvogadoProcessual(
                        nome=adv_nome,
                        numero_oab=adv_info.get("numero_oab"),
                        uf_oab=adv_info.get("uf_oab"),
                    )

            # Extração de destinatários / partes
            for dest in it.get("destinatarios", []):
                nome_parte = sanitizar_nome(dest.get("nome"))
                if not nome_parte:
                    continue

                polo = PoloProcessual.normalizar(dest.get("polo"))

                # Evita partes duplicadas no mesmo processo
                existente = next((p for p in proc.partes if p.nome == nome_parte), None)
                if not existente:
                    # Tenta inferir se é PJ ou PF pelo nome
                    termos_pj = ["LTDA", "S.A.", "S/A", "SA", "ME", "EPP", "EIRELI", "BANCO", "CIA", "COMPANHIA", "INSTITUTO"]
                    tipo_doc = TipoDocumento.CNPJ if any(t in nome_parte.split() for t in termos_pj) else TipoDocumento.OUTRO

                    proc.partes.append(ParteProcessual(
                        nome=nome_parte,
                        polo=polo,
                        tipo_documento=tipo_doc,
                        papel="AUTOR" if polo == PoloProcessual.ATIVO else ("REU" if polo == PoloProcessual.PASSIVO else "PARTE"),
                        advogados=list(advogados_map.values()),
                    ))
                else:
                    if existente.polo == PoloProcessual.DESCONHECIDO and polo != PoloProcessual.DESCONHECIDO:
                        existente.polo = polo
                    for adv in advogados_map.values():
                        if not any(a.nome == adv.nome for a in existente.advogados):
                            existente.advogados.append(adv)

        return list(processos_map.values())
