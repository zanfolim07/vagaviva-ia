import json
import math
import os
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import BadRequest


PASTA_MODELOS = Path(__file__).resolve().parent.parent / "modelos"
with (PASTA_MODELOS / "config_modelos.json").open(encoding="utf-8") as arquivo:
    CONFIG = json.load(arquivo)

MODELO_FALTA = joblib.load(PASTA_MODELOS / "modelo_falta.joblib")
MODELO_PERFIL = joblib.load(PASTA_MODELOS / "modelo_perfil.joblib")
SCALER_PERFIL = joblib.load(PASTA_MODELOS / "scaler_perfil.joblib")

FEATURES_FALTA = CONFIG["features_falta"]
FEATURES_PERFIL = CONFIG["features_perfil"]
LIMITES_RISCO = CONFIG["limites_risco"]
NIVEIS_RISCO = CONFIG["niveis_risco"]
PERFIS = CONFIG["perfis"]

if set(NIVEIS_RISCO.values()) != {"BAIXO", "MEDIO", "ALTO"}:
    raise ValueError("config_modelos.json deve mapear os níveis BAIXO, MEDIO e ALTO.")
if len(FEATURES_FALTA) != 9 or len(FEATURES_PERFIL) != 5:
    raise ValueError("A configuração não contém a ordem esperada de features.")
if any(str(grupo) not in PERFIS for grupo in range(CONFIG["agrupamento_perfil"]["n_grupos"])):
    raise ValueError("A configuração não contém nomes para todos os grupos do modelo.")

app = Flask(__name__)
CORS(app)

REGRAS_FALTA = {
    "idade": ("inteiro", 0, 130),
    "dias_antecedencia": ("inteiro", 0, None),
    "mesmo_dia": ("booleano", None, None),
    "dia_semana": ("inteiro", 0, 6),
    "recebeu_lembrete": ("booleano", None, None),
    "n_consultas_anteriores": ("inteiro", 0, None),
    "faltas_anteriores": ("inteiro", 0, None),
    "taxa_faltas_anterior": ("numero", 0, 1),
    "primeira_consulta": ("booleano", None, None),
}

REGRAS_PERFIL = {
    "idade": ("inteiro", 0, 130),
    "dias_antecedencia_media": ("numero", 0, None),
    "taxa_faltas_anterior": ("numero", 0, 1),
    "taxa_lembretes_anterior": ("numero", 0, 1),
    "n_consultas_anteriores": ("inteiro", 0, None),
}


def _validar_payload(payload, regras):
    if not isinstance(payload, dict):
        return ["body"]

    campos_invalidos = []
    for campo, (tipo, minimo, maximo) in regras.items():
        if campo not in payload:
            campos_invalidos.append(campo)
            continue

        valor = payload[campo]
        if tipo == "booleano":
            valido = isinstance(valor, bool)
        elif tipo == "inteiro":
            valido = isinstance(valor, int) and not isinstance(valor, bool)
        else:
            valido = (
                isinstance(valor, (int, float))
                and not isinstance(valor, bool)
                and math.isfinite(float(valor))
            )

        if not valido:
            campos_invalidos.append(campo)
            continue
        if minimo is not None and valor < minimo:
            campos_invalidos.append(campo)
        elif maximo is not None and valor > maximo:
            campos_invalidos.append(campo)

    if campos_invalidos:
        return sorted(set(campos_invalidos))

    if "faltas_anteriores" in payload:
        if payload["faltas_anteriores"] > payload["n_consultas_anteriores"]:
            campos_invalidos.append("faltas_anteriores")
        if payload["primeira_consulta"] != (payload["n_consultas_anteriores"] == 0):
            campos_invalidos.append("primeira_consulta")
    if "dias_antecedencia" in payload:
        if payload["mesmo_dia"] != (payload["dias_antecedencia"] == 0):
            campos_invalidos.append("mesmo_dia")
    return sorted(set(campos_invalidos))


def _obter_json():
    if not request.is_json:
        return None, (jsonify({"erro": "O corpo deve ser enviado como JSON.", "campos": ["body"]}), 400)
    try:
        payload = request.get_json()
    except BadRequest:
        return None, (jsonify({"erro": "JSON inválido.", "campos": ["body"]}), 400)
    if not isinstance(payload, dict):
        return None, (jsonify({"erro": "O corpo JSON deve ser um objeto.", "campos": ["body"]}), 400)
    return payload, None


def _gerar_motivos(entrada):
    motivos = []
    if entrada["dias_antecedencia"] > 30:
        motivos.append(f"Agendada há {entrada['dias_antecedencia']} dias")
    if not entrada["recebeu_lembrete"]:
        motivos.append("Sem lembrete")
    if entrada["primeira_consulta"]:
        motivos.append("Primeira consulta")
    elif entrada["faltas_anteriores"] > 0:
        motivos.append(
            f"Faltou em {entrada['faltas_anteriores']} das "
            f"{entrada['n_consultas_anteriores']} consultas anteriores"
        )
    return [motivo[:64] for motivo in motivos[:3]]


@app.get("/")
def status():
    return jsonify({"status": "ok", "modelos": ["falta", "perfil"]})


@app.post("/prever-falta")
def prever_falta():
    entrada, erro_json = _obter_json()
    if erro_json:
        return erro_json

    campos = _validar_payload(entrada, REGRAS_FALTA)
    if campos:
        return jsonify({"erro": "Campos ausentes ou inválidos.", "campos": campos}), 400

    linha = pd.DataFrame([{campo: entrada[campo] for campo in FEATURES_FALTA}])
    classes = list(MODELO_FALTA.classes_)
    if 1 not in classes:
        raise RuntimeError("O modelo de falta não contém a classe positiva 1.")
    indice_falta = classes.index(1)
    probabilidade = float(MODELO_FALTA.predict_proba(linha)[0][indice_falta])

    if probabilidade < LIMITES_RISCO["baixo_maximo_exclusivo"]:
        nivel = NIVEIS_RISCO["baixo"]
    elif probabilidade <= LIMITES_RISCO["medio_maximo_inclusivo"]:
        nivel = NIVEIS_RISCO["medio"]
    else:
        nivel = NIVEIS_RISCO["alto"]

    return jsonify(
        {
            "probabilidade_falta": round(probabilidade, 6),
            "nivel": nivel,
            "motivos": _gerar_motivos(entrada),
        }
    )


@app.post("/perfil-paciente")
def perfil_paciente():
    entrada, erro_json = _obter_json()
    if erro_json:
        return erro_json

    campos = _validar_payload(entrada, REGRAS_PERFIL)
    if campos:
        return jsonify({"erro": "Campos ausentes ou inválidos.", "campos": campos}), 400

    linha = pd.DataFrame([{campo: entrada[campo] for campo in FEATURES_PERFIL}])
    linha_normalizada = SCALER_PERFIL.transform(linha)
    grupo = int(MODELO_PERFIL.predict(linha_normalizada)[0])
    perfil = PERFIS.get(str(grupo))
    if perfil is None:
        raise RuntimeError(f"O grupo {grupo} não tem perfil na configuração.")

    return jsonify(
        {
            "grupo": grupo,
            "perfil": perfil["nome"],
            "estrategia_contato": perfil["estrategia_contato"],
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
