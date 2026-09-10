"""
CAEXLGS - Ponto de Entrada Principal para Execução Local e Deploy na Nuvem (Streamlit Cloud, Render, etc.)
"""
import os
import sys

# Adiciona o diretório local_app ao sys.path para importação de todos os módulos
base_dir = os.path.dirname(os.path.abspath(__file__))
local_app_dir = os.path.join(base_dir, "cnpjpw", "local_app")
if local_app_dir not in sys.path:
    sys.path.insert(0, local_app_dir)

# Executa o aplicativo principal do Streamlit
target_app = os.path.join(local_app_dir, "app.py")
with open(target_app, "r", encoding="utf-8") as f:
    code = compile(f.read(), target_app, "exec")
    exec(code, globals())
