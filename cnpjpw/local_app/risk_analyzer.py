"""
Módulo de Análise de Risco, Compliance e Inteligência Societária para Grafos de CNPJ.
Funcionalidades:
- Identificação de irregularidades cadastrais (Inapta, Baixada, Suspensa, etc.)
- Detecção de empresas recentes (< 1 ano)
- Cruzamento e mapeamento de endereços compartilhados (mesmo CEP + número)
- Agrupamento de sócios por provável parentesco (sobrenomes em comum)
- Rastreamento do Beneficiário Final (UBO) em estruturas societárias com PJs
"""
from datetime import datetime, date
import re

# Sobrenomes extremamente comuns para desconsiderar se estiverem sozinhos
SOBRENOMES_MUITO_COMUNS = {
    "silva", "santos", "oliveira", "souza", "sousa", "rodrigues",
    "ferreira", "alves", "pereira", "lima", "gomes", "costa", "ribeiro",
    "martins", "carvalho", "almeida", "lopes", "soares", "fernandes",
    "vieira", "barbosa", "rocha", "dias", "nascimento", "andrade"
}

SUFIXOS_PARENTESCO = {
    "junior", "júnior", "filho", "neto", "sobrinho", "segundo", "terceiro"
}

PREPOSICOES = {"de", "da", "do", "das", "dos", "e"}

