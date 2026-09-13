"""
Testes de Integração Live contra as APIs Públicas Reais do DataJud e ComunicaAPI/DJEN.
Executa consultas de homologação diretamente nos servidores públicos do CNJ.
"""
import unittest

from cnpjpw.local_app.judicial.datajud_client import DataJudClient
from cnpjpw.local_app.judicial.comunica_client import ComunicaClient
from cnpjpw.local_app.judicial.judicial_service import JudicialSearchService


class TestJudicialLiveAPIs(unittest.TestCase):

    def test_live_datajud_tjsp(self):
        client = DataJudClient(timeout=10)
        # Test query for a known TJSP process
        proc = client.consultar_processo("40033669720268260541", tribunal="tjsp")
        if proc:
            self.assertEqual(proc.tribunal, "TJSP")
            self.assertIsNotNone(proc.classe)
            self.assertIsNotNone(proc.orgao_julgador)
            print(f"\n[LIVE DATAJUD SUCCESS] Tribunal: {proc.tribunal}, Classe: {proc.classe}")

    def test_live_comunica_por_nome(self):
        client = ComunicaClient(timeout=10)
        # Consulta com nome de empresa de grande porte
        procs = client.buscar_por_nome("BANCO DO BRASIL SA", max_itens=2)
        self.assertGreater(len(procs), 0)
        p = procs[0]
        self.assertIsNotNone(p.numero)
        self.assertIsNotNone(p.tribunal)
        print(f"\n[LIVE COMUNICA SUCCESS] Processo: {p.numero_formatado}, Tribunal: {p.tribunal}, Partes: {len(p.partes)}")

    def test_live_judicial_service_cnpj(self):
        service = JudicialSearchService()
        # Petrobras CNPJ
        procs = service.consultar_por_cnpj(
            cnpj="33.000.167/0001-01",
            razao_social="PETROLEO BRASILEIRO S A PETROBRAS",
            max_itens=2,
            enriquecer_datajud=False,
        )
        self.assertGreater(len(procs), 0)
        vinculos = service.obter_vinculos_documento("33000167000101")
        self.assertGreater(len(vinculos), 0)
        print(f"\n[LIVE SERVICE CNPJ SUCCESS] Vínculos registrados: {len(vinculos)}")


if __name__ == "__main__":
    unittest.main()
