```python
import os
import json
import requests
from datetime import datetime

# ============================================================
# CONFIGURAÇÃO
# ============================================================

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
ITAD_API_KEY = os.environ.get("ITAD_API_KEY")

# Canal do Discord que você passou.
DISCORD_CHANNEL_ID = "1544039979041431662"

# Brasil
COUNTRY = "BR"

# Mínimo de desconto
MIN_DISCOUNT = 50

# Quantidade máxima de promoções publicadas por execução
MAX_DEALS = 10

# Lojas que vamos monitorar
# IDs oficiais do IsThereAnyDeal
SHOPS = {
    61: "Steam",
    # Os IDs das demais lojas serão preenchidos automaticamente
    # através da lista de lojas do ITAD.
}

SHOP_NAMES = {
    "Steam",
    "Nuuvem",
    "Epic Game Store",
    "GOG",
    "GreenManGaming",
    "Fanatical",
    "Humble Store",
    "GameBillet",
    "GamesPlanet US",
    "GamesPlanet UK",
    "GamesPlanet DE",
    "GamesPlanet FR",
}

# Arquivo usado para evitar publicar a mesma oferta repetidamente
POSTED_FILE = "posted_deals.json"


# ============================================================
# UTILIDADES
# ============================================================

def load_posted_deals():
    if not os.path.exists(POSTED_FILE):
        return set()

    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))
    except Exception:
        return set()


def save_posted_deals(posted):
    # Mantém somente as últimas 500 ofertas
    posted_list = list(posted)[-500:]

    with open(POSTED_FILE, "w", encoding="utf-8") as file:
        json.dump(posted_list, file, ensure_ascii=False, indent=2)


def format_brl(value):
    if value is None:
        return "Preço indisponível"

    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ============================================================
# DESCOBRIR IDS DAS LOJAS
# ============================================================

def get_shop_ids():
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

    shops = response.json()

    result = []

    for shop in shops:
        name = shop.get("name")

        if name in SHOP_NAMES:
            result.append(shop["id"])

    return result


# ============================================================
# BUSCAR PROMOÇÕES
# ============================================================

def get_deals(shop_ids):
    url = "https://api.isthereanydeal.com/deals/v2"

    headers = {
        "ITAD-API-Key": ITAD_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "country": COUNTRY,
        "offset": 0,
        "limit": 200,
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
# PUBLICAR NO DISCORD
# ============================================================

def send_to_discord(deal):
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("DISCORD_WEBHOOK_URL não configurado.")

    title = deal.get("title", "Jogo")

    # A API pode retornar diferentes estruturas dependendo da versão.
    # Por isso usamos get() de forma defensiva.

    game = deal.get("game", {})
    deal_data = deal.get("deal", {})
    shop = deal_data.get("shop", {})

    shop_name = shop.get("name", "Loja")

    price = deal_data.get("price", {})
    regular = deal_data.get("regular", {})

    current_price = price.get("amount")
    regular_price = regular.get("amount")

    cut = deal_data.get("cut", 0)

    url = deal_data.get("url")

    if not url:
        url = deal.get("url")

    if current_price is not None:
        current_price_text = format_brl(current_price)
    else:
        current_price_text = "Grátis"

    if regular_price is not None:
        regular_price_text = format_brl(regular_price)
    else:
        regular_price_text = ""

    description = (
        f"🏪 **{shop_name}**\n"
        f"💰 **{current_price_text}**"
    )

    if regular_price:
        description += f" ~~{regular_price_text}~~"

    description += f"\n📉 **{cut}% OFF**"

    embed = {
        "title": f"🔥 {title}",
        "description": description,
        "url": url,
        "color": 0x00FF66,
        "footer": {
            "text": "Promoções PC • IsThereAnyDeal"
        },
        "timestamp": datetime.utcnow().isoformat()
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
# PRINCIPAL
# ============================================================

def main():
    print("======================================")
    print(" BOT DE PROMOÇÕES PC")
    print("======================================")

    if not ITAD_API_KEY:
        raise RuntimeError(
            "ITAD_API_KEY não configurado."
        )

    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL não configurado."
        )

    print("Obtendo lojas...")

    shop_ids = get_shop_ids()

    print(f"Lojas encontradas: {shop_ids}")

    if not shop_ids:
        raise RuntimeError(
            "Nenhuma das lojas configuradas foi encontrada."
        )

    print("Buscando promoções...")

    deals = get_deals(shop_ids)

    print(f"Promoções encontradas: {len(deals)}")

    posted = load_posted_deals()

    published = 0

    for deal in deals:

        if published >= MAX_DEALS:
            break

        game = deal.get("game", {})
        deal_data = deal.get("deal", {})
        shop = deal_data.get("shop", {})

        title = deal.get("title") or game.get("title", "Jogo")
        shop_name = shop.get("name", "Loja")

        current_price = deal_data.get("price", {}).get("amount")

        # Identificador único da oferta
        deal_id = (
            f"{title}|"
            f"{shop_name}|"
            f"{current_price}"
        )

        if deal_id in posted:
            continue

        try:
            print(f"Publicando: {title} - {shop_name}")

            send_to_discord(deal)

            posted.add(deal_id)

            published += 1

        except Exception as error:
            print(
                f"Erro ao publicar {title}: {error}"
            )

    save_posted_deals(posted)

    print("--------------------------------------")
    print(f"Publicadas: {published}")
    print("Bot finalizado.")
    print("--------------------------------------")


if __name__ == "__main__":
    main()
```
