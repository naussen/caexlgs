"""
Suíte de Testes Automatizados para o Módulo de Inteligência Judicial e Vinculação Processual.
Compatível com unittest nativo do Python (sem dependência externa de pytest).
"""
import unittest
from unittest.mock import MagicMock

from cnpjpw.local_app.judicial.validators import (
    limpar_digitos,
    validar_cpf,
    validar_cnpj,
    formatar_cpf,
    formatar_cnpj,
    identificar_tipo_documento,
    sanitizar_nome,
    formatar_numero_processo_cnj,
)
from cnpjpw.local_app.judicial.models import (
    PoloProcessual,
    TipoDocumento,
    ParteProcessual,
    ProcessoJudicial,
    VinculoProcessual,
    MovimentoProcessual,
)
from cnpjpw.local_app.judicial.datajud_client import (
    DataJudClient,
    deduzir_tribunal_por_numero_cnj,
)
from cnpjpw.local_app.judicial.comunica_client import ComunicaClient
from cnpjpw.local_app.judicial.vinculador import VinculadorProcessual
from cnpjpw.local_app.judicial.judicial_service import JudicialSearchService
from cnpjpw.local_app.judicial.judicial_graph import converter_processos_para_elementos_grafo


class TestValidadoresJudiciais(unittest.TestCase):

    def test_limpar_digitos(self):
        self.assertEqual(limpar_digitos("12.345.678/0001-95"), "12345678000195")
        self.assertEqual(limpar_digitos("123.456.789-10"), "12345678910")
        self.assertEqual(limpar_digitos(None), "")
        self.assertEqual(limpar_digitos("abc-!@#"), "")

    def test_validar_cpf(self):
        self.assertTrue(validar_cpf("11144477735"))
        self.assertTrue(validar_cpf("529.982.247-25"))
        self.assertFalse(validar_cpf("11111111111"))
        self.assertFalse(validar_cpf("12345678900"))
        self.assertFalse(validar_cpf("123"))
        self.assertFalse(validar_cpf(""))
        self.assertFalse(validar_cpf(None))

    def test_validar_cnpj(self):
        self.assertTrue(validar_cnpj("00000000000191"))  # Banco do Brasil
        self.assertTrue(validar_cnpj("33.000.167/0001-01"))  # Petrobras
        self.assertFalse(validar_cnpj("00000000000000"))
        self.assertFalse(validar_cnpj("11.222.333/0001-99"))
        self.assertFalse(validar_cnpj("1234"))
        self.assertFalse(validar_cnpj(None))

    def test_formatadores_documento(self):
        self.assertEqual(formatar_cpf("52998224725"), "529.982.247-25")
        self.assertEqual(formatar_cnpj("00000000000191"), "00.000.000/0001-91")

    def test_identificar_tipo_documento(self):
        self.assertEqual(identificar_tipo_documento("529.982.247-25"), "CPF")
        self.assertEqual(identificar_tipo_documento("00.000.000/0001-91"), "CNPJ")
        self.assertEqual(identificar_tipo_documento("12345"), "INVALIDO")

    def test_sanitizar_nome(self):
        self.assertEqual(sanitizar_nome("João da Silva & Cia. Ltda."), "JOAO DA SILVA & CIA. LTDA.")
        self.assertEqual(sanitizar_nome("  Álvaro   Gonçalves   "), "ALVARO GONCALVES")
        self.assertEqual(sanitizar_nome(None), "")

    def test_formatar_e_deduzir_cnj(self):
        num_clean = "00002904020255080018"
        self.assertEqual(formatar_numero_processo_cnj(num_clean), "0000290-40.2025.5.08.0018")
        self.assertEqual(deduzir_tribunal_por_numero_cnj(num_clean), "trt8")

        num_tjsp = "10334818020238260405"
        self.assertEqual(deduzir_tribunal_por_numero_cnj(num_tjsp), "tjsp")

        num_trf3 = "50012345620244036100"
        self.assertEqual(deduzir_tribunal_por_numero_cnj(num_trf3), "trf3")


