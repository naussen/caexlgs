import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_app")))

try:
    from cnpjpw.local_app.sanitizers import (
        correspondem_pessoa_fisica,
        extrair_parte_cpf,
        nomes_correspondem
    )
except ImportError:
    from sanitizers import (
        correspondem_pessoa_fisica,
        extrair_parte_cpf,
        nomes_correspondem
    )


class TestCorrespondenciaPessoaFisica:
    def test_mesmo_nome_e_mesmo_cpf_parcial(self):
        # Ambos itens correspondem: deve associar com sucesso
        ok, erro = correspondem_pessoa_fisica(
            nome_a="ALBERTO ROBERTO",
            doc_a="***111222**",
            nome_b="ALBERTO ROBERTO",
            doc_b="***111222**"
        )
        assert ok is True
        assert erro is None

    def test_nome_parcial_e_mesmo_cpf_parcial(self):
        # Nome completo vs nome abreviado/parcial + mesmo CPF parcial
        ok, erro = correspondem_pessoa_fisica(
            nome_a="ALBERTO ROBERTO",
            doc_a="***111222**",
            nome_b="ALBERTO ROBERTO DA SILVA",
            doc_b="***111222**"
        )
        assert ok is True
        assert erro is None

    def test_cpf_completo_compativel_com_mascara(self):
        # CPF completo 123.111.222-99 contém 111222
        ok, erro = correspondem_pessoa_fisica(
            nome_a="ALBERTO ROBERTO",
            doc_a="123.111.222-99",
            nome_b="ALBERTO ROBERTO",
            doc_b="***111222**"
        )
        assert ok is True
        assert erro is None

    def test_homonimo_mesmo_nome_mas_cpfs_divergentes(self):
        # ERRO GRAVE EVITADO: Mesmo nome, porém partes de CPF diferentes
        ok, erro = correspondem_pessoa_fisica(
            nome_a="ALBERTO ROBERTO",
            doc_a="***111222**",
            nome_b="ALBERTO ROBERTO",
            doc_b="***333444**"
        )
        assert ok is False
        assert "CPFs divergentes" in erro

    def test_mesmo_cpf_mas_nomes_completamente_diferentes(self):
        ok, erro = correspondem_pessoa_fisica(
            nome_a="ALBERTO ROBERTO",
            doc_a="***111222**",
            nome_b="CARLOS EDUARDO PEREIRA",
            doc_b="***111222**"
        )
        assert ok is False
        assert "Nomes não correspondem" in erro

    def test_falta_cpf_em_um_dos_registros(self):
        # Regra do usuário: ambos itens devem corresponder (parte do CPF + Nome)
        # Se um não tem CPF, NÃO deve haver vinculação de forma alguma
        ok, erro = correspondem_pessoa_fisica(
            nome_a="ALBERTO ROBERTO",
            doc_a="***111222**",
            nome_b="ALBERTO ROBERTO",
            doc_b=""
        )
        assert ok is False
        assert "Ausência de parte do CPF" in erro

    def test_falta_cpf_em_ambos(self):
        ok, erro = correspondem_pessoa_fisica(
            nome_a="ALBERTO ROBERTO",
            doc_a=None,
            nome_b="ALBERTO ROBERTO",
            doc_b=None
        )
        assert ok is False
        assert "Ausência de parte do CPF" in erro
