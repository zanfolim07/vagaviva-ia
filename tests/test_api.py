import sys
import unittest
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO / "api"))

import app as modulo_api


class TestApiVagaViva(unittest.TestCase):
    def setUp(self):
        self.cliente = modulo_api.app.test_client()

    def test_status_informa_modelos_carregados(self):
        resposta = self.cliente.get("/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), {"status": "ok", "modelos": ["falta", "perfil"]})

    def test_prever_falta_retorna_nivel_aceito_pelo_java(self):
        entrada = {
            "idade": 45,
            "dias_antecedencia": 40,
            "mesmo_dia": False,
            "dia_semana": 1,
            "recebeu_lembrete": False,
            "n_consultas_anteriores": 3,
            "faltas_anteriores": 2,
            "taxa_faltas_anterior": 0.67,
            "primeira_consulta": False,
        }

        resposta = self.cliente.post("/prever-falta", json=entrada)
        corpo = resposta.get_json()

        self.assertEqual(resposta.status_code, 200)
        self.assertGreaterEqual(corpo["probabilidade_falta"], 0)
        self.assertLessEqual(corpo["probabilidade_falta"], 1)
        self.assertIn(corpo["nivel"], {"BAIXO", "MEDIO", "ALTO"})
        self.assertLessEqual(len(corpo["motivos"]), 3)

    def test_prever_falta_rejeita_campos_ausentes_sem_erro_servidor(self):
        casos = [
            {"faltas_anteriores": 1},
            {"dias_antecedencia": 0},
            {"idade": "45"},
            {"dia_semana": 7},
        ]

        for entrada in casos:
            with self.subTest(entrada=entrada):
                resposta = self.cliente.post("/prever-falta", json=entrada)
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("erro", resposta.get_json())
                self.assertIn("campos", resposta.get_json())

    def test_prever_falta_rejeita_inconsistencias_de_historico(self):
        entrada = {
            "idade": 45,
            "dias_antecedencia": 1,
            "mesmo_dia": False,
            "dia_semana": 1,
            "recebeu_lembrete": True,
            "n_consultas_anteriores": 1,
            "faltas_anteriores": 2,
            "taxa_faltas_anterior": 1,
            "primeira_consulta": False,
        }

        resposta = self.cliente.post("/prever-falta", json=entrada)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("faltas_anteriores", resposta.get_json()["campos"])

    def test_prever_falta_rejeita_json_invalido(self):
        resposta = self.cliente.post(
            "/prever-falta",
            data="{",
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("erro", resposta.get_json())

    def test_perfil_paciente_retorna_grupo_configurado(self):
        entrada = {
            "idade": 45,
            "dias_antecedencia_media": 12.5,
            "taxa_faltas_anterior": 0.25,
            "taxa_lembretes_anterior": 0.5,
            "n_consultas_anteriores": 4,
        }

        resposta = self.cliente.post("/perfil-paciente", json=entrada)
        corpo = resposta.get_json()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(str(corpo["grupo"]), modulo_api.PERFIS)
        self.assertEqual(corpo["perfil"], modulo_api.PERFIS[str(corpo["grupo"])]["nome"])
        self.assertEqual(
            corpo["estrategia_contato"],
            modulo_api.PERFIS[str(corpo["grupo"])]["estrategia_contato"],
        )

    def test_cors_permite_origem_do_frontend(self):
        resposta = self.cliente.get("/", headers={"Origin": "https://exemplo.test"})

        self.assertEqual(resposta.headers.get("Access-Control-Allow-Origin"), "https://exemplo.test")


if __name__ == "__main__":
    unittest.main()
