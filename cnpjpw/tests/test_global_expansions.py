"""
test_global_expansions.py — Testes automatizados das Expansões Globais do Grafo (Fase 6).

Valida:
1. Expansão de sócios até 2º grau (Grau 0: raiz, Grau 1: sócios diretos, Grau 2: empresas dos sócios);
2. Não expansão de sócios de grau 2 (sem avanço para grau 3);
3. Deduplicação por CNPJ de 14 dígitos e descarte mandatória da empresa raiz;
4. Limite configurável (25 empresas por sócio);
5. Relatório/sumário auditável de execução da expansão de sócios;
6. Expansão de contatos em toda a rede de empresas visíveis;
7. Filtragem estrita de contatos inválidos (DDD obrigatório, sintaxe de e-mail);
8. Limite por contato (25 empresas) e descarte de empresas já conhecidas na rede;
9. Tratamento resiliente e registro de avisos quando a API pública restringe buscas reversas.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_app")))

from cnpjpw.local_app import graph_expansions, data_service


class TestGlobalExpansions(unittest.TestCase):

    def setUp(self):
        self.root_company = {
            "cnpj": "11111111000111",
            "razao_social": "EMPRESA RAIZ LTDA",
            "ddd1": "11",
            "telefone_1": "999991111",
            "correio_eletronico": "contato@raiz.com.br",
            "socios": [
                {"nome": "CARLOS SILVA", "cnpj_cpf": "12345678901"},
                {"nome": "MARIA SOUZA", "cnpj_cpf": "98765432100"}
            ]
        }

    # -------------------------------------------------------------
    # 1. FUNÇÕES AUXILIARES DE VALIDAÇÃO
    # -------------------------------------------------------------
    def test_clean_cnpj(self):
        self.assertEqual(graph_expansions.clean_cnpj("11.111.111/0001-11"), "11111111000111")
        self.assertEqual(graph_expansions.clean_cnpj(11111111000111), "11111111000111")
        self.assertEqual(graph_expansions.clean_cnpj("123"), "")
        self.assertEqual(graph_expansions.clean_cnpj(None), "")

    def test_is_valid_phone(self):
        # Válidos com DDD
        self.assertTrue(graph_expansions.is_valid_phone("11999998888"))
        self.assertTrue(graph_expansions.is_valid_phone("2133334444"))
        # Inválidos: sem DDD, tamanho errado, repetições triviais
        self.assertFalse(graph_expansions.is_valid_phone("999998888"))  # sem DDD (9 dígitos)
        self.assertFalse(graph_expansions.is_valid_phone("33334444"))   # sem DDD (8 dígitos)
        self.assertFalse(graph_expansions.is_valid_phone("0000000000")) # repetição
        self.assertFalse(graph_expansions.is_valid_phone("1111111111")) # repetição
        self.assertFalse(graph_expansions.is_valid_phone("01999998888"))# DDD iniciando com 0

    def test_is_valid_email(self):
        self.assertTrue(graph_expansions.is_valid_email("contato@empresa.com.br"))
        self.assertTrue(graph_expansions.is_valid_email("financeiro@grupo.com"))
        # Inválidos
        self.assertFalse(graph_expansions.is_valid_email("contatoempresa.com.br")) # sem @
        self.assertFalse(graph_expansions.is_valid_email("@empresa.com"))          # sem user
        self.assertFalse(graph_expansions.is_valid_email("contato@com"))           # sem ponto no domínio
        self.assertFalse(graph_expansions.is_valid_email(""))
        self.assertFalse(graph_expansions.is_valid_email(None))

    def test_extract_company_contacts(self):
        comp = {
            "ddd1": "11", "telefone_1": "988887777",
            "ddd2": "21", "telefone_2": "977776666",
            "correio_eletronico": "diretoria@holding.com.br, sac@holding.com.br"
        }
        phones, emails = graph_expansions.extract_company_contacts(comp)
        self.assertIn("11988887777", phones)
        self.assertIn("21977776666", phones)
        self.assertIn("diretoria@holding.com.br", emails)
        self.assertIn("sac@holding.com.br", emails)

    # -------------------------------------------------------------
    # 2. EXPANSÃO DE SÓCIOS ATÉ SEGUNDO GRAU (GRAU 2)
    # -------------------------------------------------------------
    def test_expand_socios_grau2_semantics_and_no_grau3(self):
        """
        Valida que a expansão alcança as empresas dos sócios da raiz (grau 2),
        mas não expande os sócios das empresas de grau 2 (sem avanço para grau 3).
        """
        carlos_companies = [
            {"cnpj": "22222222000122", "razao_social": "CARLOS HOLDING LTDA", "socios": [{"nome": "OUTRO SOCIO"}]},
            {"cnpj": "33333333000133", "razao_social": "CARLOS LOGISTICA LTDA"}
        ]
        maria_companies = [
            {"cnpj": "44444444000144", "razao_social": "MARIA PARTICIPACOES LTDA"}
        ]

        def fake_buscar_socio(nome, doc=None):
            if "CARLOS" in nome:
                return data_service.QueryResult(results=carlos_companies, source="TEST")
            elif "MARIA" in nome:
                return data_service.QueryResult(results=maria_companies, source="TEST")
            return data_service.QueryResult(results=[], source="TEST")

        with patch.object(graph_expansions.data_service, "buscar_empresas_do_socio", side_effect=fake_buscar_socio) as mock_busca:
            cache, summary = graph_expansions.expand_socios_grau2(self.root_company)

            # Apenas os 2 sócios diretos da raiz foram consultados (Grau 1 -> Grau 2)
            self.assertEqual(mock_busca.call_count, 2)
            consulted_names = [call[0][0] for call in mock_busca.call_args_list]
            self.assertIn("CARLOS SILVA", consulted_names)
            self.assertIn("MARIA SOUZA", consulted_names)
            self.assertNotIn("OUTRO SOCIO", consulted_names) # Não expandiu grau 3

            # Cache preenchido com as empresas de cada sócio
            self.assertEqual(len(cache["CARLOS SILVA"]), 2)
            self.assertEqual(len(cache["MARIA SOUZA"]), 1)

            # Sumário auditável
            self.assertEqual(summary["socios_consultados"], 2)
            self.assertEqual(summary["total_socios_raiz"], 2)
            self.assertEqual(summary["empresas_encontradas"], 3)
            self.assertEqual(summary["empresas_adicionadas"], 3)
            self.assertEqual(summary["duplicatas_removidas"], 0)
            self.assertEqual(summary["falhas"], 0)

    def test_expand_socios_deduplication_and_root_protection(self):
        """
        Valida que:
        1. A empresa raiz (Grau 0) é descartada se retornada na busca do sócio;
        2. Empresas repetidas compartilhadas entre sócios são deduplicadas por CNPJ.
        """
        shared_company = {"cnpj": "55555555000155", "razao_social": "EMPRESA CONJUNTA LTDA"}
        root_company_ref = {"cnpj": "11111111000111", "razao_social": "EMPRESA RAIZ LTDA"}

        carlos_comps = [root_company_ref, shared_company]
        maria_comps = [shared_company]

        def fake_buscar(nome, doc=None):
            if "CARLOS" in nome:
                return data_service.QueryResult(results=carlos_comps, source="TEST")
            return data_service.QueryResult(results=maria_comps, source="TEST")

        with patch.object(graph_expansions.data_service, "buscar_empresas_do_socio", side_effect=fake_buscar):
            cache, summary = graph_expansions.expand_socios_grau2(self.root_company)

            # Carlos: descartou a raiz (11111111000111), manteve apenas a compartilhada
            self.assertEqual(len(cache["CARLOS SILVA"]), 1)
            self.assertEqual(cache["CARLOS SILVA"][0]["cnpj"], "55555555000155")

            # Maria: a compartilhada já foi vista em Carlos, então é deduplicada
            self.assertEqual(len(cache["MARIA SOUZA"]), 0)

            # 3 encontradas, 1 adicionada, 2 duplicatas descartadas (1 raiz + 1 repetida)
            self.assertEqual(summary["empresas_encontradas"], 3)
            self.assertEqual(summary["empresas_adicionadas"], 1)
            self.assertEqual(summary["duplicatas_removidas"], 2)

    def test_expand_socios_limit_per_partner(self):
        """Valida que uma lista com mais empresas que o limite é truncada (ex: teto de 25)."""
        many_companies = [
            {"cnpj": f"222222{i:02d}000199", "razao_social": f"EMPRESA {i}"}
            for i in range(35) # 35 empresas
        ]
        with patch.object(graph_expansions.data_service, "buscar_empresas_do_socio", return_value=data_service.QueryResult(results=many_companies, source="TEST")):
            cache, summary = graph_expansions.expand_socios_grau2(
                {"cnpj": "99999999000199", "socios": [{"nome": "JOAO GRANDE"}]},
                max_per_partner=25
            )
            # Limitado em exatamente 25
            self.assertEqual(len(cache["JOAO GRANDE"]), 25)
            self.assertEqual(summary["empresas_encontradas"], 35)
            self.assertEqual(summary["empresas_adicionadas"], 25)
            self.assertEqual(summary["duplicatas_removidas"], 10)

    # -------------------------------------------------------------
    # 3. EXPANSÃO DE CONTATOS DA REDE (EMPRESAS VISÍVEIS)
    # -------------------------------------------------------------
    def test_expand_contacts_network_scope_and_deduplication(self):
        """
        Valida que a expansão de contatos analisa todas as empresas visíveis,
        coleta contatos únicos, deduplica e descarta empresas já conhecidas na rede.
        """
        company_a = {
            "cnpj": "11111111000111",
            "ddd1": "11", "telefone_1": "988881111",
            "correio_eletronico": "financeiro@grupo.com.br"
        }
        company_b = {
            "cnpj": "22222222000122",
            "ddd1": "11", "telefone_1": "988881111", # Mesmo telefone da A
            "correio_eletronico": "operacoes@grupo.com.br"
        }

        # Busca do telefone retorna a própria Company B (já conhecida) e uma Nova Company C
        phone_results = [
            {"cnpj": "22222222000122", "razao_social": "EMPRESA B"},
            {"cnpj": "33333333000133", "razao_social": "NOVA EMPRESA C"}
        ]
        # Busca do email financeiro retorna uma Nova Company D
        email_results = [
            {"cnpj": "44444444000144", "razao_social": "NOVA EMPRESA D"}
        ]

        def fake_tel(ddd, num, months=3):
            return data_service.QueryResult(results=phone_results, source="TEST")

        def fake_email(em, months=3):
            if "financeiro" in em:
                return data_service.QueryResult(results=email_results, source="TEST")
            return data_service.QueryResult(results=[], source="TEST")

        with patch.object(graph_expansions.data_service, "buscar_telefone", side_effect=fake_tel) as mock_tel:
            with patch.object(graph_expansions.data_service, "buscar_email", side_effect=fake_email) as mock_em:
                visible = [company_a, company_b]
                cache, summary = graph_expansions.expand_contacts_network(visible, max_per_contact=25)

                # 1 telefone único compartilhado ("11988881111"), 2 e-mails únicos
                self.assertEqual(summary["empresas_analisadas"], 2)
                self.assertEqual(summary["telefones"], 1)
                self.assertEqual(summary["emails"], 2)
                self.assertEqual(summary["contatos_unicos"], 3)
                self.assertEqual(mock_tel.call_count, 1) # Deduplicou antes de chamar
                self.assertEqual(mock_em.call_count, 2)

                # Empresa B foi descartada da busca de telefone pois já era visível
                tel_cache = cache["11988881111"]
                self.assertEqual(len(tel_cache), 1)
                self.assertEqual(tel_cache[0]["cnpj"], "33333333000133")

                # Sumário
                self.assertEqual(summary["empresas_adicionadas"], 2) # C e D
                self.assertEqual(summary["duplicatas_removidas"], 1) # B descartada

    def test_expand_contacts_filters_invalid_and_no_calls(self):
        """Valida que contatos sem DDD ou com e-mail inválido são ignorados sem disparo de busca."""
        bad_company = {
            "cnpj": "99999999000199",
            "ddd1": "", "telefone_1": "988887777", # Telefone sem DDD
            "correio_eletronico": "email_invalido_sem_arroba"
        }
        with patch.object(graph_expansions.data_service, "buscar_telefone") as mock_tel:
            with patch.object(graph_expansions.data_service, "buscar_email") as mock_em:
                cache, summary = graph_expansions.expand_contacts_network([bad_company])

                mock_tel.assert_not_called()
                mock_em.assert_not_called()
                self.assertEqual(summary["contatos_unicos"], 0)
                self.assertEqual(summary["telefones"], 0)
                self.assertEqual(summary["emails"], 0)
                self.assertEqual(summary["empresas_adicionadas"], 0)

    def test_expand_contacts_public_api_graceful_handling(self):
        """Valida que aviso de não-suporte na API pública é registrado no sumário sem estourar erro."""
        valid_comp = {
            "cnpj": "11111111000111",
            "ddd1": "11", "telefone_1": "999998888"
        }
        error_resp = data_service.QueryResult(
            results=[],
            source="PUBLIC_API",
            error="API Pública não possui suporte a buscas reversas por telefone."
        )
        with patch.object(graph_expansions.data_service, "buscar_telefone", return_value=error_resp):
            cache, summary = graph_expansions.expand_contacts_network([valid_comp])

            self.assertEqual(len(summary["avisos_erros"]), 1)
            self.assertIn("não possui suporte", summary["avisos_erros"][0])
            self.assertEqual(cache["11999998888"], [])
            self.assertEqual(summary["empresas_adicionadas"], 0)


if __name__ == "__main__":
    unittest.main()
