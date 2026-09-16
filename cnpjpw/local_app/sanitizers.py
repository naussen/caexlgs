"""
sanitizers.py — Módulo de sanitização e adequação automática de dados de entrada.

Implementa regras de conversão e normalização para:
- CNPJ e CPF (remoção automática de pontuação e máscaras).
- Telefones e celulares brasileiros:
  - Adiciona o 9º dígito antes de números de celular de 8 dígitos.
  - Se tiver 10 dígitos e for celular: 2 primeiros são DDD e adiciona 9 antes dos 8 restantes.
  - Se tiver 11 dígitos: 2 primeiros são DDD e os 9 restantes são o número.
"""

import re
from typing import Dict, Any, Optional, Tuple


def adequar_documento(doc: Any) -> str:
    """
    Adequa a entrada de CNPJ ou CPF para o formato esperado pelo sistema (somente dígitos).
    
    Exemplos:
    - '21.807.980/0001-09' -> '21807980000109'
    - ' 123.456.789-01 '  -> '12345678901'
    - '21807980000109'     -> '21807980000109'
    - '***807980**'        -> '***807980**' (preserva máscara parcial da Receita para sócios)
    """
    if doc is None:
        return ""
    
    s = str(doc).strip()
    if not s:
        return ""

    # Se contém asteriscos (máscara de sigilo de sócio da Receita Federal)
    if "*" in s:
        # Remove apenas pontos, traços, barras e espaços
        return re.sub(r"[\.\-\/\s]", "", s)

    # Para entradas normais de CNPJ ou CPF: extrai estritamente os dígitos
    return "".join(c for c in s if c.isdigit())


def is_celular_prefixo(numero_8_digitos: str) -> bool:
    """
    Verifica se um número local brasileiro de 8 dígitos corresponde à faixa de celular móvel.
    No plano de numeração da Anatel:
    - Telefones fixos (STFC) iniciam com 2, 3, 4 ou 5.
    - Telefones celulares (SMP) de 8 dígitos iniciam tradicionalmente com 6, 7, 8 ou 9.
    """
    if not numero_8_digitos or len(numero_8_digitos) != 8:
        return False
    return numero_8_digitos[0] in ("6", "7", "8", "9")


