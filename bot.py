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
MIN_DISCOUNT = 50

# Preço máximo da promoção
MAX_PRICE = 600.00

# Máximo de promoções publicadas no total
MAX_DEALS = 200

# Quantidade máxima buscada por loja
DEALS_PER_SHOP = 200

# Histórico
POSTED_FILE = "posted_deals.json"


# ============================================================
# LOJAS
# ============================================================

SHOPS = {
    61: "Steam",
    50: "Nuuvem",
    35: "GOG",
}


# ============================================================
# TERMOS QUE NÃO QUEREMOS
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
        f"R$ {float(value):,.2f}"
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
# EXTRAIR DADOS DE UMA OFERTA
# ============================================================

def extract_deal(deal):

    if not isinstance(deal, dict):
        return None

    game = deal.get("game", {})

    if not isinstance(game, dict):
        game = {}

    title = (
        deal.get("title")
        or game.get("title")
        or "Jogo"
    )

    deal_info = deal.get("deal", {})

    if not isinstance(deal_info, dict):
        return None

    # ----------------------------
    # Loja
    # ----------------------------

    shop = deal_info.get("shop", {})

    if isinstance(shop, dict):

        shop_name = (
            shop.get("name")
            or shop.get("title")
            or "Loja"
        )

        shop_id = shop.get("id")

    else:

        shop_name = str(shop)
        shop_id = None

    # ----------------------------
    # Preço atual
    # ----------------------------

    price = deal_info.get("price", {})

    if isinstance(price, dict):

        current_price = price.get("amount")

    else:

        current_price = None

    # ----------------------------
    # Preço normal
    # ----------------------------

    regular = deal_info.get("regular", {})

    if isinstance(regular, dict):

        regular_price = regular.get("amount")

    else:

        regular_price = None

    # ----------------------------
    # Desconto
    # ----------------------------

    discount = deal_info.get(
        "cut",
        0
    )

    try:

        discount = float(discount)

    except (TypeError, ValueError):

        discount = 0

    # ----------------------------
    # URL
    # ----------------------------

    url = deal_info.get("url")

    if not url:

        url = deal.get("url")

    # ----------------------------
    # Plataformas
    # ----------------------------

    platforms = deal_info.get(
        "platforms",
        []
    )

    # ----------------------------
    # Tipo
    # ----------------------------

    deal_type = deal.get("type")

    return {
        "title": title,
        "shop": shop_name,
        "shop_id": shop_id,
        "current_price": current_price,
        "regular_price": regular_price,
        "discount": discount,
        "url": url,
        "platforms": platforms,
        "type": deal_type,
        "raw": deal,
    }


# ============================================================
# VERIFICAR WINDOWS
# ============================================================

def is_windows_game(deal):

    info = extract_deal(deal)

    if not info:
        return False

    platforms = info["platforms"]

    if not platforms:
        return False

    if isinstance(platforms, dict):

        platforms = [platforms]

    if isinstance(platforms, str):

        platforms = [platforms]

    for platform in platforms:

        if isinstance(platform, dict):

            platform_id = platform.get("id")

            platform_name = (
                platform.get("name")
                or ""
            ).lower()

            if platform_id == 1:
                return True

            if platform_name == "windows":
                return True

        else:

            platform_text = (
                str(platform)
                .lower()
                .strip()
            )

            if "windows" in platform_text:
                return True

            if platform_text == "pc":
                return True

    return False


# ============================================================
# VERIFICAR SE É JOGO
# ============================================================

def is_game(deal):

    info = extract_deal(deal)

    if not info:
        return False

    title_lower = info["title"].lower()

    # Bloqueia pelo título
    for keyword in BLOCKED_KEYWORDS:

        if keyword in title_lower:
            return False

    # Bloqueia pelo tipo
    deal_type = info["type"]

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
            "expansion",
        ]

        for blocked in blocked_types:

            if blocked in type_text:
                return False

    return True


# ============================================================
# BUSCAR PROMOÇÕES DE UMA LOJA
# ============================================================

