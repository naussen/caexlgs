"""
Módulo de Inteligência Artificial para Embasamento e Fundamentação de Dossiês Societários
Suporta APIs gratuitas:
- Google Gemini Free Tier (gemini-1.5-flash, gemini-2.0-flash via Google AI Studio)
- Groq Cloud Free Tier (llama-3.3-70b-versatile, llama-3.1-8b-instant)
- OpenRouter Free Models
- Fallback local robusto (Motor Forense Determinístico e Lógica Argumentativa)
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Tuple

import requests

logger = logging.getLogger("ai_grounding")

GEMINI_DEFAULT_MODEL = "gemini-1.5-flash"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
OPENROUTER_DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"


def montar_contexto_investigacao(
    root_data: Dict[str, Any],
    all_companies: Optional[list] = None,
    socios_list: Optional[list] = None,
    risk_info: Optional[Dict[str, Any]] = None,
    shared_addresses: Optional[Dict[str, Any]] = None,
    ubos: Optional[list] = None,
    existing_notes: str = ""
) -> str:
    """Prepara o sumário estruturado dos dados para o prompt do modelo."""
    razao = root_data.get("razao_social") or root_data.get("nome") or "NÃO INFORMADO"
    cnpj = root_data.get("cnpj", "")
    capital = root_data.get("capital_social", 0.0)
    situacao = root_data.get("situacao_cadastral", "ATIVA")
    natureza = root_data.get("natureza_juridica", "NÃO INFORMADA")
    data_abertura = root_data.get("data_abertura", "NÃO INFORMADA")
    logradouro = root_data.get("logradouro", "")
    numero = root_data.get("numero", "")
    bairro = root_data.get("bairro", "")
    municipio = root_data.get("municipio", "")
    uf = root_data.get("uf", "")
    cnae = root_data.get("cnae_fiscal_descricao", "NÃO INFORMADO")

    socios_str_list = []
    for s in (socios_list or []):
        nome_s = s.get("nome") or s.get("nome_socio") or "Sócio"
        qualif = s.get("qualificacao") or s.get("qualificacao_socio") or "Sócio/Administrador"
        doc = s.get("cpf_cnpj_socio") or s.get("cnpj_cpf_do_socio") or ""
        socios_str_list.append(f"- {nome_s} ({qualif}) [Doc: {doc}]")
    socios_bloco = "\n".join(socios_str_list) if socios_str_list else "- Nenhum sócio informado no QSA."

    outras_empresas = []
    if all_companies:
        for c in all_companies:
            c_cnpj = c.get("cnpj", "")
            if c_cnpj != cnpj:
                c_razao = c.get("razao_social") or c.get("nome") or c_cnpj
                outras_empresas.append(f"- {c_razao} (CNPJ: {c_cnpj}, Situação: {c.get('situacao_cadastral', 'N/D')})")
    empresas_bloco = "\n".join(outras_empresas[:20]) if outras_empresas else "- Não identificadas outras empresas no raio de varredura."

    alertas_list = []
    if risk_info:
        score = risk_info.get("score", 0)
        flags = risk_info.get("flags", [])
        alertas_list.append(f"Score de Risco Global: {score}/100")
        for f in flags:
            alertas_list.append(f"- [Alerta] {f}")
    if shared_addresses:
        alertas_list.append(f"- Endereço compartilhado com outras entidades detectadas.")
    if ubos:
        ubo_names = [u.get("name", "UBO") for u in ubos]
        alertas_list.append(f"- Beneficiários Finais Prováveis (UBO): {', '.join(ubo_names)}")
    alertas_bloco = "\n".join(alertas_list) if alertas_list else "- Nenhuma anomalia crítica automatizada registrada."

    contexto = f"""
DADOS DA EMPRESA ALVO PRINCIPAL:
- Razão Social: {razao}
- CNPJ: {cnpj}
- Situação Cadastral: {situacao}
- Data de Abertura: {data_abertura}
- Capital Social Declarado: R$ {capital:,.2f}
- Natureza Jurídica: {natureza}
- Atividade Principal (CNAE): {cnae}
- Endereço Cadastral: {logradouro}, {numero} - {bairro}, {municipio}/{uf}

QUADRO DE SÓCIOS E ADMINISTRADORES (QSA):
{socios_bloco}

REDE DE EMPRESAS VINCULADAS NO CLUSTER:
{empresas_bloco}

INDICADORES DE RISCO E EVIDÊNCIAS PRELIMINARES:
{alertas_bloco}

