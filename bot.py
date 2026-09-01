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

# IDs do IsThereAnyDeal

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
```

def save_posted(posted):

```
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
```

# ============================================================

# FORMATAÇÃO

# ============================================================

def format_brl(value):

```
if value is None:
    return "Preço indisponível"

return (
    f"R$ {value:,.2f}"
    .replace(",", "X")
    .replace(".", ",")
    .replace("X", ".")
)
```

# ============================================================

# NORMALIZAR TÍTULO

# ============================================================

def normalize_title(title):

```
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
```

# ============================================================

# BUSCAR LOJAS NO ITAD

# ============================================================

def get_shop_ids():

```
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
```

# ============================================================

# BUSCAR PROMOÇÕES

# ============================================================

def get_deals(shop_ids):

```
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
```

# ============================================================

# VERIFICAR WINDOWS

# ============================================================

def is_windows_deal(deal):

```
if not isinstance(deal, dict):
    return False

deal_info = deal.get("deal", {})

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
```

# ============================================================

# VERIFICAR SE É JOGO

# ============================================================

def is_game(deal):

```
if not isinstance(deal, dict):
    return False

info = extract_deal(deal)

title = info["title"]

title_lower = title.lower()

# Bloqueia produtos conhecidos que não são jogos
for keyword in BLOCKED_KEYWORDS:

    if keyword in title_lower:

        return False

deal_type = deal.get("type")

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
```

# ============================================================

# OBTER DADOS DA OFERTA

# ============================================================

def extract_deal(deal):

```
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
```

# ============================================================

# PUBLICAR NO DISCORD

# ============================================================

def send_to_discord(deal):

```
if not DISCORD_WEBHOOK_URL:

    raise RuntimeError(
        "DISCORD_WEBHOOK_URL não configurado."
    )

info = extract_deal(deal)

title = info["title"]
current_price = info["current_price"]
regular_price = info["regular_price"]
discount = info["discount"]
url = info["url"]

if not url:
    url = "https://isthereanydeal.com/"

# Preço atual
if current_price is not None:

    current_text = format_brl(
        current_price
    )

else:

    current_text = "Grátis"

description = (
    f"💰 **{current_text}**"
)

# Preço original
if (
    regular_price is not None
    and current_price is not None
    and regular_price > current_price
):

    description += (
        f" ~~{format_brl(regular_price)}~~"
    )

# Desconto
description += (
    f"\n📉 **{discount:g}% OFF**"
)

embed = {

    "title": f"🔥 {title}",

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
```

# ============================================================

# PRINCIPAL

# ============================================================

def main():

```
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
# VERIFICAR CONFIGURAÇÃO
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

    # Desconto mínimo
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
# MELHOR OFERTA DE CADA JOGO
# --------------------------------------------------------

best_deals = {}

for deal in filtered:

    info = extract_deal(
        deal
    )

    title = info["title"]
    discount = info["discount"]
    price = info["current_price"]

    game_key = normalize_title(
        title
    )

    if not game_key:
        continue

    # Primeira oferta encontrada
    if game_key not in best_deals:

        best_deals[
            game_key
        ] = deal

        continue

    old_deal = best_deals[
        game_key
    ]

    old_info = extract_deal(
        old_deal
    )

    old_discount = (
        old_info["discount"]
    )

    old_price = (
        old_info["current_price"]
    )

    # --------------------------------------------
    # REGRA 1:
    # MAIOR DESCONTO VENCE
    # --------------------------------------------

    if discount > old_discount:

        best_deals[
            game_key
        ] = deal

    # --------------------------------------------
    # REGRA 2:
    # MESMO DESCONTO
    # MENOR PREÇO VENCE
    # --------------------------------------------

    elif discount == old_discount:

        if (
            price is not None
            and old_price is not None
            and price < old_price
        ):

            best_deals[
                game_key
            ] = deal

print()
print(
    f"🏆 Melhores ofertas únicas: "
    f"{len(best_deals)}"
)

# --------------------------------------------------------
# ORDENAR
# --------------------------------------------------------

# Primeiro os maiores descontos
sorted_deals = sorted(
    best_deals.values(),
    key=lambda deal: (
        -extract_deal(deal)["discount"],
        extract_deal(deal)["current_price"]
        if extract_deal(deal)["current_price"]
        is not None
        else float("inf")
    )
)

# --------------------------------------------------------
# PUBLICAR
# --------------------------------------------------------

posted = load_posted()

published = 0

for deal in sorted_deals:

    if published >= MAX_DEALS:
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
            f"{title}"
        )

        continue

    try:

        print(
            f"📢 Publicando: "
            f"{title} - "
            f"{shop} - "
            f"{discount:g}% OFF"
        )

        send_to_discord(
            deal
        )

        posted.add(
            deal_id
        )

        published += 1

    except Exception as error:

        print(
            f"❌ Erro ao publicar "
            f"{title}: {error}"
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
```

# ============================================================

# EXECUTAR

# ============================================================

if **name** == "**main**":

```
main()
```