def get_deals_for_shop(shop_id):

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

        "limit": DEALS_PER_SHOP,

        # Maior desconto primeiro
        "sort": "price",

        "nondeals": False,

        "mature": False,

        # Uma loja por consulta
        "shops": [shop_id],

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
# BUSCAR TODAS AS LOJAS
# ============================================================

def get_all_deals():

    all_deals = []

    for shop_id, shop_name in SHOPS.items():

        print()
        print(
            f"🔎 Buscando {shop_name}..."
        )

        try:

            deals = get_deals_for_shop(
                shop_id
            )

            print(
                f"   📦 {len(deals)} ofertas encontradas"
            )

            all_deals.extend(
                deals
            )

        except Exception as error:

            print(
                f"   ❌ Erro em {shop_name}: "
                f"{error}"
            )

    return all_deals


# ============================================================
# FILTRAR OFERTAS
# ============================================================

def filter_deals(deals):

    filtered = []

    for deal in deals:

        info = extract_deal(deal)

        if not info:
            continue

        title = info["title"]

        # Windows
        if not is_windows_game(deal):

            print(
                f"⏭️ Sem Windows: {title}"
            )

            continue

        # Somente jogos
        if not is_game(deal):

            print(
                f"⏭️ Não é jogo: {title}"
            )

            continue

        # Desconto
        if info["discount"] < MIN_DISCOUNT:

            continue

        # Preço
        price = info["current_price"]

        if price is None:

            continue

        if float(price) > MAX_PRICE:

            continue

        filtered.append(
            deal
        )

    return filtered


# ============================================================
# REMOVER DUPLICATAS DA MESMA LOJA
# ============================================================

def remove_exact_duplicates(deals):

    unique = {}

    for deal in deals:

        info = extract_deal(deal)

        if not info:
            continue

        title = normalize_title(
            info["title"]
        )

        shop_id = info["shop_id"]

        price = info["current_price"]

        key = (
            title,
            shop_id,
            price
        )

        if key not in unique:

            unique[key] = deal

    return list(
        unique.values()
    )


# ============================================================
# ORDENAR
# ============================================================

def sort_deals(deals):

    def sort_key(deal):

        info = extract_deal(deal)

        price = info["current_price"]

        if price is None:
            price = float("inf")

        return (
            -info["discount"],
            price
        )

    return sorted(
        deals,
        key=sort_key
    )


# ============================================================
# FORMATAR LINHA
# ============================================================

def format_deal_line(deal):

    info = extract_deal(deal)

    title = info["title"]

    current_price = info["current_price"]

    regular_price = info["regular_price"]

    discount = info["discount"]

    url = info["url"]

    if current_price is not None:

        current_text = format_brl(
            current_price
        )

    else:

        current_text = "Grátis"

    price_text = (
        f"💰 **{current_text}**"
    )

    if (
        regular_price is not None
        and current_price is not None
        and regular_price > current_price
    ):

        price_text += (
            f" ~~{format_brl(regular_price)}~~"
        )

    if url:

        title_text = (
            f"[🎮 **{title}**]({url})"
        )

    else:

        title_text = (
            f"🎮 **{title}**"
        )

    return (
        f"{title_text} — "
        f"{price_text} — "
        f"📉 **{discount:g}% OFF**"
    )


# ============================================================
# ENVIAR UMA LOJA PARA O DISCORD
# ============================================================

def send_shop_to_discord(
    shop_name,
    deals
):

    if not deals:
        return

    # Discord tem limite de 2000 caracteres.
    # Deixamos margem para segurança.
    chunks = []

    current_lines = []

    current_length = 0

    # Cabeçalho
    header = (
        f"🎮 **Promoções — {shop_name}**"
    )

    current_lines.append(
        header
    )

    current_length = len(
        header
    ) + 1

    for deal in deals:

        line = format_deal_line(
            deal
        )

        line_length = (
            len(line) + 1
        )

        if (
            current_lines
            and current_length + line_length > 1800
        ):

            chunks.append(
                "\n".join(
                    current_lines
                )
            )

            current_lines = [
                f"🎮 **Promoções — {shop_name}**"
            ]

            current_length = (
                len(current_lines[0])
                + 1
            )

        current_lines.append(
            line
        )

        current_length += line_length

    if current_lines:

        chunks.append(
            "\n".join(
                current_lines
            )
        )

    # Envia cada bloco
    for chunk in chunks:

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json={
                "content": chunk
            },
            timeout=30
        )

        response.raise_for_status()