ANOTAÇÕES PRÉVIAS DO INVESTIGADOR:
{existing_notes if existing_notes.strip() else "(Nenhuma anotação prévia inserida)"}
"""
    return contexto


SYSTEM_PERICIAL_PROMPT = (
    "Você é um Auditor Forense Sênior e Analista Pericial de Inteligência Societária e Patrimonial. "
    "Sua redação é BRUTALMENTE TÉCNICA, ASSÉPTICA E PRAGMÁTICA. "
    "DIRETRIZES FUNDAMENTAIS:\n"
    "1. JAMAIS UTILIZAR ADJETIVOS QUALIFICATIVOS OU MORAIS (ex: 'fraudulento', 'severo', 'veemente', 'espúrio', 'escuso', 'ardiloso', 'fantasma', 'laranja', 'manobra').\n"
    "2. JAMAIS EMITIR CONSTATAÇÕES DE JUÍZO PRELIMINARES OU CONCLUSÕES DEFINITIVAS DE CULPA/DOLO (ex: jamais dizer 'restou comprovada a fraude', 'restou evidente a confusão patrimonial').\n"
    "3. TRABALHAR EXCLUSIVAMENTE COM INFERÊNCIAS TÉCNICAS E HIPÓTESES INVESTIGATIVAS (ex: 'os dados cadastrais sugerem a inferência de...', 'trabalha-se com a hipótese fática de...').\n"
    "4. FUNDAMENTAR OBRIGATORIAMENTE CADA PONTO EM RELAÇÕES CONCRETAS E QUANTIDADES NUMÉRICAS (quantitativo de empresas, número de sócios em comum, valores de capital social, contagem de CNPJs por endereço, datas e temporalidade).\n"
    "5. SUBSUNÇÃO JURÍDICA PURAMENTE HIPOTÉTICA nos dispositivos legais aplicáveis (Art. 50 do Código Civil, Lei 13.874/2019, Art. 133 a 137 do CPC, Art. 28 do CDC, Súmula 513/STJ)."
)


def construir_prompt_forense(contexto_investigativo: str) -> str:
    """Monta o prompt para o modelo atuar de forma brutalmente técnica, pragmática e relacional."""
    return f"""Elabore um LAUDO TÉCNICO-PERICIAL E SÍNTESE RELACIONAL INVESTIGATIVA sobre a malha societária abaixo.

REGRAS MANDATÓRIAS DE REDAÇÃO (O NÃO CUMPRIMENTO INVALIDA O LAUDO):
1. PROIBIÇÃO ABSOLUTA DE ADJETIVOS E JUÍZOS MORAIS/SUBJETIVOS:
   - Proibido usar adjetivos como "severo", "contundente", "veemente", "fraudulento", "ilícito", "criminoso", "ardiloso", "fantasma", "laranja", "espúrio", "escuso".
   - Use exclusivamente vocabulário asséptico, neutro e descritivo.

2. PROIBIÇÃO DE CONSTATAÇÕES DE JUÍZO PRELIMINARES OU CONCLUSÕES ANTECIPADAS:
   - Jamais declare fatos litigiosos como verdades consumadas (proibido dizer "restou comprovada a fraude", "restou evidente a confusão patrimonial").
   - Trate todos os achados como INFERÊNCIAS ANALÍTICAS e HIPÓTESES INVESTIGATIVAS ("os registros indicam a inferência técnica de...", "subsidia-se a hipótese fática de...", "sustenta-se a suposição relacional sujeita a confirmação probatória in loco").

3. FUNDAMENTAÇÃO OBRIGATÓRIA POR RELAÇÕES E QUANTIDADES (PRAGMATISMO BRUTAL):
   - TODA assertiva deve obrigatoriamente referenciar grandezas quantitativas e dados objetivos:
     * Quantidade de empresas interligadas (N empresas no raio de varredura);
     * Quantidade de sócios em comum e percentuais de participação;
     * Valor numérico exato do Capital Social (R$ ...) frente ao código CNAE de atuação;
     * Quantidade de CNPJs cadastrados no mesmo logradouro/número;
     * Temporalidade (diferença em anos/meses entre datas de abertura e situação cadastral ativa versus baixada).
   - Enquadrar cada hipótese fática estritamente nos dispositivos legais correlatos (Art. 50, § 2º, incisos I e III do Código Civil, Art. 133 a 137 do CPC, Art. 28, § 2º do CDC, Súmula 513/STJ).

DADOS AUDITADOS DO CASO:
{contexto_investigativo}

ESTRUTURAÇÃO DO LAUDO (EM MARKDOWN TÉCNICO):
1. IDENTIFICAÇÃO DO ALVO E DADOS QUANTITATIVOS
- Razão social, CNPJ, situação cadastral, capital social declarado vs. escopo de atividade do CNAE e temporalidade da constituição.

