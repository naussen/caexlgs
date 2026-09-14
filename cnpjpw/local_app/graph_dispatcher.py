"""
Módulo Dispatcher Unificado e Semântica de Expansão do Grafo (Fases 3 e 4 do Plano de Correções).
Centraliza a validação, sanitização, exclusão e expansão de entidades (Empresa, Sócio, Telefone, E-mail).
"""
import os
import sys
from typing import Dict, Any, Optional, Tuple, Callable
import streamlit as st

_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import api_client
import bigquery_client
import data_service

ALLOWED_ACTIONS = {"expand", "delete", "toggle_feature", "clear"}
ALLOWED_ENTITY_TYPES = {
    "EMPRESA", "EMPRESA_ROOT", "SOCIO", "UBO",
    "TELEFONE", "EMAIL", "CONTABILIDADE", "OUTRO"
}
ALLOWED_FEATURES = {"expand_socios", "expand_contacts"}

def validate_graph_event(event: Any) -> Tuple[bool, Optional[str]]:
    """
    Valida a estrutura do evento antes da execução.
    Retorna (True, None) se válido ou (False, mensagem_erro).
    """
    if not isinstance(event, dict):
        return False, "Evento deve ser um dicionário."

    action = event.get("action")
    if not action or action not in ALLOWED_ACTIONS:
        return False, f"Ação inválida: '{action}'. Permitidas: {sorted(ALLOWED_ACTIONS)}"

    if action == "expand":
        ent_val = event.get("entity_value") or event.get("val")
        if not ent_val or not str(ent_val).strip():
            return False, "Ação 'expand' requer 'entity_value' não vazio."
        ent_type = event.get("entity_type") or event.get("type")
        if ent_type and str(ent_type).upper() not in ALLOWED_ENTITY_TYPES:
            return False, f"Tipo de entidade desconhecido: '{ent_type}'"

    elif action == "delete":
        node_id = event.get("node_id") or event.get("id") or event.get("val")
        if not node_id or not str(node_id).strip():
            return False, "Ação 'delete' requer identificador de nó ('node_id')."

    elif action == "toggle_feature":
        feature = event.get("feature")
        if not feature or feature not in ALLOWED_FEATURES:
            return False, f"Feature inválida para alternância: '{feature}'. Permitidas: {sorted(ALLOWED_FEATURES)}"

    return True, None

def exclude_graph_node(node_id: str, label: str = "", root_id: Optional[str] = None) -> bool:
    """
    Executa a exclusão de um nó no grafo de forma consistente e segura.
    Bloqueia a exclusão da empresa raiz em qualquer circunstância e persiste em st.session_state.
    """
    if not node_id:
        return False

    node_str = str(node_id).strip()

    # Identifica o nó raiz atual da investigação
    current_root = root_id or st.session_state.get("current_cnpj") or st.session_state.get("selected_cnpj") or ""
    current_root_digits = "".join(filter(str.isdigit, str(current_root)))

    # Bloqueia exclusão da raiz em qualquer variação de identificador
    if current_root_digits:
        if (node_str == current_root_digits or 
            node_str == f"cnpj_{current_root_digits}" or 
            node_str.lower() == "empresa_root"):
            st.warning("⚠️ A empresa raiz sob investigação não pode ser excluída do grafo.")
            return False

    if "graph_excluded_nodes" not in st.session_state:
        st.session_state.graph_excluded_nodes = set()

    st.session_state.graph_excluded_nodes.add(node_str)
    rotulo = label or node_str
    st.toast(f"✕ Entidade '{rotulo}' removida da rede.")
    return True

def clear_graph_expansions():
    """
    Reinicializa todas as expansões do grafo para a visualização original da empresa raiz.
    """
    st.session_state.graph_excluded_nodes = set()
    st.session_state.graph_false_positive_accountants = set()
    st.session_state.graph_manual_accountants = set()
    st.session_state.graph_manual_nodes = []
    st.session_state.graph_manual_edges = []
    st.session_state.graph_cache_socios_empresas = {}
    st.session_state.graph_cache_contatos_empresas = {}
    st.session_state.multi_expanded_companies = {}
    st.session_state.multi_expanded_socios = {}
    st.session_state.multi_expanded_phones = {}
    st.session_state.multi_expanded_emails = {}
    st.session_state.graph_expand_socios = False
    st.session_state.graph_expand_contacts = False
    st.toast("🧹 Grafo reiniciado para a empresa raiz.")