def analyze_company_risk(empresa_data: dict) -> dict:
    """
    Analisa os riscos cadastrais de uma empresa:
    - Situação cadastral (Ativa, Inapta, Baixada, Suspensa, Nula)
    - Idade da empresa (recente < 1 ano)
    - Capital social
    Retorna um dicionário com os indicadores e o nível de risco.
    """
    situacao = (empresa_data.get('situacao_cadastral_descricao') or 'ATIVA').upper().strip()
    motivo_situacao = empresa_data.get('motivo_situacao_cadastral_descricao') or ''
    dt_inicio = empresa_data.get('data_inicio_atividade')
    capital = empresa_data.get('capital_social') or 0.0

    is_irregular = situacao not in ('ATIVA', '1', '2') # Na RFB, 02=Ativa
    if situacao in ('INAPTA', 'SUSPENSA', 'BAIXADA', 'NULA'):
        is_irregular = True
    elif situacao == 'ATIVA':
        is_irregular = False

    is_recente = False
    idade_meses = None
    if dt_inicio:
        try:
            if isinstance(dt_inicio, str):
                dt_obj = datetime.strptime(dt_inicio[:10], "%Y-%m-%d").date()
            elif isinstance(dt_inicio, (datetime, date)):
                dt_obj = dt_inicio if isinstance(dt_inicio, date) else dt_inicio.date()
            else:
                dt_obj = None

            if dt_obj:
                dias = (date.today() - dt_obj).days
                idade_meses = max(0, dias // 30)
                if idade_meses < 12:
                    is_recente = True
        except Exception:
            pass

    # Pontuação de risco
    risk_score = 0
    risk_flags = []

    if situacao == 'INAPTA':
        risk_score += 40
        risk_flags.append("Situação Cadastral INAPTA (Possível omissão de declarações/irregularidade fiscal)")
    elif situacao == 'BAIXADA':
        risk_score += 30
        risk_flags.append(f"Situação Cadastral BAIXADA ({motivo_situacao or 'Baixa registrada'})")
    elif situacao == 'SUSPENSA':
        risk_score += 25
        risk_flags.append("Situação Cadastral SUSPENSA")
    elif situacao == 'NULA':
        risk_score += 50
        risk_flags.append("Situação Cadastral NULA")

    if is_recente:
        risk_score += 15
        risk_flags.append(f"Empresa Recente ({idade_meses or 0} meses de atividade)")

    risk_level = "BAIXO"
    if risk_score >= 40:
        risk_level = "ALTO"
    elif risk_score >= 20:
        risk_level = "MÉDIO"

    return {
        "situacao": situacao,
        "is_irregular": is_irregular,
        "is_recente": is_recente,
        "idade_meses": idade_meses,
        "capital_social": capital,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_flags": risk_flags
    }


def normalize_address(dados: dict) -> tuple[str, str]:
    """
    Normaliza o endereço de uma empresa e retorna:
    - address_key: chave única para agrupamento (cep + numero)
    - address_label: rótulo formatado para exibição
    """
    cep = re.sub(r'\D', '', str(dados.get('cep') or '')).strip()
    numero = str(dados.get('numero') or '').strip().upper()
    logradouro = str(dados.get('logradouro') or '').strip().title()
    bairro = str(dados.get('bairro') or '').strip().title()
    municipio = str(dados.get('municipio_desc') or dados.get('municipio') or '').strip().title()
    uf = str(dados.get('uf') or '').strip().upper()

    # Normalizar número (S/N, etc)
    if not numero or numero in ('SN', 'S/N', 'SEM NUMERO', 'S N'):
        numero = 'SN'

    if not cep or len(cep) != 8:
        # Se não tem CEP válido, não agrupa para evitar falsos positivos
        return None, None

    address_key = f"{cep}_{numero}"
    address_label = f"{logradouro}, {numero} - {bairro}, {municipio}/{uf} (CEP {cep[:5]}-{cep[5:]})"
    return address_key, address_label


def detect_shared_addresses(all_companies: list[dict]) -> dict[str, list[dict]]:
    """
    Localiza endereços compartilhados entre duas ou mais empresas do grupo.
    Retorna um dicionário:
    {
      "address_key": {
          "label": address_label,
          "companies": [comp1, comp2, ...]
      }
    }
    """
    addr_map = {}
    for comp in all_companies:
        addr_key, addr_label = normalize_address(comp)
        if not addr_key:
            continue
        if addr_key not in addr_map:
            addr_map[addr_key] = {"label": addr_label, "companies": []}
        
        cnpj = comp.get('cnpj') or comp.get('cnpj_basico') or ''
        # Evita duplicar a mesma empresa
        existing_cnpjs = [c.get('cnpj') or c.get('cnpj_basico') for c in addr_map[addr_key]['companies']]
        if cnpj not in existing_cnpjs:
            addr_map[addr_key]['companies'].append(comp)

    # Filtrar apenas endereços compartilhados por 2 ou mais empresas distintas
    shared = {k: v for k, v in addr_map.items() if len(v['companies']) >= 2}
    return shared


def extract_meaningful_surnames(full_name: str) -> set[str]:
    """Extrai os sobrenomes relevantes de um nome completo para verificação de parentesco."""
    if not full_name:
        return set()
    parts = full_name.lower().strip().split()
    if len(parts) <= 1:
        return set()

    # Ignora o primeiro nome
    surnames = parts[1:]
    meaningful = set()
    for s in surnames:
        if s in PREPOSICOES or s in SUFIXOS_PARENTESCO:
            continue
        meaningful.add(s)
    return meaningful


def detect_family_relationships(socios_list: list[dict]) -> list[dict]:
    """
    Analisa uma lista de sócios e detecta prováveis vínculos de parentesco
    com base em sobrenomes compartilhados raros ou pares de sobrenomes.
    Retorna lista de arestas de parentesco detectadas:
    [{ 'socio_a': ..., 'socio_b': ..., 'sobrenomes_comuns': [...], 'confianca': 'Alta'|'Média' }]
    """
    relationships = []
    n = len(socios_list)

    for i in range(n):
        for j in range(i + 1, n):
            s1 = socios_list[i]
            s2 = socios_list[j]
            nome1 = s1.get('nome', '')
            nome2 = s2.get('nome', '')

            surnames1 = extract_meaningful_surnames(nome1)
            surnames2 = extract_meaningful_surnames(nome2)

            comuns = surnames1.intersection(surnames2)
            if not comuns:
                continue

            # Avalia relevância dos sobrenomes em comum
            comuns_raros = comuns - SOBRENOMES_MUITO_COMUNS
            confianca = None
            if len(comuns) >= 2:
                confianca = "Alta"  # 2 ou mais sobrenomes iguais (ex: Silva Ferreira)
            elif len(comuns_raros) >= 1:
                confianca = "Alta"  # 1 sobrenome específico/incomum (ex: Klabin, Safra, Batista)
            elif len(comuns) == 1 and list(comuns)[0] in SOBRENOMES_MUITO_COMUNS:
                # Apenas 1 sobrenome muito comum isolado (ex: ambos são Silva) -> ignora para evitar falso positivo
                continue

            if confianca:
                relationships.append({
                    "socio_a": nome1,
                    "socio_b": nome2,
                    "sobrenomes_comuns": sorted(list(comuns)),
                    "confianca": confianca
                })

    return relationships


def trace_ultimate_beneficial_owners(root_cnpj: str, root_data: dict, api_client, max_depth: int = 3) -> dict:
    """
    Rastreia em cadeia recursiva os Beneficiários Finais (UBO - Pessoas Físicas)
    quando a empresa possui sócios Pessoas Jurídicas (holdings / intermediárias).
    Retorna:
    {
      "ubos": [ {"nome": ..., "doc": ..., "path": [...]}, ... ],
      "intermediate_companies": [ {"cnpj": ..., "razao": ..., "depth": ...} ]
    }
    """
    visited_pjs = set()
    intermediate_companies = []
    ubos = []

    def recursive_trace(cnpj_curr: str, current_path: list, depth: int):
        if depth > max_depth or cnpj_curr in visited_pjs:
            return
        visited_pjs.add(cnpj_curr)

        if depth == 0:
            data = root_data
        else:
            data = api_client.get_cnpj(cnpj_curr)
            if not data:
                return
            intermediate_companies.append({
                "cnpj": cnpj_curr,
                "razao": data.get('nome_empresarial') or data.get('razao_social', f"CNPJ {cnpj_curr}"),
                "depth": depth
            })

        socios = data.get('socios', [])
        for s in socios:
            tipo_entidade = str(s.get('identificador_entidade_descricao') or s.get('identificador_de_socio') or '').upper()
            doc = re.sub(r'\D', '', str(s.get('cnpj_cpf') or ''))
            nome = s.get('nome', '')

            # Verifica se o sócio é PJ (CNPJ tem 14 dígitos ou tipo entidade menciona PJ)
            is_pj = (len(doc) == 14) or ('JURÍDICA' in tipo_entidade or 'JURIDICA' in tipo_entidade)

            new_path = current_path + [data.get('nome_empresarial') or cnpj_curr]

            if is_pj and doc:
                recursive_trace(doc, new_path, depth + 1)
            else:
                # É Pessoa Física (UBO direto ou indireto)
                if not any(u['nome'] == nome for u in ubos):
                    ubos.append({
                        "nome": nome,
                        "doc": s.get('cnpj_cpf', ''),
                        "qualificacao": s.get('qualificacao_descricao', ''),
                        "controlador_indireto": (depth > 0),
                        "caminho_controle": new_path[1:] if len(new_path) > 1 else ["Direto"]
                    })

    recursive_trace(root_cnpj, [], 0)

    return {
        "ubos": ubos,
        "intermediate_companies": intermediate_companies
    }
