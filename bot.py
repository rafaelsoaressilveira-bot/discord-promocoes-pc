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

MIN_DISCOUNT = 30

MAX_DEALS = 500

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

        with open(
            POSTED_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return set(json.load(file))

    except Exception:

        return set()


def save_posted(posted):

    data = list(posted)[-500:]

    with open(
        POSTED_FILE,
        "w",
        encoding="utf-8"
    ) as file:

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
# DESCOBRIR LOJAS
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

    if isinstance(data, list):

        shops = data

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
# BUSCAR PROMOÇÕES
# ============================================================

def get_deals(shop_ids):

    url = "https://api.isthereanydeal.com/deals/v2"

    headers = {
        "ITAD-API-Key": ITAD_API_KEY,
        "Content-Type": "application/json"
    }

    # Windows = plataforma 1
    #
    # type = 0 corresponde a jogo.
    #
    # cut.min = 50 significa mínimo de 50% OFF.
    #
    # O filtro é aplicado pela própria API.

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
            },

            "platform": [
                1
            ],

            "type": [
                0
            ]
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

    # A resposta atual do ITAD usa "list".

    if isinstance(data, dict):

        deals = data.get("list")

        if isinstance(deals, list):

            return deals

    # Compatibilidade caso a API retorne uma lista diretamente.

    if isinstance(data, list):

        return data

    return []


# ============================================================
# EXTRAIR DADOS
# ============================================================

def extract_deal(deal):

    if not isinstance(deal, dict):
        return None

    title = deal.get("title") or "Jogo"

    deal_info = deal.get("deal")

    if not isinstance(deal_info, dict):
        return None

    # Loja
    shop = deal_info.get("shop", {})

    if isinstance(shop, dict):
        shop_name = (
            shop.get("name")
            or shop.get("title")
            or "Loja"
        )
    else:
        shop_name = str(shop)

    # Preço atual
    price = deal_info.get("price", {})

    if isinstance(price, dict):
        current_price = price.get("amount")
    else:
        current_price = None

    # Preço normal
    regular = deal_info.get("regular", {})

    if isinstance(regular, dict):
        regular_price = regular.get("amount")
    else:
        regular_price = None

    # Desconto
    discount = deal_info.get("cut", 0)

    try:
        discount = int(discount)
    except Exception:
        discount = 0

        # URL
    url = deal_info.get("url")

    if not url:
        url = "https://isthereanydeal.com/"

    # ========================================================
    # IMAGEM DO JOGO
    # ========================================================

    assets = deal.get("assets", {})

    if not isinstance(assets, dict):
        assets = {}

    image_url = (
        assets.get("boxart")
        or assets.get("banner")
        or assets.get("icon")
        or assets.get("logo")
    )

    # Plataformas
    platforms = deal_info.get("platforms", [])

    # Tipo do produto
    game_type = deal.get("type")

    return {
        "title": title,
        "shop": shop_name,
        "current_price": current_price,
        "regular_price": regular_price,
        "discount": discount,
        "url": url,
        "image_url": image_url,
        "platforms": platforms,
        "type": game_type
    }

    # --------------------------------------------------------
    # Loja
    # --------------------------------------------------------

    shop = deal.get("shop")

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
            deal.get("shopName")
            or "Loja"
        )

    # --------------------------------------------------------
    # Preço
    # --------------------------------------------------------

    price = deal.get("price")

    if isinstance(price, dict):

        current_price = (
            price.get("amount")
            if price.get("amount") is not None
            else price.get("value")
        )

    elif isinstance(price, (int, float)):

        current_price = price

    else:

        current_price = None

    # --------------------------------------------------------
    # Preço normal
    # --------------------------------------------------------

    regular = deal.get("regular")

    if isinstance(regular, dict):

        regular_price = (
            regular.get("amount")
            if regular.get("amount") is not None
            else regular.get("value")
        )

    elif isinstance(regular, (int, float)):

        regular_price = regular

    else:

        regular_price = None

    # --------------------------------------------------------
    # Desconto
    # --------------------------------------------------------

    discount = deal.get("cut", 0)

    try:

        discount = int(discount)

    except Exception:

        discount = 0

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    url = (
        deal.get("url")
        or "https://isthereanydeal.com/"
    )

    # --------------------------------------------------------
    # Plataformas
    # --------------------------------------------------------

    platforms = deal.get("platforms") or []

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
# VERIFICAÇÃO EXTRA DE WINDOWS
# ============================================================

