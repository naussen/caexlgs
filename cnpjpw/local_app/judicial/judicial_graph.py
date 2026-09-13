"""
Integrador de Grafos para Processos Judiciais (Vis.js).
Converte processos e vínculos em nós e arestas interativas compatíveis com o Graph Builder do CAEXLGS.
"""
from typing import List, Dict, Any, Tuple
from .models import ProcessoJudicial, VinculoProcessual, PoloProcessual
from .validators import formatar_numero_processo_cnj, limpar_digitos

COLOR_PROCESSO_NODE = "#4A148C"     # Roxo Profundo / Jurídico
COLOR_PROCESSO_BORDER = "#1A237E"   # Azul Meia-Noite
COLOR_EDGE_AUTOR = "#2E7D32"        # Verde (Polo Ativo)
COLOR_EDGE_REU = "#C62828"          # Vermelho Alerta (Polo Passivo / Executado)
COLOR_EDGE_OUTROS = "#546E7A"       # Cinza ardósia


def converter_processos_para_elementos_grafo(
    processos: List[ProcessoJudicial],
    vinculos: List[VinculoProcessual],
    id_no_origem: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Gera os nós de processos judiciais (⚖️) e as arestas conectando ao nó de origem
    (Empresa CNPJ ou Pessoa Física Sócio).
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # Mapa de vínculos por número de processo para saber o polo em relação à origem
    vinculo_por_proc = {limpar_digitos(v.numero_processo): v for v in vinculos}

    for p in processos:
        num_clean = limpar_digitos(p.numero)
        node_id = f"proc_{num_clean}"
        num_formatado = p.numero_formatado or formatar_numero_processo_cnj(num_clean)

        vinculo = vinculo_por_proc.get(num_clean)
        polo_origem = vinculo.polo if vinculo else PoloProcessual.DESCONHECIDO

        # Título detalhado (Tooltip em HTML)
        partes_html = "<br>".join([f"• <b>{parte.polo.value}:</b> {parte.nome}" for parte in p.partes[:5]])
        if len(p.partes) > 5:
            partes_html += f"<br>• ... mais {len(p.partes) - 5} partes"

        tooltip = (
            f"<div style='text-align: left; max-width: 320px; font-size: 12px;'>"
            f"<b>⚖️ PROCESSO JUDICIAL</b><br>"
            f"<b>Número:</b> {num_formatado}<br>"
            f"<b>Tribunal:</b> {p.tribunal} | <b>Grau:</b> {p.grau or 'N/I'}<br>"
            f"<b>Classe:</b> {p.classe or 'Não informada'}<br>"
            f"<b>Órgão:</b> {p.orgao_julgador or 'Não informado'}<br>"
            f"<b>Última Atualização:</b> {p.data_ultima_atualizacao or 'N/I'}<br>"
            f"<hr style='margin: 4px 0;'>"
            f"<b>Partes:</b><br>{partes_html or 'Nenhuma parte mapeada'}"
            f"</div>"
        )

        nodes.append({
            "id": node_id,
            "label": f"⚖️ {p.tribunal}\n{num_formatado[:15]}...",
            "title": tooltip,
            "shape": "box",
            "margin": 8,
            "color": {
                "background": "#F3E5F5",
                "border": COLOR_PROCESSO_NODE,
                "highlight": {"background": "#E1BEE7", "border": "#311B92"},
            },
            "font": {"size": 11, "face": "Helvetica", "color": "#1A237E", "bold": True},
            "borderWidth": 2,
            "tipo": "PROCESSO",
            "dados": p.to_dict(),
        })

        # Cria a aresta conectando o nó de origem ao processo
        if polo_origem == PoloProcessual.ATIVO:
            edge_color = COLOR_EDGE_AUTOR
            edge_label = "Autor (Polo Ativo)"
        elif polo_origem == PoloProcessual.PASSIVO:
            edge_color = COLOR_EDGE_REU
            edge_label = "Réu (Polo Passivo)"
        else:
            edge_color = COLOR_EDGE_OUTROS
            edge_label = "Parte / Interessado"

        edges.append({
            "from": id_no_origem,
            "to": node_id,
            "label": edge_label,
            "font": {"size": 10, "align": "middle", "color": edge_color},
            "color": {"color": edge_color, "highlight": edge_color},
            "arrows": "to",
            "dashes": polo_origem == PoloProcessual.PASSIVO,
            "width": 2 if polo_origem == PoloProcessual.PASSIVO else 1.5,
        })

    return nodes, edges
