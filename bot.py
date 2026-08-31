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

MIN_DISCOUNT = 50

MAX_DEALS = 10

POSTED_FILE = "posted_deals.json"


# ============================================================
# LOJAS
# ============================================================

TARGET_SHOPS = {
    "steam",
    "nuuvem",
    "epic games store",
    "epic games",
    "gog",
    "green man gaming",
    "greenmangaming",
    "fanatical",
    "humble store",
    "humble bundle",
    "gamesplanet",
    "gamebillet",
}


# ============================================================
# HISTÓRICO
# ============================================================

def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()

    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))

    except Exception:
        return set()


def save_posted(posted):
    data = list(posted)[-500:]

    with open(POSTED_FILE, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# PREÇO
# ============================================================

def format_price(value):

    if value is None:
        return "Grátis"

    return (
        f"R$ {float(value):,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# ============================================================
# LOJAS
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

    data = response.json()

    # A API pode retornar uma lista diretamente
    if isinstance(data, list):
        shops = data

    # Ou uma lista dentro de uma chave
    elif isinstance(data, dict):

        shops = (
            data.get("shops")
            or data.get("results")
            or data.get("data")
            or []
        )

    else:
        shops = []

    result = {}

    for shop in shops:

        if not isinstance(shop, dict):
            continue

        shop_id = shop.get("id")

        name = (
            shop.get("title")
            or shop.get("name")
            or ""
        )

        normalized = name.strip().lower()

        if normalized in TARGET_SHOPS:

            result[name] = shop_id

    return result


# ============================================================
# PROMOÇÕES
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
        "shops": shop_ids
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

    data = response.json()

    # --------------------------------------------------------
    # Normalizar resposta
    # --------------------------------------------------------

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in (
            "deals",
            "results",
            "data"
        ):

            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


# ============================================================
# EXTRAIR INFORMAÇÕES DA OFERTA
# ============================================================

def extract_deal(deal):

    if not isinstance(deal, dict):
        return None

    title = (
        deal.get("title")
        or deal.get("name")
        or "Jogo"
    )

    # Algumas respostas colocam os dados diretamente
    info = deal.get("deal")

    if not isinstance(info, dict):
        info = deal

    # --------------------------------------------------------
    # Loja
    # --------------------------------------------------------

    shop = info.get("shop")

    if isinstance(shop, dict):

        shop_name = (
            shop.get("name")
            or shop.get("title")
            or "Loja"
        )

    elif isinstance(shop, str):

        shop_name = shop

    else:

        shop_name = (
            info.get("shopName")
            or "Loja"
        )

    # --------------------------------------------------------
    # Preço atual
    # --------------------------------------------------------

    price = info.get("price")

    if isinstance(price, dict):

        current_price = (
            price.get("amount")
            or price.get("value")
        )

    elif isinstance(price, (int, float)):

        current_price = price

    else:

        current_price = info.get("priceAmount")

    # --------------------------------------------------------
    # Preço normal
    # --------------------------------------------------------

    regular = info.get("regular")

    if isinstance(regular, dict):

        regular_price = (
            regular.get("amount")
            or regular.get("value")
        )

    elif isinstance(regular, (int, float)):

        regular_price = regular

    else:

        regular_price = info.get("regularPrice")

    # --------------------------------------------------------
    # Desconto
    # --------------------------------------------------------

    discount = (
        info.get("cut")
        or info.get("discount")
        or 0
    )

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    url = (
        info.get("url")
        or deal.get("url")
        or deal.get("link")
    )

    # --------------------------------------------------------
    # Plataformas
    # --------------------------------------------------------

    platforms = (
        info.get("platforms")
        or deal.get("platforms")
        or []
    )

    return {
        "title": title,
        "shop": shop_name,
        "current_price": current_price,
        "regular_price": regular_price,
        "discount": discount,
        "url": url,
        "platforms": platforms
    }


# ============================================================
# VERIFICAR WINDOWS
# ============================================================

def is_windows(deal):

    platforms = deal.get("platforms", [])

    # Se a API não informar plataforma,
    # não descartamos a oferta.
    if not platforms:
        return True

    for platform in platforms:

        if isinstance(platform, dict):

            name = (
                platform.get("name")
                or platform.get("title")
                or ""
            )

        else:

            name = str(platform)

        name = name.lower()

        if (
            "windows" in name
            or "pc" == name
            or "win" == name
        ):
            return True

    return False


# ============================================================
# DISCORD
# ============================================================

def send_discord(deal):

    title = deal["title"]

    shop = deal["shop"]

    current_price = deal["current_price"]

    regular_price = deal["regular_price"]

    discount = deal["discount"]

    url = deal["url"]

    description = (
        f"🏪 **{shop}**\n"
        f"💰 **{format_price(current_price)}**"
    )

    if regular_price is not None:

        description += (
            f" ~~{format_price(regular_price)}~~"
        )

    description += (
        f"\n📉 **{discount}% OFF**"
    )

    if not url:
        url = "https://isthereanydeal.com/"

    embed = {

        "title": f"🔥 {title}",

        "description": description,

        "url": url,

        "color": 0x00FF66,

        "footer": {
            "text": "Promoções PC"
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
# PRINCIPAL
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

    shops = get_shop_ids()

    print()
    print("Lojas encontradas:")

    for name, shop_id in shops.items():

        print(
            f"  ✅ {name} ({shop_id})"
        )

    print()

    if not shops:

        raise RuntimeError(
            "Nenhuma loja encontrada."
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
    # Histórico
    # --------------------------------------------------------

    posted = load_posted()

    published = 0

    # --------------------------------------------------------
    # Processar
    # --------------------------------------------------------

    for raw_deal in deals:

        if published >= MAX_DEALS:
            break

        deal = extract_deal(raw_deal)

        if not deal:
            continue

        # Somente Windows/PC
        if not is_windows(deal):
            continue

        title = deal["title"]

        shop = deal["shop"]

        price = deal["current_price"]

        discount = deal["discount"]

        # ----------------------------------------------------
        # ID único
        # ----------------------------------------------------

        deal_id = (
            f"{title}|"
            f"{shop}|"
            f"{price}"
        )

        if deal_id in posted:
            continue

        # ----------------------------------------------------
        # Publicar
        # ----------------------------------------------------

        try:

            print(
                f"📢 Publicando: "
                f"{title} - {shop}"
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


if __name__ == "__main__":
    main()
