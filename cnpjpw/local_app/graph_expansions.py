"""
graph_expansions.py — Módulo de Expansões Globais do Grafo do POMELO (Fase 6).

Implementa as operações de expansão em lote:
1. expand_socios_grau2: Expande sócios diretos da raiz (grau 1) até suas outras empresas (grau 2),
   com limite configurável (padrão 25/sócio), deduplicação por CNPJ, exclusão da raiz e sem
   avançar para o grau 3.
2. expand_contacts_network: Coleta contatos únicos válidos de todas as empresas visíveis na rede,
   valida formato (DDD obrigatório, e-mail sintático), executa busca reversa via data_service,
   aplica teto configurável (padrão 25/contato), deduplica resultados e reporta sumário auditável.
"""

import os
import sys
from typing import Dict, Any, List, Optional, Tuple, Set

_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

try:
    import data_service
except ImportError:
    from cnpjpw.local_app import data_service

DEFAULT_MAX_COMPANIES_PER_PARTNER = 25
DEFAULT_MAX_COMPANIES_PER_CONTACT = 25


def clean_cnpj(val: Any) -> str:
    """Extrai apenas os 14 dígitos de um CNPJ."""
    digits = "".join(filter(str.isdigit, str(val or "")))
    if len(digits) == 8:
        digits = digits.zfill(14)
    return digits if len(digits) == 14 else ""


def is_valid_phone(phone_digits: str) -> bool:
    """Valida se uma sequência numérica de telefone possui DDD explícito (10 ou 11 dígitos)."""
    if not phone_digits or not str(phone_digits).isdigit():
        return False
    digits = str(phone_digits)
    if len(digits) not in (10, 11):
        return False
    # Rejeita repetições triviais como '0000000000' ou '1111111111'
    if len(set(digits)) <= 1:
        return False
    # DDDs válidos no Brasil começam entre 1 e 9, com segundo dígito entre 1 e 9
    ddd = digits[:2]
    if int(ddd[0]) < 1 or int(ddd[1]) < 1:
        return False
    return True


def is_valid_email(email: str) -> bool:
    """Valida sintaxe básica de e-mail corporativo/pessoal."""
    if not email or not isinstance(email, str):
        return False
    cleaned = email.strip().lower()
    if "@" not in cleaned:
        return False
    parts = cleaned.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return False
    domain = parts[1]
    if "." not in domain or domain.startswith(".") or domain.endswith("."):
        return False
    if len(cleaned) < 6 or len(cleaned) > 254:
        return False
    return True


def extract_company_contacts(comp: Dict[str, Any]) -> Tuple[Set[str], Set[str]]:
    """
    Extrai contatos únicos válidos (telefones e e-mails) de um registro de empresa.
    Retorna (telefones_validos, emails_validos).
    """
    phones: Set[str] = set()
    emails: Set[str] = set()

    if not isinstance(comp, dict):
        return phones, emails

    # E-mails
    for em_key in ("correio_eletronico", "email", "e_mail", "email_contato"):
        raw_em = comp.get(em_key)
        if raw_em and isinstance(raw_em, str):
            for part in raw_em.replace(";", ",").replace("/", ",").split(","):
                part_clean = part.strip().lower()
                if is_valid_email(part_clean):
                    emails.add(part_clean)

    # Telefones (com DDD explícito)
    # 1. ddd1 + telefone_1
    d1 = "".join(filter(str.isdigit, str(comp.get("ddd1") or comp.get("ddd_1") or "")))
    t1 = "".join(filter(str.isdigit, str(comp.get("telefone_1") or comp.get("telefone1") or "")))
    if d1 and t1:
        cand1 = f"{d1}{t1}"
        if is_valid_phone(cand1):
            phones.add(cand1)
    elif t1 and is_valid_phone(t1):
        phones.add(t1)

    # 2. ddd2 + telefone_2
    d2 = "".join(filter(str.isdigit, str(comp.get("ddd2") or comp.get("ddd_2") or "")))
    t2 = "".join(filter(str.isdigit, str(comp.get("telefone_2") or comp.get("telefone2") or "")))
    if d2 and t2:
        cand2 = f"{d2}{t2}"
        if is_valid_phone(cand2):
            phones.add(cand2)
    elif t2 and is_valid_phone(t2):
        phones.add(t2)

    # 3. telefone genérico
    for raw_tel_key in ("telefone", "telefones", "contato_tel"):
        raw_val = comp.get(raw_tel_key)
        if raw_val and isinstance(raw_val, str):
            for part in raw_val.replace(";", ",").replace("/", ",").split(","):
                cand_dig = "".join(filter(str.isdigit, part))
                if is_valid_phone(cand_dig):
                    phones.add(cand_dig)

    return phones, emails


