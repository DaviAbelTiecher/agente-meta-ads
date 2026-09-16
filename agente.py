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
            "roas": roas
        })

    campanhas.sort(key=lambda x: -x["spend"])
    return campanhas

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

    for token in tokens.values():
        url = f"{GRAPH_API_URL}/me/adaccounts?fields=name,account_id,account_status,currency,is_prepay_account,funding_source_details,balance&access_token={token}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                continue
            dados_contas = res.json().get("data", [])
        except Exception:
            continue

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

            item_conta = {
                "account_id": account_id,
                "nome_original": nome_bruto,
                "nome": nome_limpo,
                "gestor": gestor,
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


def gerar_analise_ia_fallback(dados, mensagem, account_id=None):
    """
    Motor analítico interno de fallback para responder perguntas sobre o Dashboard de Meta Ads.
    Estrutura a resposta obrigatoriamente nos 3 blocos visuais (🚨, 📊, 💡).
    """
    if not dados or "contas" not in dados:
        return (
            "🚨 **Alerta / Diagnóstico Principal**\n"
            "Não foi possível obter os dados das contas no momento.\n\n"
            "📊 **Métricas Críticas**\n"
            "Sem métricas disponíveis.\n\n"
            "💡 **Recomendação Prática**\n"
            "Por favor, sincronize novamente a API ou atualize a página para recarregar o dashboard."
        )

    msg_lower = mensagem.lower().strip()
    resumo = dados.get("resumo", {})
    contas = dados.get("contas", [])
    contas_ativas = [c for c in contas if c.get("is_ativa") and c.get("metricas")]

    # Busca especificamente a conta informada via account_id ou pelo texto da mensagem
    conta_encontrada = None
    if account_id:
        conta_encontrada = next((c for c in contas if str(c.get("account_id")) == str(account_id)), None)

    if not conta_encontrada:
        for c in contas:
            nome_c = c.get("nome", "").lower()
            nome_orig = c.get("nome_original", "").lower()
            termos_mensagem = [
                w for w in msg_lower.split() 
                if len(w) > 3 and w not in ["métricas", "metrica", "resultado", "resultados", "desempenho", "conta", "contas", "passa", "quais", "quaisquer", "como"]
            ]
            if any(t in nome_c or t in nome_orig for t in termos_mensagem):
                conta_encontrada = c
                break

    if conta_encontrada:
        c = conta_encontrada
        m = c.get("metricas") or {}
        moeda = c.get("simbolo_moeda", "R$")
        spend = m.get("spend", 0.0)
        ctr = m.get("ctr", 0.0)
        cpc = m.get("cpc", 0.0)
        cpm = m.get("cpm", 0.0)
        roas = m.get("roas", 0.0)
        vendas = m.get("total_vendas", 0.0)
        pedidos = m.get("total_pedidos", 0)
        conversas = m.get("conversas_iniciadas", 0)
        cpa = m.get("custo_por_conversa", 0.0)
        foco = m.get("tipo_foco", "mensagens")

        diag_alertas = []
        if ctr > 0 and ctr < 1.0:
            diag_alertas.append(f"⚠️ CTR abaixo de 1% ({ctr:.2f}%) indica fadiga nos criativos ou baixo engajamento do público.")
        if foco == "vendas" and spend > 50 and roas == 0:
            diag_alertas.append(f"🚨 ROAS Zerado ({roas:.2f}x) com investimento de {moeda} {formatar_moeda(spend)}. Nenhuma venda registrada.")
        if foco == "mensagens" and spend > 30 and conversas == 0:
            diag_alertas.append(f"🚨 Nenhuma conversa iniciada apesar do investimento de {moeda} {formatar_moeda(spend)}.")

        diagnostico = " ".join(diag_alertas) if diag_alertas else f"A conta {c['nome']} está operando normalmente com foco em {'Vendas' if foco == 'vendas' else 'Mensagens'}."

        metricas_txt = [
            f"• Conta: {c['nome']} (ID: act_{c['account_id']})",
            f"• Investimento Total: {moeda} {formatar_moeda(spend)}",
            f"• CTR: {ctr:.2f}% | CPC: {moeda} {formatar_moeda(cpc)} | CPM: {moeda} {formatar_moeda(cpm)}"
        ]
        if foco == "vendas":
            metricas_txt.append(f"• Vendas Totais: {moeda} {formatar_moeda(vendas)} ({pedidos} pedidos)")
            metricas_txt.append(f"• ROAS Geral da Conta: {roas:.2f}x".replace(".", ","))
        else:
            metricas_txt.append(f"• Conversas Iniciadas: {formatar_numero(conversas)}")
            metricas_txt.append(f"• Custo por Conversa (CPA): {moeda} {formatar_moeda(cpa)}")

        recom_txt = []
        if ctr < 1.0 and ctr > 0:
            recom_txt.append("• Teste novas variações de criativos (vídeos curtos ou novas imagens) para elevar o CTR acima de 1,5%.")
        if foco == "vendas" and roas == 0:
            recom_txt.append("• Revise o funil de vendas, checkout e precificação das campanhas de e-commerce.")
        if foco == "mensagens" and conversas == 0:
            recom_txt.append("• Verifique o link do WhatsApp/Direct e os botões de chamada para ação (CTA) dos anúncios.")
        if not recom_txt:
            recom_txt.append("• Mantenha a otimização contínua das campanhas e acompanhe a Frequência e o CTR diariamente.")

        return (
            f"🚨 **Alerta / Diagnóstico Principal**\n{diagnostico}\n\n"
            f"📊 **Métricas Críticas**\n" + "\n".join(metricas_txt) + "\n\n"
            f"💡 **Recomendação Prática**\n" + "\n".join(recom_txt)
        )

    # Diagnóstico Geral
    tot_inv = resumo.get("investimento_total", 0.0)
    vendas_tot = resumo.get("vendas_totais", 0.0)
    pedidos_tot = resumo.get("pedidos_totais", 0)
    conv_tot = resumo.get("conversas_totais", 0)
    tot_contas = resumo.get("total_contas", len(contas))
    ativas_cnt = resumo.get("contas_ativas", len(contas_ativas))
    roas_geral = (vendas_tot / tot_inv) if tot_inv > 0 and vendas_tot > 0 else 0.0

    return (
        f"🚨 **Alerta / Diagnóstico Principal**\n"
        f"Análise consolidada do dashboard ({ativas_cnt} contas ativas de {tot_contas} monitoradas). "
        f"{'Desempenho de vendas ativo.' if vendas_tot > 0 else 'Foco principal em geração de mensagens e captação de clientes.'}\n\n"
        f"📊 **Métricas Críticas**\n"
        f"• Investimento Total no Período: R$ {formatar_moeda(tot_inv)}\n"
        f"• Vendas Totais: R$ {formatar_moeda(vendas_tot)} ({pedidos_tot} pedidos | ROAS Médio: {roas_geral:.2f}x)\n"
        f"• Conversas Totais no WhatsApp: {formatar_numero(conv_tot)}\n\n"
        f"💡 **Recomendação Prática**\n"
        f"• Selecione uma conta específica na barra lateral da dashboard para obter diagnósticos cirúrgicos de CTR, CPC, CPA e ROAS por campanha."
    )


def analisar_dados_ia(dados, mensagem_usuario, account_id=None):
    """
    Processa a mensagem do usuário utilizando a API do Gemini com a persona de Gestor de Tráfego Sênior
    e Especialista em Data Analytics. Injeta dados dinâmicos em JSON da conta selecionada e do período,
    com formato de resposta obrigatório em 3 blocos visuais e temperature entre 0.5 e 0.7 (0.6).
    """
    import json

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return gerar_analise_ia_fallback(dados, mensagem_usuario, account_id=account_id)

    # 1. Estruturação dos Dados Dinâmicos em JSON
    dados_dinamicos = {
        "periodo": {
            "date_preset": dados.get("date_preset"),
            "since": dados.get("since"),
            "until": dados.get("until")
        },
        "resumo_geral": dados.get("resumo", {}),
        "conta_selecionada": None,
        "contas": []
    }

    conta_selecionada_obj = None
    contas_list = dados.get("contas", []) if dados else []

    for c in contas_list:
        m = c.get("metricas") or {}
        nicho_info = c.get("nicho_info", {})

        c_data = {
            "account_id": c.get("account_id"),
            "nome": c.get("nome"),
            "gestor": c.get("gestor"),
            "status_conta": "Ativa" if c.get("is_ativa") else f"Inativa ({c.get('erro')})",
            "is_ativa": c.get("is_ativa"),
            "moeda": c.get("moeda", "BRL"),
            "saldo_restante": c.get("saldo_str"),
            "nicho": nicho_info.get("nicho", "GERAL"),
            "investimento_total": m.get("spend", 0.0),
            "vendas_totais": m.get("total_vendas", 0.0),
            "pedidos_totais": m.get("total_pedidos", 0),
            "conversas_totais": m.get("conversas_iniciadas", 0),
            "custo_por_conversa": m.get("custo_por_conversa", 0.0),
            "reach": m.get("reach", 0),
            "impressions": m.get("impressions", 0),
            "ctr": m.get("ctr", 0.0),
            "cpc": m.get("cpc", 0.0),
            "cpm": m.get("cpm", 0.0),
            "roas": m.get("roas", 0.0),
            "visitas_perfil": m.get("visitas_perfil", 0),
            "leads": m.get("leads", 0),
            "foco_principal": m.get("tipo_foco", "mensagens"),
            "campanhas": []
        }

        for camp in m.get("campanhas", []):
            c_data["campanhas"].append({
                "nome": camp.get("nome"),
                "status": camp.get("status"),
                "objective": camp.get("objective"),
                "foco": camp.get("tipo_foco"),
                "spend": camp.get("spend", 0.0),
                "reach": camp.get("reach", 0),
                "impressions": camp.get("impressions", 0),
                "ctr": camp.get("ctr", 0.0),
                "cpc": camp.get("cpc", 0.0),
                "cpm": camp.get("cpm", 0.0),
                "cliques_link": camp.get("cliques_link", 0),
                "conversas": camp.get("conversas_iniciadas", 0),
                "custo_por_conversa": camp.get("custo_por_conversa", 0.0),
                "pedidos": camp.get("total_pedidos", 0),
                "vendas": camp.get("total_vendas", 0.0),
                "roas": camp.get("roas", 0.0),
                "visitas_perfil": camp.get("visitas_perfil", 0),
                "leads": camp.get("leads", 0)
            })

        dados_dinamicos["contas"].append(c_data)

        if account_id and str(c.get("account_id")) == str(account_id):
            conta_selecionada_obj = c_data

    if conta_selecionada_obj:
        dados_dinamicos["conta_selecionada"] = conta_selecionada_obj

    json_dados_str = json.dumps(dados_dinamicos, ensure_ascii=False, indent=2)

    # 2. System Prompt com Persona, Diretrizes e Formato Obrigatório
    system_instruction_text = (
        "Você é um Gestor de Tráfego Sênior e Especialista em Data Analytics (focado em ROAS, CPA e otimização de campanhas de Meta Ads).\n"
        "Sua função é realizar diagnósticos altamente analíticos, perspicazes e práticos cruzando as métricas da dashboard.\n\n"
        "DIRETRIZES DE ANÁLISE:\n"
        "1. Cruzar métricas de CTR: Alerte imediatamente se o CTR estiver abaixo de 1% (alerta crítico de criativo desgastado ou público sem fit).\n"
        "2. Variações de CPC e CPM: Analise se o custo por clique (CPC) ou por mil impressões (CPM) está desproporcional.\n"
        "3. Desvios de CPA: Avalie o Custo por Aquisição / Custo por conversa em relação ao foco da conta.\n"
        "4. ROAS Zerado com Gasto Alto: Identifique e alerte sobre campanhas de vendas com investimento alto e ROAS 0.\n"
        "5. Considerar objetivo da campanha e nicho do cliente sem usar regras estáticas simplistas.\n\n"
        "FORMATO DE RESPOSTA OBRIGATÓRIO:\n"
        "Você DEVE SEMPRE estruturar a resposta estritamente utilizando os 3 blocos visuais abaixo:\n\n"
        "🚨 **Alerta / Diagnóstico Principal**\n"
        "[Apresente o diagnóstico principal identificando problemas críticos (CTR < 1%, ROAS zerado, CPA alto, variações de CPM/CPC) ou destacando a boa performance.]\n\n"
        "📊 **Métricas Críticas**\n"
        "[Liste os números exatos extraídos dos dados em JSON: Spend, CTR, CPC, CPM, CPA, ROAS, Vendas, Conversas, etc.]\n\n"
        "💡 **Recomendação Prática**\n"
        "[Dê sugestões diretas e acionáveis: trocar criativo, pausar campanha fraca, reajustar público, otimizar orçamento.]"
    )

    nome_conta_sel = conta_selecionada_obj['nome'] if conta_selecionada_obj else 'Nenhuma específica selecionada (Visão Geral)'
    prompt_usuario = (
        f"DADOS REAIS DA DASHBOARD META ADS (JSON):\n"
        f"```json\n{json_dados_str}\n```\n\n"
        f"CONTA ATUALMENTE SELECIONADA NA DASHBOARD: {nome_conta_sel}\n\n"
        f"PERGUNTA DO USUÁRIO: {mensagem_usuario}\n\n"
        f"Responda ao usuário obrigatoriamente estruturado nos 3 blocos visuais: 🚨 Alerta / Diagnóstico Principal, 📊 Métricas Críticas e 💡 Recomendação Prática."
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
            "temperature": 0.6
        }
    }

    modelos_candidatos = [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest"
    ]

    for modelo in modelos_candidatos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, timeout=25)
            if res.status_code == 200:
                resp_json = res.json()
                candidates = resp_json.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if text:
                        return text.strip()
            else:
                print(f"⚠️ Gemini ({modelo}) retornou código {res.status_code}: {res.text[:100]}")
        except Exception as e:
            print(f"⚠️ Erro ao conectar com Gemini ({modelo}): {e}")

    return gerar_analise_ia_fallback(dados, mensagem_usuario, account_id=account_id)


if __name__ == "__main__":
    print("\n📡 Buscando dados e métricas direto do Meta Ads...\n")
    resultado = relatorio_meta_ads(date_preset="last_30d")
    print("🚀 === RELATÓRIO DE MÉTRICAS META ADS === 🚀\n")
    print(resultado)