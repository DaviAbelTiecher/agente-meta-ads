import os
import threading
import time
from flask import Flask, jsonify, request, send_from_directory
from agente import obter_dados_estruturados

app = Flask(__name__, static_folder="static", template_folder="static")

# Cache em memória para resposta instantânea na Dashboard
CACHE_METRICAS = {}
CACHE_EM_ATUALIZACAO = {}

def atualizar_cache(date_preset="last_30d"):
    """Atualiza as métricas em segundo plano para um determinado preset de data."""
    global CACHE_METRICAS, CACHE_EM_ATUALIZACAO
    if CACHE_EM_ATUALIZACAO.get(date_preset):
        return

    CACHE_EM_ATUALIZACAO[date_preset] = True
    try:
        dados = obter_dados_estruturados(date_preset=date_preset)
        CACHE_METRICAS[date_preset] = {
            "dados": dados,
            "timestamp": time.time()
        }
    finally:
        CACHE_EM_ATUALIZACAO[date_preset] = False

def pre_carregar_todos_presets():
    """Pré-carrega todos os presets em paralelo na inicialização para evitar timeouts no navegador."""
    presets = ["last_30d", "last_15d", "last_7d", "this_month"]
    for p in presets:
        threading.Thread(target=atualizar_cache, args=(p,)).start()

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/metricas")
def api_metricas():
    date_preset = request.args.get("date_preset", "last_30d")
    force_refresh = request.args.get("force", "false").lower() == "true"

    # Sanitiza presets inválidos
    if date_preset not in ["last_30d", "last_15d", "last_7d", "this_month"]:
        date_preset = "last_30d"

    cache_item = CACHE_METRICAS.get(date_preset)
    agora = time.time()

    # Se não temos cache ou se foi forçada a atualização
    if not cache_item or force_refresh or (agora - cache_item.get("timestamp", 0) > 600):
        atualizar_cache(date_preset)
        cache_item = CACHE_METRICAS.get(date_preset)

    if cache_item:
        return jsonify(cache_item["dados"])
    else:
        return jsonify({
            "loading": False,
            "message": "Sem dados",
            "contas": [],
            "resumo": {}
        })

# Dispara o pré-carregamento inicial dos presets
threading.Thread(target=pre_carregar_todos_presets).start()

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 Servidor CRM Meta Ads rodando em: http://localhost:{porta}\n")
    app.run(host="0.0.0.0", port=porta, debug=True)
