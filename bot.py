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

# Só entram promoções com pelo menos este desconto

MIN_DISCOUNT = 30

# Só entram promoções até este preço

MAX_PRICE = 100.00

# Quantos jogos populares vamos analisar

POPULAR_GAMES = 100

# Máximo de jogos publicados

MAX_DEALS = 200

# Lojas

SHOPS = {
61: "Steam",
50: "Nuuvem",
35: "GOG",
}

# Histórico

POSTED_FILE = "posted_deals.json"

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
# BUSCAR JOGOS POPULARES
# ============================================================

def get_popular_games():


url = (
    "https://api.isthereanydeal.com/"
    "stats/most-popular/v1"
)

headers = {
    "ITAD-API-Key": ITAD_API_KEY
}

params = {
    "offset": 0,
    "limit": POPULAR_GAMES
}

response = requests.get(
    url,
    headers=headers,
    params=params,
    timeout=30
)

response.raise_for_status()

data = response.json()

if not isinstance(data, list):
    return []

# Mantém somente jogos
games = []

for item in data:

    if not isinstance(item, dict):
        continue

    if item.get("type") != "game":
        continue

    game_id = item.get("id")

    title = item.get(
        "title",
        "Jogo"
    )

    if not game_id:
        continue

    games.append({
        "id": game_id,
        "title": title,
        "position": item.get(
            "position",
            999999
        )
    })

return games


# ============================================================
# BUSCAR PREÇOS DOS JOGOS POPULARES
# ============================================================

def get_prices(game_ids):


url = (
    "https://api.isthereanydeal.com/"
    "games/prices/v3"
)

headers = {
    "ITAD-API-Key": ITAD_API_KEY,
    "Content-Type": "application/json"
}

params = {
    "country": COUNTRY,
    "shops": ",".join(
        str(shop_id)
        for shop_id in SHOPS.keys()
    ),
    "deals": "true",
    "capacity": 0
}

# A API aceita no máximo 200 IDs por chamada.
game_ids = game_ids[:200]

response = requests.post(
    url,
    headers=headers,
    params=params,
    json=game_ids,
    timeout=60
)

response.raise_for_status()

data = response.json()

if not isinstance(data, list):
    return []

return data


# ============================================================
# CONVERTER PREÇO PARA NOSSO FORMATO
# ============================================================

def parse_price_game(game_price):


if not isinstance(game_price, dict):
    return []

game_id = game_price.get("id")

deals = game_price.get(
    "deals",
    []
)

if not isinstance(deals, list):
    return []

results = []

for deal in deals:

    if not isinstance(
        deal,
        dict
    ):
        continue

    shop = deal.get(
        "shop",
        {}
    )

    if not isinstance(
        shop,
        dict
    ):
        continue

    shop_id = shop.get(
        "id"
    )

    if shop_id not in SHOPS:
        continue

    platforms = deal.get(
        "platforms",
        []
    )

    # ----------------------------------------------------
    # Somente Windows
    # ----------------------------------------------------

    has_windows = False

    if isinstance(
        platforms,
        list
    ):

        for platform in platforms:

            if not isinstance(
                platform,
                dict
            ):
                continue

            platform_id = platform.get(
                "id"
            )

            platform_name = (
                str(
                    platform.get(
                        "name",
                        ""
                    )
                )
                .lower()
            )

            if (
                platform_id == 1
                or platform_name == "windows"
            ):
                has_windows = True
                break

    if not has_windows:
        continue

    # ----------------------------------------------------
    # Preços
    # ----------------------------------------------------

    price = deal.get(
        "price",
        {}
    )

    regular = deal.get(
        "regular",
        {}
    )

    if not isinstance(
        price,
        dict
    ):
        continue

    current_price = price.get(
        "amount"
    )

    if current_price is None:
        continue

    if not isinstance(
        regular,
        dict
    ):
        regular = {}

    regular_price = regular.get(
        "amount"
    )

    discount = deal.get(
        "cut",
        0
    )

    try:
        discount = float(
            discount
        )
    except (
        TypeError,
        ValueError
    ):
        discount = 0

    # ----------------------------------------------------
    # Filtros
    # ----------------------------------------------------

    if discount < MIN_DISCOUNT:
        continue

    if float(current_price) > MAX_PRICE:
        continue

    url = deal.get(
        "url"
    )

    results.append({
        "game_id": game_id,
        "shop_id": shop_id,
        "shop": SHOPS[shop_id],
        "price": float(current_price),
        "regular": (
            float(regular_price)
            if regular_price is not None
            else None
        ),
        "discount": discount,
        "url": url
    })

return results


# ============================================================
# AGRUPAR POR JOGO
# ============================================================

def build_deal_list(
popular_games,
price_data
):


titles = {
    game["id"]: game["title"]
    for game in popular_games
}

popularity_position = {
    game["id"]: game["position"]
    for game in popular_games
}

