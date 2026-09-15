"""
test_node_exclusion.py — Testes automatizados da Exclusão de Entidades do Grafo (Fase 7).

Valida:
1. Exclusão de nó comum remove o nó e todas as suas arestas incidentes;
2. Nó permanece excluído após rerun (persiste em session_state);
3. Raiz nunca pode ser excluída em qualquer variação de identificador (CNPJ limpo, com máscara, cnpj_, empresa_root);
4. Restauração de nó recompõe o nó e suas arestas incidentes;
5. Salvar e carregar caso de investigação (case_manager) preserva as exclusões;
6. Identificador inexistente, nulo ou vazio não gera exceção.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_app")))

from cnpjpw.local_app import graph_builder, graph_dispatcher, case_manager


class TestNodeExclusion(unittest.TestCase):

    def setUp(self):
        self.root_cnpj = "11111111000111"
        self.root_data = {
            "cnpj": self.root_cnpj,
            "razao_social": "EMPRESA RAIZ LTDA",
            "nome_empresarial": "EMPRESA RAIZ LTDA",
            "ddd1": "11",
            "telefone_1": "999991111",
            "correio_eletronico": "contato@raiz.com.br",
            "socios": [
                {"nome": "CARLOS SILVA", "cnpj_cpf": "12345678901"},
                {"nome": "MARIA SOUZA", "cnpj_cpf": "98765432100"}
            ]
        }
        self.carlos_node_id = "socio_carlos silva"
        self.root_node_id = f"cnpj_{self.root_cnpj}"

    # -------------------------------------------------------------
    # 1. EXCLUIR NÓ COMUM REMOVE NÓ E ARESTAS INCIDENTES
    # -------------------------------------------------------------
    def test_exclude_common_node_removes_node_and_edges(self):
        """Valida que excluir um nó de sócio remove o nó e suas arestas conectadas à raiz."""
        # Baseline sem exclusões
        nodes_base, edges_base, _ = graph_builder.build_graph_elements(
            root_data=self.root_data,
            excluded_nodes=set()
        )
        self.assertTrue(any(n["id"] == self.carlos_node_id for n in nodes_base))
        self.assertTrue(any(e["from"] == self.root_node_id and e["to"] == self.carlos_node_id for e in edges_base))

        # Agora com o nó em excluded_nodes
        excluded = {self.carlos_node_id}
        nodes_after, edges_after, available_after = graph_builder.build_graph_elements(
            root_data=self.root_data,
            excluded_nodes=excluded
        )
        # Nó não deve estar na lista de nós nem em available_nodes
        self.assertFalse(any(n["id"] == self.carlos_node_id for n in nodes_after))
        self.assertFalse(any(a["id"] == self.carlos_node_id for a in available_after))
        # Nenhuma aresta incidente deve permanecer
        self.assertFalse(any(e["from"] == self.carlos_node_id or e["to"] == self.carlos_node_id for e in edges_after))
        # Contagem de nós diminuiu em 1
        self.assertEqual(len(nodes_after), len(nodes_base) - 1)

    # -------------------------------------------------------------
    # 2. NÓ CONTINUA EXCLUÍDO APÓS RERUN (PERSISTE EM SESSION_STATE)
    # -------------------------------------------------------------
    def test_excluded_node_persists_in_session_state(self):
        """Valida que a exclusão via dispatcher persiste em st.session_state."""
        mock_state = {
            "graph_excluded_nodes": set(),
            "current_cnpj": self.root_cnpj
        }
        with patch.object(graph_dispatcher.st, "session_state", mock_state):
            with patch.object(graph_dispatcher.st, "toast"):
                success = graph_dispatcher.exclude_graph_node(self.carlos_node_id, label="CARLOS SILVA", root_id=self.root_cnpj)
                self.assertTrue(success)
                self.assertIn(self.carlos_node_id, mock_state["graph_excluded_nodes"])

                # Simula rerun reconstruindo o grafo com o estado persistido
                nodes, edges, _ = graph_builder.build_graph_elements(
                    root_data=self.root_data,
                    excluded_nodes=mock_state["graph_excluded_nodes"]
                )
                self.assertFalse(any(n["id"] == self.carlos_node_id for n in nodes))

    # -------------------------------------------------------------
    # 3. RAIZ NUNCA PODE SER EXCLUÍDA
    # -------------------------------------------------------------
    def test_root_node_never_excluded(self):
        """
        Valida que qualquer tentativa de exclusão da raiz é bloqueada
        (CNPJ limpo, com máscara, prefixo cnpj_, ou empresa_root).
        """
        mock_state = {
            "graph_excluded_nodes": set(),
            "current_cnpj": self.root_cnpj
        }
        root_variations = [
            self.root_cnpj,                          # "11111111000111"
            "11.111.111/0001-11",                    # com máscara
            f"cnpj_{self.root_cnpj}",                # "cnpj_11111111000111"
            "empresa_root",                          # "empresa_root"
            "EMPRESA_ROOT",                          # maiúsculas
            "root"                                   # alias
        ]
        with patch.object(graph_dispatcher.st, "session_state", mock_state):
            with patch.object(graph_dispatcher.st, "warning") as mock_warn:
                with patch.object(graph_dispatcher.st, "toast"):
                    for var in root_variations:
                        res = graph_dispatcher.exclude_graph_node(var, root_id=self.root_cnpj)
                        self.assertFalse(res, f"Falha: raiz foi permitida para exclusão com identificador '{var}'")
                        self.assertEqual(len(mock_state["graph_excluded_nodes"]), 0)
                    self.assertEqual(mock_warn.call_count, len(root_variations))

    # -------------------------------------------------------------
    # 4. RESTAURAR NÓ RECOMPÕE O NÓ E SUAS ARESTAS
    # -------------------------------------------------------------
    def test_restore_node_reconstructs_edges(self):
        """Valida que restaurar um nó o remove de graph_excluded_nodes e recompõe suas arestas."""
        mock_state = {
            "graph_excluded_nodes": {self.carlos_node_id},
            "current_cnpj": self.root_cnpj
        }
        with patch.object(graph_dispatcher.st, "session_state", mock_state):
            with patch.object(graph_dispatcher.st, "toast"):
                # Restaura o nó
                res = graph_dispatcher.restore_graph_node(self.carlos_node_id, label="CARLOS SILVA")
                self.assertTrue(res)
                self.assertNotIn(self.carlos_node_id, mock_state["graph_excluded_nodes"])

                # Reconstrói o grafo após a restauração
                nodes_restored, edges_restored, _ = graph_builder.build_graph_elements(
                    root_data=self.root_data,
                    excluded_nodes=mock_state["graph_excluded_nodes"]
                )
                self.assertTrue(any(n["id"] == self.carlos_node_id for n in nodes_restored))
                self.assertTrue(any(e["to"] == self.carlos_node_id for e in edges_restored))

    def test_restore_all_nodes(self):
        """Valida restauração de todos os nós de uma só vez."""
        mock_state = {
            "graph_excluded_nodes": {self.carlos_node_id, "socio_maria souza"},
            "current_cnpj": self.root_cnpj
        }
        with patch.object(graph_dispatcher.st, "session_state", mock_state):
            with patch.object(graph_dispatcher.st, "toast"):
                res = graph_dispatcher.restore_all_graph_nodes()
                self.assertTrue(res)
                self.assertEqual(len(mock_state["graph_excluded_nodes"]), 0)

    # -------------------------------------------------------------
    # 5. SALVAR E CARREGAR CASO PRESERVA EXCLUSÕES (CASE_MANAGER)
    # -------------------------------------------------------------
    def test_save_and_load_case_preserves_exclusions(self):
        """Valida que case_manager serializa e desserializa perfeitamente o conjunto de exclusões."""
        excluded_initial = {"socio_carlos silva", "tel_11999991111"}
        json_export = case_manager.export_case_json(
            root_cnpj=self.root_cnpj,
            root_name="EMPRESA RAIZ LTDA",
            manual_nodes=[],
            manual_edges=[],
            excluded_nodes=excluded_initial,
            investigation_notes="Notas de teste"
        )
        self.assertIn("socio_carlos silva", json_export)
        self.assertIn("tel_11999991111", json_export)

        imported = case_manager.import_case_json(json_export)
        self.assertIn("excluded_nodes", imported)
        self.assertEqual(imported["excluded_nodes"], excluded_initial)
        self.assertIsInstance(imported["excluded_nodes"], set)

    # -------------------------------------------------------------
    # 6. IDENTIFICADOR INEXISTENTE NÃO GERA EXCEÇÃO
    # -------------------------------------------------------------
    def test_nonexistent_node_id_handles_gracefully(self):
        """Valida que IDs nulos, vazios ou inexistentes não lançam exceção."""
        mock_state = {
            "graph_excluded_nodes": set(),
            "current_cnpj": self.root_cnpj
        }
        with patch.object(graph_dispatcher.st, "session_state", mock_state):
            with patch.object(graph_dispatcher.st, "toast"):
                self.assertFalse(graph_dispatcher.exclude_graph_node("", root_id=self.root_cnpj))
                self.assertFalse(graph_dispatcher.exclude_graph_node(None, root_id=self.root_cnpj))
                self.assertFalse(graph_dispatcher.restore_graph_node("", label=""))
                self.assertFalse(graph_dispatcher.restore_graph_node(None, label=""))
                # ID que não está em excluded_nodes retorna False ao restaurar, sem lançar exceção
                self.assertFalse(graph_dispatcher.restore_graph_node("id_que_nunca_foi_excluido"))


if __name__ == "__main__":
    unittest.main()
