import io
import time
import html as htmllib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import altair as alt
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="値動き銘柄＆経済ニュース", page_icon="📈", layout="wide")

UA = {"User-Agent": "Mozilla/5.0"}
JST = timezone(timedelta(hours=9))

FALLBACK = {
    "7203": "トヨタ自動車", "6758": "ソニーグループ", "9984": "ソフトバンクグループ", "8306": "三菱UFJフィナンシャル・グループ",
    "6861": "キーエンス", "9983": "ファーストリテイリング", "8035": "東京エレクトロン", "6098": "リクルートホールディングス",
    "9432": "日本電信電話", "7974": "任天堂", "6501": "日立製作所", "8316": "三井住友フィナンシャルグループ", "8058": "三菱商事",
    "4063": "信越化学工業", "6367": "ダイキン工業", "4519": "中外製薬", "6902": "デンソー", "7267": "ホンダ", "8031": "三井物産",
    "9433": "KDDI", "6954": "ファナック", "6594": "ニデック", "4502": "武田薬品工業", "8001": "伊藤忠商事", "7741": "HOYA",
    "6857": "アドバンテスト", "6146": "ディスコ", "4568": "第一三共", "9434": "ソフトバンク", "8411": "みずほフィナンシャルグループ",
    "2914": "JT", "6981": "村田製作所", "6723": "ルネサスエレクトロニクス", "7011": "三菱重工業", "7013": "IHI", "5401": "日本製鉄",
    "4661": "オリエンタルランド", "3382": "セブン&アイ・ホールディングス", "8766": "東京海上ホールディングス", "6503": "三菱電機",
    "7751": "キヤノン", "6752": "パナソニック ホールディングス", "4543": "テルモ", "2802": "味の素", "9020": "JR東日本",
    "9101": "日本郵船", "9104": "商船三井", "5108": "ブリヂストン", "6301": "コマツ", "8802": "三菱地所", "4755": "楽天グループ",
}

JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"

NEWS_FEEDS = {
    "NHK 経済": "https://www3.nhk.or.jp/rss/news/cat5.xml",
    "Yahoo!ニュース 経済": "https://news.yahoo.co.jp/rss/topics/business.xml",
}

CAUSE_KEYWORDS = {
    "決算・業績": ["決算", "業績", "増益", "減益", "赤字", "黒字", "最高益", "営業利益", "純利益", "売上高"],
    "業績予想の修正": ["下方修正", "上方修正", "下振れ", "上振れ", "予想を修正", "見通し"],
    "格付け・目標株価": ["格下げ", "格上げ", "目標株価", "投資判断", "レーティング", "引き下げ", "引き上げ"],
    "不祥事・リスク": ["不正", "不祥事", "訴訟", "提訴", "リコール", "事故", "行政処分", "課徴金", "データ流出", "障害", "調査"],
    "資本政策・配当": ["増資", "公募", "売り出し", "自社株買い", "株式分割", "増配", "減配", "配当", "上場廃止"],
    "M&A・提携": ["買収", "TOB", "提携", "統合", "出資", "合併"],
    "市場全体・マクロ": ["日経平均", "米株", "ダウ", "円高", "円安", "利上げ", "利下げ", "関税", "米国株", "ハイテク株"],
}


def classify(title):
    return [cat for cat, kws in CAUSE_KEYWORDS.items() if any(k in title for k in kws)]


def md_safe(text):
    return text.replace("[", "(").replace("]", ")")


# ---------------- データ取得（キャッシュ付き） ----------------
@st.cache_data(ttl=86400, show_spinner="銘柄リストを読み込み中…")
def load_universe(full: bool):
    if full:
        try:
            r = requests.get(JPX_URL, headers=UA, timeout=30)
            r.raise_for_status()
            df = pd.read_excel(io.BytesIO(r.content))
            df = df[df["市場・商品区分"].astype(str).str.contains("プライム")]
            return dict(zip(df["コード"].astype(str), df["銘柄名"])), "JPX プライム市場"
        except Exception:
            pass
    return FALLBACK, "主要銘柄"