# =========================================================================
# 1. EXPANSÃO DE SÓCIOS ATÉ SEGUNDO GRAU (GRAU 2)
# =========================================================================

def expand_socios_grau2(
    root_data: Dict[str, Any],
    max_per_partner: int = DEFAULT_MAX_COMPANIES_PER_PARTNER,
    cache: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Expande os sócios da empresa raiz até o segundo grau de relacionamento.

    Definições de Grau:
    - Grau 0: Empresa raiz (root_data).
    - Grau 1: Sócios diretos da raiz (root_data['socios']).
    - Grau 2: Outras empresas onde os sócios de grau 1 participam.
    - Grau 3+: NÃO são expandidos nesta operação.

    Regras obrigatórias:
    1. Deduplicação por CNPJ completo (14 dígitos).
    2. Exclusão mandatória da empresa raiz (Grau 0).
    3. Limite configurável (padrão 25 empresas por sócio).
    4. Resumo auditável com contagem de consultas, achados, descartes e falhas.
    """
    if cache is None:
        cache = {}

    root_cnpj = clean_cnpj(root_data.get("cnpj"))
    root_razao = root_data.get("razao_social") or root_data.get("nome_empresarial") or "EMPRESA RAIZ"
    socios_list = root_data.get("socios") or []

    summary: Dict[str, Any] = {
        "grau0_cnpj": root_cnpj,
        "grau0_razao": root_razao,
        "total_socios_raiz": len(socios_list),
        "socios_consultados": 0,
        "empresas_encontradas": 0,
        "empresas_adicionadas": 0,
        "duplicatas_removidas": 0,
        "falhas": 0,
        "detalhes_falhas": []
    }

    # Rastreia CNPJs já adicionados à rede para deduplicação global
    seen_cnpjs: Set[str] = {root_cnpj} if root_cnpj else set()
    # Adiciona também CNPJs que já existiam no cache de consultas anteriores
    for prev_comps in cache.values():
        for pc in prev_comps:
            p_cnpj = clean_cnpj(pc.get("cnpj"))
            if p_cnpj:
                seen_cnpjs.add(p_cnpj)

    for socio in socios_list:
        if not isinstance(socio, dict):
            continue

        n_socio = str(socio.get("nome") or "").strip()
        if not n_socio:
            continue

        doc_socio = socio.get("cnpj_cpf") or socio.get("cpf_cnpj") or socio.get("doc") or socio.get("cpf")

        # Se já estiver em cache, computa estatísticas
        if n_socio in cache:
            cached_list = cache[n_socio]
            summary["empresas_adicionadas"] += len(cached_list)
            continue

        summary["socios_consultados"] += 1

        try:
            resp = data_service.buscar_empresas_do_socio(n_socio, doc_socio)
            raw_companies = resp.results if isinstance(resp.results, list) else []

            if resp.error and not raw_companies:
                summary["falhas"] += 1
                summary["detalhes_falhas"].append(f"{n_socio}: {resp.error}")
                cache[n_socio] = []
                continue

            summary["empresas_encontradas"] += len(raw_companies)

            valid_for_partner: List[Dict[str, Any]] = []
            for comp in raw_companies:
                comp_cnpj = clean_cnpj(comp.get("cnpj"))

                # Regra: Descarta a empresa raiz (Grau 0)
                if comp_cnpj and comp_cnpj == root_cnpj:
                    summary["duplicatas_removidas"] += 1
                    continue

                # Regra: Deduplica se já foi encontrada nesta ou em outra expansão
                if comp_cnpj and comp_cnpj in seen_cnpjs:
                    summary["duplicatas_removidas"] += 1
                    continue

                # Regra: Limite configurável por sócio
                if len(valid_for_partner) >= max_per_partner:
                    summary["duplicatas_removidas"] += 1  # Excedentes ao teto
                    continue

                if comp_cnpj:
                    seen_cnpjs.add(comp_cnpj)

                valid_for_partner.append(comp)

            cache[n_socio] = valid_for_partner
            summary["empresas_adicionadas"] += len(valid_for_partner)

        except Exception as e:
            summary["falhas"] += 1
            summary["detalhes_falhas"].append(f"{n_socio}: {str(e)}")
            cache[n_socio] = []

    return cache, summary


# =========================================================================
# 2. EXPANSÃO DE CONTATOS DA REDE (EMPRESAS VISÍVEIS)
# =========================================================================

def expand_contacts_network(
    visible_companies: List[Dict[str, Any]],
    max_per_contact: int = DEFAULT_MAX_COMPANIES_PER_CONTACT,
    cache: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    months: int = 3
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Expande contatos únicos (telefone e e-mail) de todas as empresas visíveis no grafo.

    Regras obrigatórias:
    1. Escopo: contatos de todas as empresas atualmente visíveis.
    2. Coleta de contatos únicos antes de disparar consultas.
    3. Filtro rigoroso: descarta contatos vazios ou sem formato válido (DDD obrigatório).
    4. Limite configurável (padrão 25 empresas por contato).
    5. Cache persistido por chave normalizada (dígitos para fone, minúsculas para e-mail).
    6. Resumo auditável contendo contatos únicos, empresas encontradas e avisos/erros.
    """
    if cache is None:
        cache = {}

    summary: Dict[str, Any] = {
        "empresas_analisadas": len(visible_companies),
        "contatos_unicos": 0,
        "telefones": 0,
        "emails": 0,
        "empresas_encontradas": 0,
        "empresas_adicionadas": 0,
        "duplicatas_removidas": 0,
        "avisos_erros": []
    }

    # Mapeia CNPJs já visíveis para não duplicar empresas que já estão na rede
    known_cnpjs: Set[str] = set()
    for c in visible_companies:
        cnpj_c = clean_cnpj(c.get("cnpj"))
        if cnpj_c:
            known_cnpjs.add(cnpj_c)

    # Adiciona também empresas que já existiam no cache de contatos
    for prev_comps in cache.values():
        for pc in prev_comps:
            p_cnpj = clean_cnpj(pc.get("cnpj"))
            if p_cnpj:
                known_cnpjs.add(p_cnpj)

    # 1. Coleta e deduplicação prévia de contatos em toda a rede visível
    all_phones: Set[str] = set()
    all_emails: Set[str] = set()

    for comp in visible_companies:
        c_phones, c_emails = extract_company_contacts(comp)
        all_phones.update(c_phones)
        all_emails.update(c_emails)

    summary["contatos_unicos"] = len(all_phones) + len(all_emails)
    summary["telefones"] = len(all_phones)
    summary["emails"] = len(all_emails)

    # 2. Processamento de Telefones Únicos
    for phone_key in sorted(all_phones):
        if phone_key in cache:
            summary["empresas_adicionadas"] += len(cache[phone_key])
            continue

        ddd = phone_key[:2]
        num = phone_key[2:]

        try:
            resp = data_service.buscar_telefone(ddd, num, months=months)
            raw_comps = resp.results if isinstance(resp.results, list) else []

            if resp.error and not raw_comps:
                summary["avisos_erros"].append(f"Fone ({ddd}) {num}: {resp.error}")
                cache[phone_key] = []
                continue

            summary["empresas_encontradas"] += len(raw_comps)

            valid_for_contact: List[Dict[str, Any]] = []
            for comp in raw_comps:
                c_cnpj = clean_cnpj(comp.get("cnpj"))

                # Descarta se já é conhecida no cluster visível
                if c_cnpj and c_cnpj in known_cnpjs:
                    summary["duplicatas_removidas"] += 1
                    continue

                if len(valid_for_contact) >= max_per_contact:
                    summary["duplicatas_removidas"] += 1
                    continue

                if c_cnpj:
                    known_cnpjs.add(c_cnpj)

                valid_for_contact.append(comp)

            cache[phone_key] = valid_for_contact
            summary["empresas_adicionadas"] += len(valid_for_contact)

        except Exception as e:
            summary["avisos_erros"].append(f"Fone ({ddd}) {num}: {str(e)}")
            cache[phone_key] = []

    # 3. Processamento de E-mails Únicos
    for email_key in sorted(all_emails):
        if email_key in cache:
            summary["empresas_adicionadas"] += len(cache[email_key])
            continue

        try:
            resp = data_service.buscar_email(email_key, months=months)
            raw_comps = resp.results if isinstance(resp.results, list) else []

            if resp.error and not raw_comps:
                summary["avisos_erros"].append(f"E-mail {email_key}: {resp.error}")
                cache[email_key] = []
                continue

            summary["empresas_encontradas"] += len(raw_comps)

            valid_for_contact: List[Dict[str, Any]] = []
            for comp in raw_comps:
                c_cnpj = clean_cnpj(comp.get("cnpj"))

                if c_cnpj and c_cnpj in known_cnpjs:
                    summary["duplicatas_removidas"] += 1
                    continue

                if len(valid_for_contact) >= max_per_contact:
                    summary["duplicatas_removidas"] += 1
                    continue

                if c_cnpj:
                    known_cnpjs.add(c_cnpj)

                valid_for_contact.append(comp)

            cache[email_key] = valid_for_contact
            summary["empresas_adicionadas"] += len(valid_for_contact)

        except Exception as e:
            summary["avisos_erros"].append(f"E-mail {email_key}: {str(e)}")
            cache[email_key] = []

    return cache, summary
