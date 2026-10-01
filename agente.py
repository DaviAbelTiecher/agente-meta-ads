import os
import sys
import time
import datetime
import requests
from dotenv import load_dotenv
from config_nichos import obter_nicho_conta

# Garante suporte a UTF-8 no terminal Windows para exibição de emojis
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 1. Carrega as chaves do arquivo .env
load_dotenv(override=True)

GRAPH_API_URL = "https://graph.facebook.com/v19.0"

# Mapeamento em memória de tokens por account_id para consultas detalhadas de anúncios
CONTA_TOKENS_CACHE = {}


def obter_parametro_data(date_preset="last_30d", since=None, until=None):
    """Retorna a string de parâmetro para chamadas do Meta API considerando intervalo de datas customizado ou preset."""
    if since and until:
        time_range_json = f'{{"since":"{since}","until":"{until}"}}'
        return f"&time_range={time_range_json}", f"insights.time_range({time_range_json})"
    elif date_preset == "last_15d":
        today = datetime.date.today()
        s = (today - datetime.timedelta(days=15)).strftime("%Y-%m-%d")
        u = today.strftime("%Y-%m-%d")
        time_range_json = f'{{"since":"{s}","until":"{u}"}}'
        return f"&time_range={time_range_json}", f"insights.time_range({time_range_json})"
    else:
        preset = date_preset if date_preset else "last_30d"
        return f"&date_preset={preset}", f"insights.date_preset({preset})"

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

def buscar_campanhas_conta(account_id, token, date_preset="last_30d", since=None, until=None):
    """Busca as campanhas da conta e calcula o ROAS e métricas exatas de cada campanha individual."""
    param_ins, param_camp_ins = obter_parametro_data(date_preset, since=since, until=until)
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

        # Identifica se a campanha tem objetivo real de MENSAGEM (WhatsApp/Direct/Messenger)
        termos_msg = ["whats", "whatsapp", "msg", "mensagem", "mensagens", "direct", "conversa", "chat"]
        tem_kw_msg = any(t in nome_lower for t in termos_msg)
        
        termos_nao_msg = ["perfil", "[ig]", "instagram", "seguidores", "alcance", "awareness", "tráfego", "trafego", "engajamento][ig", "engajamento [ig]"]
        tem_kw_nao_msg = any(t in nome_lower for t in termos_nao_msg)
        
        custo_meta_msg = extrair_acao(cost_per_action, tipos_conversas)

        if not is_vendas:
            if tem_kw_msg:
                is_mensagem = True
            elif custo_meta_msg > 0 and not tem_kw_nao_msg:
                is_mensagem = True
            elif tem_kw_nao_msg:
                is_mensagem = False
            elif camp.get("objective") == "OUTCOME_ENGAGEMENT" and conversas_iniciadas > 0:
                is_mensagem = True
            else:
                is_mensagem = False
        else:
            is_mensagem = False

        custo_por_conversa = 0.0
        if is_mensagem and conversas_iniciadas > 0:
            custo_por_conversa = custo_meta_msg if custo_meta_msg > 0 else (spend / conversas_iniciadas)

        roas = extrair_acao(purchase_roas, tipos_compras)
        if roas == 0 and spend > 0 and total_vendas > 0:
            roas = total_vendas / spend

        # Indicadores táticos de alta performance
        taxa_conversao_clique = 0.0
        if cliques_link > 0:
            if is_vendas and total_pedidos > 0:
                taxa_conversao_clique = round((total_pedidos / cliques_link) * 100.0, 2)
            elif conversas_iniciadas > 0:
                taxa_conversao_clique = round((conversas_iniciadas / cliques_link) * 100.0, 2)

        fadiga_criativo = (frequency >= 2.4 and ctr < 1.0)
        cpm_elevado = (cpm > 35.0)

        campanhas.append({
            "id": camp.get("id"),
            "nome": camp.get("name"),
            "status": camp.get("status"),
            "objective": camp.get("objective"),
            "tipo_foco": tipo_foco,
            "is_mensagem": is_mensagem,
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
            "taxa_conversao_clique": taxa_conversao_clique,
            "fadiga_criativo": fadiga_criativo,
            "cpm_elevado": cpm_elevado
        })

    campanhas.sort(key=lambda x: -x["spend"])
    total_spend_camp = sum(c["spend"] for c in campanhas)
    for c in campanhas:
        c["peso_orcamento_pct"] = round((c["spend"] / total_spend_camp * 100.0), 1) if total_spend_camp > 0 else 0.0

    return campanhas

