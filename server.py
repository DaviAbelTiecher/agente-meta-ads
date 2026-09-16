import os
import threading
import time
from flask import Flask, jsonify, request, send_from_directory
from agente import obter_dados_estruturados, analisar_dados_ia

app = Flask(__name__, static_folder="static", template_folder="static")

# Cache em memória para resposta instantânea na Dashboard
CACHE_METRICAS = {}
CACHE_EM_ATUALIZACAO = {}

def atualizar_cache(cache_key, date_preset=None, since=None, until=None):
    """Atualiza as métricas em segundo plano para um determinado preset de data ou intervalo customizado."""
    global CACHE_METRICAS, CACHE_EM_ATUALIZACAO
    if CACHE_EM_ATUALIZACAO.get(cache_key):
        return

    CACHE_EM_ATUALIZACAO[cache_key] = True
    try:
        dados = obter_dados_estruturados(date_preset=date_preset, since=since, until=until)
        if dados and len(dados.get("contas", [])) > 0:
            CACHE_METRICAS[cache_key] = {
                "dados": dados,
                "timestamp": time.time()
            }
            print(f"✅ Cache '{cache_key}' atualizado com {len(dados['contas'])} contas.")
        else:
            print(f"⚠️ Nenhuma conta retornada para cache '{cache_key}': {dados}")
    except Exception as e:
        print(f"❌ Erro ao atualizar cache '{cache_key}': {e}")
    finally:
        CACHE_EM_ATUALIZACAO[cache_key] = False

def pre_carregar_inicial():
    """Pré-carrega o preset padrão ao iniciar o servidor de forma limpa."""
    atualizar_cache("last_30d", date_preset="last_30d")

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/metricas")
def api_metricas():
    since = request.args.get("since")
    until = request.args.get("until")
    date_preset = request.args.get("date_preset")
    force_refresh = request.args.get("force", "false").lower() == "true"

    if since and until:
        cache_key = f"custom_{since}_{until}"
    else:
        if not date_preset or date_preset not in ["today", "yesterday", "last_7d", "last_15d", "last_30d", "this_month", "last_month"]:
            date_preset = "last_30d"
        cache_key = date_preset

    cache_item = CACHE_METRICAS.get(cache_key)
    agora = time.time()

    # Se não temos cache ou se foi forçada a atualização
    if not cache_item or force_refresh or (agora - cache_item.get("timestamp", 0) > 600):
        # Dispara atualização em thread de segundo plano para resposta instantânea na API
        threading.Thread(target=atualizar_cache, args=(cache_key, date_preset, since, until)).start()
        cache_item = CACHE_METRICAS.get(cache_key)

    if cache_item:
        return jsonify(cache_item["dados"])
    else:
        return jsonify({
            "loading": True,
            "message": "Buscando métricas do período no Meta Ads...",
            "contas": [],
            "resumo": {}
        })

@app.route("/api/chat", methods=["POST"])
def api_chat():
    req_data = request.get_json() or {}
    mensagem = req_data.get("message", "").strip()
    date_preset = req_data.get("date_preset", "last_30d")
    since = req_data.get("since")
    until = req_data.get("until")
    account_id = req_data.get("account_id")

    if not mensagem:
        return jsonify({"answer": "Por favor, digite uma pergunta."}), 400

    if since and until:
        cache_key = f"custom_{since}_{until}"
    else:
        cache_key = date_preset if date_preset in ["today", "yesterday", "last_7d", "last_15d", "last_30d", "this_month", "last_month"] else "last_30d"

    cache_item = CACHE_METRICAS.get(cache_key)
    if cache_item and cache_item.get("dados"):
        dados = cache_item["dados"]
    else:
        dados = obter_dados_estruturados(date_preset=date_preset, since=since, until=until)

    resposta = analisar_dados_ia(dados, mensagem, account_id=account_id)
    return jsonify({"answer": resposta})

# Dispara o pré-carregamento inicial dos dados
threading.Thread(target=pre_carregar_inicial).start()

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 Servidor CRM Meta Ads rodando em: http://localhost:{porta}\n")
    app.run(host="0.0.0.0", port=porta, debug=True, use_reloader=False)