def adequar_telefone(tel: Any, default_ddd: str = "") -> Dict[str, Any]:
    """
    Higieniza e adequa números de telefone segundo as regras da telefonia brasileira:
    
    1. Celular com 8 dígitos:
       - Se for celular (inicia com 6, 7, 8 ou 9), adiciona '9' na frente -> 9 dígitos.
    2. Telefone com 10 dígitos:
       - Primeiros 2 dígitos são o DDD.
       - Se os 8 restantes forem celular (iniciando com 6, 7, 8 ou 9), adiciona '9' antes do restante.
       - Se os 8 restantes forem fixo (iniciando com 2, 3, 4 ou 5), mantém os 8 dígitos.
    3. Celular com 11 dígitos:
       - Primeiros 2 dígitos são o DDD e os 9 restantes são o número.
       
    Retorna dicionário com:
      - raw: entrada original
      - digits: somente dígitos extraídos (sem prefixo DDI +55 se presente)
      - ddd: DDD com 2 dígitos (ou default_ddd se fornecido e aplicável)
      - numero: número do telefone ajustado (com 8 ou 9 dígitos)
      - numero_original_8: versão de 8 dígitos correspondente se era celular (para busca retroativa)
      - telefone_completo: DDD + número
      - tipo: 'CELULAR' | 'FIXO' | 'DESCONHECIDO'
      - valido: True se possui DDD (2 dígitos) e número válido (8 ou 9 dígitos)
      - ajuste_realizado: descrição amigável de eventuais conversões feitas
    """
    raw_str = str(tel or "").strip()
    result = {
        "raw": raw_str,
        "digits": "",
        "ddd": "",
        "numero": "",
        "numero_original_8": "",
        "telefone_completo": "",
        "tipo": "DESCONHECIDO",
        "valido": False,
        "ajuste_realizado": None,
        "erro": None
    }

    if not raw_str:
        result["erro"] = "Telefone não informado."
        return result

    # Extrai apenas dígitos
    digits = "".join(c for c in raw_str if c.isdigit())

    # Trata DDI 55 (Brasil) se inserido com 12 ou 13 dígitos (+55 11 98765-4321 / +55 11 8765-4321)
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    result["digits"] = digits
    num_digits = len(digits)

    # Caso 1: 11 Dígitos (DDD + 9 dígitos de celular)
    if num_digits == 11:
        ddd = digits[:2]
        numero = digits[2:]
        result["ddd"] = ddd
        result["numero"] = numero
        result["telefone_completo"] = ddd + numero
        result["tipo"] = "CELULAR" if numero.startswith("9") else "DESCONHECIDO"
        if numero.startswith("9"):
            # Guarda a versão de 8 dígitos para buscas retroativas em bases antigas
            result["numero_original_8"] = numero[1:]
        result["valido"] = _validar_ddd(ddd)
        return result

    # Caso 2: 10 Dígitos (DDD + 8 dígitos)
    elif num_digits == 10:
        ddd = digits[:2]
        restante = digits[2:]
        result["ddd"] = ddd
        
        if is_celular_prefixo(restante):
            # Celular de 10 dígitos (DDD + 8 dígitos): adiciona 9 antes do restante
            numero_ajustado = "9" + restante
            result["numero"] = numero_ajustado
            result["numero_original_8"] = restante
            result["telefone_completo"] = ddd + numero_ajustado
            result["tipo"] = "CELULAR"
            result["ajuste_realizado"] = f"Adicionado 9º dígito ao celular: ({ddd}) {numero_ajustado}"
        else:
            # Telefone fixo (inicia com 2, 3, 4, 5)
            result["numero"] = restante
            result["telefone_completo"] = ddd + restante
            result["tipo"] = "FIXO"

        result["valido"] = _validar_ddd(ddd)
        return result

    # Caso 3: 8 Dígitos (Sem DDD informado)
    elif num_digits == 8:
        ddd_fallback = "".join(c for c in str(default_ddd or "") if c.isdigit())[:2]
        if is_celular_prefixo(digits):
            numero_ajustado = "9" + digits
            result["numero"] = numero_ajustado
            result["numero_original_8"] = digits
            result["tipo"] = "CELULAR"
            result["ajuste_realizado"] = f"Adicionado 9º dígito: {numero_ajustado}"
        else:
            result["numero"] = digits
            result["tipo"] = "FIXO"

        if ddd_fallback and _validar_ddd(ddd_fallback):
            result["ddd"] = ddd_fallback
            result["telefone_completo"] = ddd_fallback + result["numero"]
            result["valido"] = True
        else:
            result["telefone_completo"] = result["numero"]
            result["valido"] = False
            result["erro"] = "DDD não informado (são necessários 2 dígitos de DDD)."
        return result

    # Caso 4: 9 Dígitos (Número móvel de 9 dígitos sem DDD)
    elif num_digits == 9:
        ddd_fallback = "".join(c for c in str(default_ddd or "") if c.isdigit())[:2]
        result["numero"] = digits
        if digits.startswith("9"):
            result["tipo"] = "CELULAR"
            result["numero_original_8"] = digits[1:]
        
        if ddd_fallback and _validar_ddd(ddd_fallback):
            result["ddd"] = ddd_fallback
            result["telefone_completo"] = ddd_fallback + digits
            result["valido"] = True
        else:
            result["telefone_completo"] = digits
            result["valido"] = False
            result["erro"] = "DDD não informado (são necessários 2 dígitos de DDD)."
        return result

    else:
        result["erro"] = f"Tamanho de telefone não reconhecido ({num_digits} dígitos). Esperado DDD + número (10 ou 11 dígitos)."
        return result


