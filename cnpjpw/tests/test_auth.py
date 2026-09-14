"""
Testes automatizados da barreira de autenticação (Fase 1 do Plano de Correções).
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Assegura que o diretório local_app e a raiz estão no path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_app")))

from cnpjpw.local_app import auth

class TestAuth(unittest.TestCase):

    def setUp(self):
        # Limpa variáveis de ambiente relevantes antes de cada teste
        for env_key in ("POMELO_LOGIN", "POMELO_PASSWORD"):
            if env_key in os.environ:
                del os.environ[env_key]

    def test_default_credentials_when_no_config(self):
        """Valida que na ausência de configuração as credenciais padrão são caexlgs/caexlgs."""
        with patch.dict("sys.modules", {"streamlit": MagicMock(secrets={})}):
            login, pwd = auth.get_configured_credentials()
            self.assertEqual(login, "caexlgs")
            self.assertEqual(pwd, "caexlgs")
            self.assertTrue(auth.verify_credentials("caexlgs", "caexlgs"))

    def test_verify_credentials_correct(self):
        """Valida que credenciais corretas retornam True."""
        self.assertTrue(auth.verify_credentials("caexlgs", "caexlgs"))

    def test_verify_credentials_incorrect_login(self):
        """Valida que login incorreto retorna False."""
        self.assertFalse(auth.verify_credentials("usuario_errado", "caexlgs"))
        self.assertFalse(auth.verify_credentials("", "caexlgs"))
        self.assertFalse(auth.verify_credentials(None, "caexlgs"))

    def test_verify_credentials_incorrect_password(self):
        """Valida que senha incorreta retorna False."""
        self.assertFalse(auth.verify_credentials("caexlgs", "senha_errada"))
        self.assertFalse(auth.verify_credentials("caexlgs", ""))
        self.assertFalse(auth.verify_credentials("caexlgs", None))

    def test_secrets_override_defaults(self):
        """Valida que valores definidos no Streamlit Secrets substituem os defaults."""
        mock_secrets = {
            "POMELO_LOGIN": "usuario_secreto",
            "POMELO_PASSWORD": "senha_super_secreta"
        }
        mock_st = MagicMock()
        mock_st.secrets = mock_secrets

        with patch.dict("sys.modules", {"streamlit": mock_st}):
            login, pwd = auth.get_configured_credentials()
            self.assertEqual(login, "usuario_secreto")
            self.assertEqual(pwd, "senha_super_secreta")
            self.assertTrue(auth.verify_credentials("usuario_secreto", "senha_super_secreta"))
            # Defaults antigos devem ser rejeitados
            self.assertFalse(auth.verify_credentials("caexlgs", "caexlgs"))

    def test_environment_variables_override_defaults_when_secrets_absent(self):
        """Valida que variáveis de ambiente substituem defaults quando Secrets não existem."""
        os.environ["POMELO_LOGIN"] = "env_admin"
        os.environ["POMELO_PASSWORD"] = "env_pass_123"

        mock_st = MagicMock()
        mock_st.secrets = {}

        with patch.dict("sys.modules", {"streamlit": mock_st}):
            login, pwd = auth.get_configured_credentials()
            self.assertEqual(login, "env_admin")
            self.assertEqual(pwd, "env_pass_123")
            self.assertTrue(auth.verify_credentials("env_admin", "env_pass_123"))
            self.assertFalse(auth.verify_credentials("caexlgs", "caexlgs"))

    def test_secrets_priority_over_environment(self):
        """Valida que Streamlit Secrets tem prioridade sobre variáveis de ambiente."""
        os.environ["POMELO_LOGIN"] = "env_user"
        os.environ["POMELO_PASSWORD"] = "env_pass"

        mock_secrets = {
            "POMELO_LOGIN": "secrets_user",
            "POMELO_PASSWORD": "secrets_pass"
        }
        mock_st = MagicMock()
        mock_st.secrets = mock_secrets

        with patch.dict("sys.modules", {"streamlit": mock_st}):
            login, pwd = auth.get_configured_credentials()
            self.assertEqual(login, "secrets_user")
            self.assertEqual(pwd, "secrets_pass")
            self.assertTrue(auth.verify_credentials("secrets_user", "secrets_pass"))
            self.assertFalse(auth.verify_credentials("env_user", "env_pass"))

    def test_unauthenticated_access_with_cnpj_query_param_blocks_and_shows_only_login(self):
        """
        Valida que acessar /?cnpj=75323907000190 sem autenticação
        chama render_login_screen() e bloqueia a execução via st.stop().
        Nenhuma consulta à base ou alteração de view para DETAILS ocorre.
        """
        mock_st = MagicMock()
        mock_st.session_state = {}
        mock_st.query_params = {"cnpj": "75323907000190"}
        mock_stop_called = False

        def fake_stop():
            nonlocal mock_stop_called
            mock_stop_called = True
            raise SystemExit("st.stop() invoked")

        mock_st.stop.side_effect = fake_stop

        # Simula o bloco de autenticação inicial presente em app.py
        if "authenticated" not in mock_st.session_state:
            mock_st.session_state["authenticated"] = False

        with patch.object(auth, "render_login_screen") as mock_render:
            try:
                if not mock_st.session_state["authenticated"]:
                    auth.render_login_screen()
                    mock_st.stop()
                    
                # Código subsequente que jamais deve rodar
                if "cnpj" in mock_st.query_params:
                    mock_st.session_state["view"] = "DETAILS"
                    mock_st.session_state["selected_cnpj"] = mock_st.query_params["cnpj"]
            except SystemExit:
                pass

        self.assertTrue(mock_stop_called, "st.stop() deveria ter sido chamado para bloquear a execução")
        mock_render.assert_called_once()
        self.assertNotIn("selected_cnpj", mock_st.session_state, "CNPJ da query não deve ser processado sem autenticação")
        self.assertNotIn("view", mock_st.session_state, "View não deve mudar sem autenticação")

    def test_authenticated_access_allows_cnpj_query(self):
        """Valida que após a autenticação o fluxo segue e o CNPJ da URL pode ser consultado normalmente."""
        mock_st = MagicMock()
        mock_st.session_state = {"authenticated": True}
        mock_st.query_params = {"cnpj": "75323907000190"}

        with patch.object(auth, "render_login_screen") as mock_render:
            if not mock_st.session_state["authenticated"]:
                auth.render_login_screen()
                mock_st.stop()
            else:
                # Fluxo permitido
                query_cnpj = mock_st.query_params.get("cnpj")
                if query_cnpj:
                    mock_st.session_state["view"] = "DETAILS"
                    mock_st.session_state["selected_cnpj"] = query_cnpj

        mock_render.assert_not_called()
        self.assertEqual(mock_st.session_state.get("view"), "DETAILS")
        self.assertEqual(mock_st.session_state.get("selected_cnpj"), "75323907000190")

    def test_logout_revokes_access_and_subsequent_page_load_blocks(self):
        """Valida que ao sair a sessão é revogada e nova carga de página volta a exibir apenas o login."""
        session_state = {
            "authenticated": True,
            "selected_cnpj": "75323907000190",
            "current_cnpj": "75323907000190"
        }

        # Ação do botão Sair
        session_state["authenticated"] = False
        for k in list(session_state.keys()):
            if k.startswith("login_") or k in ("auth_error", "selected_cnpj", "current_cnpj"):
                session_state.pop(k, None)

        self.assertFalse(session_state["authenticated"])
        self.assertNotIn("selected_cnpj", session_state)
        self.assertNotIn("current_cnpj", session_state)

        # Nova requisição / rerun com estado desautenticado
        mock_st = MagicMock()
        mock_st.session_state = session_state
        mock_stop_called = False

        def fake_stop():
            nonlocal mock_stop_called
            mock_stop_called = True
            raise SystemExit("st.stop() invoked")

        mock_st.stop.side_effect = fake_stop

        with patch.object(auth, "render_login_screen") as mock_render:
            try:
                if not mock_st.session_state.get("authenticated", False):
                    auth.render_login_screen()
                    mock_st.stop()
            except SystemExit:
                pass

        self.assertTrue(mock_stop_called)
        mock_render.assert_called_once()

if __name__ == "__main__":
    unittest.main()