def executar_expansao_entidade(ent_type: str, ent_val: str, ent_label: str = "", root_id: Optional[str] = None):
    """
    Executa a expansão pontual de uma entidade específica com semântica estrita (Fase 4):
    1. Empresa: Valida 14 dígitos numéricos, consulta ficha completa e impede duplicação da raiz.
    2. Sócio/UBO: Usa documento se disponível e não mascarado, senão nome. Normaliza chave de cache
       preservando nome original e filtra duplicatas e a empresa raiz.
    3. Telefone: Apenas dígitos, exige DDD explícito (10 ou 11 dígitos), remove fallback arbitrário '11'.
    4. E-mail: Normaliza em minúsculas, valida formato com '@', partes não vazias e filtra raiz.
    """
    ent_type = (ent_type or '').upper()
    val_str = str(ent_val or '').strip()

    # Sanitização defensiva contra prefixos de node IDs
    if val_str.lower().startswith("socio_"):
        val_str = val_str[6:].strip()
    elif val_str.lower().startswith("cnpj_"):
        val_str = val_str[5:].strip()
    elif val_str.lower().startswith("email_"):
        val_str = val_str[6:].strip()
    elif val_str.lower().startswith("tel_"):
        val_str = val_str[4:].strip()

    # Identifica o CNPJ da empresa raiz atual
    current_root = root_id or st.session_state.get("current_cnpj") or st.session_state.get("selected_cnpj") or ""
    current_root_clean = "".join(filter(str.isdigit, str(current_root)))

    # 1. EMPRESA
    if ent_type in ("EMPRESA", "EMPRESA_ROOT") or (val_str.isdigit() and len(val_str) in (8, 14)):
        cnpj_limpo = "".join(filter(str.isdigit, val_str))
        if len(cnpj_limpo) == 8:
            cnpj_limpo = cnpj_limpo.zfill(14)

        if len(cnpj_limpo) != 14:
            st.warning(f"CNPJ inválido para expansão: '{val_str}'. Requer 14 dígitos numéricos.")
            return

        # Regra 5 e 6: Se a empresa for a raiz, não adicioná-la a multi_expanded_companies
        if current_root_clean and cnpj_limpo == current_root_clean:
            st.info("ℹ️ Os vínculos diretos da empresa raiz já estão carregados na rede. Para ampliar a investigação, utilize '👥 Expandir Sócios (2º Grau)' ou '📞 Expandir Contatos'.")
            return

        if "multi_expanded_companies" not in st.session_state:
            st.session_state.multi_expanded_companies = {}

        if cnpj_limpo in st.session_state.multi_expanded_companies:
            st.info(f"As conexões da empresa {ent_label or cnpj_limpo} já estão expandidas na rede.")
            return

        with st.spinner(f"Consultando dados e conexões da empresa {ent_label or cnpj_limpo}..."):
            resp_obj = data_service.get_cnpj(cnpj_limpo)
            emp_dados = resp_obj.get("results") if isinstance(resp_obj, dict) and "results" in resp_obj else resp_obj
            if emp_dados and not emp_dados.get('erro'):
                st.session_state.multi_expanded_companies[cnpj_limpo] = emp_dados
                nome_emp = emp_dados.get('nome_empresarial') or emp_dados.get('razao_social') or cnpj_limpo
                st.toast(f"✅ Relações de {nome_emp} expandidas com sucesso!")
            else:
                err = resp_obj.get("error") if isinstance(resp_obj, dict) else None
                st.warning(err or f"Não foi possível obter dados para o CNPJ {cnpj_limpo}.")

    # 2. SÓCIO OU UBO
    elif ent_type in ("SOCIO", "UBO"):
        # Regra 1 e 2: Usar documento quando disponível e não mascarado; nome como fallback
        doc_digits = "".join(filter(str.isdigit, val_str))
        tem_doc_valido = len(doc_digits) in (11, 14) and "*" not in val_str

        # Regra 3: Normalizar somente para chave de cache; preservar nome original para exibição
        nome_original = ent_label if ent_label and ent_label != val_str else val_str
        cache_key = doc_digits if tem_doc_valido else val_str.strip().upper()

        if "multi_expanded_socios" not in st.session_state:
            st.session_state.multi_expanded_socios = {}

        if cache_key in st.session_state.multi_expanded_socios and st.session_state.multi_expanded_socios.get(cache_key):
            st.info(f"As empresas do sócio {nome_original} já estão expandidas na rede.")
            return

        with st.spinner(f"Buscando empresas vinculadas ao sócio {nome_original}..."):
            if tem_doc_valido:
                resp_obj = data_service.buscar_socio(doc_digits)
            else:
                resp_obj = data_service.buscar_empresas_do_socio(val_str.strip().upper())

            res_soc = resp_obj.get("results") if isinstance(resp_obj, dict) and "results" in resp_obj else resp_obj

            # Regra 4: Adicionar empresas encontradas, excluindo duplicatas e a raiz
            seen_cnpjs = set()
            filtered_res = []
            for emp in (res_soc or []):
                e_cnpj = "".join(filter(str.isdigit, str(emp.get('cnpj') or emp.get('cnpj_completo') or emp.get('cnpj_basico') or '')))
                if e_cnpj:
                    if current_root_clean and e_cnpj == current_root_clean:
                        continue
                    if e_cnpj in seen_cnpjs:
                        continue
                    seen_cnpjs.add(e_cnpj)
                filtered_res.append(emp)

            if filtered_res:
                st.session_state.multi_expanded_socios[cache_key] = filtered_res
                st.toast(f"✅ {len(filtered_res)} empresa(s) do sócio {nome_original} adicionada(s) à rede!")
            else:
                err = resp_obj.get("error") if isinstance(resp_obj, dict) else None
                st.warning(err or f"Nenhuma outra empresa encontrada para o sócio {nome_original}.")

    # 3. TELEFONE
    elif ent_type == "TELEFONE":
        fone_limpo = "".join(filter(str.isdigit, val_str))
        # Regra 1, 2 e 3: Apenas dígitos, exigir DDD explícito (10 ou 11 dígitos), sem fallback arbitrário '11'
        if len(fone_limpo) not in (10, 11):
            st.warning(f"Telefone inválido para expansão: '{val_str}'. É obrigatório DDD com 2 dígitos seguido do número (ex: 11999998888).")
            return

        ddd = fone_limpo[:2]
        num = fone_limpo[2:]

        if "multi_expanded_phones" not in st.session_state:
            st.session_state.multi_expanded_phones = {}

        if fone_limpo in st.session_state.multi_expanded_phones and st.session_state.multi_expanded_phones.get(fone_limpo):
            st.info(f"As empresas com telefone ({ddd}) {num} já estão expandidas na rede.")
            return

        with st.spinner(f"Buscando empresas com telefone ({ddd}) {num}..."):
            months = st.session_state.get('bq_months', 3)
            resp_obj = data_service.buscar_telefone(ddd, num, months=months)
            res_tel = resp_obj.get("results") if isinstance(resp_obj, dict) and "results" in resp_obj else resp_obj

            seen_cnpjs = set()
            filtered_tel = []
            for emp in (res_tel or []):
                e_cnpj = "".join(filter(str.isdigit, str(emp.get('cnpj') or emp.get('cnpj_completo') or '')))
                if e_cnpj:
                    if current_root_clean and e_cnpj == current_root_clean:
                        continue
                    if e_cnpj in seen_cnpjs:
                        continue
                    seen_cnpjs.add(e_cnpj)
                filtered_tel.append(emp)

            if filtered_tel:
                st.session_state.multi_expanded_phones[fone_limpo] = filtered_tel
                st.toast(f"✅ {len(filtered_tel)} empresa(s) com telefone ({ddd}) {num} adicionada(s)!")
            else:
                err = resp_obj.get("error") if isinstance(resp_obj, dict) else None
                st.warning(err or f"Nenhuma outra empresa encontrada com telefone ({ddd}) {num}.")

    # 4. E-MAIL
    elif ent_type == "EMAIL":
        em_limpo = val_str.strip().lower()
        # Regra 1 e 2: Normalizar com strip().lower(), validar presença de '@' e partes não vazias
        if "@" not in em_limpo:
            st.warning(f"E-mail inválido para expansão: '{val_str}'. Ausência de '@'.")
            return
        parts = em_limpo.split("@")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip() or "." not in parts[1]:
            st.warning(f"E-mail inválido para expansão: '{val_str}'. Formato esperado: usuario@dominio.com.")
            return

        if "multi_expanded_emails" not in st.session_state:
            st.session_state.multi_expanded_emails = {}

        if em_limpo in st.session_state.multi_expanded_emails and st.session_state.multi_expanded_emails.get(em_limpo):
            st.info(f"As empresas com e-mail {em_limpo} já estão expandidas na rede.")
            return

        with st.spinner(f"Buscando empresas com e-mail {em_limpo}..."):
            months = st.session_state.get('bq_months', 3)
            resp_obj = data_service.buscar_email(em_limpo, months=months)
            res_em = resp_obj.get("results") if isinstance(resp_obj, dict) and "results" in resp_obj else resp_obj

            seen_cnpjs = set()
            filtered_em = []
            for emp in (res_em or []):
                e_cnpj = "".join(filter(str.isdigit, str(emp.get('cnpj') or emp.get('cnpj_completo') or '')))
                if e_cnpj:
                    if current_root_clean and e_cnpj == current_root_clean:
                        continue
                    if e_cnpj in seen_cnpjs:
                        continue
                    seen_cnpjs.add(e_cnpj)
                filtered_em.append(emp)

            if filtered_em:
                st.session_state.multi_expanded_emails[em_limpo] = filtered_em
                st.toast(f"✅ {len(filtered_em)} empresa(s) com e-mail {em_limpo} adicionada(s)!")
            else:
                err = resp_obj.get("error") if isinstance(resp_obj, dict) else None
                st.warning(err or f"Nenhuma outra empresa encontrada com e-mail {em_limpo}.")

