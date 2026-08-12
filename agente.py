import os
import sys
import datetime
import requests
from dotenv import load_dotenv

# Garante suporte a UTF-8 no terminal Windows para exibição de emojis
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 1. Carrega as chaves do arquivo .env
load_dotenv(override=True)

GRAPH_API_URL = "https://graph.facebook.com/v19.0"

def obter_parametro_data(date_preset):
    """Retorna a string de parâmetro para chamadas do Meta API considerando interval de datas customizado para last_15d."""
    if date_preset == "last_15d":
        today = datetime.date.today()
        since = (today - datetime.timedelta(days=15)).strftime("%Y-%m-%d")
        until = today.strftime("%Y-%m-%d")
        return f"&time_range={{\"since\":\"{since}\",\"until\":\"{until}\"}}", f"insights.time_range({{\"since\":\"{since}\",\"until\":\"{until}\"}})"
    else:
        return f"&date_preset={date_preset}", f"insights.date_preset({date_preset})"

def obter_tokens():
    """Retorna um dicionário com todos os tokens do Meta encontrados no .env."""
    tokens = {}
    for chave, valor in os.environ.items():
        if (chave.startswith("META_ACCESS_TOKEN") or chave.startswith("META_TOKEN")) and valor.strip():
            tokens[chave] = valor.strip()
    return tokens

def formatar_moeda(valor):
    try:
        val = float(valor)
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

def formatar_numero(valor):
    try:
        val = int(float(valor))
        return f"{val:,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"

def extrair_acao(actions, tipos_acao):
    """Procura por um tipo de ação na lista de ações do Meta e retorna a quantidade."""
    if not actions or not isinstance(actions, list):
        return 0
    for acao in actions:
        if acao.get("action_type") in tipos_acao:
            return float(acao.get("value", 0))
    return 0