class TestDataJudClient(unittest.TestCase):

    def test_parsear_hit(self):
        client = DataJudClient()
        mock_source = {
            "numeroProcesso": "10334818020238260405",
            "tribunal": "TJSP",
            "grau": "G1",
            "classe": {"codigo": 12154, "nome": "Execução de Título Extrajudicial"},
            "orgaoJulgador": {"codigo": 9981, "nome": "7ª Vara Cível da Comarca de Osasco"},
            "dataAjuizamento": "2023-08-15T14:30:00",
            "assuntos": [{"nome": "Contratos Bancários"}, {"nome": "Inadimplemento"}],
            "movimentos": [
                {"codigo": 60, "nome": "Expedição de Mandado", "dataHora": "2024-01-10T10:00:00"},
                {"codigo": 26, "nome": "Distribuição", "dataHora": "2023-08-15T14:35:00"}
            ]
        }
        proc = client._parsear_hit(mock_source)
        self.assertEqual(proc.numero, "10334818020238260405")
        self.assertEqual(proc.tribunal, "TJSP")
        self.assertEqual(proc.classe, "Execução de Título Extrajudicial")
        self.assertEqual(proc.orgao_julgador, "7ª Vara Cível da Comarca de Osasco")
        self.assertEqual(len(proc.assuntos), 2)
        self.assertIn("Contratos Bancários", proc.assuntos)
        self.assertEqual(len(proc.movimentos), 2)
        self.assertEqual(proc.movimentos[0].nome, "Expedição de Mandado")


class TestComunicaClient(unittest.TestCase):

    def test_agrupar_por_processo(self):
        client = ComunicaClient()
        mock_items = [
            {
                "numero_processo": "00002904020255080018",
                "numeroprocessocommascara": "0000290-40.2025.5.08.0018",
                "siglaTribunal": "TRT8",
                "nomeClasse": "Ação Trabalhista",
                "nomeOrgao": "1ª Vara do Trabalho de Belém",
                "data_disponibilizacao": "2025-02-10",
                "link": "https://pje.trt8.jus.br/comunicacao/1",
                "destinatarios": [
                    {"nome": "EMPRESA ALFA LTDA", "polo": "P"},
                    {"nome": "JOAO DA SILVA", "polo": "A"}
                ],
                "destinatarioadvogados": [
                    {"advogado": {"nome": "DR. ROBERTO CARLOS", "numero_oab": "12345", "uf_oab": "PA"}}
                ]
            },
            {
                "numero_processo": "00002904020255080018",
                "numeroprocessocommascara": "0000290-40.2025.5.08.0018",
                "siglaTribunal": "TRT8",
                "data_disponibilizacao": "2025-03-01",
                "destinatarios": [
                    {"nome": "EMPRESA ALFA LTDA", "polo": "P"}
                ],
                "destinatarioadvogados": []
            }
        ]

        processos = client._agrupar_por_processo(mock_items)
        self.assertEqual(len(processos), 1)
        proc = processos[0]
        self.assertEqual(proc.numero, "00002904020255080018")
        self.assertEqual(proc.data_ultima_atualizacao, "2025-03-01")
        self.assertEqual(len(proc.partes), 2)

        reus = proc.polo_passivo
        autores = proc.polo_ativo
        self.assertEqual(len(reus), 1)
        self.assertEqual(reus[0].nome, "EMPRESA ALFA LTDA")
        self.assertEqual(len(autores), 1)
        self.assertEqual(autores[0].nome, "JOAO DA SILVA")


class TestVinculadorProcessual(unittest.TestCase):

    def test_vinculacao_bidirecional_e_estatisticas(self):
        vinculador = VinculadorProcessual()

        proc = ProcessoJudicial(
            numero="00002904020255080018",
            numero_formatado="0000290-40.2025.5.08.0018",
            tribunal="TRT8",
            classe="Ação Trabalhista",
            partes=[
                ParteProcessual(nome="EMPRESA ALFA LTDA", polo=PoloProcessual.PASSIVO),
                ParteProcessual(nome="JOAO DA SILVA", polo=PoloProcessual.ATIVO),
            ]
        )

        # 1. Vincula CNPJ da empresa Alfa como Ré
        v_cnpj = vinculador.vincular(
            documento="00.000.000/0001-91",
            nome_parte="EMPRESA ALFA LTDA",
            processo=proc,
            polo=PoloProcessual.PASSIVO,
            papel="REU",
        )
        self.assertEqual(v_cnpj.documento, "00000000000191")
        self.assertEqual(v_cnpj.polo, PoloProcessual.PASSIVO)
        self.assertEqual(v_cnpj.papel, "REU")

        # 2. Vincula CPF do João da Silva como Autor
        v_cpf = vinculador.vincular(
            documento="529.982.247-25",
            nome_parte="JOAO DA SILVA",
            processo=proc,
            polo=PoloProcessual.ATIVO,
            papel="AUTOR",
        )
        self.assertEqual(v_cpf.documento, "52998224725")
        self.assertEqual(v_cpf.polo, PoloProcessual.ATIVO)

        # 3. Consulta bidirecional: por documento
        procs_cnpj = vinculador.obter_processos_por_documento("00.000.000/0001-91")
        self.assertEqual(len(procs_cnpj), 1)
        self.assertEqual(procs_cnpj[0].numero_processo, "00002904020255080018")

        # 4. Consulta bidirecional: por processo
        docs_proc = vinculador.obter_documentos_por_processo("00002904020255080018")
        self.assertEqual(len(docs_proc), 2)
        docs_set = {v.documento for v in docs_proc}
        self.assertIn("00000000000191", docs_set)
        self.assertIn("52998224725", docs_set)

        # 5. Resumo estatístico
        stats = vinculador.gerar_resumo_estatistico("00000000000191")
        self.assertEqual(stats["total_processos"], 1)
        self.assertEqual(stats["como_reu"], 1)
        self.assertEqual(stats["como_autor"], 0)
        self.assertEqual(stats["distribuicao_tribunais"]["TRT8"], 1)