def handle_graph_action(event: Dict[str, Any], expand_fn: Optional[Callable] = None, root_id: Optional[str] = None) -> bool:
    """
    Ponto único e centralizado para validar e despachar ações do grafo.
    Deduplica execuções por nonce e roteia para as funções correspondentes.
    Retorna True se uma ação válida foi executada com sucesso.
    """
    is_valid, err_msg = validate_graph_event(event)
    if not is_valid:
        if err_msg:
            st.warning(f"Ação do grafo rejeitada: {err_msg}")
        return False

    # Deduplicação por nonce (impede repetição no mesmo ciclo do Streamlit)
    nonce = event.get("nonce")
    if nonce:
        last_nonce = st.session_state.get("last_processed_graph_nonce")
        if nonce == last_nonce:
            return False
        st.session_state["last_processed_graph_nonce"] = nonce

    action = event.get("action")

    if action == "expand":
        ent_type = event.get("entity_type") or event.get("type") or "OUTRO"
        ent_val = event.get("entity_value") or event.get("val")
        ent_lbl = event.get("entity_label") or event.get("label") or ent_val
        fn = expand_fn or (lambda t, v, l: executar_expansao_entidade(t, v, l, root_id=root_id))
        fn(ent_type, ent_val, ent_lbl)
        return True

    elif action == "delete":
        node_id = event.get("node_id") or event.get("id") or event.get("val")
        ent_lbl = event.get("entity_label") or event.get("label") or node_id
        return exclude_graph_node(node_id, ent_lbl, root_id=root_id)

    elif action == "toggle_feature":
        feature = event.get("feature")
        if feature == "expand_socios":
            st.session_state.graph_expand_socios = not st.session_state.get('graph_expand_socios', False)
            return True
        elif feature == "expand_contacts":
            st.session_state.graph_expand_contacts = not st.session_state.get('graph_expand_contacts', False)
            return True
        return False

    elif action == "clear":
        clear_graph_expansions()
        return True

    return False