def buscar_campanhas_conta(account_id, token, date_preset="last_30d"):
    """Busca as campanhas da conta e calcula o ROAS e métricas exatas de cada campanha individual."""
    param_ins, param_camp_ins = obter_parametro_data(date_preset)
    fields = "spend,reach,impressions,cpm,cpc,ctr,frequency,inline_link_clicks,actions,action_values,purchase_roas,cost_per_action_type"
    url = (
        f"{GRAPH_API_URL}/act_{account_id}/campaigns"
        f"?fields=name,status,objective,{param_camp_ins}{{{fields}}}"
        f"&access_token={token}"
    )
    try:
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            return []
        dados_campanhas = res.json().get("data", [])
    except Exception:
        return []

    campanhas = []

    tipos_perfil = ["instagram_profile_views", "profile_visit", "page_engagement"]
    tipos_conversas = [
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_initiated",
        "messaging_conversation_started_7d",
        "onsite_conversion.messaging_first_reply",
        "messaging_user_depth_2_conversations"
    ]
    tipos_compras = ["purchase", "offsite_conversion.fb_pixel_purchase", "onsite_conversion.purchase", "omni_purchase"]
    tipos_carrinhos = ["add_to_cart", "offsite_conversion.fb_pixel_add_to_cart", "onsite_conversion.add_to_cart"]
    tipos_checkouts = ["initiate_checkout", "offsite_conversion.fb_pixel_initiate_checkout", "onsite_conversion.initiate_checkout"]
    tipos_leads = ["lead", "offsite_conversion.fb_pixel_lead", "onsite_conversion.lead"]

    for camp in dados_campanhas:
        insights_data = camp.get("insights", {}).get("data", [])
        if not insights_data:
            continue
        
        insight = insights_data[0]
        spend = float(insight.get("spend", 0))
        reach = int(insight.get("reach", 0))
        impressions = int(insight.get("impressions", 0))
        cpm = float(insight.get("cpm", 0))
        cpc = float(insight.get("cpc", 0))
        ctr = float(insight.get("ctr", 0))
        frequency = float(insight.get("frequency", 0))
        cliques_link = int(insight.get("inline_link_clicks", 0))

        actions = insight.get("actions", [])
        action_values = insight.get("action_values", [])
        purchase_roas = insight.get("purchase_roas", [])
        cost_per_action = insight.get("cost_per_action_type", [])

        if cliques_link == 0:
            cliques_link = int(extrair_acao(actions, ["link_click"]))

        visitas_perfil = extrair_acao(actions, tipos_perfil)
        conversas_iniciadas = extrair_acao(actions, tipos_conversas)
        total_pedidos = extrair_acao(actions, tipos_compras)
        total_vendas = extrair_acao(action_values, tipos_compras)
        carrinhos = extrair_acao(actions, tipos_carrinhos)
        checkouts = extrair_acao(actions, tipos_checkouts)
        leads = extrair_acao(actions, tipos_leads)

        if spend == 0 and total_pedidos == 0 and total_vendas == 0 and conversas_iniciadas == 0 and impressions == 0:
            continue
        custo_por_conversa = 0.0
        if conversas_iniciadas > 0:
            custo_meta = extrair_acao(cost_per_action, tipos_conversas)
            custo_por_conversa = custo_meta if custo_meta > 0 else (spend / conversas_iniciadas)

        roas = extrair_acao(purchase_roas, tipos_compras)
        if roas == 0 and spend > 0 and total_vendas > 0:
            roas = total_vendas / spend

        nome_lower = camp.get("name", "").lower()
        is_vendas = (
            total_pedidos > 0 or 
            total_vendas > 0 or 
            camp.get("objective") == "OUTCOME_SALES" or 
            "vendas" in nome_lower or 
            "delivery" in nome_lower or 
            "site" in nome_lower or 
            "roas" in nome_lower or 
            "promocao" in nome_lower or 
            "promo" in nome_lower
        )
        tipo_foco = "vendas" if is_vendas else "mensagens"

        campanhas.append({
            "id": camp.get("id"),
            "nome": camp.get("name"),
            "status": camp.get("status"),
            "objective": camp.get("objective"),
            "tipo_foco": tipo_foco,
            "spend": spend,
            "reach": reach,
            "impressions": impressions,
            "cpm": cpm,
            "cpc": cpc,
            "ctr": ctr,
            "frequency": frequency,
            "cliques_link": cliques_link,
            "visitas_perfil": visitas_perfil,
            "conversas_iniciadas": conversas_iniciadas,
            "custo_por_conversa": custo_por_conversa,
            "total_pedidos": total_pedidos,
            "total_vendas": total_vendas,
            "carrinhos": carrinhos,
            "checkouts": checkouts,
            "leads": leads,
            "roas": roas
        })

    campanhas.sort(key=lambda x: -x["spend"])
    return campanhas

