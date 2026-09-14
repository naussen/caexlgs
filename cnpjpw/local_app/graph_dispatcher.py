"""
Módulo Dispatcher Unificado de Ações do Grafo (Fase 3 do Plano de Correções).
Centraliza a validação, sanitização e roteamento de todos os eventos do grafo,
sejam provenientes do componente interativo Vis.js ou de controles externos.
"""
from typing import Dict, Any, Optional, Tuple, Callable
import streamlit as st

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
        if expand_fn:
            expand_fn(ent_type, ent_val, ent_lbl)
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
