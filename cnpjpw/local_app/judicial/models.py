"""
Modelos de Dados para Gestão de Processos Judiciais e Vinculação Documental.
Estruturas imutáveis e fortemente tipadas seguindo padrões de Clean Architecture.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class PoloProcessual(str, Enum):
    ATIVO = "ATIVO"              # Autor, Exequente, Requerente
    PASSIVO = "PASSIVO"          # Réu, Executado, Requerido
    TERCEIRO = "TERCEIRO"        # Testemunha, Perito, Interessado
    OUTROS = "OUTROS"
    DESCONHECIDO = "DESCONHECIDO"

    @classmethod
    def normalizar(cls, valor: Optional[str]) -> "PoloProcessual":
        if not valor:
            return cls.DESCONHECIDO
        v = valor.strip().upper()
        if v in ("A", "AT", "ATIVO", "AUTOR", "EXEQUENTE", "REQUERENTE"):
            return cls.ATIVO
        if v in ("P", "PA", "PASSIVO", "REU", "EXECUTADO", "REQUERIDO"):
            return cls.PASSIVO
        if v in ("T", "TERCEIRO", "INTERESSADO"):
            return cls.TERCEIRO
        return cls.OUTROS


class TipoDocumento(str, Enum):
    CPF = "CPF"
    CNPJ = "CNPJ"
    OUTRO = "OUTRO"


@dataclass
class AdvogadoProcessual:
    nome: str
    numero_oab: Optional[str] = None
    uf_oab: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParteProcessual:
    nome: str
    documento: Optional[str] = None
    tipo_documento: TipoDocumento = TipoDocumento.OUTRO
    polo: PoloProcessual = PoloProcessual.DESCONHECIDO
    papel: Optional[str] = None
    advogados: List[AdvogadoProcessual] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nome": self.nome,
            "documento": self.documento,
            "tipo_documento": self.tipo_documento.value,
            "polo": self.polo.value,
            "papel": self.papel,
            "advogados": [adv.to_dict() for adv in self.advogados],
        }


@dataclass
class MovimentoProcessual:
    codigo: Optional[int]
    nome: str
    data_hora: Optional[str] = None
    complemento: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessoJudicial:
    numero: str
    numero_formatado: str
    tribunal: str
    grau: Optional[str] = None
    classe: Optional[str] = None
    orgao_julgador: Optional[str] = None
    data_ajuizamento: Optional[str] = None
    data_ultima_atualizacao: Optional[str] = None
    assuntos: List[str] = field(default_factory=list)
    partes: List[ParteProcessual] = field(default_factory=list)
    movimentos: List[MovimentoProcessual] = field(default_factory=list)
    origens: List[str] = field(default_factory=list)
    link_consulta: Optional[str] = None

    @property
    def polo_ativo(self) -> List[ParteProcessual]:
        return [p for p in self.partes if p.polo == PoloProcessual.ATIVO]

    @property
    def polo_passivo(self) -> List[ParteProcessual]:
        return [p for p in self.partes if p.polo == PoloProcessual.PASSIVO]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "numero": self.numero,
            "numero_formatado": self.numero_formatado,
            "tribunal": self.tribunal,
            "grau": self.grau,
            "classe": self.classe,
            "orgao_julgador": self.orgao_julgador,
            "data_ajuizamento": self.data_ajuizamento,
            "data_ultima_atualizacao": self.data_ultima_atualizacao,
            "assuntos": self.assuntos,
            "partes": [p.to_dict() for p in self.partes],
            "movimentos": [m.to_dict() for m in self.movimentos],
            "origens": self.origens,
            "link_consulta": self.link_consulta,
        }


@dataclass
class VinculoProcessual:
    """
    Representa a associação qualificada entre um Documento (CPF ou CNPJ) / Nome
    e um Processo Judicial específico.
    """
    documento: str
    documento_formatado: str
    tipo_documento: TipoDocumento
    nome_parte: str
    numero_processo: str
    numero_formatado: str
    tribunal: str
    polo: PoloProcessual
    papel: str
    data_vinculo: Optional[str] = None
    fonte: str = "DATAJUD"
    confianca: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "documento": self.documento,
            "documento_formatado": self.documento_formatado,
            "tipo_documento": self.tipo_documento.value,
            "nome_parte": self.nome_parte,
            "numero_processo": self.numero_processo,
            "numero_formatado": self.numero_formatado,
            "tribunal": self.tribunal,
            "polo": self.polo.value,
            "papel": self.papel,
            "data_vinculo": self.data_vinculo,
            "fonte": self.fonte,
            "confianca": self.confianca,
        }