def buscar_metricas_conta(account_id, token, date_preset="last_30d"):
    """Busca insights (investimento, alcance, visitas, conversas, pedidos, vendas, ROAS) de uma conta de anúncio."""
    param_ins, param_camp_ins = obter_parametro_data(date_preset)
    fields = "spend,reach,impressions,cpm,cpc,ctr,frequency,inline_link_clicks,actions,action_values,purchase_roas,cost_per_action_type"
    url = (
        f"{GRAPH_API_URL}/act_{account_id}/insights"
        f"?fields={fields}"
        f"{param_ins}"
        f"&access_token={token}"
    )
    
    try:
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            return None, f"Erro na chamada de insights: {res.text}"
        dados = res.json().get("data", [])
    except Exception as e:
        return None, f"Erro de conexão com Meta API: {str(e)}"

    campanhas = buscar_campanhas_conta(account_id, token, date_preset=date_preset)

    if not dados:
        spend = sum(c["spend"] for c in campanhas)
        reach = sum(c["reach"] for c in campanhas)
        impressions = sum(c["impressions"] for c in campanhas)
        cpm = (spend / impressions * 1000) if impressions > 0 else 0.0
        cpc = 0.0
        ctr = 0.0
        frequency = 1.0
        cliques_link = sum(c["cliques_link"] for c in campanhas)
        actions = []
        action_values = []
        cost_per_action = []
    else:
        insight = dados[0]
        spend = float(insight.get("spend", 0))
        reach = int(insight.get("reach", 0))
        impressions = int(insight.get("impressions", 0))
        cpm = float(insight.get("cpm", 0))
        cpc = float(insight.get("cpc", 0))
        ctr = float(insight.get("ctr", 0))
        frequency = float(insight.get("frequency", 0))
        cliques_link = int(insight.get("inline_link_clicks", 0))
        actions = insight.get("actions", [])
        action_values = insight.get("action_values", [])
        cost_per_action = insight.get("cost_per_action_type", [])
        if cliques_link == 0:
            cliques_link = int(extrair_acao(actions, ["link_click"]))

    # Métricas de Engajamento e Mensagens
    tipos_perfil = [
        "instagram_profile_views",
        "profile_visit",
        "page_engagement"
    ]
    visitas_perfil = extrair_acao(actions, tipos_perfil)

    tipos_conversas = [
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_initiated",
        "messaging_conversation_started_7d",
        "onsite_conversion.messaging_first_reply",
        "messaging_user_depth_2_conversations"
    ]
    conversas_iniciadas = extrair_acao(actions, tipos_conversas)

    custo_por_conversa = 0.0
    if conversas_iniciadas > 0:
        custo_meta = extrair_acao(cost_per_action, tipos_conversas)
        custo_por_conversa = custo_meta if custo_meta > 0 else (spend / conversas_iniciadas)

    tipos_carrinhos = ["add_to_cart", "offsite_conversion.fb_pixel_add_to_cart", "onsite_conversion.add_to_cart"]
    tipos_checkouts = ["initiate_checkout", "offsite_conversion.fb_pixel_initiate_checkout", "onsite_conversion.initiate_checkout"]
    tipos_leads = ["lead", "offsite_conversion.fb_pixel_lead", "onsite_conversion.lead"]

    carrinhos = extrair_acao(actions, tipos_carrinhos)
    checkouts = extrair_acao(actions, tipos_checkouts)
    leads = extrair_acao(actions, tipos_leads)

    camps_vendas = [c for c in campanhas if c["tipo_foco"] == "vendas" and c["spend"] > 0]
    spend_vendas = sum(c["spend"] for c in camps_vendas)
    total_pedidos_vendas = sum(c["total_pedidos"] for c in camps_vendas)
    total_vendas_vendas = sum(c["total_vendas"] for c in camps_vendas)

    # Identifica relatório de vendas considerando APENAS as campanhas de vendas para TODOS os períodos (30d, 15d, 7d, este mês)
    if spend_vendas > 0 and (total_pedidos_vendas > 0 or total_vendas_vendas > 0 or len(camps_vendas) > 0):
        tipo_foco = "vendas"
        total_pedidos = total_pedidos_vendas
        total_vendas = total_vendas_vendas
        roas = total_vendas_vendas / spend_vendas if spend_vendas > 0 else 0.0
    else:
        tipo_foco = "mensagens"
        tipos_compras = ["purchase", "offsite_conversion.fb_pixel_purchase", "onsite_conversion.purchase", "omni_purchase"]
        total_pedidos = extrair_acao(actions, tipos_compras)
        total_vendas = extrair_acao(action_values, tipos_compras)
        roas = 0.0

    # Recalcula o Custo por Conversa da conta ignorando campanhas puras de alcance (sem conversas)
    if conversas_iniciadas > 0:
        camps_msg = [c for c in campanhas if c["conversas_iniciadas"] > 0]
        if camps_msg:
            investimento_msg = sum(c["spend"] for c in camps_msg)
            custo_por_conversa = investimento_msg / conversas_iniciadas

    return {
        "tipo_foco": tipo_foco,
        "spend": spend,
        "reach": reach,
        "impressions": impressions,
        "cpm": cpm,
        "cpc": cpc,
        "ctr": ctr,
        "frequency": frequency,
        "cliques_link": cliques_link,
        "visitas_perfil": visitas_perfil,
        "conversas_iniciadas": conversas_iniciadas,
        "custo_por_conversa": custo_por_conversa,
        "total_pedidos": total_pedidos,
        "total_vendas": total_vendas,
        "carrinhos": carrinhos,
        "checkouts": checkouts,
        "leads": leads,
        "roas": roas,
        "campanhas": campanhas
    }, None