# ============================================================
# PRINCIPAL
# ============================================================

def main():

    print()
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
    # Verificar secrets
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
    # Configuração atual
    # --------------------------------------------------------

    print()
    print(
        f"📉 Desconto mínimo: "
        f"{MIN_DISCOUNT}%"
    )

    print(
        f"💰 Preço máximo: "
        f"{format_brl(MAX_PRICE)}"
    )

    print(
        f"📦 Máximo publicado: "
        f"{MAX_DEALS}"
    )

    print(
        "🪟 Plataforma: Windows"
    )

    print(
        "🎮 Tipo: Jogos"
    )

    # --------------------------------------------------------
    # Buscar lojas separadamente
    # --------------------------------------------------------

    deals = get_all_deals()

    print()
    print(
        f"📦 Total recebido: "
        f"{len(deals)} ofertas"
    )

    # --------------------------------------------------------
    # Filtrar
    # --------------------------------------------------------

    filtered = filter_deals(
        deals
    )

    print()
    print(
        f"✅ Ofertas válidas: "
        f"{len(filtered)}"
    )

    # --------------------------------------------------------
    # Remover duplicatas exatas
    # --------------------------------------------------------

    unique = remove_exact_duplicates(
        filtered
    )

    print(
        f"✅ Ofertas únicas: "
        f"{len(unique)}"
    )

    # --------------------------------------------------------
    # Ordenar
    # --------------------------------------------------------

    sorted_deals = sort_deals(
        unique
    )

    # --------------------------------------------------------
    # Limitar quantidade
    # --------------------------------------------------------

    sorted_deals = sorted_deals[
        :MAX_DEALS
    ]

    # --------------------------------------------------------
    # Histórico
    # --------------------------------------------------------

    posted = load_posted()

    new_deals = []

    for deal in sorted_deals:

        info = extract_deal(
            deal
        )

        title = info["title"]

        shop = info["shop"]

        price = info["current_price"]

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

        new_deals.append(
            deal
        )

    print()
    print(
        f"🆕 Novas ofertas: "
        f"{len(new_deals)}"
    )

    # --------------------------------------------------------
    # Agrupar por loja
    # --------------------------------------------------------

    grouped = {}

    for deal in new_deals:

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
    # Ordem das lojas
    # --------------------------------------------------------

    shop_order = [
        "Steam",
        "Nuuvem",
        "GOG"
    ]

    published = 0

    # --------------------------------------------------------
    # Publicar
    # --------------------------------------------------------

    for shop_name in shop_order:

        shop_deals = grouped.get(
            shop_name,
            []
        )

        if not shop_deals:
            continue

        print()
        print(
            f"📨 Publicando "
            f"{len(shop_deals)} ofertas "
            f"da {shop_name}..."
        )

        try:

            send_shop_to_discord(
                shop_name,
                shop_deals
            )

            for deal in shop_deals:

                info = extract_deal(
                    deal
                )

                title = info["title"]

                price = info["current_price"]

                deal_id = (
                    f"{normalize_title(title)}|"
                    f"{shop_name.lower()}|"
                    f"{price}"
                )

                posted.add(
                    deal_id
                )

            published += len(
                shop_deals
            )

        except Exception as error:

            print(
                f"❌ Erro ao publicar "
                f"{shop_name}: {error}"
            )

    # --------------------------------------------------------
    # Salvar histórico
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
        "------------------------------------------"
    )


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":
    main()
