import unittest
from cnpjpw.local_app.graph_builder import (
    build_graph_elements,
    get_relationship_type,
    NON_DIRECTIONAL_RELATIONSHIPS,
    COLOR_EMPRESA_ROOT,
    COLOR_SOCIO
)

class TestGraphDeduplication(unittest.TestCase):
    def setUp(self):
        self.root_company = {
            'cnpj': '12345678000190',
            'cnpj_basico': '12345678',
            'cnpj_ordem': '0001',
            'cnpj_dv': '90',
            'razao_social': 'EMPRESA RAIZ INVESTIGADA LTDA',
            'situacao_cadastral_descricao': 'ATIVA',
            'socios': [
                {
                    'nome': 'ALBERTO ROBERTO',
                    'qualificacao_descricao': 'Socio-Administrador',
                    'cnpj_cpf': '***111222**'
                },
                {
                    'nome': 'BEATRIZ MENDES',
                    'qualificacao_descricao': 'Socio',
                    'cnpj_cpf': '***333444**'
                }
            ],
            'correio_eletronico': 'diretoria@raizinvestigada.com.br',
            'ddd1': '11',
            'telefone_1': '30304040'
        }

        self.partner_company = {
            'cnpj': '98765432000188',
            'razao_social': 'HOLDING PARTICIPACOES LTDA',
            'situacao_cadastral_descricao': 'ATIVA',
            'socios': [
                {
                    'nome': 'ALBERTO ROBERTO',
                    'qualificacao_descricao': 'Socio',
                    'cnpj_cpf': '***111222**'
                }
            ],
            'correio_eletronico': 'contato@holding.com.br',
            'ddd1': '11',
            'telefone_1': '30304040'
        }

    def test_get_relationship_type_classification(self):
        self.assertEqual(get_relationship_type(label='Parentesco'), 'PARENTESCO')
        self.assertEqual(get_relationship_type(label='mesmo endereco'), 'ENDERECO')
        self.assertEqual(get_relationship_type(label='e-mail'), 'EMAIL')
        self.assertEqual(get_relationship_type(label='mesmo e-mail'), 'MESMO_EMAIL')
        self.assertEqual(get_relationship_type(label='telefone'), 'TELEFONE')
        self.assertEqual(get_relationship_type(label='mesmo fone'), 'MESMO_TELEFONE')
        self.assertEqual(get_relationship_type(label='Participacao'), 'PARTICIPACAO')
        self.assertEqual(get_relationship_type(label='Socio-Administrador'), 'SOCIETARIO')
        self.assertEqual(get_relationship_type(label='Autor'), 'JUDICIAL')
        self.assertEqual(get_relationship_type(manual=True), 'MANUAL')
        self.assertEqual(get_relationship_type(custom_type='CUSTOM_VINCULO'), 'CUSTOM_VINCULO')

    def test_expansion_idempotence(self):
        socios_exp = {'ALBERTO ROBERTO': [self.partner_company]}
        contatos_exp = {'1130304040': [self.partner_company]}
        extra_comps = {'98765432000188': self.partner_company}

        nodes_run1, edges_run1, avail_run1 = build_graph_elements(
            root_data=self.root_company,
            socios_empresas=socios_exp,
            contatos_empresas=contatos_exp,
            extra_companies=extra_comps
        )

        nodes_run2, edges_run2, avail_run2 = build_graph_elements(
            root_data=self.root_company,
            socios_empresas=socios_exp,
            contatos_empresas=contatos_exp,
            extra_companies=extra_comps
        )

        self.assertEqual(len(nodes_run1), len(nodes_run2))
        self.assertEqual(len(edges_run1), len(edges_run2))
        self.assertEqual(len(avail_run1), len(avail_run2))
        self.assertEqual({n['id'] for n in nodes_run1}, {n['id'] for n in nodes_run2})

    def test_root_not_duplicated_under_any_circumstance(self):
        socios_with_root = {'ALBERTO ROBERTO': [self.root_company, self.partner_company]}
        contatos_with_root = {'1130304040': [self.root_company]}
        extra_with_root = {'12345678000190': self.root_company, '98765432000188': self.partner_company}

        nodes, edges, _ = build_graph_elements(
            root_data=self.root_company,
            socios_empresas=socios_with_root,
            contatos_empresas=contatos_with_root,
            extra_companies=extra_with_root
        )

        root_nodes = [n for n in nodes if n['id'] == 'cnpj_12345678000190']
        self.assertEqual(len(root_nodes), 1)
        self.assertEqual(root_nodes[0]['_type'], 'EMPRESA_ROOT')
        self.assertFalse(any(e['from'] == 'cnpj_12345678000190' and e['to'] == 'cnpj_12345678000190' for e in edges))

    def test_identical_edges_appear_only_once(self):
        m_nodes = [
            {'id': 'manual_1', 'label': 'Investigado A', 'type': 'MANUAL_PF'},
            {'id': 'manual_2', 'label': 'Investigado B', 'type': 'MANUAL_PF'}
        ]
        m_edges = [
            {'from': 'manual_1', 'to': 'manual_2', 'label': 'Vinculo Direto'},
            {'from': 'manual_1', 'to': 'manual_2', 'label': 'Vinculo Direto'}
        ]

        nodes, edges, _ = build_graph_elements(
            root_data=self.root_company,
            manual_nodes=m_nodes,
            manual_edges=m_edges
        )

        manual_matches = [
            e for e in edges
            if e['from'] == 'manual_1' and e['to'] == 'manual_2' and e['label'] == 'Vinculo Direto'
        ]
        self.assertEqual(len(manual_matches), 1)

    def test_different_relationship_types_preserved(self):
        fam_rels = [{'socio_a': 'alberto roberto', 'socio_b': 'beatriz mendes'}]
        m_edges = [{'from': 'socio_alberto roberto', 'to': 'socio_beatriz mendes', 'label': 'Procurador de Fato'}]

        nodes, edges, _ = build_graph_elements(
            root_data=self.root_company,
            family_relationships=fam_rels,
            manual_edges=m_edges
        )

        alberto_beatriz_edges = [
            e for e in edges
            if (e['from'] in ('socio_alberto roberto', 'socio_beatriz mendes') and
                e['to'] in ('socio_alberto roberto', 'socio_beatriz mendes'))
        ]
        self.assertEqual(len(alberto_beatriz_edges), 2)
        types = {e.get('_type') for e in alberto_beatriz_edges}
        self.assertIn('PARENTESCO', types)
        self.assertIn('MANUAL', types)

    def test_non_directional_edges_deduplicated_regardless_of_order(self):
        fam_rels = [
            {'socio_a': 'alberto roberto', 'socio_b': 'beatriz mendes'},
            {'socio_a': 'beatriz mendes', 'socio_b': 'alberto roberto'}
        ]

        nodes, edges, _ = build_graph_elements(
            root_data=self.root_company,
            family_relationships=fam_rels
        )

        parentesco_edges = [e for e in edges if e.get('_type') == 'PARENTESCO']
        self.assertEqual(len(parentesco_edges), 1)

    def test_edges_never_added_if_node_missing_or_excluded(self):
        m_edges = [
            {'from': 'cnpj_12345678000190', 'to': 'no_inexistente_999', 'label': 'Vinculo Fantasma'},
            {'from': 'no_fantasma_1', 'to': 'no_fantasma_2', 'label': 'Inexistente'}
        ]
        excluded = {'socio_beatriz mendes'}

        nodes, edges, _ = build_graph_elements(
            root_data=self.root_company,
            manual_edges=m_edges,
            excluded_nodes=excluded
        )

        self.assertFalse(any(e['from'] == 'no_inexistente_999' or e['to'] == 'no_inexistente_999' for e in edges))
        self.assertFalse(any(e['from'] == 'socio_beatriz mendes' or e['to'] == 'socio_beatriz mendes' for e in edges))

    def test_root_expansion_does_not_replicate_edges(self):
        base_nodes, base_edges, _ = build_graph_elements(root_data=self.root_company)
        base_alberto_edges = [
            e for e in base_edges
            if e['from'] == 'cnpj_12345678000190' and e['to'] == 'socio_alberto roberto'
        ]
        self.assertEqual(len(base_alberto_edges), 1)

        exp_nodes, exp_edges, _ = build_graph_elements(
            root_data=self.root_company,
            extra_companies={'12345678000190': self.root_company}
        )
        exp_alberto_edges = [
            e for e in exp_edges
            if e['from'] == 'cnpj_12345678000190' and e['to'] == 'socio_alberto roberto'
        ]
        self.assertEqual(len(exp_alberto_edges), 1)
        self.assertEqual(len(base_nodes), len(exp_nodes))
        self.assertEqual(len(base_edges), len(exp_edges))

if __name__ == '__main__':
    unittest.main()
