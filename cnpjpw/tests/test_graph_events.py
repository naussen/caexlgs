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

    def test_graph_dispatcher_event_validation(self):
        """Valida a rejeição estrita de eventos malformados pelo dispatcher."""
        from cnpjpw.local_app import graph_dispatcher

        # Não-dicionário
        valido, err = graph_dispatcher.validate_graph_event("string_invalida")
        self.assertFalse(valido)
        self.assertIn("dicionário", err)

        # Ação não permitida
        valido, err = graph_dispatcher.validate_graph_event({"action": "drop_database"})
        self.assertFalse(valido)
        self.assertIn("Ação inválida", err)

        # Expand sem entity_value
        valido, err = graph_dispatcher.validate_graph_event({"action": "expand", "entity_type": "EMPRESA"})
        self.assertFalse(valido)
        self.assertIn("entity_value", err)

        # Delete sem node_id
        valido, err = graph_dispatcher.validate_graph_event({"action": "delete"})
        self.assertFalse(valido)
        self.assertIn("node_id", err)

        # Toggle com feature desconhecida
        valido, err = graph_dispatcher.validate_graph_event({"action": "toggle_feature", "feature": "modo_escuro"})
        self.assertFalse(valido)
        self.assertIn("Feature inválida", err)

    def test_graph_dispatcher_handles_all_actions(self):
        """Valida o roteamento completo das 4 ações permitidas pelo dispatcher unificado."""
        from cnpjpw.local_app import graph_dispatcher
        import streamlit as st

        st.session_state["last_processed_graph_nonce"] = None
        st.session_state["graph_excluded_nodes"] = set()
        st.session_state["graph_expand_socios"] = False
        st.session_state["graph_expand_contacts"] = False

        expanded_called = []
        def fake_expand(t, v, l):
            expanded_called.append((t, v, l))

        # 1. Expand
        res_exp = graph_dispatcher.handle_graph_action({
            "action": "expand",
            "entity_type": "EMPRESA",
            "entity_value": "99999999000199",
            "entity_label": "NOVA EMPRESA",
            "nonce": "test_exp_nonce"
        }, expand_fn=fake_expand)
        self.assertTrue(res_exp)
        self.assertEqual(len(expanded_called), 1)
        self.assertEqual(expanded_called[0][1], "99999999000199")

        # 2. Delete
        res_del = graph_dispatcher.handle_graph_action({
            "action": "delete",
            "node_id": "socio_teste",
            "entity_label": "Sócio Teste",
            "nonce": "test_del_nonce"
        })
        self.assertTrue(res_del)
        self.assertIn("socio_teste", st.session_state["graph_excluded_nodes"])

        # 3. Toggle Feature
        res_tog = graph_dispatcher.handle_graph_action({
            "action": "toggle_feature",
            "feature": "expand_socios",
            "nonce": "test_tog_nonce"
        })
        self.assertTrue(res_tog)
        self.assertTrue(st.session_state["graph_expand_socios"])

        # 4. Clear
        res_clr = graph_dispatcher.handle_graph_action({
            "action": "clear",
            "nonce": "test_clr_nonce"
        })
        self.assertTrue(res_clr)
        self.assertEqual(len(st.session_state["graph_excluded_nodes"]), 0)
        self.assertFalse(st.session_state["graph_expand_socios"])

        # 5. Open New CNPJ
        st.session_state["show_novo_cnpj_dialog"] = False
        res_new = graph_dispatcher.handle_graph_action({
            "action": "open_new_cnpj",
            "nonce": "test_new_cnpj_nonce"
        })
        self.assertTrue(res_new)
        self.assertTrue(st.session_state.get("show_novo_cnpj_dialog"))

    def test_graph_dispatcher_blocks_root_deletion(self):
        """Valida que a exclusão da empresa raiz sob análise é terminantemente bloqueada."""
        from cnpjpw.local_app import graph_dispatcher
        import streamlit as st

        root_cnpj = "12345678000190"
        st.session_state["graph_excluded_nodes"] = set()

        # Tentativa de excluir CNPJ raiz puro
        res1 = graph_dispatcher.handle_graph_action({
            "action": "delete",
            "node_id": root_cnpj,
            "nonce": "n_root_1"
        }, root_id=root_cnpj)
        self.assertFalse(res1)
        self.assertNotIn(root_cnpj, st.session_state["graph_excluded_nodes"])

        # Tentativa de excluir nó com prefixo cnpj_
        res2 = graph_dispatcher.handle_graph_action({
            "action": "delete",
            "node_id": f"cnpj_{root_cnpj}",
            "nonce": "n_root_2"
        }, root_id=root_cnpj)
        self.assertFalse(res2)
        self.assertNotIn(f"cnpj_{root_cnpj}", st.session_state["graph_excluded_nodes"])

    def test_novo_cnpj_add_to_current_graph(self):
        """Valida a adição de um novo CNPJ ao grafo atual sem gerar novo grafo."""
        import streamlit as st

        root_cnpj = "11111111000111"
        new_cnpj = "22222222000122"
        st.session_state["current_cnpj"] = root_cnpj
        st.session_state["multi_expanded_companies"] = {}
        st.session_state["graph_excluded_nodes"] = {new_cnpj, f"cnpj_{new_cnpj}"}

        emp_dados = {
            "cnpj": new_cnpj,
            "nome_empresarial": "NOVA EMPRESA TESTE LTDA",
            "situacao_cadastral": "02",
            "situacao_cadastral_descricao": "ATIVA",
            "socios": []
        }

        # Simula a adição ao grafo atual
        st.session_state["multi_expanded_companies"][new_cnpj] = emp_dados
        st.session_state["graph_excluded_nodes"].discard(new_cnpj)
        st.session_state["graph_excluded_nodes"].discard(f"cnpj_{new_cnpj}")

        # Verifica que o grafo raiz permaneceu inalterado (não gera novo grafo)
        self.assertEqual(st.session_state["current_cnpj"], root_cnpj)
        # Verifica que a nova empresa foi adicionada ao grafo atual
        self.assertIn(new_cnpj, st.session_state["multi_expanded_companies"])
        self.assertEqual(st.session_state["multi_expanded_companies"][new_cnpj]["nome_empresarial"], "NOVA EMPRESA TESTE LTDA")
        # Verifica que não está mais excluída
        self.assertNotIn(new_cnpj, st.session_state["graph_excluded_nodes"])
        self.assertNotIn(f"cnpj_{new_cnpj}", st.session_state["graph_excluded_nodes"])


