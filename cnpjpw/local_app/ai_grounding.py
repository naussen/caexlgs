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


def construir_prompt_forense(contexto_investigativo: str) -> str:
    """Monta o prompt para o modelo atuar como perito forense e jurista."""
    return f"""Você é um Perito Forense Sênior e Especialista Jurídico em Investigação Patrimonial, Combate a Fraudes Societárias e Recuperação de Ativos no Direito Brasileiro.

Com base nos dados extraídos e auditados da empresa alvo e de sua rede de relacionamentos, elabore um PARECER TÉCNICO-ARGUMENTATIVO DE EMBASAMENTO FORENSE E JURÍDICO rigoroso, formal e fundamentado, pronto para instruir processos judiciais, medidas cautelares ou procedimentos de investigação fiscal/patrimonial.

DADOS DO CASO:
{contexto_investigativo}

ESTRUTURA OBRIGATÓRIA DO PARECER:
1. SÍNTESE DO OBJETO E IDENTIFICAÇÃO DO ALVO
- Apresentação formal da sociedade, regularidade cadastral e conformidade aparente do capital social em relação ao ramo de atuação.

2. ANÁLISE DE VÍNCULOS SOCIETÁRIOS E BENEFICIÁRIOS FINAIS
- Avaliação da cadeia societária, presença de interpostas pessoas ("laranjas"), concentração ou diluição de controle e identificação dos beneficiários econômicos reais.

3. MATRIZ DE RISCO, TIPOLOGIAS DE FRAUDE E FUNDAMENTAÇÃO LEGAL
- Análise de indicadores de grupo econômico de fato, confusão patrimonial, promiscuidade de endereços ou desvio de finalidade.
- Fundamentação expressa nos dispositivos legais pertinentes:
  * Artigo 50 do Código Civil (Desconsideração da Personalidade Jurídica direta e inversa - Lei da Liberdade Econômica nº 13.874/2019).
  * Artigo 28 do Código de Defesa do Consumidor e Artigo 14 da Lei Anticorrupção (Lei nº 12.846/2013), se cabível.
  * Artigo 133 a 137 do Código de Processo Civil (Incidente de Desconsideração da Personalidade Jurídica - IDPJ).
  * Jurisprudência consolidada do Superior Tribunal de Justiça (STJ), incluindo Súmula 513/STJ e teses sobre grupo econômico sem subordinação formal.

4. RECOMENDAÇÕES ESTRATÉGICAS DE MEDIDAS PROCESSUAIS E CAUTELARES
- Ações sugeridas para constrição e efetividade da execução/investigação (ex.: penhora de faturamento, indisponibilidade via CNIB/SISBAJUD/RENAJUD, quebra de sigilo bancário/fiscal, arrolamento de bens ou bloqueio de cotas sociais das empresas conexas).

5. CONCLUSÃO PERICIAL
- Síntese taxativa sobre a viabilidade de extensão da responsabilidade patrimonial aos sócios, administradores ou sociedades do mesmo grupo econômico.

REGRAS:
- Redija em português formal, tom pericial objetivo, claro e fundamentado.
- Não invente fatos externos, apenas interprete com profundidade jurídica e técnica os dados apresentados.
- Use formatação Markdown clara com tópicos organizados.
"""


def _chamar_gemini(api_key: str, prompt: str, model_name: str = GEMINI_DEFAULT_MODEL) -> Tuple[bool, str]:
    """Chama a API do Google Gemini (Free Tier via Google AI Studio)."""
    if not api_key:
        return False, "Chave de API do Google Gemini não configurada."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
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
            {"role": "system", "content": "Você é um perito forense sênior e jurista em recuperação de ativos e direito societário."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
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
            {"role": "system", "content": "Você é um perito forense sênior e jurista em recuperação de ativos e direito societário."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
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
        header = f"[PARECER FORENSE GERADO VIA IA - {provider_used.upper()}]\n\n"
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
        header = f"[FUNDAMENTAÇÃO GERADA PELO MOTOR FORENSE LOCAL (Modo Offline / Fallback: {reason})]\n\n"
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