def buscar_anuncios_conta(account_id, token, date_preset="last_30d", since=None, until=None, limit=20):
    """
    Busca os criativos/anúncios da conta com métricas aprofundadas (spend, CTR, frequência, conversas, CPA, ROAS).
    Permite ao Gestor Sênior diagnosticar causa raiz no nível do criativo específico e tomar decisões cirúrgicas.
    """
    if not token or not account_id:
        return []

    param_ins, param_camp_ins = obter_parametro_data(date_preset, since=since, until=until)
    fields = "spend,reach,impressions,cpm,cpc,ctr,frequency,inline_link_clicks,actions,action_values,purchase_roas,cost_per_action_type"
    url = (
        f"{GRAPH_API_URL}/act_{account_id}/ads"
        f"?fields=name,status,effective_status,campaign{{name}},adset{{name}},{param_camp_ins}{{{fields}}}"
        f"&limit={limit}"
        f"&access_token={token}"
    )

    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return []
        dados_anuncios = res.json().get("data", [])
    except Exception:
        return []

    tipos_conversas = [
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_initiated",
        "messaging_conversation_started_7d",
        "onsite_conversion.messaging_first_reply",
        "messaging_user_depth_2_conversations"
    ]
    tipos_compras = ["purchase", "offsite_conversion.fb_pixel_purchase", "onsite_conversion.purchase", "omni_purchase"]

    anuncios = []
    for item in dados_anuncios:
        insights_list = item.get("insights", {}).get("data", [])
        if not insights_list:
            continue
        ins = insights_list[0]
        spend = float(ins.get("spend", 0))
        if spend == 0:
            continue

        reach = int(ins.get("reach", 0))
        impressions = int(ins.get("impressions", 0))
        cpm = float(ins.get("cpm", 0))
        cpc = float(ins.get("cpc", 0))
        ctr = float(ins.get("ctr", 0))
        frequency = float(ins.get("frequency", 0))
        cliques_link = int(ins.get("inline_link_clicks", 0))

        actions = ins.get("actions", [])
        action_values = ins.get("action_values", [])
        purchase_roas = ins.get("purchase_roas", [])
        cost_per_action = ins.get("cost_per_action_type", [])

        if cliques_link == 0:
            cliques_link = int(extrair_acao(actions, ["link_click"]))

        conversas = extrair_acao(actions, tipos_conversas)
        pedidos = extrair_acao(actions, tipos_compras)
        vendas = extrair_acao(action_values, tipos_compras)
        roas = extrair_acao(purchase_roas, tipos_compras)
        if roas == 0 and spend > 0 and vendas > 0:
            roas = vendas / spend

        custo_conversa = 0.0
        if conversas > 0:
            custo_meta = extrair_acao(cost_per_action, tipos_conversas)
            custo_conversa = custo_meta if custo_meta > 0 else (spend / conversas)

        cpa_compra = (spend / pedidos) if pedidos > 0 else 0.0
        fadiga = (frequency >= 2.5 and ctr < 1.0)

        anuncios.append({
            "nome_anuncio": item.get("name", "Sem Nome"),
            "status": item.get("effective_status") or item.get("status"),
            "campanha": item.get("campaign", {}).get("name", "N/A"),
            "conjunto": item.get("adset", {}).get("name", "N/A"),
            "spend": spend,
            "frequency": frequency,
            "ctr": ctr,
            "cpm": cpm,
            "cpc": cpc,
            "cliques_link": cliques_link,
            "conversas": conversas,
            "custo_por_conversa": custo_conversa,
            "pedidos": pedidos,
            "vendas": vendas,
            "roas": roas,
            "cpa_compra": cpa_compra,
            "fadiga_saturacao": fadiga
        })

    anuncios.sort(key=lambda x: -x["spend"])
    return anuncios


def buscar_metricas_conta(account_id, token, date_preset="last_30d", since=None, until=None):
    """Busca insights (investimento, alcance, visitas, conversas, pedidos, vendas, ROAS) de uma conta de anúncio."""
    param_ins, param_camp_ins = obter_parametro_data(date_preset, since=since, until=until)
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

    campanhas = buscar_campanhas_conta(account_id, token, date_preset=date_preset, since=since, until=until)

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

    # Recalcula o Custo por Conversa da conta considerando APENAS campanhas com objetivo real de MENSAGEM
    if conversas_iniciadas > 0:
        camps_msg = [c for c in campanhas if c.get("is_mensagem") and c["conversas_iniciadas"] > 0]
        if camps_msg:
            investimento_msg = sum(c["spend"] for c in camps_msg)
            conversas_msg = sum(c["conversas_iniciadas"] for c in camps_msg)
            custo_por_conversa = investimento_msg / conversas_msg if conversas_msg > 0 else 0.0
        else:
            camps_sem_vendas = [c for c in campanhas if c["tipo_foco"] != "vendas" and c["conversas_iniciadas"] > 0 and not any(kw in (c["nome"] or "").lower() for kw in ["perfil", "[ig]", "instagram", "seguidores", "alcance", "awareness"])]
            if camps_sem_vendas:
                investimento_msg = sum(c["spend"] for c in camps_sem_vendas)
                conversas_msg = sum(c["conversas_iniciadas"] for c in camps_sem_vendas)
                custo_por_conversa = investimento_msg / conversas_msg if conversas_msg > 0 else 0.0
            else:
                custo_por_conversa = 0.0
    else:
        custo_por_conversa = 0.0

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
    "749845321489148",   # CHACARA BONS VENTOS
    "3005734976424838",  # Casa Durigan
    "1043217331876050"   # DOYA
}

EXCLUDED_ACCOUNT_IDS = {
    "1189618016437224"   # Conta Inativa/Bloqueada removida pelo usuário
}

def limpar_nome_conta(nome):
    if not nome:
        return "Sem Nome"
    nome_limpo = re.sub(r'^(CA\s*[-–—:]\s*)+', '', nome, flags=re.IGNORECASE).strip()
    return nome_limpo if nome_limpo else nome