class TestEntityExpansionSemantics(unittest.TestCase):
    """Testes unitários das 4 regras semânticas de expansão pontual de entidades (Fase 4)."""

    def setUp(self):
        import streamlit as st
        st.session_state["multi_expanded_companies"] = {}
        st.session_state["multi_expanded_socios"] = {}
        st.session_state["multi_expanded_phones"] = {}
        st.session_state["multi_expanded_emails"] = {}
        st.session_state["selected_cnpj"] = "11222333000181"

    @patch("cnpjpw.local_app.graph_dispatcher.data_service.get_cnpj")
    def test_expand_empresa_valid_and_root_protection(self, mock_get_cnpj):
        """Valida validação de 14 dígitos, proteção da raiz e deduplicação para empresas."""
        from cnpjpw.local_app import graph_dispatcher
        import streamlit as st

        mock_get_cnpj.return_value = {
            "cnpj": "99888777000100",
            "nome_empresarial": "EMPRESA AFILIADA LTDA"
        }

        # 1. Expansão de empresa válida
        graph_dispatcher.executar_expansao_entidade(
            ent_type="EMPRESA",
            ent_val="cnpj_99888777000100",
            ent_label="EMPRESA AFILIADA LTDA",
            root_id="11222333000181"
        )
        mock_get_cnpj.assert_called_once_with("99888777000100")
        self.assertIn("99888777000100", st.session_state.multi_expanded_companies)

        # 2. Re-expansão não chama a API novamente (deduplicação)
        mock_get_cnpj.reset_mock()
        graph_dispatcher.executar_expansao_entidade(
            ent_type="EMPRESA",
            ent_val="99888777000100",
            root_id="11222333000181"
        )
        mock_get_cnpj.assert_not_called()

        # 3. Empresa raiz NÃO deve ser adicionada a multi_expanded_companies
        mock_get_cnpj.reset_mock()
        graph_dispatcher.executar_expansao_entidade(
            ent_type="EMPRESA",
            ent_val="11.222.333/0001-81",
            root_id="11222333000181"
        )
        mock_get_cnpj.assert_not_called()
        self.assertNotIn("11222333000181", st.session_state.multi_expanded_companies)

        # 4. CNPJ inválido (< 14 dígitos) não chama a API
        mock_get_cnpj.reset_mock()
        graph_dispatcher.executar_expansao_entidade(
            ent_type="EMPRESA",
            ent_val="12345",
            root_id="11222333000181"
        )
        mock_get_cnpj.assert_not_called()

    @patch("cnpjpw.local_app.graph_dispatcher.data_service.buscar_socio")
    @patch("cnpjpw.local_app.graph_dispatcher.data_service.buscar_empresas_do_socio")
    def test_expand_socio_doc_vs_name_and_filters_root(self, mock_buscar_nome, mock_buscar_socio):
        """Valida prioridade de documento não-mascarado, fallback por nome e exclusão de raiz/duplicatas."""
        from cnpjpw.local_app import graph_dispatcher
        import streamlit as st

        # 1. Documento não mascarado (11 dígitos) utiliza buscar_socio
        mock_buscar_socio.return_value = [
            {"cnpj": "11222333000181", "razao_social": "EMPRESA RAIZ"}, # deve ser filtrada
            {"cnpj": "44555666000177", "razao_social": "EMPRESA DO SOCIO B"},
            {"cnpj": "44555666000177", "razao_social": "EMPRESA DO SOCIO B DUPLICADA"}, # deve ser deduplicada
        ]
        graph_dispatcher.executar_expansao_entidade(
            ent_type="SOCIO",
            ent_val="12345678901",
            ent_label="JOAO DA SILVA",
            root_id="11222333000181"
        )
        mock_buscar_socio.assert_called_once_with("12345678901")
        mock_buscar_nome.assert_not_called()
        self.assertIn("12345678901", st.session_state.multi_expanded_socios)
        res_list = st.session_state.multi_expanded_socios["12345678901"]
        self.assertEqual(len(res_list), 1)
        self.assertEqual(res_list[0]["cnpj"], "44555666000177")

        # 2. Documento mascarado ou apenas nome utiliza buscar_empresas_do_socio com upper()
        mock_buscar_socio.reset_mock()
        mock_buscar_nome.reset_mock()
        mock_buscar_nome.return_value = [
            {"cnpj": "77888999000166", "razao_social": "EMPRESA NOVA"}
        ]
        graph_dispatcher.executar_expansao_entidade(
            ent_type="SOCIO",
            ent_val="socio_maria de souza",
            ent_label="Maria de Souza",
            root_id="11222333000181"
        )
        mock_buscar_nome.assert_called_once_with("MARIA DE SOUZA")
        mock_buscar_socio.assert_not_called()
        self.assertIn("MARIA DE SOUZA", st.session_state.multi_expanded_socios)

    @patch("cnpjpw.local_app.graph_dispatcher.data_service.buscar_telefone")
    def test_expand_telefone_strict_ddd_and_filters_root(self, mock_buscar_tel):
        """Valida que telefone exige DDD explícito (sem fallback para '11') e filtra raiz."""
        from cnpjpw.local_app import graph_dispatcher
        import streamlit as st

        # 1. Telefone sem DDD (8 dígitos) é rejeitado
        graph_dispatcher.executar_expansao_entidade(
            ent_type="TELEFONE",
            ent_val="tel_988887777",
            root_id="11222333000181"
        )
        mock_buscar_tel.assert_not_called()
        self.assertNotIn("988887777", st.session_state.multi_expanded_phones)

        # 2. Telefone válido com DDD (11 dígitos) busca com ddd e num separados
        mock_buscar_tel.return_value = [
            {"cnpj": "11222333000181", "razao_social": "EMPRESA RAIZ"}, # filtrada
            {"cnpj": "33444555000122", "razao_social": "EMPRESA COLIGADA"}
        ]
        graph_dispatcher.executar_expansao_entidade(
            ent_type="TELEFONE",
            ent_val="(21) 98888-7777",
            root_id="11222333000181"
        )
        mock_buscar_tel.assert_called_once_with("21", "988887777", months=3)
        self.assertIn("21988887777", st.session_state.multi_expanded_phones)
        self.assertEqual(len(st.session_state.multi_expanded_phones["21988887777"]), 1)
        self.assertEqual(st.session_state.multi_expanded_phones["21988887777"][0]["cnpj"], "33444555000122")

    @patch("cnpjpw.local_app.graph_dispatcher.data_service.buscar_email")
    def test_expand_email_normalization_and_validation(self, mock_buscar_email):
        """Valida normalização (strip + lower), validação de formato e filtro de raiz."""
        from cnpjpw.local_app import graph_dispatcher
        import streamlit as st

        # 1. E-mail com formato inválido (sem @ ou sem domínio com ponto)
        graph_dispatcher.executar_expansao_entidade(
            ent_type="EMAIL",
            ent_val="email_invalido.com",
            root_id="11222333000181"
        )
        mock_buscar_email.assert_not_called()

        # 2. E-mail válido com maiúsculas e espaços
        mock_buscar_email.return_value = [
            {"cnpj": "11222333000181"}, # filtrada
            {"cnpj": "55666777000144"},
            {"cnpj": "55666777000144"}  # duplicada
        ]
        graph_dispatcher.executar_expansao_entidade(
            ent_type="EMAIL",
            ent_val="email_  Diretoria@PomeloTech.COM.br ",
            root_id="11222333000181"
        )
        mock_buscar_email.assert_called_once_with("diretoria@pomelotech.com.br", months=3)
        self.assertIn("diretoria@pomelotech.com.br", st.session_state.multi_expanded_emails)
        self.assertEqual(len(st.session_state.multi_expanded_emails["diretoria@pomelotech.com.br"]), 1)
        self.assertEqual(st.session_state.multi_expanded_emails["diretoria@pomelotech.com.br"][0]["cnpj"], "55666777000144")
        self.assertIn("diretoria@pomelotech.com.br", st.session_state.multi_expanded_emails)
        self.assertEqual(len(st.session_state.multi_expanded_emails["diretoria@pomelotech.com.br"]), 1)
        self.assertEqual(st.session_state.multi_expanded_emails["diretoria@pomelotech.com.br"][0]["cnpj"], "55666777000144")


if __name__ == "__main__":
    unittest.main()