import re

DAVI_ACCOUNT_IDS = {
    "1497103687754020",  # TITULAR BISTRO QUADROS
    "946711893418648",   # RESERVA BISTROQUADROS
    "3681113115526507",  # O Píer 2752 ADS
    "3779958585591852",  # Tirolesa
    "24007854312173347", # CANTINA BORDIGNON
    "1123342295755382",  # Itá Eco Turismo
    "537973965440696",   # FOCAS NOVO
    "2813853518995411",  # FOCAS JOINVILLE
    "653709310119105",   # FOCA'S BURGER
    "1473513237271653",  # SKY Village
    "726136737177745",   # Cabana Paraíso Natural
    "1082857080125960",  # Refugio das Pedras
    "907450422127857",   # CABANA FAZENDA RURAL
    "1059727207234978",  # BARRA BONITA
    "1371633781402796",  # CABANA SAFIRA
    "749845321489148"    # CHACARA BONS VENTOS
}

def limpar_nome_conta(nome):
    if not nome:
        return "Sem Nome"
    nome_limpo = re.sub(r'^(CA\s*[-–—:]\s*)+', '', nome, flags=re.IGNORECASE).strip()
    return nome_limpo if nome_limpo else nome

def obter_dados_estruturados(date_preset="last_30d"):
    """
    Consolida todas as contas e métricas do Meta Ads organizadas para JSON (API/Dashboard).
    """
    load_dotenv(override=True)
    tokens = obter_tokens()
    if not tokens:
        return {"error": "Nenhum token encontrado no arquivo .env", "contas": [], "resumo": {}}

    contas = []
    contas_processadas = set()

    resumo = {
        "total_contas": 0,
        "contas_ativas": 0,
        "contas_inativas": 0,
        "investimento_total": 0.0,
        "alcance_total": 0,
        "vendas_totais": 0.0,
        "pedidos_totais": 0,
        "conversas_totais": 0
    }

    for token in tokens.values():
        url = f"{GRAPH_API_URL}/me/adaccounts?fields=name,account_id,account_status,currency&access_token={token}"
        try:
            res = requests.get(url)
            if res.status_code != 200:
                continue
            dados_contas = res.json().get("data", [])
        except Exception:
            continue

        for conta in dados_contas:
            account_id = str(conta.get("account_id"))
            if account_id in contas_processadas:
                continue
            contas_processadas.add(account_id)

            nome_bruto = conta.get("name", "Sem Nome")
            nome_limpo = limpar_nome_conta(nome_bruto)
            gestor = "Davi" if account_id in DAVI_ACCOUNT_IDS else "Gabriel"
            status_num = conta.get("account_status")
            is_ativa = (status_num == 1)
            moeda = conta.get("currency", "BRL")
            simbolo_moeda = "R$" if moeda == "BRL" else f"{moeda} "

            resumo["total_contas"] += 1
            if is_ativa:
                resumo["contas_ativas"] += 1
            else:
                resumo["contas_inativas"] += 1

            item_conta = {
                "account_id": account_id,
                "nome_original": nome_bruto,
                "nome": nome_limpo,
                "gestor": gestor,
                "status_num": status_num,
                "is_ativa": is_ativa,
                "moeda": moeda,
                "simbolo_moeda": simbolo_moeda,
                "metricas": None,
                "erro": None
            }

            if is_ativa:
                metricas, err = buscar_metricas_conta(account_id, token, date_preset=date_preset)
                if err:
                    item_conta["erro"] = err
                else:
                    item_conta["metricas"] = metricas
                    resumo["investimento_total"] += metricas.get("spend", 0.0)
                    resumo["alcance_total"] += metricas.get("reach", 0)
                    resumo["vendas_totais"] += metricas.get("total_vendas", 0.0)
                    resumo["pedidos_totais"] += int(metricas.get("total_pedidos", 0))
                    resumo["conversas_totais"] += int(metricas.get("conversas_iniciadas", 0))
            else:
                item_conta["erro"] = f"Conta Inativa/Bloqueada (Código {status_num})"

            contas.append(item_conta)

    # Ordena contas em ordem alfabética por nome limpo
    contas.sort(key=lambda x: x["nome"].lower())

    return {
        "date_preset": date_preset,
        "resumo": resumo,
        "contas": contas
    }

