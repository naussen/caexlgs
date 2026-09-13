"""
Módulo de Validação e Normalização de Documentos e Nomes para Inteligência Processual.
Fornece validação estrita com dígitos verificadores (CPF e CNPJ),
formatação padronizada e higienização de strings para consultas judiciais.
"""
import re
import unicodedata
from typing import Optional, Tuple


def limpar_digitos(valor: Optional[str]) -> str:
    """Remove qualquer caractere não numérico da string."""
    if not valor:
        return ""
    return re.sub(r"\D", "", str(valor))


def validar_cpf(cpf: Optional[str]) -> bool:
    """
    Valida um CPF brasileiro através do cálculo dos dois dígitos verificadores (Módulo 11).
    Rejeita sequências repetidas conhecidas (ex.: '111.111.111-11').
    """
    digitos = limpar_digitos(cpf)
    if len(digitos) != 11:
        return False
    if digitos == digitos[0] * 11:
        return False

    # Primeiro dígito verificador
    soma = sum(int(digitos[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    if int(digitos[9]) != d1:
        return False

    # Segundo dígito verificador
    soma = sum(int(digitos[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    return int(digitos[10]) == d2


def validar_cnpj(cnpj: Optional[str]) -> bool:
    """
    Valida um CNPJ brasileiro através do cálculo dos dígitos verificadores (Módulo 11).
    Rejeita sequências com tamanho incorreto ou repetidas.
    """
    digitos = limpar_digitos(cnpj)
    if len(digitos) != 14:
        return False
    if digitos == digitos[0] * 14:
        return False

    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_1 = sum(int(digitos[i]) * pesos_1[i] for i in range(12))
    resto_1 = soma_1 % 11
    d1 = 0 if resto_1 < 2 else 11 - resto_1
    if int(digitos[12]) != d1:
        return False

    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_2 = sum(int(digitos[i]) * pesos_2[i] for i in range(13))
    resto_2 = soma_2 % 11
    d2 = 0 if resto_2 < 2 else 11 - resto_2
    return int(digitos[13]) == d2


def formatar_cpf(cpf: str) -> str:
    """Formata 11 dígitos no padrão XXX.XXX.XXX-XX."""
    d = limpar_digitos(cpf).zfill(11)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def formatar_cnpj(cnpj: str) -> str:
    """Formata 14 dígitos no padrão XX.XXX.XXX/YYYY-ZZ."""
    d = limpar_digitos(cnpj).zfill(14)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def identificar_tipo_documento(doc: Optional[str]) -> str:
    """
    Identifica o tipo de documento com base no comprimento dos dígitos:
    Retorna 'CPF', 'CNPJ' ou 'INVALIDO'.
    """
    d = limpar_digitos(doc)
    if len(d) == 11 and validar_cpf(d):
        return "CPF"
    if len(d) == 14 and validar_cnpj(d):
        return "CNPJ"
    return "INVALIDO"


def sanitizar_nome(nome: Optional[str]) -> str:
    """
    Normaliza nome de pessoa física ou razão social:
    Remove acentuação, caracteres especiais extras e normaliza espaçamentos.
    """
    if not nome:
        return ""
    # Remove acentos
    texto = unicodedata.normalize("NFKD", str(nome))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Remove caracteres estranhos mas mantém letras, números e espaços
    texto = re.sub(r"[^\w\s\-&.]", " ", texto)
    # Compacta múltiplos espaços em branco e deixa em caixa alta
    texto = re.sub(r"\s+", " ", texto).strip().upper()
    return texto


def formatar_numero_processo_cnj(numero: Optional[str]) -> str:
    """
    Formata número único CNJ de 20 dígitos no formato:
    NNNNNNN-DD.AAAA.J.TR.OOOO
    """
    d = limpar_digitos(numero)
    if len(d) == 20:
        return f"{d[0:7]}-{d[7:9]}.{d[9:13]}.{d[13:14]}.{d[14:16]}.{d[16:20]}"
    return str(numero or "").strip()


def formatar_cnae(cnae_str: Optional[str]) -> str:
    """Formata CNAE de 7 dígitos para 0000-0/00."""
    d = limpar_digitos(cnae_str)
    if len(d) == 7:
        return f"{d[:4]}-{d[4]}/{d[5:]}"
    return str(cnae_str or "").strip()


def obter_cnae_completo(cnae_cod: Optional[str], cnae_desc: Optional[str] = "") -> Tuple[str, str]:
    """
    Retorna tupla (cnae_formatado, cnae_descricao_oficial).
    Formata o código CNAE (ex: 9312-3/00) e enriquece a descrição textual
    consultando a API pública do IBGE se estiver ausente ou puramente numérica.
    """
    import urllib.request
    import json

    cnae_fmt = formatar_cnae(cnae_cod)
    cnae_limpo = limpar_digitos(cnae_cod)

    desc_atual = str(cnae_desc or "").strip()
    if desc_atual and not desc_atual.isdigit() and len(desc_atual) > 3 and desc_atual.lower() != "não informada":
        return cnae_fmt, desc_atual

    if cnae_limpo:
        try:
            url = f"https://servicodados.ibge.gov.br/api/v2/cnae/subclasses/{cnae_limpo}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict) and "descricao" in data:
                    return cnae_fmt, str(data["descricao"]).strip().upper()
        except Exception:
            pass

    return cnae_fmt, desc_atual or "Atividade econômica não informada"

