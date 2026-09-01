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

TARGET_SHOPS = {
    35,  # GOG
    50,  # Nuuvem
    61,  # Steam
}


# ============================================================
# PRODUTOS QUE NÃO SÃO JOGOS
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

    title = re.sub(
        r"[^\w\s]",
        " ",
        title,
        flags=re.UNICODE
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    return title.strip()

# ============================================================
# BUSCAR LOJAS
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

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        deals = data.get("list")

        if isinstance(deals, list):
            return deals

    return []

# ============================================================
# EXTRAIR DADOS
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

# ============================================================
# CRIAR LINHA DA PROMOÇÃO
# ============================================================

def format_deal_line(deal):

    info = extract_deal(deal)

    title = info["title"]
    current_price = info["current_price"]
    regular_price = info["regular_price"]
    discount = info["discount"]
    url = info["url"]

    if not url:
        url = "https://isthereanydeal.com/"

    if current_price is not None:
        current_text = format_brl(
            current_price
        )
    else:
        current_text = "Grátis"

    price_text = (
        f"**{current_text}**"
    )

    if (
        regular_price is not None
        and current_price is not None
        and regular_price > current_price
    ):
        price_text += (
            f" ~~{format_brl(regular_price)}~~"
        )

    return (
        f"🔥 [{title}]({url}) "
        f"— {price_text} "
        f"**{discount:g}% OFF**"
    )

# ============================================================
# PUBLICAR GRUPO NO DISCORD
# ============================================================

def send_group_to_discord(shop_name, deals):

    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL não configurado."
        )

    # Discord permite aproximadamente 2000 caracteres
    # por mensagem. Mantemos margem de segurança.
    chunks = []
    current_chunk = []

    current_length = 0

    for deal in deals:

        line = format_deal_line(
            deal
        )

        line_length = len(line) + 1

        if (
            current_chunk
            and current_length + line_length > 1800
        ):

            chunks.append(
                current_chunk
            )

            current_chunk = []
            current_length = 0

        current_chunk.append(
            line
        )

        current_length += line_length

    if current_chunk:
        chunks.append(
            current_chunk
        )

    for chunk in chunks:

        description = "\n".join(
            chunk
        )

        embed = {
            "title": f"🎮 Promoções — {shop_name}",
            "description": description,
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

    print(
        "=========================================="
    )

    print(
        "       BOT DE PROMOÇÕES DE PC"
    )

    print(
        "=========================================="
    )

    # --------------------------------------------------------
    # CONFIGURAÇÃO
    # --------------------------------------------------------

    if not ITAD_API_KEY:

        raise RuntimeError(
            "ITAD_API_KEY não configurado."
        )

    if not DISCORD_WEBHOOK_URL:

        raise RuntimeError(
            "DISCORD_WEBHOOK_URL não configurado."
        )

    # --------------------------------------------------------
    # LOJAS
    # --------------------------------------------------------

    print()
    print(
        "🔎 Procurando lojas..."
    )

    shop_ids = get_shop_ids()

    if not shop_ids:

        raise RuntimeError(
            "Nenhuma loja configurada foi encontrada."
        )

    # --------------------------------------------------------
    # PROMOÇÕES
    # --------------------------------------------------------

    print()
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

    deals = get_deals(
        shop_ids
    )

    print()
    print(
        f"📦 {len(deals)} promoções encontradas."
    )

    # --------------------------------------------------------
    # FILTRAR
    # --------------------------------------------------------

    filtered = []

    for deal in deals:

        if not isinstance(
            deal,
            dict
        ):
            continue

        info = extract_deal(
            deal
        )

        title = info["title"]

        # Windows
        if not is_windows_deal(
            deal
        ):

            print(
                f"⏭️ Ignorando sem Windows: "
                f"{title}"
            )

            continue

        # Somente jogos
        if not is_game(
            deal
        ):

            print(
                f"⏭️ Ignorando não-jogo: "
                f"{title}"
            )

            continue

        # Desconto
        if info["discount"] < MIN_DISCOUNT:
            continue

        filtered.append(
            deal
        )

    print()
    print(
        f"🎮 Jogos válidos após filtros: "
        f"{len(filtered)}"
    )

    # --------------------------------------------------------
    # NÃO DUPLICAR O MESMO JOGO
    #
    # IMPORTANTE:
    # Aqui NÃO vamos escolher somente uma loja.
    #
    # Exemplo:
    #
    # Diablo 4 - Steam 60%
    # Diablo 4 - Nuuvem 55%
    #
    # Os DOIS podem aparecer.
    #
    # O mesmo jogo só será eliminado se for
    # exatamente a mesma oferta na mesma loja.
    # --------------------------------------------------------

    unique_deals = {}

    for deal in filtered:

        info = extract_deal(
            deal
        )

        title = normalize_title(
            info["title"]
        )

        shop = info["shop"].lower()

        price = info["current_price"]

        key = (
            f"{title}|"
            f"{shop}|"
            f"{price}"
        )

        if key not in unique_deals:

            unique_deals[key] = deal

    # --------------------------------------------------------
    # ORDENAR
    # --------------------------------------------------------

    sorted_deals = sorted(
        unique_deals.values(),
        key=lambda deal: (
            -extract_deal(
                deal
            )["discount"],

            extract_deal(
                deal
            )["current_price"]
            if extract_deal(
                deal
            )["current_price"] is not None
            else float("inf")
        )
    )

    print()
    print(
        f"📋 Ofertas únicas: "
        f"{len(sorted_deals)}"
    )

    # --------------------------------------------------------
    # HISTÓRICO
    # --------------------------------------------------------

    posted = load_posted()

    # --------------------------------------------------------
    # SELECIONAR NOVAS OFERTAS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # AGRUPAR POR LOJA
    # --------------------------------------------------------

    grouped = {}

    for deal in deals_to_publish:

        info = extract_deal(
            deal
        )

        shop = info["shop"]

        if shop not in grouped:
            grouped[shop] = []

        grouped[shop].append(
            deal
        )

    # --------------------------------------------------------
    # PUBLICAR
    # --------------------------------------------------------

    published = 0

    for shop_name, shop_deals in grouped.items():

        print()
        print(
            f"📨 Enviando "
            f"{len(shop_deals)} promoções "
            f"da {shop_name}..."
        )

        try:

            send_group_to_discord(
                shop_name,
                shop_deals
            )

            for deal in shop_deals:

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

                posted.add(
                    deal_id
                )

            published += len(
                shop_deals
            )

            print(
                f"✅ {len(shop_deals)} "
                f"promoções enviadas."
            )

        except Exception as error:

            print(
                f"❌ Erro ao enviar "
                f"{shop_name}: {error}"
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