from concurrent.futures import ThreadPoolExecutor

def processar_conta_individual(item_conta, token, date_preset, since, until):
    if item_conta["is_ativa"]:
        metricas, err = buscar_metricas_conta(item_conta["account_id"], token, date_preset=date_preset, since=since, until=until)
        if err:
            item_conta["erro"] = err
        else:
            item_conta["metricas"] = metricas
    else:
        item_conta["erro"] = f"Conta Inativa/Bloqueada (Código {item_conta['status_num']})"
    return item_conta

def obter_dados_estruturados(date_preset="last_30d", since=None, until=None):
    """
    Consolida todas as contas e métricas do Meta Ads organizadas para JSON (API/Dashboard).
    Utiliza ThreadPoolExecutor para buscar dados de múltiplas contas em paralelo.
    """
    load_dotenv(override=True)
    tokens = obter_tokens()
    if not tokens:
        return {"error": "Nenhum token encontrado no arquivo .env", "contas": [], "resumo": {}}

    contas_base = []
    contas_processadas = set()

    def _buscar_adaccounts_token(tok):
        u = f"{GRAPH_API_URL}/me/adaccounts?fields=name,account_id,account_status,currency,is_prepay_account,funding_source_details,balance&access_token={tok}"
        try:
            r = requests.get(u, timeout=12)
            if r.status_code == 200:
                return r.json().get("data", []), tok
        except Exception:
            pass
        return [], tok

    with ThreadPoolExecutor(max_workers=20) as executor:
        token_results = list(executor.map(_buscar_adaccounts_token, tokens.values()))

    for dados_contas, token in token_results:
        for conta in dados_contas:
            account_id = str(conta.get("account_id"))
            if account_id in contas_processadas or account_id in EXCLUDED_ACCOUNT_IDS:
                continue
            contas_processadas.add(account_id)

            nome_bruto = conta.get("name", "Sem Nome")
            nome_limpo = limpar_nome_conta(nome_bruto)
            gestor = "Davi" if account_id in DAVI_ACCOUNT_IDS else "Gabriel"
            status_num = conta.get("account_status")
            is_ativa = (status_num != 101)
            moeda = conta.get("currency", "BRL")
            simbolo_moeda = "R$" if moeda == "BRL" else f"{moeda} "

            is_prepay = conta.get("is_prepay_account", False)
            funding_details = conta.get("funding_source_details", {}) or {}
            balance_raw = conta.get("balance", "0")

            is_cartao = (not is_prepay) or (funding_details.get("type") == 1)

            saldo_restante = 0.0
            saldo_str = "Cartão"

            if not is_cartao:
                display_str = funding_details.get("display_string", "")
                match = re.search(r"R\$\s*([\d\.,]+)", display_str)
                if match:
                    val_str = match.group(1).replace(".", "").replace(",", ".")
                    try:
                        saldo_restante = float(val_str)
                        saldo_str = f"{simbolo_moeda} {formatar_moeda(saldo_restante)}"
                    except ValueError:
                        saldo_str = "Cartão"
                else:
                    try:
                        bal_val = float(balance_raw) / 100.0
                        saldo_restante = bal_val
                        saldo_str = f"{simbolo_moeda} {formatar_moeda(saldo_restante)}"
                    except (ValueError, TypeError):
                        saldo_str = "Cartão"

            nicho_info = obter_nicho_conta(nome_limpo)
            CONTA_TOKENS_CACHE[account_id] = token

            item_conta = {
                "account_id": account_id,
                "nome_original": nome_bruto,
                "nome": nome_limpo,
                "gestor": gestor,
                "nicho_info": nicho_info,
                "nicho": nicho_info.get("nicho", "GERAL"),
                "nicho_desc": nicho_info.get("descricao", ""),
                "status_num": status_num,
                "is_ativa": is_ativa,
                "moeda": moeda,
                "simbolo_moeda": simbolo_moeda,
                "is_cartao": is_cartao,
                "saldo_restante": saldo_restante,
                "saldo_str": saldo_str,
                "token": token,
                "metricas": None,
                "erro": None
            }
            contas_base.append(item_conta)

    contas = []
    resumo = {
        "total_contas": len(contas_base),
        "contas_ativas": 0,
        "contas_inativas": 0,
        "investimento_total": 0.0,
        "alcance_total": 0,
        "vendas_totais": 0.0,
        "pedidos_totais": 0,
        "conversas_totais": 0
    }

    # Busca métricas em paralelo com ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [
            executor.submit(processar_conta_individual, item, item["token"], date_preset, since, until)
            for item in contas_base
        ]
        for future in futures:
            try:
                item_processado = future.result()
                # Remove o token do objeto JSON final por segurança
                item_processado.pop("token", None)
                contas.append(item_processado)

                if item_processado["is_ativa"]:
                    resumo["contas_ativas"] += 1
                    m = item_processado.get("metricas")
                    if m:
                        resumo["investimento_total"] += m.get("spend", 0.0)
                        resumo["alcance_total"] += m.get("reach", 0)
                        resumo["vendas_totais"] += m.get("total_vendas", 0.0)
                        resumo["pedidos_totais"] += int(m.get("total_pedidos", 0))
                        resumo["conversas_totais"] += int(m.get("conversas_iniciadas", 0))
                else:
                    resumo["contas_inativas"] += 1
            except Exception as e:
                pass

    # Ordena contas em ordem alfabética por nome limpo
    contas.sort(key=lambda x: x["nome"].lower())

    return {
        "date_preset": date_preset,
        "since": since,
        "until": until,
        "resumo": resumo,
        "contas": contas
    }