2. MAPEAMENTO RELACIONAL SOCIETÁRIO E TITULARIDADE ECONÔMICA FINAL (UBO)
- Quantitativo de sócios (PF e PJ), estrutura em camadas intermediárias e convergência do controle societário final para os beneficiários econômicos apurados.

3. HIPÓTESES INVESTIGATIVAS FÁTICAS E SUBSUNÇÃO NORMATIVA
- Correlações de domicílio fiscal (quantitativo exato de CNPJs no mesmo endereço sem segregação de instalações formalmente averbada);
- Correlações temporais (coexistência temporal entre sociedades baixadas/inaptas e sociedades operantes sob gestão idêntica);
- Hipótese técnica de configuração de grupo econômico sob coordenação unificada;
- Enquadramento normativo cabível como hipótese de incidência do Art. 50 do Código Civil (confusão patrimonial ou desvio de finalidade) e Art. 28 do CDC.

4. MEDIDAS PRAGMÁTICAS DE INSTRUÇÃO PROBATÓRIA E CONSTRIÇÃO SUGERIDAS
- Diligências práticas quantitativas recomendadas (mandado de constatação física in loco, consulta financeira via SISBAJUD, levantamento de bens via RENAJUD/CNIB, análise de livros contábeis ECD/ECF).

5. SÍNTESE DAS INFERÊNCIAS TÉCNICAS
- Quadro resumo pragmático e asséptico das inferências traçadas com base estrita nos dados relacionais e quantitativos examinados.
"""


def _chamar_gemini(api_key: str, prompt: str, model_name: str = GEMINI_DEFAULT_MODEL) -> Tuple[bool, str]:
    """Chama a API do Google Gemini (Free Tier via Google AI Studio)."""
    if not api_key:
        return False, "Chave de API do Google Gemini não configurada."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PERICIAL_PROMPT}]
        },
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 3000
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        if response.status_code == 200:
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                content_parts = candidates[0].get("content", {}).get("parts", [])
                if content_parts:
                    return True, content_parts[0].get("text", "")
            return False, "Resposta vazia da API do Gemini."
        else:
            err_msg = f"Erro Gemini HTTP {response.status_code}: {response.text[:300]}"
            logger.warning(err_msg)
            return False, err_msg
    except Exception as ex:
        err_msg = f"Exceção ao chamar Gemini: {str(ex)}"
        logger.error(err_msg)
        return False, err_msg


def _chamar_groq(api_key: str, prompt: str, model_name: str = GROQ_DEFAULT_MODEL) -> Tuple[bool, str]:
    """Chama a API gratuita da Groq Cloud (Llama-3.3-70b-versatile)."""
    if not api_key:
        return False, "Chave de API Groq não configurada."
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PERICIAL_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 3000
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                return True, choices[0].get("message", {}).get("content", "")
            return False, "Resposta vazia da API Groq."
        else:
            err_msg = f"Erro Groq HTTP {response.status_code}: {response.text[:300]}"
            logger.warning(err_msg)
            return False, err_msg
    except Exception as ex:
        err_msg = f"Exceção ao chamar Groq: {str(ex)}"
        logger.error(err_msg)
        return False, err_msg


def _chamar_openrouter(api_key: str, prompt: str, model_name: str = OPENROUTER_DEFAULT_MODEL) -> Tuple[bool, str]:
    """Chama a API OpenRouter (modelos gratuitos disponíveis)."""
    if not api_key:
        return False, "Chave de API OpenRouter não configurada."
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/cnpjpw/local_app",
        "X-Title": "CNPJ-PW Forensic Dossier Engine"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PERICIAL_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 3000
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                return True, choices[0].get("message", {}).get("content", "")
            return False, "Resposta vazia da API OpenRouter."
        else:
            err_msg = f"Erro OpenRouter HTTP {response.status_code}: {response.text[:300]}"
            logger.warning(err_msg)
            return False, err_msg
    except Exception as ex:
        err_msg = f"Exceção ao chamar OpenRouter: {str(ex)}"
        logger.error(err_msg)
        return False, err_msg


def gerar_fundamentacao_dossie_ia(
    root_data: Dict[str, Any],
    all_companies: Optional[list] = None,
    socios_list: Optional[list] = None,
    risk_info: Optional[Dict[str, Any]] = None,
    shared_addresses: Optional[Dict[str, Any]] = None,
    ubos: Optional[list] = None,
    existing_notes: str = "",
    provider: str = "auto",
    custom_api_key: str = "",
    gemini_key: str = "",
    groq_key: str = "",
    openrouter_key: str = ""
) -> Dict[str, Any]:
    """
    Gera a fundamentação técnica e jurídica do dossiê com inteligência artificial.
    Prioriza chaves fornecidas pelo usuário ou variáveis de ambiente.
    Caso não haja chave configurada ou ocorra erro de conexão/cota, utiliza o
    motor determinístico local como fallback de alta confiabilidade.
    """
    contexto = montar_contexto_investigacao(
        root_data=root_data,
        all_companies=all_companies,
        socios_list=socios_list,
        risk_info=risk_info,
        shared_addresses=shared_addresses,
        ubos=ubos,
        existing_notes=existing_notes
    )
    prompt = construir_prompt_forense(contexto)
    
    # Resolver chaves com prioridade: custom_api_key -> parametro -> env
    k_gemini = custom_api_key if provider == "gemini" and custom_api_key else (gemini_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""))
    k_groq = custom_api_key if provider == "groq" and custom_api_key else (groq_key or os.getenv("GROQ_API_KEY", ""))
    k_openrouter = custom_api_key if provider == "openrouter" and custom_api_key else (openrouter_key or os.getenv("OPENROUTER_API_KEY", ""))

    success = False
    result_text = ""
    provider_used = "none"
    error_details = []

    # Se selecionado provider específico
    if provider == "gemini" and k_gemini:
        success, result_text = _chamar_gemini(k_gemini, prompt)
        if success:
            provider_used = "Google Gemini (gemini-1.5-flash)"
        else:
            error_details.append(f"Gemini: {result_text}")
    elif provider == "groq" and k_groq:
        success, result_text = _chamar_groq(k_groq, prompt)
        if success:
            provider_used = "Groq Cloud (llama-3.3-70b-versatile)"
        else:
            error_details.append(f"Groq: {result_text}")
    elif provider == "openrouter" and k_openrouter:
        success, result_text = _chamar_openrouter(k_openrouter, prompt)
        if success:
            provider_used = "OpenRouter (Free Model)"
        else:
            error_details.append(f"OpenRouter: {result_text}")

    # Modo Auto: tenta na ordem Gemini -> Groq -> OpenRouter se chaves existirem
    if not success and provider in ("auto", "gemini", "groq", "openrouter"):
        if k_gemini and not success:
            success, result_text = _chamar_gemini(k_gemini, prompt)
            if success:
                provider_used = "Google Gemini (gemini-1.5-flash)"
            else:
                error_details.append(f"Gemini: {result_text}")

        if k_groq and not success:
            success, result_text = _chamar_groq(k_groq, prompt)
            if success:
                provider_used = "Groq Cloud (llama-3.3-70b-versatile)"
            else:
                error_details.append(f"Groq: {result_text}")

        if k_openrouter and not success:
            success, result_text = _chamar_openrouter(k_openrouter, prompt)
            if success:
                provider_used = "OpenRouter (Free Model)"
            else:
                error_details.append(f"OpenRouter: {result_text}")

    # Se teve sucesso com IA:
    if success and result_text:
        header = f"[LAUDO TÉCNICO-RELACIONAL VIA IA - {provider_used.upper()}]\n\n"
        return {
            "success": True,
            "provider": provider_used,
            "used_ai": True,
            "texto_integral": header + result_text.strip(),
            "error": None
        }

    # Fallback determinístico local robusto
    try:
        try:
            from cnpjpw.local_app.report_generator import build_argumentative_dossier
        except ImportError:
            import report_generator
            build_argumentative_dossier = report_generator.build_argumentative_dossier

        local_result = build_argumentative_dossier(
            root_data=root_data,
            all_companies=all_companies,
            socios_list=socios_list,
            risk_info=risk_info,
            shared_addresses=shared_addresses,
            ubos=ubos,
            notes=existing_notes
        )
        local_text = local_result.get("texto_integral", "")
        reason = "Chave de API não informada" if not (k_gemini or k_groq or k_openrouter) else f"Falha na API ({'; '.join(error_details)})"
        header = f"[LAUDO TÉCNICO-RELACIONAL - MOTOR FORENSE LOCAL (Modo Offline / Fallback: {reason})]\n\n"
        return {
            "success": True,
            "provider": "Motor Forense Local (Offline / Determinístico)",
            "used_ai": False,
            "fallback_reason": reason,
            "texto_integral": header + local_text.strip(),
            "error": None
        }
    except Exception as ex:
        logger.error(f"Erro no fallback local: {ex}")
        return {
            "success": False,
            "provider": "none",
            "used_ai": False,
            "texto_integral": existing_notes,
            "error": str(ex)
        }
