"""
Motor de Vinculação e Relacionamento Bidirecional: Documento (CPF / CNPJ) ↔ Processos Judiciais.
Permite registrar, indexar, consultar e exportar associações entre pessoas físicas,
empresas e ações judiciais, com qualificação de polo (Autor vs Réu).
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .validators import (
    limpar_digitos,
    formatar_cpf,
    formatar_cnpj,
    identificar_tipo_documento,
    formatar_numero_processo_cnj,
    sanitizar_nome,
)
from .models import VinculoProcessual, ProcessoJudicial, PoloProcessual, TipoDocumento

logger = logging.getLogger("VinculadorProcessual")


class VinculadorProcessual:
    """Gerencia a indexação e busca bidirecional de vínculos Documento ↔ Processo."""

    def __init__(self):
        # Mapeamento documento_limpo -> Lista de VinculoProcessual
        self._doc_para_vinculos: Dict[str, List[VinculoProcessual]] = {}
        # Mapeamento numero_processo_limpo -> Lista de VinculoProcessual
        self._proc_para_vinculos: Dict[str, List[VinculoProcessual]] = {}

    def vincular(
        self,
        documento: str,
        nome_parte: str,
        processo: ProcessoJudicial,
        polo: Optional[PoloProcessual] = None,
        papel: Optional[str] = None,
        fonte: str = "DATAJUD",
        confianca: float = 1.0,
    ) -> VinculoProcessual:
        """Cria e registra o vínculo bidirecional entre um Documento (CPF/CNPJ) e um Processo."""
        doc_clean = limpar_digitos(documento)
        tipo_str = identificar_tipo_documento(doc_clean)

        if tipo_str == "CPF":
            tipo_enum = TipoDocumento.CPF
            doc_formatado = formatar_cpf(doc_clean)
        elif tipo_str == "CNPJ":
            tipo_enum = TipoDocumento.CNPJ
            doc_formatado = formatar_cnpj(doc_clean)
        else:
            tipo_enum = TipoDocumento.OUTRO
            doc_formatado = doc_clean

        proc_clean = limpar_digitos(processo.numero)
        proc_formatado = processo.numero_formatado or formatar_numero_processo_cnj(proc_clean)

        # Se o polo não for fornecido explicitamente, tenta deduzir da lista de partes do processo
        polo_final = polo or PoloProcessual.DESCONHECIDO
        nome_sanitizado = sanitizar_nome(nome_parte)

        if polo_final == PoloProcessual.DESCONHECIDO and nome_sanitizado:
            for p in processo.partes:
                if sanitizar_nome(p.nome) == nome_sanitizado:
                    polo_final = p.polo
                    break

        papel_final = papel or ("AUTOR" if polo_final == PoloProcessual.ATIVO else ("REU" if polo_final == PoloProcessual.PASSIVO else "PARTE"))

        vinculo = VinculoProcessual(
            documento=doc_clean,
            documento_formatado=doc_formatado,
            tipo_documento=tipo_enum,
            nome_parte=nome_sanitizado,
            numero_processo=proc_clean,
            numero_formatado=proc_formatado,
            tribunal=processo.tribunal,
            polo=polo_final,
            papel=papel_final,
            data_vinculo=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            fonte=fonte,
            confianca=confianca,
        )

        # Indexa no mapa de documento
        if doc_clean not in self._doc_para_vinculos:
            self._doc_para_vinculos[doc_clean] = []

        # Evita duplicação do mesmo processo no mesmo documento
        existentes_doc = self._doc_para_vinculos[doc_clean]
        if not any(v.numero_processo == proc_clean for v in existentes_doc):
            existentes_doc.append(vinculo)

        # Indexa no mapa de processo
        if proc_clean not in self._proc_para_vinculos:
            self._proc_para_vinculos[proc_clean] = []

        existentes_proc = self._proc_para_vinculos[proc_clean]
        if not any(v.documento == doc_clean for v in existentes_proc):
            existentes_proc.append(vinculo)

        return vinculo

    def obter_processos_por_documento(self, documento: str) -> List[VinculoProcessual]:
        """Retorna todos os vínculos/processos associados a um determinado CPF ou CNPJ."""
        doc_clean = limpar_digitos(documento)
        return self._doc_para_vinculos.get(doc_clean, [])

    def obter_documentos_por_processo(self, numero_processo: str) -> List[VinculoProcessual]:
        """Retorna todas as partes/documentos vinculados a um determinado processo judicial."""
        proc_clean = limpar_digitos(numero_processo)
        return self._proc_para_vinculos.get(proc_clean, [])

    def gerar_resumo_estatistico(self, documento: str) -> Dict[str, Any]:
        """Gera resumo quantitativo de processos por polo e tribunal para análise de risco."""
        vinculos = self.obter_processos_por_documento(documento)
        total = len(vinculos)
        como_autor = sum(1 for v in vinculos if v.polo == PoloProcessual.ATIVO)
        como_reu = sum(1 for v in vinculos if v.polo == PoloProcessual.PASSIVO)
        outros = total - (como_autor + como_reu)

        tribunais_count: Dict[str, int] = {}
        for v in vinculos:
            trib = v.tribunal or "DESCONHECIDO"
            tribunais_count[trib] = tribunais_count.get(trib, 0) + 1

        return {
            "total_processos": total,
            "como_autor": como_autor,
            "como_reu": como_reu,
            "outros_polos": outros,
            "distribuicao_tribunais": tribunais_count,
        }

    def exportar_para_dict(self) -> Dict[str, Any]:
        """Exporta todo o repositório de vínculos para estrutura serializável em JSON."""
        return {
            doc: [v.to_dict() for v in lista]
            for doc, lista in self._doc_para_vinculos.items()
        }

    def importar_de_dict(self, dados: Dict[str, Any]):
        """Restaura vínculos de um estado serializado."""
        for doc, lista in dados.items():
            for d in lista:
                vinculo = VinculoProcessual(
                    documento=d["documento"],
                    documento_formatado=d["documento_formatado"],
                    tipo_documento=TipoDocumento(d["tipo_documento"]),
                    nome_parte=d["nome_parte"],
                    numero_processo=d["numero_processo"],
                    numero_formatado=d["numero_formatado"],
                    tribunal=d["tribunal"],
                    polo=PoloProcessual(d["polo"]),
                    papel=d["papel"],
                    data_vinculo=d.get("data_vinculo"),
                    fonte=d.get("fonte", "DATAJUD"),
                    confianca=float(d.get("confianca", 1.0)),
                )
                if vinculo.documento not in self._doc_para_vinculos:
                    self._doc_para_vinculos[vinculo.documento] = []
                self._doc_para_vinculos[vinculo.documento].append(vinculo)

                if vinculo.numero_processo not in self._proc_para_vinculos:
                    self._proc_para_vinculos[vinculo.numero_processo] = []
                self._proc_para_vinculos[vinculo.numero_processo].append(vinculo)