def relatorio_meta_ads(date_preset="last_30d", since=None, until=None):
    dados = obter_dados_estruturados(date_preset=date_preset, since=since, until=until)
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


def identificar_contexto_pergunta(mensagem_usuario, account_id, contas_list):
    """
    Identifica de forma inteligente se a pergunta do parceiro é sobre:
    1. Multi-contas / Panorama da operação toda (se envolver saldo, geral, vazamento, escala, etc.).
    2. Uma conta específica citada diretamente no texto da mensagem.
    3. A conta atualmente selecionada na dashboard (se a pergunta não tiver escopo geral).
    """
    import re
    msg_clean = (mensagem_usuario or "").lower().strip()

    termos_multi = [
        "contas", "saldo", "saldos", "todas", "geral", "panorama", "operação", "operacao",
        "quais", "quem", "resumo", "visão geral", "visao geral", "vazamento", "vazamentos",
        "escala", "escalar", "pré-pago", "prepago", "cartão", "cartao", "risco", "fracas",
        "melhores", "piores", "sangrando", "torrando", "queimando", "clientes", "menor", "menos", "pouco"
    ]

    # 1. Se a mensagem contém palavras-chave de multi-contas ou saldos, prioriza a visão geral da operação
    if any(t in msg_clean for t in termos_multi):
        return None, True

    # 2. Verifica se alguma conta específica foi citada diretamente pelo nome no texto
    for c in contas_list:
        nome_c = c.get("nome", "").lower()
        palavras_nome = [
            w for w in re.split(r'[\s\-_]+', nome_c)
            if len(w) >= 4 and w not in ["conta", "interno", "gestor", "tráfego", "trafego", "para", "como", "sobre", "onde", "qual", "olha", "analisa"]
        ]
        if any(w in msg_clean for w in palavras_nome):
            return c, False  # Conta específica indicada no texto

    # 3. Se não tem indício de multi-contas e foi passado account_id da dashboard, usa a conta selecionada
    if account_id:
        conta_sel = next((c for c in contas_list if str(c.get("account_id")) == str(account_id)), None)
        if conta_sel:
            return conta_sel, False

    # 4. Caso contrário, multi-contas por padrão
    return None, True


