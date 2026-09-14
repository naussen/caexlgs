"""
test_data_service.py — Testes automatizados da camada unificada de dados e fallback (Fase 5).

Valida:
1. Detecção de credenciais do BigQuery (Secrets, ambiente, arquivo local);
2. Estrutura padronizada de retorno: results, source, error, fallback_used;
3. Fallback transparente de BigQuery para API quando o primeiro falha;
4. Bloqueio de chamadas reversas por telefone e e-mail na API pública (Regra 5);
5. Conformidade do cálculo de sigilo ativo (BigQuery/Local vs Pública).
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Assegura que o diretório raiz e local_app estão no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_app")))

from cnpjpw.local_app import data_service, api_client, bigquery_client


class TestDataServiceUnifiedLayer(unittest.TestCase):

    def setUp(self):
        # Limpa variáveis de ambiente e estado antes de cada teste
        self.sample_company = {
            "cnpj": "12345678000190",
            "razao_social": "POMELO TECNOLOGIA LTDA",
            "nome_empresarial": "POMELO TECNOLOGIA LTDA"
        }

    # -------------------------------------------------------------
    # 1. TESTES DE DETECÇÃO DE CREDENCIAIS (REGRA 3)
    # -------------------------------------------------------------
    def test_bigquery_available_via_streamlit_secrets(self):
        """Valida que credenciais em st.secrets habilitam o BigQuery."""
        mock_st = MagicMock()
        mock_st.secrets = {"GCP_SERVICE_ACCOUNT_JSON": '{"type": "service_account"}'}
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            with patch.object(data_service.bigquery_client, "HAS_BIGQUERY", True):
                with patch.object(data_service.bigquery_client, "get_credentials_path", return_value=""):
                    with patch.dict(os.environ, {}, clear=True):
                        self.assertTrue(data_service.is_bigquery_available())

    def test_bigquery_available_via_env_var(self):
        """Valida que credenciais em variável de ambiente habilitam o BigQuery."""
        with patch.object(data_service.bigquery_client, "HAS_BIGQUERY", True):
            with patch.object(data_service.bigquery_client, "get_credentials_path", return_value=""):
                with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/key.json"}):
                    self.assertTrue(data_service.is_bigquery_available())

    def test_bigquery_unavailable_when_no_credentials(self):
        """Valida que sem credenciais em secrets, env ou disco, is_bigquery_available retorna False."""
        mock_st = MagicMock()
        mock_st.secrets = {}
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            with patch.object(data_service.bigquery_client, "HAS_BIGQUERY", True):
                with patch.object(data_service.bigquery_client, "get_credentials_path", return_value=""):
                    with patch.dict(os.environ, {}, clear=True):
                        self.assertFalse(data_service.is_bigquery_available())

    # -------------------------------------------------------------
    # 2. TESTES DE ESTRUTURA PADRONIZADA DE RETORNO (REGRA 4)
    # -------------------------------------------------------------
    def test_query_response_explicit_contract(self):
        """Valida que o retorno segue exatamente o contrato da Fase 5."""
        resp = data_service.QueryResult(
            results=[{"cnpj": "123"}],
            source="BIGQUERY",
            error=None,
            fallback_used=False
        )
        # Deve se comportar como dicionário estrito
        self.assertIn("results", resp)
        self.assertIn("source", resp)
        self.assertIn("error", resp)
        self.assertIn("fallback_used", resp)
        self.assertEqual(resp["source"], "BIGQUERY")
        self.assertFalse(resp["fallback_used"])
        self.assertIsNone(resp["error"])
        # E oferecer acessores de propriedade
        self.assertEqual(resp.source, "BIGQUERY")
        self.assertEqual(resp.fallback_used, False)
        self.assertEqual(len(resp.results), 1)

    # -------------------------------------------------------------
    # 3. TESTES DE FALLBACK TRANSPARENTE
    # -------------------------------------------------------------
    def test_get_cnpj_bigquery_success(self):
        """Valida que quando o BigQuery responde com sucesso, source é BIGQUERY e fallback_used é False."""
        with patch.object(data_service, "should_use_bigquery", return_value=True):
            with patch.object(data_service.bigquery_client, "get_cnpj", return_value=self.sample_company) as mock_bq:
                resp = data_service.get_cnpj("12345678000190")

                mock_bq.assert_called_once_with("12345678000190")
                self.assertEqual(resp.source, data_service.SOURCE_BIGQUERY)
                self.assertFalse(resp.fallback_used)
                self.assertIsNone(resp.error)
                self.assertEqual(resp.results["cnpj"], "12345678000190")

    def test_get_cnpj_bigquery_failure_triggers_api_fallback(self):
        """Valida que falha do BigQuery aciona contingência na API com fallback_used=True."""
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.json.return_value = self.sample_company

        with patch.object(data_service, "should_use_bigquery", return_value=True):
            with patch.object(data_service.bigquery_client, "get_cnpj", side_effect=Exception("BigQuery timeout")) as mock_bq:
                with patch("requests.get", return_value=mock_http_resp) as mock_requests_get:
                    resp = data_service.get_cnpj("12345678000190")

                    mock_bq.assert_called_once_with("12345678000190")
                    mock_requests_get.assert_called_once()
                    self.assertTrue(resp.fallback_used)
                    self.assertIn(resp.source, (data_service.SOURCE_PUBLIC_API, data_service.SOURCE_LOCAL_API))
                    self.assertIsNotNone(resp.error)
                    self.assertIn("BigQuery falhou", resp.error)
                    self.assertEqual(resp.results["cnpj"], "12345678000190")

    # -------------------------------------------------------------
    # 4. REGRA 5 — BLOQUEIO DE BUSCA REVERSA NA API PÚBLICA
    # -------------------------------------------------------------
    def test_reverse_phone_search_blocked_on_public_api(self):
        """Valida que busca reversa por telefone na API pública é bloqueada sem fazer requisição HTTP."""
        with patch.object(data_service, "should_use_bigquery", return_value=False):
            with patch.object(data_service, "get_api_source", return_value="PUBLIC_API"):
                with patch("requests.get") as mock_http_get:
                    resp = data_service.buscar_telefone("11", "999998888")

                    mock_http_get.assert_not_called()
                    self.assertEqual(resp.results, [])
                    self.assertEqual(resp.source, data_service.SOURCE_PUBLIC_API)
                    self.assertIn("não possui suporte a buscas reversas por telefone", resp.error)

    def test_reverse_email_search_blocked_on_public_api(self):
        """Valida que busca reversa por e-mail na API pública é bloqueada sem fazer requisição HTTP."""
        with patch.object(data_service, "should_use_bigquery", return_value=False):
            with patch.object(data_service, "get_api_source", return_value="PUBLIC_API"):
                with patch("requests.get") as mock_http_get:
                    resp = data_service.buscar_email("contato@pomelotech.com.br")

                    mock_http_get.assert_not_called()
                    self.assertEqual(resp.results, [])
                    self.assertEqual(resp.source, data_service.SOURCE_PUBLIC_API)
                    self.assertIn("não possui suporte a buscas reversas por e-mail", resp.error)

    # -------------------------------------------------------------
    # 5. REGRA 7 — CÁLCULO DO SELO DE SIGILO ATIVO
    # -------------------------------------------------------------
    def test_privacy_active_when_using_bigquery(self):
        """Valida que quando BigQuery é utilizado, o sigilo total está ativo."""
        with patch.object(data_service, "should_use_bigquery", return_value=True):
            self.assertTrue(data_service.is_privacy_active())

    def test_privacy_active_when_using_local_api(self):
        """Valida que quando a API é local (banco privado), o sigilo está ativo."""
        with patch.object(data_service, "should_use_bigquery", return_value=False):
            with patch.object(data_service, "get_api_source", return_value="LOCAL_API"):
                self.assertTrue(data_service.is_privacy_active())

    def test_privacy_inactive_when_using_public_api(self):
        """Valida que quando a API pública externa está conectada, o selo de sigilo é desativado."""
        with patch.object(data_service, "should_use_bigquery", return_value=False):
            with patch.object(data_service, "get_api_source", return_value="PUBLIC_API"):
                self.assertFalse(data_service.is_privacy_active())


if __name__ == "__main__":
    unittest.main()