def is_windows_game(deal):

    # O filtro principal já é feito pelo ITAD.
    # Esta segunda verificação serve como segurança.

    platforms = deal.get("platforms", [])

    if not platforms:
        return False

    for platform in platforms:

        if isinstance(platform, dict):

            platform_id = platform.get("id")

            platform_name = (
                platform.get("name")
                or ""
            ).lower()

            if platform_id == 1:
                return True

            if "windows" in platform_name:
                return True

    return False


# ============================================================
# VERIFICAÇÃO EXTRA DE JOGO
# ============================================================

def is_game(deal):

    deal_type = (
        deal.get("type")
        or "game"
    )

    if isinstance(deal_type, dict):

        deal_type = (
            deal_type.get("name")
            or deal_type.get("type")
            or ""
        )

    deal_type = str(deal_type).lower()

    return deal_type == "game"


# ============================================================
# DISCORD
# ============================================================

def send_to_discord(deal):

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
        f"\n🪟 **Windows / PC**"
    )

    embed = {
    "title": f"🔥 {title}",
    "description": description,
    "url": url,

    "thumbnail": {
        "url": deal["image_url"]
    } if deal.get("image_url") else {},

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
# PRINCIPAL
# ============================================================

def main():

    print()
    print("==========================================")
    print("       BOT DE PROMOÇÕES DE PC")
    print("==========================================")
    print()

    # --------------------------------------------------------
    # Lojas
    # --------------------------------------------------------

    print("🔎 Procurando lojas...")
    print()

    shops = get_shop_ids()

    print("Lojas encontradas:")

    for name, shop_id in shops.items():

        print(
            f"  ✅ {name} ({shop_id})"
        )

    print()

    if not shops:

        raise RuntimeError(
            "Nenhuma loja configurada foi encontrada."
        )

    # --------------------------------------------------------
    # Promoções
    # --------------------------------------------------------

    print(
        f"🔎 Buscando jogos com "
        f"{MIN_DISCOUNT}% OFF ou mais..."
    )

    print(
        "🪟 Plataforma: Windows"
    )

    print(
        "🎮 Tipo: Jogos"
    )

    print()

    deals = get_deals(
        list(shops.values())
    )

    print(
        f"📦 {len(deals)} promoções encontradas."
    )

    print()

    # --------------------------------------------------------
    # Histórico
    # --------------------------------------------------------

    posted = load_posted()

    published = 0

    # --------------------------------------------------------
    # Processar ofertas
    # --------------------------------------------------------

    for raw_deal in deals:

        if published >= MAX_DEALS:
            break

        deal = extract_deal(raw_deal)

        if not deal:
            continue

        # Segurança adicional:
        # somente jogos.

        if not is_game(raw_deal):

            print(
                f"⏭️ Ignorando não-jogo: "
                f"{deal['title']}"
            )

            continue

        # Segurança adicional:
        # somente Windows.

        if not is_windows_game(deal):

            print(
                f"⏭️ Ignorando sem Windows: "
                f"{deal['title']}"
            )

            continue

        # Segurança adicional:
        # desconto mínimo.

        if deal["discount"] < MIN_DISCOUNT:

            continue

        # ----------------------------------------------------
        # ID da oferta
        # ----------------------------------------------------

        deal_id = (
            f"{deal['title']}|"
            f"{deal['shop']}|"
            f"{deal['current_price']}"
        )

        if deal_id in posted:

            print(
                f"⏭️ Já publicada: "
                f"{deal['title']}"
            )

            continue

        # ----------------------------------------------------
        # Publicar
        # ----------------------------------------------------

        try:

            print(
                f"📢 Publicando: "
                f"{deal['title']} - "
                f"{deal['shop']} - "
                f"{deal['discount']}% OFF"
            )

            send_to_discord(deal)

            posted.add(deal_id)

            published += 1

        except Exception as error:

            print(
                f"❌ Erro ao publicar "
                f"{deal['title']}: {error}"
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
