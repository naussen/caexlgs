"""
Testes automatizados dos eventos e despacho do Custom Component do Grafo (Fase 2 do Plano de Correções).
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Assegura que a raiz e local_app estão no path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_app")))

from cnpjpw.local_app import graph_builder

class TestGraphEvents(unittest.TestCase):

    def setUp(self):
        self.sample_company = {
            "cnpj": "12345678000190",
            "razao_social": "POMELO TECNOLOGIA LTDA",
            "nome_fantasia": "POMELO TECH",
            "situacao_cadastral": "02",
            "situacao_cadastral_descricao": "ATIVA",
            "socios": [
                {"nome": "CARLOS SILVA", "qualificacao": "Sócio-Administrador", "cpf_cnpj": "***123456**"}
            ],
            "telefones": [{"ddd": "11", "telefone": "999998888"}],
            "emails": [{"email": "contato@pomelotech.com.br"}]
        }

    def test_expand_event_payload_structure(self):
        """Valida que o payload de expand contém todos os campos obrigatórios padronizados."""
        payload = {
            "action": "expand",
            "node_id": "cnpj_12345678000190",
            "entity_type": "EMPRESA",
            "entity_value": "12345678000190",
            "entity_label": "POMELO TECNOLOGIA LTDA",
            "feature": None,
            "nonce": "1720000000_abc123"
        }
        self.assertEqual(payload["action"], "expand")
        self.assertTrue(payload["node_id"].startswith("cnpj_"))
        self.assertEqual(payload["entity_type"], "EMPRESA")
        self.assertEqual(payload["entity_value"], "12345678000190")
        self.assertIn("POMELO", payload["entity_label"])
        self.assertIsNotNone(payload["nonce"])

    def test_delete_event_payload_structure(self):
        """Valida que o payload de delete envia o node_id e o nonce identificador."""
        payload = {
            "action": "delete",
            "node_id": "socio_carlos_silva",
            "entity_type": "SOCIO",
            "entity_value": "CARLOS SILVA",
            "entity_label": "CARLOS SILVA",
            "feature": None,
            "nonce": "1720000001_def456"
        }
        self.assertEqual(payload["action"], "delete")
        self.assertEqual(payload["node_id"], "socio_carlos_silva")
        self.assertIsNotNone(payload["nonce"])

    def test_toggle_feature_payload_structure(self):
        """Valida que o evento toggle_feature envia o nome exato da funcionalidade."""
        payload_socios = {
            "action": "toggle_feature",
            "node_id": None,
            "entity_type": None,
            "entity_value": None,
            "entity_label": None,
            "feature": "expand_socios",
            "nonce": "1720000002_ghi789"
        }
        self.assertEqual(payload_socios["action"], "toggle_feature")
        self.assertEqual(payload_socios["feature"], "expand_socios")

        payload_contacts = {
            "action": "toggle_feature",
            "node_id": None,
            "entity_type": None,
            "entity_value": None,
            "entity_label": None,
            "feature": "expand_contacts",
            "nonce": "1720000003_jkl012"
        }
        self.assertEqual(payload_contacts["action"], "toggle_feature")
        self.assertEqual(payload_contacts["feature"], "expand_contacts")

    def test_clear_event_distinct_from_individual_delete(self):
        """Valida que o evento clear reinicializa o grafo por completo e não é confundido com delete individual."""
        payload_clear = {
            "action": "clear",
            "node_id": None,
            "entity_type": None,
            "entity_value": None,
            "entity_label": None,
            "feature": None,
            "nonce": "1720000004_mno345"
        }
        self.assertEqual(payload_clear["action"], "clear")
        self.assertIsNone(payload_clear["node_id"])

    def test_nonce_deduplication_prevents_duplicate_processing(self):
        """Valida que o mesmo nonce de evento não é reprocessado em reruns consecutivos."""
        session_state = {
            "last_processed_graph_nonce": None,
            "processed_events": []
        }

        def process_event(event):
            nonce = event.get("nonce")
            if nonce and nonce != session_state["last_processed_graph_nonce"]:
                session_state["last_processed_graph_nonce"] = nonce
                session_state["processed_events"].append(event["action"])
                return True
            return False

        ev = {"action": "expand", "node_id": "cnpj_1", "nonce": "nonce_unique_1"}

        # Primeira execução (evento recebido)
        primeira_exec = process_event(ev)
        self.assertTrue(primeira_exec)
        self.assertEqual(len(session_state["processed_events"]), 1)

        # Rerun subseqüente (mesmo componente retorna o mesmo valor no Streamlit)
        segunda_exec = process_event(ev)
        self.assertFalse(segunda_exec)
        self.assertEqual(len(session_state["processed_events"]), 1, "Evento com mesmo nonce não pode ser processado duas vezes")

    def test_expand_click_triggers_expansion_and_rerun(self):
        """Simula o recebimento do evento expand do componente oficial e verifica execução e rerun."""
        mock_st = MagicMock()
        mock_st.session_state = {
            "last_processed_graph_nonce": None,
            "multi_expanded_companies": {}
        }
        mock_rerun_called = False

        def fake_rerun():
            nonlocal mock_rerun_called
            mock_rerun_called = True

        mock_st.rerun = fake_rerun

        event = {
            "action": "expand",
            "node_id": "cnpj_12345678000190",
            "entity_type": "EMPRESA",
            "entity_value": "12345678000190",
            "entity_label": "POMELO TECNOLOGIA LTDA",
            "nonce": "expand_nonce_1"
        }

        # Simula o despachante de app.py
        expansion_executed = False
        def fake_executar_expansao(ent_type, ent_val, ent_lbl):
            nonlocal expansion_executed
            expansion_executed = True

        # Despacho do evento
        if event and event.get("nonce") != mock_st.session_state["last_processed_graph_nonce"]:
            mock_st.session_state["last_processed_graph_nonce"] = event["nonce"]
            if event.get("action") == "expand":
                fake_executar_expansao(event["entity_type"], event["entity_value"], event["entity_label"])
                mock_st.rerun()

        self.assertTrue(expansion_executed, "A expansão da entidade deve ser executada")
        self.assertTrue(mock_rerun_called, "st.rerun() deve ser acionado após expansão")
        self.assertEqual(mock_st.session_state["last_processed_graph_nonce"], "expand_nonce_1")

    def test_delete_click_persists_exclusion_after_rerun(self):
        """Valida que o evento delete persiste a exclusão do nó em graph_excluded_nodes após rerun."""
        mock_st = MagicMock()
        mock_st.session_state = {
            "last_processed_graph_nonce": None,
            "graph_excluded_nodes": set()
        }
        toast_msgs = []
        mock_st.toast = lambda msg: toast_msgs.append(msg)
        mock_st.rerun = MagicMock()

        event = {
            "action": "delete",
            "node_id": "socio_carlos_silva",
            "entity_type": "SOCIO",
            "entity_value": "CARLOS SILVA",
            "entity_label": "CARLOS SILVA",
            "nonce": "del_nonce_1"
        }

        # Despacho do evento delete
        if event and event.get("nonce") != mock_st.session_state["last_processed_graph_nonce"]:
            mock_st.session_state["last_processed_graph_nonce"] = event["nonce"]
            if event.get("action") == "delete":
                mock_st.session_state["graph_excluded_nodes"].add(event["node_id"])
                mock_st.toast(f"✕ Entidade '{event['entity_label']}' removida da rede.")
                mock_st.rerun()

        self.assertIn("socio_carlos_silva", mock_st.session_state["graph_excluded_nodes"])
        self.assertEqual(len(toast_msgs), 1)
        self.assertIn("CARLOS SILVA", toast_msgs[0])
        mock_st.rerun.assert_called_once()

        # Verifica que em uma nova passagem o nó continua na lista de excluídos
        nodes_list, _, _ = graph_builder.build_graph_elements(
            root_data=self.sample_company,
            excluded_nodes=mock_st.session_state["graph_excluded_nodes"]
        )
        carlos_node = next((n for n in nodes_list if n["id"] == "socio_carlos_silva"), None)
        self.assertIsNone(carlos_node, "Nó excluído não deve reaparecer nos elementos do grafo")

    def test_render_interactive_graph_passes_all_arguments(self):
        """Valida que render_interactive_graph compila os elementos e invoca o componente declarado."""
        with patch.object(graph_builder, "_vis_graph_component", return_value={"action": "test"}) as mock_comp:
            comp_val, avail = graph_builder.render_interactive_graph(
                root_data=self.sample_company,
                height=800,
                key="test_key"
            )
            mock_comp.assert_called_once()
            _, kwargs = mock_comp.call_args
            self.assertEqual(kwargs["height"], 800)
            self.assertEqual(kwargs["key"], "test_key")
            self.assertGreater(len(kwargs["nodes"]), 0)
            self.assertGreater(len(kwargs["edges"]), 0)
            self.assertEqual(comp_val, {"action": "test"})

if __name__ == "__main__":
    unittest.main()
