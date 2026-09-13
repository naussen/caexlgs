"""
Serviço Orquestrador de Busca e Inteligência Judicial (JudicialSearchService).
Unifica as consultas ao DataJud (CNJ) e ComunicaAPI/DJEN, promovendo o enriquecimento cruzado,
a validação de documentos (CPF e CNPJ) e a vinculação automática das partes aos processos.
"""
import logging
from typing import List, Optional, Dict, Any

from .validators import (
    limpar_digitos,
    validar_cpf,
    validar_cnpj,
    identificar_tipo_documento,
    sanitizar_nome,
)
from .models import ProcessoJudicial, VinculoProcessual, PoloProcessual, TipoDocumento
from .datajud_client import DataJudClient
from .comunica_client import ComunicaClient
from .vinculador import VinculadorProcessual

logger = logging.getLogger("JudicialSearchService")


class JudicialSearchService:
    """Fachada unificada para busca e enriquecimento de dados processuais."""

    def __init__(
        self,
        datajud_client: Optional[DataJudClient] = None,
        comunica_client: Optional[ComunicaClient] = None,
        vinculador: Optional[VinculadorProcessual] = None,
    ):
        self.datajud = datajud_client or DataJudClient()
        self.comunica = comunica_client or ComunicaClient()
        self.vinculador = vinculador or VinculadorProcessual()

    def consultar_por_cnpj(
        self,
        cnpj: str,
        razao_social: Optional[str] = None,
        max_itens: int = 20,
        enriquecer_datajud: bool = True,
    ) -> List[ProcessoJudicial]:
        """
        Executa consulta completa de processos para um CNPJ:
        1. Valida o formato e os dígitos do CNPJ.
        2. Busca citações no DJEN pelo CNPJ formatado/numérico.
        3. Se informada a Razão Social, busca adicionalmente por nome da parte.
        4. Consolida e deduplica os processos encontrados.
        5. Opcionalmente enriquece com metadados do DataJud (movimentações, vara, classe).
        6. Registra as vinculações no motor de relacionamentos.
        """
        cnpj_limpo = limpar_digitos(cnpj)
        if not validar_cnpj(cnpj_limpo):
            logger.warning(f"CNPJ inválido fornecido: {cnpj}")
            return []

        processos_encontrados: Dict[str, ProcessoJudicial] = {}

        # 1. Busca por texto do documento
        procs_doc = self.comunica.buscar_por_documento(cnpj_limpo, max_itens=max_itens)
        for p in procs_doc:
            processos_encontrados[p.numero] = p

        # 2. Busca pela Razão Social (se disponível e não atingiu o limite)
        if razao_social and len(processos_encontrados) < max_itens:
            procs_nome = self.comunica.buscar_por_nome(razao_social, max_itens=max_itens)
            for p in procs_nome:
                if p.numero not in processos_encontrados:
                    processos_encontrados[p.numero] = p

        lista_final = list(processos_encontrados.values())[:max_itens]

        # 3. Enriquecimento no DataJud e Vinculação
        return self._processar_e_vincular(
            lista_final,
            documento=cnpj_limpo,
            nome_parte=razao_social or f"CNPJ {cnpj_limpo}",
            enriquecer_datajud=enriquecer_datajud,
        )

    def consultar_por_cpf(
        self,
        cpf: str,
        nome: Optional[str] = None,
        max_itens: int = 20,
        enriquecer_datajud: bool = True,
    ) -> List[ProcessoJudicial]:
        """
        Executa consulta de processos para uma Pessoa Física por CPF:
        1. Valida os dígitos verificadores do CPF.
        2. Busca no DJEN pelo documento e opcionalmente pelo nome da pessoa.
        3. Enriquece os dados via DataJud.
        4. Registra o vínculo CPF ↔ Processo.
        """
        cpf_limpo = limpar_digitos(cpf)
        if not validar_cpf(cpf_limpo):
            logger.warning(f"CPF inválido fornecido: {cpf}")
            return []

        processos_encontrados: Dict[str, ProcessoJudicial] = {}

        # 1. Busca pelo documento
        procs_doc = self.comunica.buscar_por_documento(cpf_limpo, max_itens=max_itens)
        for p in procs_doc:
            processos_encontrados[p.numero] = p

        # 2. Busca por nome se informado
        if nome and len(processos_encontrados) < max_itens:
            procs_nome = self.comunica.buscar_por_nome(nome, max_itens=max_itens)
            for p in procs_nome:
                if p.numero not in processos_encontrados:
                    processos_encontrados[p.numero] = p

        lista_final = list(processos_encontrados.values())[:max_itens]

        return self._processar_e_vincular(
            lista_final,
            documento=cpf_limpo,
            nome_parte=nome or f"CPF {cpf_limpo}",
            enriquecer_datajud=enriquecer_datajud,
        )

    def consultar_por_nome(
        self,
        nome: str,
        tribunal: Optional[str] = None,
        max_itens: int = 20,
        enriquecer_datajud: bool = True,
    ) -> List[ProcessoJudicial]:
        """
        Busca processos exclusivamente pelo nome (Pessoa Física ou Razão Social).
        """
        nome_sanitizado = sanitizar_nome(nome)
        if not nome_sanitizado:
            return []

        processos = self.comunica.buscar_por_nome(nome_sanitizado, tribunal=tribunal, max_itens=max_itens)
        return self._processar_e_vincular(
            processos,
            documento=None,
            nome_parte=nome_sanitizado,
            enriquecer_datajud=enriquecer_datajud,
        )

    def consultar_por_processo(
        self,
        numero_processo: str,
        tribunal: Optional[str] = None,
    ) -> Optional[ProcessoJudicial]:
        """
        Busca detalhada 360º de um único processo:
        Cruza informações do DataJud (metadados de movimentações e capa)
        com informações do DJEN (destinatários, advogados e comunicações).
        """
        num_clean = limpar_digitos(numero_processo)
        if not num_clean:
            return None

        # 1. Consulta no DataJud
        proc_datajud = self.datajud.consultar_processo(num_clean, tribunal=tribunal)

        # 2. Consulta no DJEN
        procs_djen = self.comunica.buscar_por_processo(num_clean)
        proc_djen = procs_djen[0] if procs_djen else None

        if not proc_datajud and not proc_djen:
            return None

        # Mescla os dados
        if proc_datajud and proc_djen:
            proc_datajud.partes = proc_djen.partes
            proc_datajud.link_consulta = proc_djen.link_consulta
            if "DJEN" not in proc_datajud.origens:
                proc_datajud.origens.append("DJEN")
            return proc_datajud

        return proc_datajud or proc_djen

    def obter_vinculos_documento(self, documento: str) -> List[VinculoProcessual]:
        """Retorna todos os vínculos de um determinado documento no repositório."""
        return self.vinculador.obter_processos_por_documento(documento)

    def obter_estatisticas_documento(self, documento: str) -> Dict[str, Any]:
        """Retorna resumo estatístico de ações judiciais para análise de risco e compliance."""
        return self.vinculador.gerar_resumo_estatistico(documento)

    def _processar_e_vincular(
        self,
        processos: List[ProcessoJudicial],
        documento: Optional[str],
        nome_parte: str,
        enriquecer_datajud: bool,
    ) -> List[ProcessoJudicial]:
        """Enriquece processos com DataJud e registra os vínculos."""
        resultado: List[ProcessoJudicial] = []

        for p in processos:
            # Tenta enriquecer com DataJud se solicitado
            if enriquecer_datajud and len(p.movimentos) == 0:
                try:
                    p_dj = self.datajud.consultar_processo(p.numero, tribunal=p.tribunal)
                    if p_dj:
                        p.movimentos = p_dj.movimentos
                        p.data_ajuizamento = p_dj.data_ajuizamento
                        if not p.classe and p_dj.classe:
                            p.classe = p_dj.classe
                        if not p.orgao_julgador and p_dj.orgao_julgador:
                            p.orgao_julgador = p_dj.orgao_julgador
                        if "DATAJUD" not in p.origens:
                            p.origens.append("DATAJUD")
                except Exception as e:
                    logger.debug(f"Não foi possível enriquecer processo {p.numero} no DataJud: {e}")

            # Se houver documento informado, registra o vínculo
            if documento:
                # Localiza o polo da parte dentro do processo
                polo = None
                nome_norm = sanitizar_nome(nome_parte)
                for parte in p.partes:
                    if sanitizar_nome(parte.nome) == nome_norm:
                        polo = parte.polo
                        break

                self.vinculador.vincular(
                    documento=documento,
                    nome_parte=nome_parte,
                    processo=p,
                    polo=polo,
                    fonte=",".join(p.origens),
                )

            resultado.append(p)

        return resultado
