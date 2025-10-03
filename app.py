import os
from datetime import datetime

import pandas as pd
from flask import Flask, request, jsonify

app = Flask(__name__)

DATASET_PATH = "./folhas_dataset.csv"

class Dado:
    def __init__(self, nsu, nome_da_imagem, categoria_detectada, area_verde_pixels, area_manchas_pixels, porcentagem_doenca_folha):
        self.nsu = nsu
        self.nome_da_imagem = nome_da_imagem
        self.categoria_detectada = categoria_detectada
        self.area_verde_pixels = area_verde_pixels
        self.area_manchas_pixels = area_manchas_pixels
        self.porcentagem_doenca_folha = porcentagem_doenca_folha
        self.data_registro = datetime.now().isoformat()

@app.route("/app", methods=["POST"])
def create_data():
    db = pd.DataFrame(pd.read_csv("./folhas_dataset.csv"))
    nsu = get_nsu(db)

    data = request.get_json(force=True)

    # validation
    required_fields = [
        "nome_da_imagem",
        "categoria_detectada",
        "area_verde_pixels",
        "area_manchas_pixels",
        "porcentagem_doenca_folha",
    ]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Campo faltante: {field}"}), 400

    novo_dado = Dado(
        nsu,
        data["nome_da_imagem"],
        data["categoria_detectada"],
        data["area_verde_pixels"],
        data["area_manchas_pixels"],
        data["porcentagem_doenca_folha"]
    )

    persist(novo_dado)

    return jsonify({"message": "Data stored", "id": nsu}), 201


def get_nsu(db):
    nsu = db['nsu'].iloc[-1]
    return int(nsu) + 1

def persist(dado):
    df = pd.DataFrame([dado.__dict__])
    print(df)

    header = not os.path.exists(DATASET_PATH)
    df.to_csv(DATASET_PATH, mode="a", header=header, index=False)


@app.route("/app", methods=["GET"])
def get_data():
    db = pd.read_csv("./folhas_dataset.csv")

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("perPage", 10))

    assert page > 0
    assert per_page > 0

    start = (page - 1) * per_page

    result = db[start:start + per_page].to_dict('records')

    print(result)

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": db.shape[0],
        "results": result,
    })