result = []

for game_price in price_data:

    game_id = game_price.get(
        "id"
    )

    title = titles.get(
        game_id
    )

    if not title:
        continue

    deals = parse_price_game(
        game_price
    )

    for deal in deals:

        deal["title"] = title

        deal["popularity_position"] = (
            popularity_position.get(
                game_id,
                999999
            )
        )

        result.append(
            deal
        )

return result


# ============================================================
# AGRUPAR PARA O DISCORD
# ============================================================

def group_by_shop(deals):


grouped = {}

for deal in deals:

    shop = deal["shop"]

    if shop not in grouped:
        grouped[shop] = []

    grouped[shop].append(
        deal
    )

return grouped


# ============================================================
# ORDENAR
# ============================================================

def sort_shop_deals(deals):


# Primeiro: jogos mais populares.
# Depois: maior desconto.
# Depois: menor preço.

return sorted(
    deals,
    key=lambda deal: (
        deal["popularity_position"],
        -deal["discount"],
        deal["price"]
    )
)


# ============================================================
# CRIAR LINHA
# ============================================================

def format_deal_line(deal):


title = deal["title"]

price = deal["price"]

regular = deal["regular"]

discount = deal["discount"]

url = deal["url"]

current_text = format_brl(
    price
)

price_text = (
    f"💰 **{current_text}**"
)

if (
    regular is not None
    and regular > price
):

    price_text += (
        f" ~~{format_brl(regular)}~~"
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
# ENVIAR UMA LOJA
# ============================================================

def send_shop_to_discord(
shop_name,
deals
):


if not deals:
    return

lines = []

header = (
    f"🎮 **Promoções — {shop_name}**"
)

current = [
    header
]

length = len(
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
        current
        and length + line_length > 1800
    ):

        lines.append(
            "\n".join(
                current
            )
        )

        current = [
            header
        ]

        length = (
            len(header) + 1
        )

    current.append(
        line
    )

    length += line_length

if current:

    lines.append(
        "\n".join(current)
    )

for message in lines:

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={
            "content": message
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

if not ITAD_API_KEY:
    raise RuntimeError(
        "ITAD_API_KEY não configurado."
    )

if not DISCORD_WEBHOOK_URL:
    raise RuntimeError(
        "DISCORD_WEBHOOK_URL não configurado."
    )

print()
print(
    f"⭐ Buscando os "
    f"{POPULAR_GAMES} jogos mais populares..."
)

popular_games = get_popular_games()

print(
    f"✅ {len(popular_games)} jogos populares encontrados."
)

if not popular_games:
    raise RuntimeError(
        "Nenhum jogo popular foi encontrado."
    )

game_ids = [
    game["id"]
    for game in popular_games
]

print()
print(
    "💰 Buscando promoções "
    f"em até {len(SHOPS)} lojas..."
)

price_data = get_prices(
    game_ids
)

print(
    f"✅ {len(price_data)} jogos retornaram preços."
)

# --------------------------------------------------------
# Transformar preços em ofertas
# --------------------------------------------------------

deals = build_deal_list(
    popular_games,
    price_data
)

print()
print(
    f"🎯 Ofertas que passaram pelos filtros: "
    f"{len(deals)}"
)

# --------------------------------------------------------
# Ordenação geral
# --------------------------------------------------------

deals = sorted(
    deals,
    key=lambda deal: (
        deal["popularity_position"],
        -deal["discount"],
        deal["price"]
    )
)

# Limite geral
deals = deals[:MAX_DEALS]

# --------------------------------------------------------
# Histórico
# --------------------------------------------------------

posted = load_posted()

new_deals = []

for deal in deals:

    title_key = normalize_title(
        deal["title"]
    )

    deal_id = (
        f"{title_key}|"
        f"{deal['shop_id']}|"
        f"{deal['price']}"
    )

    if deal_id in posted:
        continue

    deal["_id"] = deal_id

    new_deals.append(
        deal
    )

print(
    f"🆕 Novas ofertas: "
    f"{len(new_deals)}"
)

# --------------------------------------------------------
# Agrupar por loja
# --------------------------------------------------------

grouped = group_by_shop(
    new_deals
)

published = 0

shop_order = [
    "Steam",
    "Nuuvem",
    "GOG"
]

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

    shop_deals = sort_shop_deals(
        shop_deals
    )

    print()
    print(
        f"📨 Enviando "
        f"{len(shop_deals)} ofertas "
        f"de {shop_name}..."
    )

    try:

        send_shop_to_discord(
            shop_name,
            shop_deals
        )

        for deal in shop_deals:

            posted.add(
                deal["_id"]
            )

        published += len(
            shop_deals
        )

        print(
            f"✅ {len(shop_deals)} "
            f"enviadas."
        )

    except Exception as error:

        print(
            f"❌ Erro em {shop_name}: "
            f"{error}"
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

if **name** == "**main**":
main()
