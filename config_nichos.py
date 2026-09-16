"""
Mapeamento de Nichos de Mercado para Contas do Meta Ads.
Permite personalizar a avaliação da IA (Gemini e Fallback) reduzindo falsos positivos.
"""

MAPEAMENTO_NICHOS = {
    "acheiemsc": {
        "nicho": "INTERNO",
        "descricao": "conta interna, raramente usada"
    },
    "Anfitrion": {
        "nicho": "ALTO_TICKET",
        "descricao": "venda de alto ticket R$ 3k+, CPL de R$ 60-70 é normal"
    },
    "Antonieta Pizzaria": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "pizzaria estabelecida"
    },
    "BARRA BONITA": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "Boca do Monte": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria e xis"
    },
    "BOKAS CHAPECÓ": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "restaurante"
    },
    "CABANA ALMA MONTANHA": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "CABANA FAZENDA RURAL": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "Cabana Fazenda santa Ines": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "Cabana Paraíso Natural": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "CABANA SAFIRA": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "CANTINA BORDIGNON": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "restaurante/pizzaria"
    },
    "CANTINA ITA": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "restaurante"
    },
    "Casa Durigan": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "DICAS DO ACHEI": {
        "nicho": "INTERNO",
        "descricao": "conta interna, raramente usada"
    },
    "DOYA": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "padaria"
    },
    "FOCA'S BURGER": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "FOCAS JOINVILLE": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "FOCAS NOVO": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "FRANQUIAS MUITA CARNE": {
        "nicho": "FRANQUIA_B2B",
        "descricao": "venda de franquias, público mais restrito e caro"
    },
    "GFC - CHAPECÓ": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "frango frito"
    },
    "Itá Eco Turismo": {
        "nicho": "CABANA_TURISMO",
        "descricao": "turismo e atrações"
    },
    "MUITA CARNE VACARIA": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "Muita Carne (Balneario Camb...)": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "Muita Carne (Chapecó)": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "Muita Carne (S.do Oeste)": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "MUITA CARNE BELTRÃO": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "MUITA CARNE ERECHIM": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "Muita Carne ITAJAI": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "MUITA CARNE MARAVILHA": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "MUITA CARNE PINHALZINHO": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "MUITA CARNE XANXERE": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "hamburgueria"
    },
    "O Píer 2752 ADS": {
        "nicho": "CABANA_TURISMO",
        "descricao": "restaurante focado em turismo"
    },
    "PASTEL MARIA": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "pastelaria"
    },
    "Pousada Tramonto ADS": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "RANCHO EXILIO DO POETA": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "Refugio das Pedras": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "RESERVA BISTROQUADROS": {
        "nicho": "CABANA_TURISMO",
        "descricao": "restaurante focado em turismo"
    },
    "SKY Village": {
        "nicho": "CABANA_TURISMO",
        "descricao": "cabana"
    },
    "Tirolesa": {
        "nicho": "CABANA_TURISMO",
        "descricao": "parque/atração turística"
    },
    "TITULAR BISTRO QUADROS": {
        "nicho": "CABANA_TURISMO",
        "descricao": "restaurante focado em turismo"
    },
    "TITULAR DON": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "pizzaria"
    },
    "VIRALIZE": {
        "nicho": "ALTO_TICKET",
        "descricao": "venda de alto ticket R$ 3k+, CPL de R$ 60-70 é normal"
    },
    "Welev": {
        "nicho": "DELIVERY_FOOD",
        "descricao": "cafeteria"
    }
}

def obter_nicho_conta(nome_conta):
    """
    Retorna o dicionário de nicho e descrição para uma dada conta.
    Busca por correspondência exata ou aproximada (case-insensitive).
    """
    if not nome_conta:
        return {"nicho": "GERAL", "descricao": "estabelecimento geral"}
    
    nome_norm = nome_conta.strip().lower()
    
    # 1. Busca exata
    for key, val in MAPEAMENTO_NICHOS.items():
        if key.lower() == nome_norm:
            return val
            
    # 2. Busca aproximada / substring
    for key, val in MAPEAMENTO_NICHOS.items():
        key_norm = key.lower()
        if key_norm in nome_norm or nome_norm in key_norm:
            return val
            
    return {"nicho": "GERAL", "descricao": "estabelecimento geral"}