def gerar_analise_ia_fallback(dados, mensagem, account_id=None):
    """
    Co-piloto e Auxiliar de Gestão de Tráfego interno de alta velocidade.
    Atua como parceiro de trincheira no Discord/WhatsApp: curto, provocativo, baseado em dados reais,
    sem relatórios burocráticos ou títulos padronizados.
    """
    if not dados or "contas" not in dados:
        return (
            "Cara, ainda tô sem os dados sincronizados aqui na dashboard. "
            "Dá um refresh na tela ou confere os tokens no .env pra eu puxar as métricas ao vivo da operação!"
        )

    msg_lower = (mensagem or "").lower().strip()
    resumo = dados.get("resumo", {})
    contas = dados.get("contas", [])
    contas_ativas = [c for c in contas if c.get("is_ativa") and c.get("metricas")]

    conta_encontrada, is_multi = identificar_contexto_pergunta(mensagem, account_id, contas)

    # 1. Cenário: Pergunta sobre Saldos / Contas com saldo baixo / Pré-pagas
    termos_saldo = ["saldo", "saldos", "recarga", "cartão", "cartao", "pré-pago", "prepago", "boleto", "pix", "crédito"]
    if any(t in msg_lower for t in termos_saldo) and not conta_encontrada:
        prepagas_criticas = []
        prepagas_ok = []
        cartao_cnt = 0

        for c in contas:
            is_cart = c.get("is_cartao", True)
            saldo_r = c.get("saldo_restante", 0.0)
            saldo_str = c.get("saldo_str", "Cartão")
            sp = (c.get("metricas") or {}).get("spend", 0.0)

            if is_cart or saldo_str == "Cartão":
                cartao_cnt += 1
            else:
                item = {
                    "nome": c.get("nome"),
                    "saldo": saldo_str,
                    "saldo_num": saldo_r,
                    "spend": sp
                }
                if saldo_r < 80.0:
                    prepagas_criticas.append(item)
                else:
                    prepagas_ok.append(item)

        # Ordena: contas queimando verba com saldo zerado/baixo primeiro
        prepagas_criticas.sort(key=lambda x: (0 if x["spend"] > 0 else 1, x["saldo_num"]))

        if prepagas_criticas:
            linhas = [
                "Davi, dei um confere geral em todas as 46 contas da nossa operação. As seguintes contas pré-pagas estão no osso ou zeradas e precisam de recarga urgente pra não travar no leilão e resetar a fase de aprendizado do pixel:\n"
            ]
            for it in prepagas_criticas:
                if it["spend"] > 0 or it["saldo_num"] > 0:
                    alerta_gasto = f" (já consumiu R$ {formatar_moeda(it['spend'])} no período)" if it['spend'] > 0 else ""
                    linhas.append(f"• **{it['nome']}:** Saldo atual em **{it['saldo']}**{alerta_gasto}")

            linhas.append(f"\nO restante da operação tá rodando seguro ({cartao_cnt} contas direto no cartão de crédito e outras {len(prepagas_ok)} pré-pagas abastecidas).")
            linhas.append(f"Bora avisar os clientes dessas zeradas hoje pra faturar esse Pix/boleto antes que o Meta corte a entrega?")
            return "\n".join(linhas)
        else:
            exemplo_ok_txt = f" (ex: {prepagas_ok[0]['nome']} com {prepagas_ok[0]['saldo']})" if prepagas_ok else ""
            return (
                f"Davi, olhei os saldos de ponta a ponta e a operação tá tranquila: "
                f"{cartao_cnt} contas tão direto no cartão de crédito e as pré-pagas tão abastecidas{exemplo_ok_txt}. "
                f"Nenhuma conta em risco iminente de pausar por falta de verba hoje.\n\n"
                f"Bora focar em otimizar criativo ou escalar alguma conta específica?"
            )

    # 2. Cenário: Pergunta sobre Vazamento de Verba / Contas Fracas / Sangrias
    termos_vazamento = ["fraca", "fracas", "ruim", "ruins", "vazamento", "vazamentos", "sangrando", "torrando", "queimando", "pior", "piores"]
    if any(t in msg_lower for t in termos_vazamento) and not conta_encontrada:
        vazamentos = []
        for c in contas_ativas:
            m = c.get("metricas") or {}
            sp = m.get("spend", 0.0)
            c_roas = m.get("roas", 0.0)
            c_conv = m.get("conversas_iniciadas", 0)
            c_cpa = m.get("custo_por_conversa", 0.0)
            c_foco = m.get("tipo_foco", "mensagens")
            c_ctr = m.get("ctr", 0.0)
            c_freq = m.get("frequency", 1.0)
            nicho = c.get("nicho", "GERAL")

            if sp > 40.0:
                if c_foco == "vendas" and c_roas < 1.1:
                    vazamentos.append({
                        "nome": c.get("nome"),
                        "nicho": nicho,
                        "motivo": f"investiu **R$ {formatar_moeda(sp)}** com ROAS de **{c_roas:.2f}x** (margem negativa)",
                        "diagnostico": f"CTR em {c_ctr:.2f}% e frequência {c_freq:.2f}. Anúncios não estão convertendo no carrinho."
                    })
                elif c_foco == "mensagens" and c_conv == 0:
                    vazamentos.append({
                        "nome": c.get("nome"),
                        "nicho": nicho,
                        "motivo": f"torrou **R$ {formatar_moeda(sp)}** com **ZERO conversas** geradas no zap",
                        "diagnostico": f"Houve cliques mas 0 mensagens iniciadas. Vazamento no pós-clique ou número de zap com erro."
                    })
                elif c_foco == "mensagens" and c_cpa > 10.0 and nicho == "DELIVERY_FOOD":
                    vazamentos.append({
                        "nome": c.get("nome"),
                        "nicho": nicho,
                        "motivo": f"CPA de mensagem explodiu para **R$ {formatar_moeda(c_cpa)}** no delivery",
                        "diagnostico": f"Frequência bateu {c_freq:.2f} e CTR caiu pra {c_ctr:.2f}%. O criativo saturou na região."
                    })

        if vazamentos:
            linhas = ["Mano, separei os pontos onde a nossa verba tá sangrando sem gerar retorno proporcional:\n"]
            for v in vazamentos[:3]:
                linhas.append(f"• **{v['nome']} ({v['nicho']}):** {v['motivo']}. {v['diagnostico']}")
            linhas.append(f"\nBora pausar os criativos saturados de **{vazamentos[0]['nome']}** agora e rodar teste de novo gancho?")
            return "\n".join(linhas)

    # 3. Cenário: Pergunta sobre Escala / Melhores Contas / Oportunidades
    termos_escala = ["escala", "escalar", "melhor", "melhores", "roi", "roas", "top", "ganhando", "campeã", "campea", "acelerar"]
    if any(t in msg_lower for t in termos_escala) and not conta_encontrada:
        escalas = []
        for c in contas_ativas:
            m = c.get("metricas") or {}
            sp = m.get("spend", 0.0)
            c_roas = m.get("roas", 0.0)
            c_conv = m.get("conversas_iniciadas", 0)
            c_cpa = m.get("custo_por_conversa", 0.0)
            c_foco = m.get("tipo_foco", "mensagens")
            c_freq = m.get("frequency", 1.0)
            nicho = c.get("nicho", "GERAL")

            if sp > 30.0:
                if c_foco == "vendas" and c_roas >= 2.5:
                    escalas.append({
                        "nome": c.get("nome"),
                        "nicho": nicho,
                        "resultado": f"ROAS de **{c_roas:.2f}x** (R$ {formatar_moeda(m.get('total_vendas', 0))} em vendas)",
                        "freq": c_freq
                    })
                elif c_foco == "mensagens" and c_conv >= 8 and c_cpa <= 4.0:
                    escalas.append({
                        "nome": c.get("nome"),
                        "nicho": nicho,
                        "resultado": f"**{c_conv} conversas** com CPA de **R$ {formatar_moeda(c_cpa)}**",
                        "freq": c_freq
                    })

        if escalas:
            linhas = ["Cara, essas frentes tão com validação máxima e pedindo mais orçamento pra tracionar:\n"]
            for esc in escalas[:3]:
                linhas.append(f"• **{esc['nome']} ({esc['nicho']}):** Entregando {esc['resultado']}. Frequência ainda em {esc['freq']:.2f} (tem muita lenha pra queimar no público).")
            linhas.append(f"\nSugiro subir 15% a 20% no budget diário de **{escalas[0]['nome']}** hoje. Bora fazer essa escala gradual?")
            return "\n".join(linhas)

    # 4. Cenário: Análise de Conta Específica
    if conta_encontrada:
        c = conta_encontrada
        m = c.get("metricas") or {}
        nome_conta = c.get("nome", "Conta")
        nicho_info = c.get("nicho_info") or {}
        nicho_nome = nicho_info.get("nicho", "GERAL")
        moeda = c.get("simbolo_moeda", "R$")
        spend = m.get("spend", 0.0)
        cpm = m.get("cpm", 0.0)
        cpc = m.get("cpc", 0.0)
        ctr = m.get("ctr", 0.0)
        freq = m.get("frequency", 1.0)
        cliques = m.get("cliques_link", 0)
        conversas = m.get("conversas_iniciadas", 0)
        cpa = m.get("custo_por_conversa", 0.0)
        roas = m.get("roas", 0.0)
        pedidos = m.get("total_pedidos", 0)
        vendas = m.get("total_vendas", 0.0)
        foco = m.get("tipo_foco", "mensagens")
        saldo_str = c.get("saldo_str", "Cartão")

        if spend == 0:
            return (
                f"Cara, dei um confere na conta **{nome_conta}** ({nicho_nome}) e ela tá com **R$ 0,00 investidos** nesse filtro de data. "
                f"Os anúncios tão ativos no Gerenciador ou foram pausados? "
                f"Se a conta for pré-paga, confere se o saldo tá abastecido ({saldo_str}). "
                f"Quer que eu puxe os dados de outro período ou de outra conta?"
            )

        linhas = [f"Cara, olhei a **{nome_conta}** ({nicho_nome}) a fundo:"]
        if foco == "vendas":
            linhas.append(f"Rodamos com **{moeda} {formatar_moeda(spend)}** de spend, gerando **{pedidos} pedidos** ({moeda} {formatar_moeda(vendas)}) com **ROAS de {roas:.2f}x**.")
        else:
            linhas.append(f"Gastamos **{moeda} {formatar_moeda(spend)}**, gerando **{conversas} conversas no zap** a um CPA médio de **{moeda} {formatar_moeda(cpa)}**.")

        causas = []
        if freq >= 2.3 and ctr < 1.0:
            causas.append(f"Frequência em **{freq:.2f}** e CTR despencou pra **{ctr:.2f}%** (fadiga de criativo).")
        elif ctr >= 1.8:
            causas.append(f"CTR forte de **{ctr:.2f}%** (gancho segurando o leilão).")

        if cpm > 45.0:
            causas.append(f"CPM elevado (**{moeda} {formatar_moeda(cpm)}**), leilão disputado.")
        elif cpm < 18.0 and cpm > 0:
            causas.append(f"CPM barato (**{moeda} {formatar_moeda(cpm)}**), entrega favorável.")

        if cliques > 20 and conversas == 0 and foco == "mensagens":
            causas.append(f"**{cliques} cliques** e 0 conversas (gargalo no pós-clique / página).")

        if causas:
            linhas.append("• " + " | ".join(causas))

        if freq >= 2.3 or ctr < 1.0:
            linhas.append(f"\nMeu veredito: bora subir 2 variações novas de criativo com outro gancho pra rejuvenescer essa campanha? O que acha?")
        elif foco == "vendas" and roas >= 2.5:
            linhas.append(f"\nMeu veredito: o retorno tá excelente. Bora subir 20% no budget diário pra tracionar mais vendas?")
        elif foco == "mensagens" and conversas >= 5 and cpa <= 4.0:
            linhas.append(f"\nMeu veredito: campanha validada e CPA saudável. Bora aumentar a verba diária aos poucos?")
        else:
            linhas.append(f"\nQuer focar em ajustar os criativos dessa conta ou olhar os conjuntos específicos?")

        return "\n".join(linhas)

    # 5. Cenário: Visão Geral da Operação / Saudação / Default
    tot_inv = resumo.get("investimento_total", 0.0)
    vendas_tot = resumo.get("vendas_totais", 0.0)
    conv_tot = resumo.get("conversas_totais", 0)
    ativas_cnt = resumo.get("contas_ativas", len(contas_ativas))
    roas_geral = (vendas_tot / tot_inv) if tot_inv > 0 and vendas_tot > 0 else 0.0

    return (
        f"Fala, parceiro! Dei uma varrida completa na nossa operação:\n\n"
        f"Tamo com **{ativas_cnt} contas ativas** rodando no período, movimentando um total de **R$ {formatar_moeda(tot_inv)}**. "
        f"Já geramos **{formatar_numero(conv_tot)} conversas no WhatsApp** e **R$ {formatar_moeda(vendas_tot)} em vendas** (ROAS geral de **{roas_geral:.2f}x**).\n\n"
        f"Me diz aí: quer dar prioridade em conferir os **saldos das contas pré-pagas**, ver onde tem **verba vazando**, ou achar frentes pra **escalar verba** hoje?"
    )