@st.cache_data(ttl=900, show_spinner="株価を取得中…（全銘柄の場合は数分かかります）")
def fetch_changes(names: dict, batch: int = 150):
    codes = list(names.keys())
    rows = []
    for i in range(0, len(codes), batch):
        chunk = [c + ".T" for c in codes[i:i + batch]]
        try:
            df = yf.download(chunk, period="7d", interval="1d", group_by="ticker",
                             auto_adjust=False, progress=False, threads=True)
        except Exception:
            continue
        for t in chunk:
            try:
                close = df[t]["Close"].dropna()
                vol = df[t]["Volume"].dropna()
                if len(close) < 2:
                    continue
                last, prev = float(close.iloc[-1]), float(close.iloc[-2])
                code = t[:-2]
                rows.append({
                    "コード": code, "銘柄名": names.get(code, ""),
                    "終値": round(last, 1), "前日終値": round(prev, 1),
                    "前日比(円)": round(last - prev, 1),
                    "変動率(%)": round((last / prev - 1) * 100, 2),
                    "出来高": int(vol.iloc[-1]) if len(vol) else 0,
                    "日付": str(close.index[-1].date()),
                })
            except Exception:
                continue
    return pd.DataFrame(rows)


@st.cache_data(ttl=900)
def index_change(symbol="^N225"):
    try:
        c = yf.Ticker(symbol).history(period="7d")["Close"].dropna()
        return round((float(c.iloc[-1]) / float(c.iloc[-2]) - 1) * 100, 2) if len(c) >= 2 else None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def history(code):
    return yf.Ticker(code + ".T").history(period="3mo")["Close"]


@st.cache_data(ttl=600)
def fetch_feed(url):
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    return [{"title": it.findtext("title", ""), "link": it.findtext("link", ""),
             "published": it.findtext("pubDate", "")} for it in root.iter("item")]


@st.cache_data(ttl=1800)
def search_stock_news(name, days, limit=5):
    q = quote(f'"{name}" 株 when:{days}d')
    url = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for it in root.iter("item"):
        title = it.findtext("title", "")
        pub = it.findtext("pubDate", "")
        try:
            pub = parsedate_to_datetime(pub).astimezone(JST).strftime("%m/%d %H:%M")
        except Exception:
            pass
        items.append({"title": title, "link": it.findtext("link", ""),
                      "source": it.findtext("source", ""), "date": pub, "tags": classify(title)})
    return items[:limit]


# ---------------- サイドバー ----------------
st.title("📈 値動きの大きい日本株 ＆ 経済ニュース")

with st.sidebar:
    st.header("設定")
    choice = st.radio("対象銘柄", ["主要約50銘柄（高速）", "プライム全銘柄（時間がかかる）"])
    top_n = st.slider("表示件数", 3, 20, 10)
    min_volume = st.number_input("最低出来高（株）", 0, 10_000_000, 100_000, step=50_000)
    lookback = st.slider("要因ニュースの対象期間（日）", 1, 7, 3)
    if st.button("🔄 最新データに更新"):
        st.cache_data.clear()
        st.session_state.pop("report", None)
        st.rerun()

names, universe_label = load_universe(choice.startswith("プライム"))
data = fetch_changes(names)

if data.empty:
    st.error("株価データを取得できませんでした。Yahoo Financeの制限や一時的な障害の可能性があります。"
             "しばらくしてから「最新データに更新」を押してください。")
    st.stop()

data = data[data["出来高"] >= min_volume]
if data.empty:
    st.warning("条件に合う銘柄がありません。サイドバーの最低出来高を下げてください。")
    st.stop()
latest = data["日付"].max()
data = data[data["日付"] == latest]
gainers = data.sort_values("変動率(%)", ascending=False).head(top_n).reset_index(drop=True)
losers = data.sort_values("変動率(%)", ascending=True).head(top_n).reset_index(drop=True)
nikkei = index_change()

c1, c2, c3 = st.columns(3)
c1.metric("対象日", latest)
c2.metric("集計銘柄数", f"{len(data)}（{universe_label}）")
c3.metric("日経平均", f"{nikkei:+.2f}%" if nikkei is not None else "取得不可")
st.caption(f"表示更新: {datetime.now(JST):%Y-%m-%d %H:%M} JST ／ 無料データのため遅延・欠損があり得ます。投資助言ではありません。")

tab_rank, tab_chart, tab_news, tab_cause = st.tabs(["🏆 ランキング", "📊 グラフ", "📰 経済ニュース", "🔍 要因分析"])

# ---------------- ランキング ----------------
with tab_rank:
    st.subheader("上昇率ランキング")
    st.dataframe(gainers, use_container_width=True, hide_index=True)
    st.subheader("下落率ランキング")
    st.dataframe(losers, use_container_width=True, hide_index=True)

