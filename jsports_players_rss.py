import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from xml.etree.ElementTree import Element, SubElement, ElementTree
from email.utils import format_datetime
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import re

BASE_URL = "https://www.jsports.co.jp"
LIST_URL = "https://www.jsports.co.jp/rugby/university/player/"

STATE_FILE = "jsports_players_state.json"
RSS_FILE = "jsports_players.xml"

JST = timezone(timedelta(hours=9))

headers = {
    "User-Agent": "Mozilla/5.0"
}


# --------------------------------------------------
# ページ取得
# --------------------------------------------------

def get_page(url):
    try:
        r = requests.get(
            url,
            headers=headers,
            timeout=30
        )
        r.raise_for_status()
        return r

    except requests.RequestException as e:
        print("取得失敗:", url)
        print("理由:", e)
        return None


# --------------------------------------------------
# 現在の選手一覧を取得
# --------------------------------------------------

r = get_page(LIST_URL)

if r is None:
    print()
    print("J SPORTSを取得できなかったため、今回は更新しません。")
    print("既存データをそのまま維持します。")
    raise SystemExit(0)

print("HTTP:", r.status_code)

soup = BeautifulSoup(r.text, "html.parser")

players = {}

for a in soup.find_all("a", href=True):

    link = urljoin(
        BASE_URL,
        a["href"]
    )

    # 個別選手ページだけを対象
    if not re.fullmatch(
        r"https://www\.jsports\.co\.jp/rugby/university/player/\d+/",
        link
    ):
        continue

    name = " ".join(
        a.stripped_strings
    ).strip()

    if not name:
        continue

    players[link] = name


print("現在の選手数:", len(players))

# 異常取得時に既存データを壊さない
if len(players) < 10:
    print()
    print("選手数が異常に少ないため、今回は更新しません。")
    print("サイト構造変更の可能性があります。")
    raise SystemExit(0)


# --------------------------------------------------
# URL順に固定
# --------------------------------------------------

current_state = {
    url: players[url]
    for url in sorted(players.keys())
}


# --------------------------------------------------
# 前回の選手一覧を読み込む
# --------------------------------------------------

old_state = None

if os.path.exists(STATE_FILE):
    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            old_state = json.load(f)

    except Exception as e:
        print("既存STATE読み込みエラー:", e)
        print("安全のため今回は更新しません。")
        raise SystemExit(0)


# --------------------------------------------------
# 初回実行
# --------------------------------------------------

if old_state is None:

    print()
    print("初回実行です。")
    print("現在の選手一覧を基準データとして保存します。")

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            current_state,
            f,
            ensure_ascii=False,
            indent=2
        )

    # 初回RSS作成
    rss = Element(
        "rss",
        version="2.0"
    )

    channel = SubElement(
        rss,
        "channel"
    )

    SubElement(
        channel,
        "title"
    ).text = "J SPORTS 大学ラグビー 注目選手 更新情報"

    SubElement(
        channel,
        "link"
    ).text = LIST_URL

    SubElement(
        channel,
        "description"
    ).text = "J SPORTS 大学ラグビー注目選手ページの更新を検知します"

    SubElement(
        channel,
        "language"
    ).text = "ja"

    tree = ElementTree(rss)

    tree.write(
        RSS_FILE,
        encoding="utf-8",
        xml_declaration=True
    )

    print("基準選手数:", len(current_state))
    print("保存:", STATE_FILE)
    print("保存:", RSS_FILE)
    print()
    print("初期化完了")
    raise SystemExit(0)


# --------------------------------------------------
# 前回との差分を調べる
# --------------------------------------------------

old_urls = set(old_state.keys())
current_urls = set(current_state.keys())

added_urls = current_urls - old_urls
removed_urls = old_urls - current_urls

renamed = []

for url in current_urls & old_urls:

    if current_state[url] != old_state[url]:
        renamed.append(
            (
                url,
                old_state[url],
                current_state[url]
            )
        )


print()
print("追加:", len(added_urls), "件")
print("削除:", len(removed_urls), "件")
print("名称変更:", len(renamed), "件")


# --------------------------------------------------
# 変更なし
# --------------------------------------------------

if (
    not added_urls
    and not removed_urls
    and not renamed
):

    print()
    print("選手一覧に変更はありません。")
    print("RSSは更新しません。")
    raise SystemExit(0)


