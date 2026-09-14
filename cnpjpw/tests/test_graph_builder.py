"""
Testes unitários para o módulo graph_builder.
Valida geração correta de elementos do grafo, filtragem de contadores e montagem do HTML standalone.
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
                }
            ],
            "correio_eletronico": "contato@pomelotech.com.br",
            "ddd1": "11",
            "telefone_1": "987654321"
        }

    def test_is_probable_accountant(self):
        self.assertTrue(is_probable_accountant(label="ESCRITORIO CONTABIL LTDA"))
        self.assertTrue(is_probable_accountant(title="Assessoria e Auditoria"))
        self.assertTrue(is_probable_accountant(cnae="6920-6/01"))
        self.assertTrue(is_probable_accountant(cnae="6920602"))
        self.assertFalse(is_probable_accountant(label="PADARIA DO BAIRRO", cnae="4721102"))

    def test_build_graph_elements_basic(self):
        nodes, edges, available = build_graph_elements(
            root_data=self.sample_company,
            socios_empresas={},
            contatos_empresas={},
            shared_addresses={},
            family_relationships=[],
            ubos=[]
        )
        # Deve ter nó da empresa raiz, 2 sócios, e nós de contato (email, telefone)
        self.assertTrue(len(nodes) >= 3, f"Esperado >= 3 nós, obtido {len(nodes)}")
        self.assertTrue(len(edges) >= 2, f"Esperado >= 2 arestas, obtido {len(edges)}")
        
        # Valida nó raiz
        root_node = next((n for n in nodes if n["id"] == "cnpj_12345678000190"), None)
        self.assertIsNotNone(root_node)
        self.assertEqual(root_node["color"]["background"], COLOR_EMPRESA_ROOT)
        self.assertEqual(root_node["shape"], "dot")

        # Valida contador detectado
        contador_node = next((n for n in nodes if "MARIA CONTABILIDAD" in n["label"]), None)
        self.assertIsNotNone(contador_node)
        self.assertEqual(contador_node["color"]["background"], COLOR_CONTADOR)

    def test_build_graph_elements_with_exclusion(self):
        # Excluir o nó de e-mail
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
        # Verifica desligamento da física para performance leve
        self.assertIn("physics: { enabled: false }", html_code)
        self.assertTrue(len(available) >= 3)

    def test_empty_data_html(self):
        html_code, available = build_graph_html(root_data={})
        self.assertIn("Nenhum dado cadastral disponível para gerar o grafo", html_code)
        self.assertEqual(len(available), 0)

if __name__ == "__main__":
    unittest.main()