# ---------------- グラフ ----------------
with tab_chart:
    movers = pd.concat([gainers, losers]).drop_duplicates("コード").rename(columns={"変動率(%)": "変動率"})
    movers["銘柄"] = movers["コード"] + " " + movers["銘柄名"].str.slice(0, 10)
    movers["方向"] = movers["変動率"].apply(lambda v: "上昇" if v >= 0 else "下落")
    chart = alt.Chart(movers).mark_bar().encode(
        x=alt.X("変動率:Q", title="前日比 (%)"),
        y=alt.Y("銘柄:N", sort="-x", title=None),
        color=alt.Color("方向:N", scale=alt.Scale(domain=["上昇", "下落"], range=["#d62728", "#1f77b4"]), legend=None),
        tooltip=["コード", "銘柄名", "変動率", "終値"],
    ).properties(height=max(250, 26 * len(movers)))
    st.altair_chart(chart, use_container_width=True)

    st.subheader("上位銘柄の3か月チャート")
    for label, df in (("上昇上位", gainers.head(3)), ("下落上位", losers.head(3))):
        st.markdown(f"**{label}**")
        cols = st.columns(len(df))
        for col, (_, r) in zip(cols, df.iterrows()):
            with col:
                st.caption(f'{r["コード"]} {r["銘柄名"][:12]}  {r["変動率(%)"]:+.1f}%')
                try:
                    st.line_chart(history(r["コード"]), height=180)
                except Exception:
                    st.write("チャートを取得できませんでした")

# ---------------- 経済ニュース ----------------
with tab_news:
    for source, url in NEWS_FEEDS.items():
        st.subheader(source)
        try:
            for e in fetch_feed(url)[:10]:
                st.markdown(f"- [{md_safe(e['title'])}]({e['link']})  \n  {e['published']}")
        except Exception as ex:
            st.write(f"取得できませんでした: {ex}")

# ---------------- 要因分析 ----------------
def render_report(report):
    for item in report:
        arrow = "📈" if item["変動率"] >= 0 else "📉"
        st.markdown(f'#### {arrow} {item["コード"]} {item["銘柄名"]}　{item["変動率"]:+.2f}%')
        if nikkei is not None and abs(nikkei) >= 1 and (nikkei > 0) == (item["変動率"] > 0):
            st.caption(f"参考: 日経平均も {nikkei:+.2f}% と同じ方向に動いており、市場全体の影響も考えられます。")
        elif nikkei is not None:
            st.caption(f"参考: 日経平均は {nikkei:+.2f}%")
        if item["error"]:
            st.write(f"ニュースを取得できませんでした: {item['error']}")
        elif item["tags"]:
            st.markdown(f"**要因の候補（見出しからの分類）:** {'、'.join(item['tags'])}")
        else:
            st.markdown("**関連する報道が見つからず、要因は特定できません。**")
        for a in item["articles"]:
            tg = f"　`{'・'.join(a['tags'])}`" if a["tags"] else ""
            st.markdown(f"- [{md_safe(a['title'])}]({a['link']})  \n  {a['source']} / {a['date']}{tg}")


with tab_cause:
    st.info("値動きの大きい銘柄ごとに、直近の関連ニュースを検索し、見出しの言葉から要因の「候補」を分類します。"
            "因果関係を証明するものではありません。根拠の記事リンクを必ず確認してください。")
    target = st.radio("対象", ["下落", "上昇", "両方"], horizontal=True)
    if st.button("要因を調べる"):
        frames = []
        if target in ("下落", "両方"):
            frames.append(losers)
        if target in ("上昇", "両方"):
            frames.append(gainers)
        targets = pd.concat(frames).reset_index(drop=True)
        report = []
        bar = st.progress(0.0, text="ニュースを検索中…")
        for i, (_, r) in enumerate(targets.iterrows()):
            try:
                arts, err = search_stock_news(r["銘柄名"], lookback), ""
            except Exception as ex:
                arts, err = [], str(ex)
            report.append({"コード": r["コード"], "銘柄名": r["銘柄名"], "変動率": r["変動率(%)"],
                           "articles": arts, "error": err,
                           "tags": sorted({t for a in arts for t in a["tags"]})})
            bar.progress((i + 1) / len(targets), text=f"ニュースを検索中… {i + 1}/{len(targets)}")
            time.sleep(0.3)
        bar.empty()
        st.session_state["report"] = report

    report = st.session_state.get("report")
    if report:
        render_report(report)
        csv = pd.DataFrame([{
            "コード": x["コード"], "銘柄名": x["銘柄名"], "変動率(%)": x["変動率"],
            "要因の候補": "、".join(x["tags"]) if x["tags"] else "特定できず",
            "根拠（見出し）": " | ".join(a["title"] for a in x["articles"]),
            "根拠（URL）": " | ".join(a["link"] for a in x["articles"]),
        } for x in report]).to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSVでダウンロード", csv, "要因レポート.csv", "text/csv")
