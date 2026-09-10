@echo off
chcp 65001 > nul
title Consulta CNPJ e Grafos - CAEXLGS
echo ================================================================
echo           CAEXLGS - Consulta CNPJ, Grafos & Inteligencia
echo ================================================================
echo.
echo Verificando instalacao do Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao foi encontrado no seu computador!
    echo Por favor, instale o Python em https://www.python.org/
    echo Lembre-se de marcar a opcao "Add python.exe to PATH" na instalacao.
    echo.
    pause
    exit /b 1
)

echo Iniciando o aplicativo Streamlit...
echo Abrindo seu navegador padrao...
echo.
streamlit run cnpjpw/local_app/app.py

pause