# --------------------------------------------------
# 変更内容を表示
# --------------------------------------------------

for url in sorted(added_urls):
    print(
        "追加:",
        current_state[url],
        url
    )

for url in sorted(removed_urls):
    print(
        "削除:",
        old_state[url],
        url
    )

for url, old_name, new_name in renamed:
    print(
        "変更:",
        old_name,
        "→",
        new_name,
        url
    )


# --------------------------------------------------
# 既存RSSを読み込む
# --------------------------------------------------

old_rss_items = []

if os.path.exists(RSS_FILE):

    try:
        old_tree = ElementTree()
        old_tree.parse(RSS_FILE)
        old_root = old_tree.getroot()

        for item in old_root.findall(
            "./channel/item"
        ):

            old_rss_items.append({
                "title": item.findtext(
                    "title",
                    ""
                ),
                "link": item.findtext(
                    "link",
                    ""
                ),
                "guid": item.findtext(
                    "guid",
                    ""
                ),
                "pubDate": item.findtext(
                    "pubDate",
                    ""
                ),
                "description": item.findtext(
                    "description",
                    ""
                )
            })

    except Exception as e:
        print("既存RSS読み込みエラー:", e)
        print("安全のため今回は更新しません。")
        raise SystemExit(0)


# --------------------------------------------------
# 今回の変更内容
# --------------------------------------------------

now = datetime.now(JST)

description_lines = []

if added_urls:

    description_lines.append(
        f"追加: {len(added_urls)}名"
    )

    for url in sorted(added_urls):
        description_lines.append(
            f"+ {current_state[url]}"
        )

if removed_urls:

    description_lines.append(
        f"削除: {len(removed_urls)}名"
    )

    for url in sorted(removed_urls):
        description_lines.append(
            f"- {old_state[url]}"
        )

if renamed:

    description_lines.append(
        f"名称変更: {len(renamed)}名"
    )

    for url, old_name, new_name in renamed:
        description_lines.append(
            f"{old_name} → {new_name}"
        )


description = "\n".join(
    description_lines
)

title = (
    "J SPORTS 大学ラグビー "
    "注目選手ページが更新されました"
)

# 毎回異なるGUIDにする
change_key = (
    now.isoformat()
    + description
)

guid = hashlib.sha256(
    change_key.encode("utf-8")
).hexdigest()


new_item = {
    "title": title,
    "link": LIST_URL,
    "guid": guid,
    "pubDate": format_datetime(now),
    "description": description
}


# --------------------------------------------------
# RSS作成
# --------------------------------------------------

rss = Element(
    "rss",
    version="2.0"
)

channel = SubElement(
    rss,
    "channel"
)

SubElement(
    channel,
    "title"
).text = "J SPORTS 大学ラグビー 注目選手 更新情報"

SubElement(
    channel,
    "link"
).text = LIST_URL

SubElement(
    channel,
    "description"
).text = "J SPORTS 大学ラグビー注目選手ページの更新を検知します"

SubElement(
    channel,
    "language"
).text = "ja"


# 今回の変更を先頭に追加
items = [new_item] + old_rss_items

# 履歴は最大50件
items = items[:50]


for data in items:

    item = SubElement(
        channel,
        "item"
    )

    SubElement(
        item,
        "title"
    ).text = data["title"]

    SubElement(
        item,
        "link"
    ).text = data["link"]

    guid_element = SubElement(
        item,
        "guid",
        isPermaLink="false"
    )

    guid_element.text = data["guid"]

    SubElement(
        item,
        "pubDate"
    ).text = data["pubDate"]

    SubElement(
        item,
        "description"
    ).text = data["description"]


# --------------------------------------------------
# RSS保存
# --------------------------------------------------

tree = ElementTree(rss)

tree.write(
    RSS_FILE,
    encoding="utf-8",
    xml_declaration=True
)


# --------------------------------------------------
# 新しい状態を保存
#
# RSS生成が成功した後に更新する
# --------------------------------------------------

with open(
    STATE_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        current_state,
        f,
        ensure_ascii=False,
        indent=2
    )


print()
print("変更を検知しました。")
print("RSSに新着を追加しました。")
print("保存:", RSS_FILE)
print("基準データ更新:", STATE_FILE)