def analisar_dados_ia(dados, mensagem_usuario, account_id=None):
    """
    Co-piloto e Auxiliar de Gestão de Tráfego do Davi no Meta Ads.
    Conecta via Gemini (usando GEMINI_API_KEY do .env) com instrução de parceiro direto de Discord/WhatsApp.
    Se a API remota oscilar, executa o motor analítico de fallback instantâneo.
    """
    import json

    if not dados:
        dados = {}

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return gerar_analise_ia_fallback(dados, mensagem_usuario, account_id=account_id)

    periodo_info = {
        "date_preset": dados.get("date_preset"),
        "since": dados.get("since"),
        "until": dados.get("until")
    }

    contas_list = dados.get("contas", []) if dados else []
    conta_encontrada, is_multi = identificar_contexto_pergunta(mensagem_usuario, account_id, contas_list)

    # 1. Mapeia e prioriza saldos pré-pagos de TODAS as contas para que a IA nunca fique sem os dados
    saldos_criticos = []
    saldos_ok = []
    contas_cartao = []

    for c in contas_list:
        is_cart = c.get("is_cartao", True)
        s_str = c.get("saldo_str", "Cartão")
        s_num = c.get("saldo_restante", 0.0)
        sp = (c.get("metricas") or {}).get("spend", 0.0)
        nm = c.get("nome", "Sem Nome")

        if is_cart or s_str == "Cartão":
            contas_cartao.append(nm)
        else:
            status_desc = "ZERADA (R$ 0,00)" if s_num <= 0.01 else ("CRÍTICO (< R$ 80)" if s_num < 80 else "OK")
            if sp > 0:
                status_desc += " [ANÚNCIO ATIVO]"
            item_saldo = {
                "conta": nm,
                "saldo": s_str,
                "saldo_num": s_num,
                "spend_periodo": sp,
                "status": status_desc
            }
            if s_num < 80:
                saldos_criticos.append(item_saldo)
            else:
                saldos_ok.append(item_saldo)

    # Ordena saldos críticos: quem tem spend ativo e saldo zerado fica no topo absoluto
    saldos_criticos.sort(key=lambda x: (0 if (x["spend_periodo"] > 0 and x["saldo_num"] <= 0.05) else (1 if x["saldo_num"] <= 0.05 else 2), x["saldo_num"]))

    # Resumo consolidado de todas as contas ativas
    contas_ativas_resumo = []
    for c in contas_list:
        if c.get("is_ativa") and c.get("metricas"):
            m = c.get("metricas") or {}
            contas_ativas_resumo.append({
                "nome": c.get("nome"),
                "nicho": c.get("nicho", "GERAL"),
                "metodo_pagamento": "Cartão" if c.get("is_cartao", True) else "Pré-pago",
                "saldo": c.get("saldo_str"),
                "spend": m.get("spend", 0.0),
                "conversas": m.get("conversas_iniciadas", 0),
                "cpa": m.get("custo_por_conversa", 0.0),
                "vendas": m.get("total_vendas", 0.0),
                "roas": m.get("roas", 0.0)
            })

    # Dados dinâmicos completos (SEMPRE contém a visão completa de todas as 46 contas da operação)
    dados_dinamicos = {
        "periodo": periodo_info,
        "resumo_geral_operacao": dados.get("resumo", {}),
        "total_contas_operacao": len(contas_list),
        "saldos_prepagos_criticos": saldos_criticos,
        "saldos_prepagos_abastecidos": [f"{s['conta']}: {s['saldo']}" for s in saldos_ok[:6]],
        "contas_no_cartao_de_credito_qtd": len(contas_cartao),
        "todas_contas_resumo": contas_ativas_resumo
    }

    # Se há uma conta específica em tela ou citada pelo usuário, injeta os detalhes de anúncios e criativos dela
    if conta_encontrada:
        c = conta_encontrada
        m = c.get("metricas") or {}
        aid = str(c.get("account_id"))
        token = CONTA_TOKENS_CACHE.get(aid) or c.get("token")
        anuncios_criativos = []
        if token:
            try:
                anuncios_criativos = buscar_anuncios_conta(
                    aid, token,
                    date_preset=periodo_info.get("date_preset", "last_30d"),
                    since=periodo_info.get("since"),
                    until=periodo_info.get("until"),
                    limit=10
                )
            except Exception:
                anuncios_criativos = []

        dados_dinamicos["conta_em_foco"] = {
            "account_id": aid,
            "nome": c.get("nome"),
            "status": "Ativa" if c.get("is_ativa") else f"Inativa ({c.get('erro')})",
            "metodo_pagamento": "Cartão" if c.get("is_cartao", True) else "Pré-pago",
            "saldo_restante": c.get("saldo_str"),
            "nicho": c.get("nicho_info", {}).get("nicho", "GERAL"),
            "metricas": {
                "spend": m.get("spend", 0.0),
                "cpm": m.get("cpm", 0.0),
                "cpc": m.get("cpc", 0.0),
                "ctr_link": m.get("ctr", 0.0),
                "frequencia": m.get("frequency", 1.0),
                "conversas": m.get("conversas_iniciadas", 0),
                "cpa_conversa": m.get("custo_por_conversa", 0.0),
                "vendas": m.get("total_vendas", 0.0),
                "roas": m.get("roas", 0.0)
            },
            "campanhas": [
                {
                    "nome": camp.get("nome"),
                    "spend": camp.get("spend", 0.0),
                    "cpm": camp.get("cpm", 0.0),
                    "cpc": camp.get("cpc", 0.0),
                    "ctr": camp.get("ctr", 0.0),
                    "conversas": camp.get("conversas_iniciadas", 0),
                    "cpa": camp.get("custo_por_conversa", 0.0),
                    "vendas": camp.get("total_vendas", 0.0),
                    "roas": camp.get("roas", 0.0)
                }
                for camp in (m.get("campanhas") or [])
            ],
            "top_criativos": anuncios_criativos
        }

    json_dados_str = json.dumps(dados_dinamicos, ensure_ascii=False, indent=2)

    system_instruction_text = (
        "VOCÊ É O CO-PILOTO E AUXILIAR DE GESTÃO DE TRÁFEGO DO DAVI (SEU PARCEIRO NO DISCORD/WHATSAPP).\n"
        "O SEU PARCEIRO SE CHAMA DAVI. NUNCA, SOB HIPÓTESE ALGUMA, CHAME ELE DE GABRIEL.\n\n"
        "REGRA DE OURO - MÁXIMO DE 6 A 10 LINHAS (ZERO ENROLAÇÃO E ZERO REDAÇÃO):\n"
        "- O Davi ODEIA respostas longas, redações, e relatórios formais. Se você mandar mais de 10 linhas ou fizer relatório, você falhou.\n"
        "- Fale como numa call rápida no Discord ou mensagem de áudio/texto no WhatsApp: parceiro de trincheira, papo reto, direto ao ponto.\n"
        "- PROIBIDO títulos formais de consultoria (ex: NADA de 'Ação imediata:', 'Recomendação tática:', 'Triage:', 'Estancamento:').\n"
        "- PROIBIDO listas longas de lição de casa numeradas (1, 2, 3).\n"
        "- VOCÊ É O CO-PILOTO DELE: Nunca dê ordens arrogantes ('minha decisão de comando', 'faça isso'). Jogue junto com ele.\n"
        "- NUNCA reclame de dados e NUNCA peça pro Davi mandar dump ou rodar scripts. Todos os dados das 46 contas já estão no JSON.\n\n"
        "COMO RESPONDER:\n"
        "1. RESPONDA PRIMEIRO E DIRETO O QUE ELE PERGUNTOU:\n"
        "   - Se perguntou de SALDO: liste DIRETO as contas pré-pagas que estão ZERADAS (R$ 0,00) ou com saldo crítico com anúncio rodando. Sem enrolar!\n"
        "   - Se perguntou de UMA CONTA: fale do CPA, CTR, criativos ou escala dessa conta em poucas linhas.\n"
        "   - Se perguntou de escala/vazamento: aponte as contas principais direto com números reais.\n"
        "2. FECHAMENTO:\n"
        "   - Termine com UMA pergunta provocativa curta passando a bola pro Davi tomar a decisão."
    )

    contexto_nome = conta_encontrada['nome'] if conta_encontrada else 'Toda a Operação (Multi-Contas)'
    prompt_usuario = (
        f"DADOS AO VIVO DA OPERAÇÃO META ADS (JSON):\n"
        f"```json\n{json_dados_str}\n```\n\n"
        f"CONTEXTO: {contexto_nome}\n"
        f"MENSAGEM DO DAVI: {mensagem_usuario}\n\n"
        f"Responda ao Davi em 6 a 10 linhas no máximo, direto ao ponto no estilo WhatsApp parceiro."
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_instruction_text}]
        },
        "contents": [
            {
                "parts": [{"text": prompt_usuario}]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 280
        }
    }

    modelos_candidatos = [
        "gemini-3.5-flash-lite",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3.8-flash"
    ]

    for modelo in modelos_candidatos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                resp_json = res.json()
                candidates = resp_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts if not p.get("thought", False)).strip()
                    if not text and parts:
                        text = parts[-1].get("text", "").strip()
                    if text:
                        return text
            elif res.status_code in [429, 503]:
                continue
            elif res.status_code == 404:
                continue
        except Exception as e:
            print(f"⚠️ Erro chamando modelo Gemini {modelo}: {e}")
            continue

    return gerar_analise_ia_fallback(dados, mensagem_usuario, account_id=account_id)



if __name__ == "__main__":
    print("\n📡 Buscando dados e métricas direto do Meta Ads...\n")
    resultado = relatorio_meta_ads(date_preset="last_30d")
    print("🚀 === RELATÓRIO DE MÉTRICAS META ADS === 🚀\n")
    print(resultado)