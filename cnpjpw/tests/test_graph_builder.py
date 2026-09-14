"""
Testes unitários para o módulo graph_builder.
Valida geração correta de elementos do grafo, filtragem rigorosa de contadores,
prevenção e tratamento de falsos positivos (ex: assessoria esportiva) e montagem do HTML standalone.
"""
import unittest
from cnpjpw.local_app.graph_builder import (
    build_graph_elements,
    build_graph_html,
    is_probable_accountant,
    COLOR_EMPRESA_ROOT,
    COLOR_SOCIO,
    COLOR_CONTADOR
)

class TestGraphBuilder(unittest.TestCase):
    def setUp(self):
        self.sample_company = {
            "cnpj": "12345678000190",
            "razao_social": "POMELO TECNOLOGIA LTDA",
            "nome_fantasia": "POMELO TECH",
            "cnae_fiscal_principal": "6201501",
            "situacao_cadastral": "ATIVA",
            "socios": [
                {
                    "nome": "CARLOS SILVA",
                    "qualificacao_descricao": "Sócio-Administrador",
                    "cnpj_cpf": "***111222**"
                },
                {
                    "nome": "MARIA CONTABILIDADE ASSESSORIA",
                    "qualificacao_descricao": "Sócio",
                    "cnpj_cpf": "***333444**"
                },
                {
                    "nome": "CNN SPORTS ASSESSORIA ESPORTIVA",
                    "qualificacao_descricao": "Sócio",
                    "cnpj_cpf": "***555666**"
                }
            ],
            "correio_eletronico": "contato@pomelotech.com.br",
            "ddd1": "11",
            "telefone_1": "987654321"
        }

    def test_is_probable_accountant_true_cases(self):
        """Casos legítimos de contabilidade devem ser detectados com precisão."""
        self.assertTrue(is_probable_accountant(label="ESCRITORIO CONTABIL LTDA"))
        self.assertTrue(is_probable_accountant(label="SILVA & SOUZA CONTABILIDADE"))
        self.assertTrue(is_probable_accountant(label="PERICIA CONTABIL E AUDITORIA FISCAL"))
        self.assertTrue(is_probable_accountant(label="ASSESSORIA CONTABIL E TRIBUTARIA"))
        self.assertTrue(is_probable_accountant(label="CONSULTORIA TRIBUTARIA E CONTABIL"))
        self.assertTrue(is_probable_accountant(cnae="6920-6/01"))
        self.assertTrue(is_probable_accountant(cnae="6920602"))

    def test_is_probable_accountant_false_positive_prevention(self):
        """Termos não-contábeis (ex: esportes, advocacia, medicina) NÃO devem ser classificados como contador."""
        # Caso específico reportado pelo usuário: assessoria esportiva
        self.assertFalse(is_probable_accountant(label="CNN SPORTS ASSESSORIA"))
        self.assertFalse(is_probable_accountant(label="CNN SPORTS ASSESSORIA ESPORTIVA LTDA"))
        self.assertFalse(is_probable_accountant(label="FUTEBOL E SPORTS CONSULTORIA"))
        
        # Outros setores comuns
        self.assertFalse(is_probable_accountant(label="PADARIA DO BAIRRO", cnae="4721102"))
        self.assertFalse(is_probable_accountant(label="ABC ASSESSORIA JURIDICA E ADVOCACIA"))
        self.assertFalse(is_probable_accountant(label="CLINICA MEDICA E CONSULTORIA EM SAUDE"))
        self.assertFalse(is_probable_accountant(label="IMOBILIARIA E ASSESSORIA DE IMOVEIS"))
        self.assertFalse(is_probable_accountant(label="ASSESSORIA DE IMPRENSA E COMUNICACAO"))
        self.assertFalse(is_probable_accountant(label="CONSULTORIA EM TECNOLOGIA E SOFTWARE"))

    def test_build_graph_elements_basic(self):
        nodes, edges, available = build_graph_elements(
            root_data=self.sample_company,
            socios_empresas={},
            contatos_empresas={},
            shared_addresses={},
            family_relationships=[],
            ubos=[]
        )
        self.assertTrue(len(nodes) >= 4, f"Esperado >= 4 nós, obtido {len(nodes)}")
        self.assertTrue(len(edges) >= 3, f"Esperado >= 3 arestas, obtido {len(edges)}")
        
        # Valida nó raiz
        root_node = next((n for n in nodes if n["id"] == "cnpj_12345678000190"), None)
        self.assertIsNotNone(root_node)
        self.assertEqual(root_node["color"]["background"], COLOR_EMPRESA_ROOT)
        self.assertEqual(root_node["shape"], "dot")

        # Valida contador real detectado
        contador_node = next((n for n in nodes if "MARIA CONTABILIDAD" in n["label"]), None)
        self.assertIsNotNone(contador_node)
        self.assertEqual(contador_node["color"]["background"], COLOR_CONTADOR)

        # Valida que CNN SPORTS NÃO foi classificado como contador
        cnn_node = next((n for n in nodes if "CNN SPORTS" in n["label"]), None)
        self.assertIsNotNone(cnn_node)
        self.assertFalse(cnn_node["_is_accountant"])
        self.assertNotEqual(cnn_node["color"]["background"], COLOR_CONTADOR)
        self.assertFalse(cnn_node["label"].startswith("🧮"))

    def test_user_override_false_positive(self):
        """Analista marca um nó detectado como falso positivo e ele perde a condição de contador."""
        socio_contabil_id = "socio_maria contabilidade assessoria"
        
        # 1. Sem override: é contador
        nodes1, _, _ = build_graph_elements(self.sample_company)
        n1 = next(n for n in nodes1 if n["id"] == socio_contabil_id)
        self.assertTrue(n1["_is_accountant"])
        self.assertEqual(n1["color"]["background"], COLOR_CONTADOR)
        
        # 2. Com override de falso positivo: deixa de ser contador
        nodes2, _, _ = build_graph_elements(
            self.sample_company,
            false_positive_accountants={socio_contabil_id}
        )
        n2 = next(n for n in nodes2 if n["id"] == socio_contabil_id)
        self.assertFalse(n2["_is_accountant"])
        self.assertEqual(n2["color"]["background"], COLOR_SOCIO)
        self.assertFalse(n2["label"].startswith("🧮"))

    def test_user_override_manual_accountant(self):
        """Analista marca manualmente uma entidade que não é contador automático."""
        socio_carlos_id = "socio_carlos silva"
        
        # 1. Sem override: não é contador
        nodes1, _, _ = build_graph_elements(self.sample_company)
        n1 = next(n for n in nodes1 if n["id"] == socio_carlos_id)
        self.assertFalse(n1["_is_accountant"])
        
        # 2. Com override manual: vira contador
        nodes2, _, _ = build_graph_elements(
            self.sample_company,
            manual_accountants={socio_carlos_id}
        )
        n2 = next(n for n in nodes2 if n["id"] == socio_carlos_id)
        self.assertTrue(n2["_is_accountant"])
        self.assertEqual(n2["color"]["background"], COLOR_CONTADOR)
        self.assertTrue(n2["label"].startswith("🧮"))

    def test_build_graph_elements_with_exclusion(self):
        excluded = {"email_contato@pomelotech.com.br"}
        nodes, edges, _ = build_graph_elements(
            root_data=self.sample_company,
            excluded_nodes=excluded
        )
        email_node = next((n for n in nodes if n["id"] == "email_contato@pomelotech.com.br"), None)
        self.assertIsNone(email_node, "Nó excluído não deve aparecer na lista de nós")

    def test_build_graph_html_generation(self):
        html_code, available = build_graph_html(
            root_data=self.sample_company,
            height="850px"
        )
        self.assertIsInstance(html_code, str)
        self.assertIn("vis-network", html_code)
        self.assertIn("POMELO TECNOLOGIA LTDA", html_code)
        self.assertIn("CARLOS SILVA", html_code)
        self.assertIn("network.fit(", html_code)
        self.assertIn("stabilizationIterationsDone", html_code)
        self.assertIn("physics: { enabled: false }", html_code)
        self.assertTrue(len(available) >= 4)

    def test_empty_data_html(self):
        html_code, available = build_graph_html(root_data={})
        self.assertIn("Nenhum dado cadastral disponível para gerar o grafo", html_code)
        self.assertEqual(len(available), 0)

    def test_expand_node_html_elements(self):
        """Verifica se os botões de ação (+ e X) e o root_cnpj são injetados no HTML standalone."""
        html_code, available = build_graph_html(root_data=self.sample_company)
        self.assertIn('var rootCnpj = "12345678000190";', html_code)
        self.assertIn('node-actions-menu', html_code)
        self.assertIn('btn-node-expand', html_code)
        self.assertIn('btn-node-delete', html_code)
        self.assertIn('data-target-node', html_code)
        self.assertIn('Graph Bridge Receiver', html_code)
        self.assertIn('triggerExpand(nodeId)', html_code)
        self.assertIn('triggerDelete(nodeId)', html_code)
        self.assertIn("searchParams.set('cnpj', rootCnpj)", html_code)
        self.assertIn("searchParams.set('expand_type', nType)", html_code)

    def test_api_client_resilient_fallback(self):
        """Valida que o api_client opera com fallback automático e não falha silenciosamente."""
        from cnpjpw.local_app import api_client
        # Mesmo com ENGINE_MODE = 'BIGQUERY', deve identificar que não há credenciais e não levantar exceção
        api_client.set_engine_mode("BIGQUERY")
        self.assertFalse(api_client.is_bigquery_available())
        self.assertFalse(api_client.is_bigquery_mode())

        # Modo AUTO
        api_client.set_engine_mode("AUTO")
        self.assertFalse(api_client.is_bigquery_mode())

if __name__ == "__main__":
    unittest.main()
