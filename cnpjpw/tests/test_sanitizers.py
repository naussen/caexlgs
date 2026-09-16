import os
import sys
import pytest

# Assegura que o diretório raiz e local_app estão no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_app")))

try:
    from cnpjpw.local_app.sanitizers import adequar_documento, adequar_telefone, is_celular_prefixo
except ImportError:
    from sanitizers import adequar_documento, adequar_telefone, is_celular_prefixo


class TestAdequarDocumento:
    def test_cnpj_com_pontuacao(self):
        # Exemplo especificado pelo usuário: 21.807.980/0001-09 -> 21807980000109
        entrada = "21.807.980/0001-09"
        assert adequar_documento(entrada) == "21807980000109"

    def test_cpf_com_pontuacao(self):
        # Exemplo especificado pelo usuário: CPF
        entrada = "123.456.789-01"
        assert adequar_documento(entrada) == "12345678901"

    def test_documento_com_espacos_e_caracteres_estranhos(self):
        assert adequar_documento("  21.807.980 / 0001-09  ") == "21807980000109"
        assert adequar_documento("CPF: 123.456.789-01") == "12345678901"

    def test_documento_ja_sem_pontuacao(self):
        assert adequar_documento("21807980000109") == "21807980000109"
        assert adequar_documento("12345678901") == "12345678901"

    def test_documento_vazio_ou_nulo(self):
        assert adequar_documento("") == ""
        assert adequar_documento(None) == ""
        assert adequar_documento("   ") == ""

    def test_documento_com_mascara_parcial_socio(self):
        # Preserva asteriscos da Receita Federal
        assert adequar_documento("***.807.980-**") == "***807980**"
        assert adequar_documento("***807980**") == "***807980**"


class TestAdequarTelefone:
    def test_celular_11_digitos(self):
        # Caso o celular tenha 11 dígitos, considerar os 2 primeiros como DDD
        res = adequar_telefone("11987654321")
        assert res["valido"] is True
        assert res["ddd"] == "11"
        assert res["numero"] == "987654321"
        assert res["tipo"] == "CELULAR"
        assert res["telefone_completo"] == "11987654321"
        assert res["numero_original_8"] == "87654321"

    def test_celular_11_digitos_com_formatacao(self):
        res = adequar_telefone("(11) 98765-4321")
        assert res["valido"] is True
        assert res["ddd"] == "11"
        assert res["numero"] == "987654321"
        assert res["tipo"] == "CELULAR"

    def test_celular_10_digitos_inicia_com_9(self):
        # Caso tenha 10 dígitos e seja celular: 2 primeiros são DDD e adiciona 9 antes do restante
        res = adequar_telefone("1198765432")
        assert res["valido"] is True
        assert res["ddd"] == "11"
        assert res["numero"] == "998765432"
        assert res["tipo"] == "CELULAR"
        assert res["numero_original_8"] == "98765432"
        assert res["telefone_completo"] == "11998765432"
        assert res["ajuste_realizado"] is not None

    def test_celular_10_digitos_inicia_com_8(self):
        # Celular antigo de 8 dígitos (ex: 87654321 com DDD 11 -> 1187654321)
        res = adequar_telefone("(11) 8765-4321")
        assert res["valido"] is True
        assert res["ddd"] == "11"
        assert res["numero"] == "987654321"
        assert res["tipo"] == "CELULAR"
        assert res["numero_original_8"] == "87654321"
        assert res["telefone_completo"] == "11987654321"

    def test_celular_10_digitos_inicia_com_7_ou_6(self):
        # Outras faixas móveis
        res7 = adequar_telefone("2177654321")
        assert res7["ddd"] == "21"
        assert res7["numero"] == "977654321"
        assert res7["tipo"] == "CELULAR"

        res6 = adequar_telefone("3167654321")
        assert res6["ddd"] == "31"
        assert res6["numero"] == "967654321"
        assert res6["tipo"] == "CELULAR"

    def test_telefone_fixo_10_digitos(self):
        # Fixo inicia com 2, 3, 4 ou 5 -> NÃO adiciona 9
        res = adequar_telefone("(11) 3333-4444")
        assert res["valido"] is True
        assert res["ddd"] == "11"
        assert res["numero"] == "33334444"
        assert res["tipo"] == "FIXO"
        assert res["telefone_completo"] == "1133334444"
        assert res["ajuste_realizado"] is None

    def test_celular_8_digitos(self):
        # Celular de 8 dígitos sem DDD: adiciona 9 antes
        res = adequar_telefone("87654321")
        assert res["numero"] == "987654321"
        assert res["numero_original_8"] == "87654321"
        assert res["tipo"] == "CELULAR"

        # Com default_ddd
        res_com_ddd = adequar_telefone("87654321", default_ddd="11")
        assert res_com_ddd["valido"] is True
        assert res_com_ddd["ddd"] == "11"
        assert res_com_ddd["numero"] == "987654321"
        assert res_com_ddd["telefone_completo"] == "11987654321"

    def test_celular_com_ddi_55(self):
        res = adequar_telefone("+55 (11) 98765-4321")
        assert res["valido"] is True
        assert res["ddd"] == "11"
        assert res["numero"] == "987654321"

    def test_telefone_invalido(self):
        assert adequar_telefone("")["valido"] is False
        assert adequar_telefone(None)["valido"] is False
        assert adequar_telefone("123")["valido"] is False
