import os
from datetime import datetime

import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATASET_PATH = "./folhas_dataset.csv"


class Dado:
    def __init__(self, nsu, nome_da_imagem, categoria_detectada, area_verde_pixels,
                 area_manchas_pixels, porcentagem_doenca_folha):
        self.nsu = nsu
        self.nome_da_imagem = nome_da_imagem
        self.categoria_detectada = categoria_detectada
        self.area_verde_pixels = area_verde_pixels
        self.area_manchas_pixels = area_manchas_pixels
        self.porcentagem_doenca_folha = porcentagem_doenca_folha
        self.data_registro = datetime.now().isoformat()


def safe_read_csv():
    """Reads the dataset or returns an empty DataFrame if not found."""
    if not os.path.exists(DATASET_PATH):
        return pd.DataFrame()
    try:
        return pd.read_csv(DATASET_PATH)
    except Exception:
        return pd.DataFrame()  # fallback if file is corrupted


@app.route("/app", methods=["POST", "OPTIONS"])
def create_data():
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200  # handle CORS preflight

    db = safe_read_csv()
    nsu = get_nsu(db)

    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    required_fields = [
        "nome_da_imagem", "categoria_detectada",
        "area_verde_pixels", "area_manchas_pixels",
        "porcentagem_doenca_folha"
    ]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Campo faltante: {field}"}), 400

    try:
        novo_dado = Dado(
            nsu,
            str(data["nome_da_imagem"]),
            str(data["categoria_detectada"]),
            float(data["area_verde_pixels"]),
            float(data["area_manchas_pixels"]),
            float(data["porcentagem_doenca_folha"])
        )
    except (ValueError, TypeError):
        return jsonify({"error": "Tipos inválidos nos campos"}), 400

    persist(novo_dado)

    return jsonify({"message": "Data stored", "id": nsu}), 201


def get_nsu(db):
    if db.empty:
        return 1
    nsu = db['nsu'].iloc[-1]
    return int(nsu) + 1


def persist(dado):
    df = pd.DataFrame([dado.__dict__])
    header = not os.path.exists(DATASET_PATH)
    df.to_csv(DATASET_PATH, mode="a", header=header, index=False)


@app.route("/app", methods=["GET", "OPTIONS"])
def get_data():
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    db = safe_read_csv()

    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = max(int(request.args.get("perPage", 10)), 1)
    except ValueError:
        return jsonify({"error": "Parâmetros inválidos"}), 400

    start = (page - 1) * per_page
    result = db[start:start + per_page].to_dict('records')

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": int(db.shape[0]),
        "results": result,
    })


@app.route("/app/<int:nsu_id>", methods=["GET", "OPTIONS"])
def get_data_by_id(nsu_id):
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    db = safe_read_csv()
    record = db[db['nsu'] == nsu_id]

    if record.empty:
        return jsonify({"error": "Registro não encontrado"}), 404

    return jsonify(record.to_dict('records')[0]), 200


@app.route("/app/metrics", methods=["GET", "OPTIONS"])
def get_metrics():
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    db = safe_read_csv()
    if db.empty:
        return jsonify({"message": "Dataset está vazio, sem métricas para calcular"}), 200

    try:
        total_records = int(db.shape[0])
        most_common_category = db['categoria_detectada'].mode()[0] if not db['categoria_detectada'].mode().empty else None
        category_distribution = db['categoria_detectada'].value_counts().to_dict()

        # safe numeric stats
        disease_stats = db['porcentagem_doenca_folha'].describe().to_dict()
        green_area_stats = db['area_verde_pixels'].describe().to_dict()
        spots_area_stats = db['area_manchas_pixels'].describe().to_dict()

        # safe datetime parsing
        db['data_registro'] = pd.to_datetime(db['data_registro'], errors="coerce")
        db = db.dropna(subset=['data_registro'])

        registros_por_dia = db.groupby(db['data_registro'].dt.date).size().astype(int).to_dict()
        media_doenca_por_dia = db.groupby(db['data_registro'].dt.date)['porcentagem_doenca_folha'].mean().round(2).to_dict()

        sete_dias_atras = datetime.now() - pd.Timedelta(days=7)
        registros_ultimos_7_dias = int(db[db['data_registro'] >= sete_dias_atras].shape[0])

        metrics = {
            "estatisticas_gerais": {
                "total_de_registros": total_records,
                "categoria_mais_comum": most_common_category,
                "distribuicao_por_categoria": category_distribution,
                "estatisticas_porcentagem_doenca": {k: round(v, 2) if isinstance(v, float) else int(v) for k, v in disease_stats.items()}
            },
            "evolucao_temporal": {
                "registros_nos_ultimos_7_dias": registros_ultimos_7_dias,
                "contagem_de_registros_por_dia": {str(k): v for k, v in registros_por_dia.items()},
                "media_de_porcentagem_de_doenca_por_dia": {str(k): v for k, v in media_doenca_por_dia.items()}
            }
        }

        return jsonify(metrics), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao calcular métricas: {str(e)}"}), 500
