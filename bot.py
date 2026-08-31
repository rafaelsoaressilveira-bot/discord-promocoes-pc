import os
import json
import requests
from datetime import datetime, timezone

# ============================================================
# CONFIGURAÇÃO
# ============================================================

ITAD_API_KEY = os.environ["ITAD_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

COUNTRY = "BR"

# Desconto mínimo
MIN_DISCOUNT = 50

# Máximo de promoções por execução
MAX_DEALS = 10

# Arquivo para evitar repetir ofertas
POSTED_FILE = "posted_deals.json"


# ============================================================
# LOJAS
# ============================================================
#
# O ITAD fornece os IDs através do endpoint /service/shops/v1.
# Nós descobrimos os IDs automaticamente pelo nome.
#

TARGET_SHOPS = {
    "Steam",
    "Nuuvem",
    "Epic Games Store",
    "GOG",
    "Green Man Gaming",
    "Fanatical",
    "Humble Store",
    "Gamesplanet",
    "GameBillet",
}


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def load_posted():
    """Carrega as ofertas que já foram publicadas."""

    if not os.path.exists(POSTED_FILE):
        return set()

    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))

    except Exception:
        return set()


def save_posted(posted):
    """Salva as últimas ofertas publicadas."""

    # Mantém somente as últimas 500
    data = list(posted)[-500:]

    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def format_price(price):
    """Converte preço para formato brasileiro."""

    if price is None:
        return "Grátis"

    return (
        f"R$ {price:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# ============================================================
# BUSCAR LOJAS
# ============================================================

def get_shops():
    """Obtém as lojas disponíveis no ITAD."""

    url = "https://api.isthereanydeal.com/service/shops/v1"

    headers = {
        "ITAD-API-Key": ITAD_API_KEY
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def find_target_shop_ids():
    """Encontra os IDs das lojas que queremos."""

    shops = get_shops()

    found = {}

    for shop in shops:

        # A API atual usa 'title'
        name = shop.get("title", "")

        # Comparação sem diferença entre maiúsculas/minúsculas
        name_lower = name.lower()

        for target in TARGET_SHOPS:

            if name_lower == target.lower():
                found[target] = shop["id"]

    return found


# ============================================================
# BUSCAR PROMOÇÕES
# ============================================================

def get_deals(shop_ids):
    """Busca promoções no Brasil."""

    url = "https://api.isthereanydeal.com/deals/v2"

    headers = {
        "ITAD-API-Key": ITAD_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "country": COUNTRY,

        "offset": 0,

        "limit": 200,

        # Maior desconto primeiro
        "sort": "-cut",

        "nondeals": False,

        "mature": False,

        "shops": shop_ids,

        "filter": {
            "cut": {
                "min": MIN_DISCOUNT
            }
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# VERIFICAR SE É PC / WINDOWS
# ============================================================

def is_windows_deal(deal):
    """
    O ITAD informa as plataformas da oferta.
    Queremos somente jogos que tenham Windows.
    """

    deal_info = deal.get("deal", {})

    platforms = deal_info.get("platforms", [])

    if not platforms:
        # Se a API não informar plataforma,
        # aceitamos para não perder ofertas.
        return True

    for platform in platforms:

        name = platform.get("name", "").lower()

        if name == "windows":
            return True

    return False


# ============================================================
# ENVIAR PARA DISCORD
# ============================================================

def send_discord(deal):

    game_title = deal.get("title", "Jogo")

    deal_info = deal.get("deal", {})

    shop = deal_info.get("shop", {})

    shop_name = shop.get("name", "Loja")

    price = deal_info.get("price", {})

    regular = deal_info.get("regular", {})

    current_price = price.get("amount")

    regular_price = regular.get("amount")

    discount = deal_info.get("cut", 0)

    url = deal_info.get("url")

    # --------------------------------------------------------
    # Preços
    # --------------------------------------------------------

    current_text = format_price(current_price)

    regular_text = format_price(regular_price)

    # --------------------------------------------------------
    # Descrição
    # --------------------------------------------------------

    description = (
        f"🏪 **{shop_name}**\n"
        f"💰 **{current_text}**"
    )

    if regular_price is not None:
        description += f" ~~{regular_text}~~"

    description += f"\n📉 **{discount}% OFF**"

    # --------------------------------------------------------
    # Embed
    # --------------------------------------------------------

    embed = {
        "title": f"🔥 {game_title}",

        "description": description,

        "url": url,

        "color": 0x00FF66,

        "footer": {
            "text": "Promoções PC • IsThereAnyDeal"
        },

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    }

    payload = {
        "embeds": [embed]
    }

    response = requests.post(
        DISCORD_WEBHOOK_URL,

        json=payload,

        timeout=30
    )

    response.raise_for_status()


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    print()
    print("==========================================")
    print("       BOT DE PROMOÇÕES DE PC")
    print("==========================================")
    print()

    # --------------------------------------------------------
    # Encontrar lojas
    # --------------------------------------------------------

    print("🔎 Procurando lojas...")

    shops = find_target_shop_ids()

    print()
    print("Lojas encontradas:")

    for name, shop_id in shops.items():
        print(f"  ✅ {name} ({shop_id})")

    print()

    if not shops:

        raise RuntimeError(
            "Nenhuma loja foi encontrada."
        )

    # --------------------------------------------------------
    # Buscar promoções
    # --------------------------------------------------------

    print("🔎 Buscando promoções...")

    deals = get_deals(
        list(shops.values())
    )

    print(
        f"📦 {len(deals)} promoções encontradas."
    )

    # --------------------------------------------------------
    # Carregar histórico
    # --------------------------------------------------------

    posted = load_posted()

    published = 0

    # --------------------------------------------------------
    # Processar promoções
    # --------------------------------------------------------

    for deal in deals:

        if published >= MAX_DEALS:
            break

        # Somente Windows / PC
        if not is_windows_deal(deal):
            continue

        title = deal.get(
            "title",
            "Jogo"
        )

        deal_info = deal.get(
            "deal",
            {}
        )

        shop = deal_info.get(
            "shop",
            {}
        )

        shop_name = shop.get(
            "name",
            "Loja"
        )

        price = deal_info.get(
            "price",
            {}
        ).get(
            "amount"
        )

        # ----------------------------------------------------
        # ID único da oferta
        # ----------------------------------------------------

        deal_id = (
            f"{title}|"
            f"{shop_name}|"
            f"{price}"
        )

        # Já publicamos?
        if deal_id in posted:
            continue

        # ----------------------------------------------------
        # Publicar
        # ----------------------------------------------------

        try:

            print(
                f"📢 Publicando: "
                f"{title} - {shop_name}"
            )

            send_discord(deal)

            posted.add(deal_id)

            published += 1

        except Exception as error:

            print(
                f"❌ Erro ao publicar "
                f"{title}: {error}"
            )

    # --------------------------------------------------------
    # Salvar histórico
    # --------------------------------------------------------

    save_posted(posted)

    print()
    print("------------------------------------------")
    print(
        f"✅ Promoções publicadas: {published}"
    )
    print("------------------------------------------")
    print()


# ============================================================
# INICIAR
# ============================================================

if __name__ == "__main__":
    main()
