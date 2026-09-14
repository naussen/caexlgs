"""
Módulo de Autenticação Compartilhada para o POMELO (Fase 1).
Suporta credenciais via Streamlit Secrets, Variáveis de Ambiente ou Defaults.
"""
import os
import hmac

DEFAULT_LOGIN = "caexlgs"
DEFAULT_PASSWORD = "caexlgs"

def get_configured_credentials() -> tuple[str, str]:
    """
    Carrega as credenciais configuradas seguindo a prioridade:
    1. Streamlit Secrets (POMELO_LOGIN, POMELO_PASSWORD)
    2. Variáveis de Ambiente (POMELO_LOGIN, POMELO_PASSWORD)
    3. Defaults temporários (caexlgs / caexlgs)
    """
    login = None
    password = None

    # 1. Streamlit Secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "POMELO_LOGIN" in st.secrets:
                val = st.secrets["POMELO_LOGIN"]
                if val:
                    login = str(val)
            if "POMELO_PASSWORD" in st.secrets:
                val = st.secrets["POMELO_PASSWORD"]
                if val:
                    password = str(val)
    except Exception:
        pass

    # 2. Variáveis de Ambiente (se não definidas em secrets)
    if not login:
        env_login = os.getenv("POMELO_LOGIN")
        if env_login:
            login = env_login

    if not password:
        env_pwd = os.getenv("POMELO_PASSWORD")
        if env_pwd:
            password = env_pwd

    # 3. Defaults temporários
    if not login:
        login = DEFAULT_LOGIN
    if not password:
        password = DEFAULT_PASSWORD

    return login, password

def verify_credentials(username: str | None, password: str | None) -> bool:
    """
    Função pura que valida as credenciais informadas usando hmac.compare_digest
    para mitigar timing attacks. Retorna True em caso de correspondência exata.
    Nunca registra senha em logs ou mensagens de erro.
    """
    if not username or not password:
        return False

    expected_login, expected_password = get_configured_credentials()

    login_ok = hmac.compare_digest(str(username).encode("utf-8"), expected_login.encode("utf-8"))
    pwd_ok = hmac.compare_digest(str(password).encode("utf-8"), expected_password.encode("utf-8"))

    return login_ok and pwd_ok

def render_login_screen():
    """
    Renderiza o formulário de login no Streamlit.
    Garante que nenhuma tela ou dado seja acessível antes da autenticação.
    """
    import streamlit as st

    logo_path = os.path.join(os.path.dirname(__file__), "assets", "pomelo_logo.png")

    col_l, col_m, col_r = st.columns([1, 1.3, 1])
    with col_m:
        st.write("")
        st.write("")
        if os.path.exists(logo_path):
            st.image(logo_path, width=110)
        st.title("POMELO")
        st.subheader("Acesso Restrito")
        st.caption("Autenticação necessária para acessar a plataforma de inteligência societária.")

        with st.form("form_login", clear_on_submit=False):
            input_user = st.text_input("Usuário", key="login_user_input", autocomplete="username")
            input_pass = st.text_input("Senha", type="password", key="login_pass_input", autocomplete="current-password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)

            if submitted:
                if verify_credentials(input_user, input_pass):
                    st.session_state.authenticated = True
                    st.session_state.pop("auth_error", None)
                    st.rerun()
                else:
                    st.error("Login ou senha inválidos.")