def _validar_ddd(ddd: str) -> bool:
    """Valida se o DDD brasileiro é composto por 2 dígitos numéricos válidos (11 a 99)."""
    if len(ddd) != 2 or not ddd.isdigit():
        return False
    # No Brasil, DDDs válidos são entre 11 e 99 (primeiro dígito entre 1 e 9, segundo entre 1 e 9)
    d1 = int(ddd[0])
    d2 = int(ddd[1])
    return 1 <= d1 <= 9 and 1 <= d2 <= 9


# ==========================================================
# REGRAS ESTRITAS DE ASSOCIAÇÃO DE PESSOAS FÍSICAS (PF)
# ==========================================================

def extrair_parte_cpf(doc: Any) -> str:
    """
    Extrai a parte numérica identificadora do CPF (ex: os 6 dígitos intermediários de ***123456**
    ou os dígitos de um CPF completo de 11 dígitos).
    """
    if not doc:
        return ""
    digits = "".join(c for c in str(doc) if c.isdigit())
    # Se for um CPF completo de 11 dígitos, os dígitos intermediários (posições 3 a 8 inclusive)
    # correspondem ao padrão de máscara da Receita Federal (***123456**)
    if len(digits) == 11:
        return digits[3:9]
    return digits


def normalizar_nome(nome: str) -> str:
    """Remove acentos, caracteres especiais e espaços extras para comparação de nomes."""
    if not nome:
        return ""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(nome).strip().upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    return " ".join(s.split())


def nomes_correspondem(nome_a: str, nome_b: str) -> bool:
    """
    Verifica se dois nomes correspondem entre si (nome completo ou parcial).
    Suporta:
    - Nomes idênticos após normalização.
    - Um nome contido integralmente no outro (ex: 'ALBERTO ROBERTO' contido em 'ALBERTO ROBERTO DA SILVA').
    - Primeiro nome e último sobrenome coincidentes (mínimo 2 palavras iguais).
    """
    na = normalizar_nome(nome_a)
    nb = normalizar_nome(nome_b)

    if not na or not nb:
        return False

    if na == nb:
        return True

    # Um nome é substring do outro (ex: abreviação ou ausência de um sobrenome do meio)
    if na in nb or nb in na:
        return True

    words_a = na.split()
    words_b = nb.split()

    # Se ambos têm pelo menos 2 partes e o primeiro e último nomes coincidem
    if len(words_a) >= 2 and len(words_b) >= 2:
        if words_a[0] == words_b[0] and words_a[-1] == words_b[-1]:
            # Pelo menos 2 nomes em comum
            inter = set(words_a).intersection(set(words_b))
            if len(inter) >= 2:
                return True

    return False


def correspondem_pessoa_fisica(
    nome_a: str, doc_a: str, nome_b: str, doc_b: str
) -> Tuple[bool, Optional[str]]:
    """
    Regra Crítica: Ao associar pessoas físicas, ambos itens DEVEM corresponder:
    1. Parte do CPF;
    2. Nome completo ou parcial.
    
    Caso não correspondam entre si, NÃO deve haver vinculação de forma alguma.
    Retorna (True, None) se ambos itens corresponderem ou (False, motivo).
    """
    cpf_a = extrair_parte_cpf(doc_a)
    cpf_b = extrair_parte_cpf(doc_b)

    # 1. Ambos os itens devem corresponder: exigência de parte do CPF presente em ambos
    if not cpf_a or not cpf_b:
        return False, "Ausência de parte do CPF para confirmação da identidade (ambos devem possuir CPF e Nome correspondentes)"

    # Se as partes do CPF forem divergentes (ex: 111222 != 333444)
    if cpf_a != cpf_b:
        # Se um for substring do outro (ex: CPF completo 11 dígitos e máscara de 6 dígitos)
        if not (cpf_a in cpf_b or cpf_b in cpf_a):
            return False, f"CPFs divergentes ({doc_a} vs {doc_b}) - pessoas distintas (homônimo rejeitado)"

    # 2. Nome completo ou parcial deve corresponder
    if not nomes_correspondem(nome_a, nome_b):
        return False, f"Nomes não correspondem ('{nome_a}' vs '{nome_b}')"

    return True, None