def relatorio_meta_ads(date_preset="last_30d"):
    dados = obter_dados_estruturados(date_preset=date_preset)
    if "error" in dados:
        return f"❌ ERRO: {dados['error']}"

    relatorio = []
    relatorio.append(f"📅 PERÍODO DE ANÁLISE: {date_preset.upper()}\n")

    for conta in dados["contas"]:
        nome = conta["nome"]
        account_id = conta["account_id"]
        simbolo_moeda = conta["simbolo_moeda"]

        if not conta["is_ativa"]:
            relatorio.append(f"🏢 CONTA: {nome} (ID: act_{account_id}) - 🔴 INATIVA/BLOQUEADA ({conta['erro']})\n")
            continue

        relatorio.append(f"🏢 CONTA: {nome} (ID: act_{account_id})")
        relatorio.append("-" * 50)

        if conta["erro"]:
            relatorio.append(f"ℹ️ {conta['erro']}\n")
            continue

        m = conta["metricas"]
        relatorio.append(f"💰 Investimento: {simbolo_moeda} {formatar_moeda(m['spend'])}")
        relatorio.append(f"📢 Pessoas alcançadas: {formatar_numero(m['reach'])}")

        if m["tipo_foco"] == "vendas":
            relatorio.append(f"🛵 Total de pedidos: {formatar_numero(m['total_pedidos'])}")
            relatorio.append(f"📈 Total em vendas: {simbolo_moeda} {formatar_moeda(m['total_vendas'])}")
            roas_val = m['roas']
            relatorio.append(f"🤑 ROAS Geral (Conta): a cada 1 real, voltam {roas_val:.2f}".replace(".", ",") + "x")
        else:
            relatorio.append(f"👤 Visitas ao Perfil: {formatar_numero(m['visitas_perfil'])}")
            relatorio.append(f"💬 Conversas Iniciadas: {formatar_numero(m['conversas_iniciadas'])}")
            relatorio.append(f"📊 Custo por Conversas Iniciadas: {simbolo_moeda} {formatar_moeda(m['custo_por_conversa'])}")

        if m.get("campanhas"):
            relatorio.append("\n  🎯 CAMPANHAS DA CONTA:")
            for camp in m["campanhas"]:
                c_spend = formatar_moeda(camp["spend"])
                if camp["tipo_foco"] == "vendas":
                    c_roas = f"{camp['roas']:.2f}".replace(".", ",")
                    c_vendas = formatar_moeda(camp["total_vendas"])
                    c_pedidos = formatar_numero(camp["total_pedidos"])
                    relatorio.append(
                        f"    📌 {camp['nome']} -> Spend: {simbolo_moeda} {c_spend} | Pedidos: {c_pedidos} | Vendas: {simbolo_moeda} {c_vendas} | 🤑 ROAS: {c_roas}x"
                    )
                else:
                    c_conv = formatar_numero(camp["conversas_iniciadas"])
                    c_cpc = formatar_moeda(camp["custo_por_conversa"])
                    relatorio.append(
                        f"    📌 {camp['nome']} -> Spend: {simbolo_moeda} {c_spend} | Conversas: {c_conv} | Custo/Conv: {simbolo_moeda} {c_cpc}"
                    )
        relatorio.append("")

    return "\n".join(relatorio)

if __name__ == "__main__":
    print("\n📡 Buscando dados e métricas direto do Meta Ads...\n")
    resultado = relatorio_meta_ads(date_preset="last_30d")
    print("🚀 === RELATÓRIO DE MÉTRICAS META ADS === 🚀\n")
    print(resultado)