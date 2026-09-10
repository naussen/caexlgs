"""
Módulo para Persistência e Gerenciamento de Casos de Investigação (Dossiês JSON).
Permite exportar e importar o estado completo da análise:
- Nós e vínculos manuais
- Nós excluídos (contadores, etc.)
- Anotações e conclusões da investigação
- Opções ativas de expansão e filtros
"""
import json
from datetime import datetime

CURRENT_CASE_VERSION = "1.0"

def export_case_json(
    root_cnpj: str,
    root_name: str,
    manual_nodes: list,
    manual_edges: list,
    excluded_nodes: set,
    investigation_notes: str = "",
    active_options: dict = None
) -> str:
    """
    Serializa o dossiê de investigação em uma string JSON formatada.
    """
    if active_options is None:
        active_options = {}

    case_data = {
        "format": "antigravity-cnpj-investigation-case",
        "version": CURRENT_CASE_VERSION,
        "exported_at": datetime.now().isoformat(),
        "root_company": {
            "cnpj": root_cnpj,
            "name": root_name
        },
        "investigation": {
            "notes": investigation_notes or "",
            "manual_nodes": manual_nodes or [],
            "manual_edges": manual_edges or [],
            "excluded_nodes": list(excluded_nodes or [])
        },
        "options": active_options
    }

    return json.dumps(case_data, indent=2, ensure_ascii=False)


def import_case_json(json_str: str) -> dict:
    """
    Importa e valida um arquivo de dossiê de investigação em JSON.
    Retorna um dicionário estruturado com os dados do caso.
    """
    try:
        data = json.loads(json_str)
    except Exception as e:
        raise ValueError(f"Arquivo JSON inválido ou corrompido: {str(e)}")

    if data.get("format") != "antigravity-cnpj-investigation-case":
        # Formato genérico compatível
        pass

    investigation = data.get("investigation", {})
    return {
        "version": data.get("version", CURRENT_CASE_VERSION),
        "exported_at": data.get("exported_at"),
        "root_company": data.get("root_company", {}),
        "notes": investigation.get("notes", ""),
        "manual_nodes": investigation.get("manual_nodes", []),
        "manual_edges": investigation.get("manual_edges", []),
        "excluded_nodes": set(investigation.get("excluded_nodes", [])),
        "options": data.get("options", {})
    }
