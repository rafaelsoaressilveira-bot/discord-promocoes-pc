import os
import json
import re
import requests
from datetime import datetime, timezone


# ============================================================
# CONFIGURAÇÃO
# ============================================================

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
ITAD_API_KEY = os.environ.get("ITAD_API_KEY")

COUNTRY = "BR"

# Desconto mínimo
MIN_DISCOUNT = 30

# Máximo de jogos publicados por execução
MAX_DEALS = 200

# Arquivo para evitar repetir ofertas
POSTED_FILE = "posted_deals.json"


# ============================================================
# LOJAS
# ============================================================

# IDs oficiais do IsThereAnyDeal
TARGET_SHOPS = {
    35,  # GOG
    50,  # Nuuvem
    61,  # Steam
}


# ============================================================
# TERMOS QUE NÃO SÃO JOGOS
# ============================================================

BLOCKED_KEYWORDS = [
    "dlc",
    "add-on",
    "addon",
    "soundtrack",
    "season pass",
    "expansion pass",
    "expansion",
    "geforce now",
    "subscription",
    "membership",
    "wallet",
    "currency",
    "points",
    "credits",
    "upgrade",
    "demo version",
    "ost",
]


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

    # Mantém somente os últimos 1000 registros
    posted_list = list(posted)[-1000:]

    with open(
        POSTED_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            posted_list,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# FORMATAÇÃO
# ============================================================

def format_brl(value):

    if value is None:
        return "Preço indisponível"

    return (
        f"R$ {value:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# ============================================================
# NORMALIZAR TÍTULO
# ============================================================

def normalize_title(title):

    if not title:
        return ""

    title = str(title).lower().strip()

    # Remove caracteres especiais
    title = re.sub(
        r"[^\w\s]",
        " ",
        title,
        flags=re.UNICODE
    )

    # Remove espaços duplicados
    title = re.sub(
        r"\s+",
        " ",
        title
    )

    return title.strip()


# ============================================================
# BUSCAR LOJAS NO ITAD
# ============================================================

def get_shop_ids():

    url = (
        "https://api.isthereanydeal.com/"
        "service/shops/v1"
    )

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

    print()
    print("Lojas encontradas:")

    for shop in shops:

        shop_id = shop.get("id")
        name = shop.get("name", "")

        try:
            numeric_id = int(shop_id)
        except (TypeError, ValueError):
            continue

        if numeric_id in TARGET_SHOPS:

            result.append(numeric_id)

            print(
                f"  ✅ {name} ({numeric_id})"
            )

    return result


# ============================================================
# BUSCAR PROMOÇÕES
# ============================================================

def get_deals(shop_ids):

    url = (
        "https://api.isthereanydeal.com/"
        "deals/v2"
    )

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

    data = response.json()

    # Resposta pode ser uma lista
    if isinstance(data, list):
        return data

    # Ou pode vir dentro de "list"
    if isinstance(data, dict):

        deals = data.get("list")

        if isinstance(deals, list):
            return deals

    return []


# ============================================================
# OBTER DADOS DA OFERTA
# ============================================================

def extract_deal(deal):

    game = deal.get(
        "game",
        {}
    )

    if not isinstance(game, dict):
        game = {}

    title = (
        deal.get("title")
        or game.get("title")
        or "Jogo"
    )

    deal_info = deal.get(
        "deal",
        {}
    )

    if not isinstance(deal_info, dict):
        deal_info = {}

    shop = deal_info.get(
        "shop",
        {}
    )

    if isinstance(shop, dict):

        shop_name = shop.get(
            "name",
            "Loja"
        )

    else:

        shop_name = str(shop)

    price = deal_info.get(
        "price",
        {}
    )

    if not isinstance(price, dict):
        price = {}

    regular = deal_info.get(
        "regular",
        {}
    )

    if not isinstance(regular, dict):
        regular = {}

    current_price = price.get(
        "amount"
    )

    regular_price = regular.get(
        "amount"
    )

    discount = deal_info.get(
        "cut",
        0
    )

    try:
        discount = float(discount)
    except (TypeError, ValueError):
        discount = 0

    url = deal_info.get(
        "url"
    )

    if not url:
        url = deal.get(
            "url"
        )

    return {
        "title": title,
        "shop": shop_name,
        "current_price": current_price,
        "regular_price": regular_price,
        "discount": discount,
        "url": url,
        "raw": deal
    }


# ============================================================
# VERIFICAR WINDOWS
# ============================================================

def is_windows_deal(deal):

    if not isinstance(deal, dict):
        return False

    deal_info = deal.get(
        "deal",
        {}
    )

    if not isinstance(deal_info, dict):
        return False

    platforms = deal_info.get(
        "platforms",
        []
    )

    if not platforms:
        return False

    if isinstance(platforms, str):
        platforms = [platforms]

    for platform in platforms:

        platform_text = (
            str(platform)
            .lower()
            .strip()
        )

        if (
            "windows" in platform_text
            or platform_text == "pc"
        ):
            return True

    return False


# ============================================================
# VERIFICAR SE É JOGO
# ============================================================

def is_game(deal):

    if not isinstance(deal, dict):
        return False

    info = extract_deal(deal)

    title = info["title"]

    title_lower = title.lower()

    # Bloqueia produtos que não são jogos
    for keyword in BLOCKED_KEYWORDS:

        if keyword in title_lower:
            return False

    deal_type = deal.get(
        "type"
    )

    if deal_type is not None:

        type_text = (
            str(deal_type)
            .lower()
            .strip()
        )

        blocked_types = [
            "dlc",
            "addon",
            "add-on",
            "soundtrack",
            "software",
            "application",
            "subscription",
            "currency",
            "wallet",
            "season pass",
            "expansion"
        ]

        for blocked in blocked_types:

            if blocked in type_text:
                return False

    return True

# --------------------------------------------------------
# PUBLICAR
# --------------------------------------------------------

posted = load_posted()

# Todas as ofertas selecionadas serão publicadas juntas
deals_to_publish = []

for deal in sorted_deals:

    if len(deals_to_publish) >= MAX_DEALS:
        break

    info = extract_deal(
        deal
    )

    title = info["title"]
    shop = info["shop"]
    price = info["current_price"]
    discount = info["discount"]

    # Identificador da oferta
    deal_id = (
        f"{normalize_title(title)}|"
        f"{shop.lower()}|"
        f"{price}"
    )

    if deal_id in posted:

        print(
            f"⏭️ Já publicada: "
            f"{title} - {shop}"
        )

        continue

    print(
        f"📢 Preparando: "
        f"{title} - "
        f"{shop} - "
        f"{discount:g}% OFF"
    )

    deals_to_publish.append(
        deal
    )

    posted.add(
        deal_id
    )


# Envia todas as promoções agrupadas
if deals_to_publish:

    print()
    print(
        f"📨 Enviando "
        f"{len(deals_to_publish)} promoções "
        f"agrupadas..."
    )

    try:

        send_to_discord(
            deals_to_publish
        )

        published = len(
            deals_to_publish
        )

        print(
            f"✅ {published} promoções enviadas."
        )

    except Exception as error:

        print(
            f"❌ Erro ao enviar promoções: "
            f"{error}"
        )

        # Se falhou, não deixa as ofertas
        # marcadas como publicadas.
        for deal in deals_to_publish:

            info = extract_deal(
                deal
            )

            title = info["title"]
            shop = info["shop"]
            price = info["current_price"]

            deal_id = (
                f"{normalize_title(title)}|"
                f"{shop.lower()}|"
                f"{price}"
            )

            posted.discard(
                deal_id
            )

        published = 0

else:

    published = 0

    print(
        "ℹ️ Nenhuma promoção nova para publicar."
    )

    # --------------------------------------------------------
    # SALVAR HISTÓRICO
    # --------------------------------------------------------

    save_posted(
        posted
    )

    print()
    print(
        "------------------------------------------"
    )

    print(
        f"✅ Promoções publicadas: "
        f"{published}"
    )

    print(
        "------------------------------------------")


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":
    main()