class TestJudicialService(unittest.TestCase):

    def test_consultar_por_cnpj(self):
        mock_comunica = MagicMock()
        mock_datajud = MagicMock()
        vinculador = VinculadorProcessual()

        service = JudicialSearchService(
            datajud_client=mock_datajud,
            comunica_client=mock_comunica,
            vinculador=vinculador,
        )

        proc_mock = ProcessoJudicial(
            numero="00002904020255080018",
            numero_formatado="0000290-40.2025.5.08.0018",
            tribunal="TRT8",
            partes=[
                ParteProcessual(nome="PETROLEO BRASILEIRO S A PETROBRAS", polo=PoloProcessual.PASSIVO),
                ParteProcessual(nome="MARCOS SOUZA", polo=PoloProcessual.ATIVO),
            ]
        )
        mock_comunica.buscar_por_documento.return_value = [proc_mock]
        mock_comunica.buscar_por_nome.return_value = []

        proc_enriquecido = ProcessoJudicial(
            numero="00002904020255080018",
            numero_formatado="0000290-40.2025.5.08.0018",
            tribunal="TRT8",
            classe="Procedimento Sumaríssimo",
            orgao_julgador="3ª Vara do Trabalho de Belém",
            data_ajuizamento="2025-01-10",
            movimentos=[MovimentoProcessual(codigo=1, nome="Audiência Concluída")]
        )
        mock_datajud.consultar_processo.return_value = proc_enriquecido

        resultados = service.consultar_por_cnpj(
            cnpj="33.000.167/0001-01",
            razao_social="PETROLEO BRASILEIRO S A PETROBRAS",
            enriquecer_datajud=True,
        )

        self.assertEqual(len(resultados), 1)
        p = resultados[0]
        self.assertEqual(p.numero, "00002904020255080018")
        self.assertEqual(p.classe, "Procedimento Sumaríssimo")
        self.assertEqual(p.orgao_julgador, "3ª Vara do Trabalho de Belém")
        self.assertEqual(len(p.movimentos), 1)

        vinculos = service.obter_vinculos_documento("33.000.167/0001-01")
        self.assertEqual(len(vinculos), 1)
        self.assertEqual(vinculos[0].polo, PoloProcessual.PASSIVO)
        self.assertEqual(vinculos[0].papel, "REU")


class TestGrafoJudicial(unittest.TestCase):

    def test_converter_processos_para_grafo(self):
        proc = ProcessoJudicial(
            numero="00002904020255080018",
            numero_formatado="0000290-40.2025.5.08.0018",
            tribunal="TRT8",
            classe="Ação Trabalhista",
            partes=[
                ParteProcessual(nome="EMPRESA ALFA LTDA", polo=PoloProcessual.PASSIVO)
            ]
        )
        vinculo = VinculoProcessual(
            documento="00000000000191",
            documento_formatado="00.000.000/0001-91",
            tipo_documento=TipoDocumento.CNPJ,
            nome_parte="EMPRESA ALFA LTDA",
            numero_processo="00002904020255080018",
            numero_formatado="0000290-40.2025.5.08.0018",
            tribunal="TRT8",
            polo=PoloProcessual.PASSIVO,
            papel="REU",
        )

        nodes, edges = converter_processos_para_elementos_grafo(
            processos=[proc],
            vinculos=[vinculo],
            id_no_origem="empresa_00000000000191",
        )

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["id"], "proc_00002904020255080018")
        self.assertIn("TRT8", nodes[0]["label"])
        self.assertEqual(nodes[0]["tipo"], "PROCESSO")

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["from"], "empresa_00000000000191")
        self.assertEqual(edges[0]["to"], "proc_00002904020255080018")
        self.assertIn("Réu", edges[0]["label"])
        self.assertTrue(edges[0]["dashes"])


if __name__ == "__main__":
    unittest.main()
