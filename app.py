import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import altair as alt
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

JST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0"}
st.set_page_config(page_title="Market Lens｜日経ニュースと値動き上位10社", page_icon="📊", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Noto+Sans+JP:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'DM Sans','Noto Sans JP',sans-serif}
.stApp{background:#f5f7fb;color:#17233b}
.block-container{max-width:1450px;padding-top:1.2rem;padding-bottom:3rem;padding-left:clamp(1rem,3vw,2.4rem);padding-right:clamp(1rem,3vw,2.4rem)}
.hero{background:radial-gradient(circle at 90% 0%,#526bd866,transparent 32%),linear-gradient(125deg,#17264c,#2d4ca8 68%,#4267e8);color:white;border-radius:22px;padding:clamp(1.3rem,3vw,2.1rem);margin-bottom:1.2rem;box-shadow:0 14px 36px #203a801c}
.hero .eyebrow{color:#d6e0ff;font-size:.75rem;letter-spacing:.13em;font-weight:800}
.hero h1{color:white!important;font-size:clamp(1.7rem,3.4vw,2.6rem);letter-spacing:-.04em;margin:.45rem 0}
.hero p{color:#e5ebff;max-width:800px;line-height:1.7;margin:0}
div[data-testid="stMetric"]{background:white;border:1px solid #e5eaf2;border-radius:16px;padding:1rem;box-shadow:0 4px 15px #1e2d4b08}
div[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:.35rem;border-bottom:1px solid #e5eaf2;padding-bottom:.4rem}
div[data-testid="stTabs"] button{border-radius:10px;font-weight:700;padding:.6rem .8rem}
div[data-testid="stTabs"] button[aria-selected="true"]{background:#eaf0ff;color:#294dc9}
.stButton>button,.stDownloadButton>button{border-radius:10px;font-weight:700}
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid #e5eaf2}
@media(max-width:760px){.block-container{padding-top:.7rem}.hero{border-radius:16px}div[data-testid="stMetric"]{padding:.7rem}div[data-testid="stMetricValue"]{font-size:1.2rem}div[data-testid="stTabs"] [data-baseweb="tab-list"]{overflow-x:auto;gap:.15rem}div[data-testid="stTabs"] button{padding:.5rem .55rem;font-size:.8rem}}
</style>
""", unsafe_allow_html=True)

# ---- 値動きランキングの対象銘柄（コード: 表示名） ----
JP = {
    "7203.T": "トヨタ自動車", "6758.T": "ソニーグループ", "9984.T": "ソフトバンクグループ",
    "8306.T": "三菱UFJフィナンシャル・グループ", "7974.T": "任天堂", "8035.T": "東京エレクトロン",
    "6857.T": "アドバンテスト", "7011.T": "三菱重工業", "9432.T": "NTT", "8058.T": "三菱商事",
    "6501.T": "日立製作所", "6098.T": "リクルートホールディングス", "9983.T": "ファーストリテイリング",
    "8316.T": "三井住友フィナンシャルグループ", "8411.T": "みずほフィナンシャルグループ",
    "6861.T": "キーエンス", "4063.T": "信越化学工業", "6367.T": "ダイキン工業", "6954.T": "ファナック",
    "7267.T": "ホンダ", "7741.T": "HOYA", "4502.T": "武田薬品工業", "9433.T": "KDDI",
    "9434.T": "ソフトバンク", "8001.T": "伊藤忠商事", "8031.T": "三井物産", "6902.T": "デンソー",
    "6981.T": "村田製作所", "6594.T": "ニデック", "6723.T": "ルネサスエレクトロニクス",
    "6146.T": "ディスコ", "7013.T": "IHI", "5401.T": "日本製鉄", "4568.T": "第一三共",
    "6326.T": "クボタ", "7751.T": "キヤノン", "2914.T": "JT",
}
US = {
    "AAPL": "アップル", "MSFT": "マイクロソフト", "NVDA": "エヌビディア", "AMZN": "アマゾン",
    "GOOGL": "アルファベット", "META": "メタ・プラットフォームズ", "TSLA": "テスラ", "JPM": "JPモルガン",
    "AMD": "AMD", "AVGO": "ブロードコム", "NFLX": "ネットフリックス", "ORCL": "オラクル",
    "CRM": "セールスフォース", "INTC": "インテル", "MU": "マイクロン・テクノロジー",
    "QCOM": "クアルコム", "PLTR": "パランティア", "COST": "コストコ", "WMT": "ウォルマート",
    "V": "ビザ", "MA": "マスターカード", "BAC": "バンク・オブ・アメリカ", "XOM": "エクソンモービル",
    "LLY": "イーライリリー", "UNH": "ユナイテッドヘルス", "DIS": "ウォルト・ディズニー",
    "BA": "ボーイング", "UBER": "ウーバー", "KO": "コカ・コーラ", "PFE": "ファイザー",
}


# ---- 日経ニュース取得（Googleニュース経由で日経の記事のみ） ----
def _clean_title(title, source):
    for suffix in (f" - {source}", " - 日本経済新聞", " - 日経電子版"):
        if suffix.strip(" -") and title.endswith(suffix):
            return title[: -len(suffix)].strip()
    return title.strip()


@st.cache_data(ttl=600, show_spinner=False)
def nikkei_news(query, days=3):
    """site:nikkei.com で絞った最新記事を新しい順で返す。"""
    url = "https://news.google.com/rss/search?q=" + quote(f"{query} when:{days}d") + "&hl=ja&gl=JP&ceid=JP:ja"
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return []
    out = []
    for it in root.iter("item"):
        source = (it.findtext("source", "") or "").strip()
        title = _clean_title(it.findtext("title", "") or "", source)
        try:
            published = parsedate_to_datetime(it.findtext("pubDate", "")).astimezone(JST)
        except Exception:
            published = None
        out.append({"title": title, "link": it.findtext("link", ""), "source": source or "日本経済新聞", "published": published})
    # 日経グループの記事に限定（Nikkei Asia など英語媒体は除外）。該当が無ければ全件を使う
    nikkei_only = [x for x in out if "日本経済新聞" in x["source"] or "日経" in x["source"]]
    out = nikkei_only or out
    out.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=JST), reverse=True)
    return out


@st.cache_data(ttl=600, show_spinner=False)
def latest_nikkei(days=2):
    """トップ・市場・経済など複数の検索をまとめて重複を除き、新しい順に並べる。"""
    merged, seen = [], set()
    for q in ("site:nikkei.com", "site:nikkei.com 株価 市場", "site:nikkei.com 経済 企業"):
        for x in nikkei_news(q, days):
            if x["title"] not in seen:
                seen.add(x["title"])
                merged.append(x)
    merged.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=JST), reverse=True)
    return merged


def show_news(items, limit=20, empty_msg="日経の記事を取得できませんでした。しばらくしてから「データを更新」を押してください。"):
    if not items:
        st.info(empty_msg)
        return
    for x in items[:limit]:
        title = x["title"].replace("[", "［").replace("]", "］")
        when = x["published"].strftime("%Y-%m-%d %H:%M") if x["published"] else ""
        if x.get("link"):
            st.markdown(f"**[{title}]({x['link']})**")
        else:
            st.markdown(f"**{title}**")
        st.caption(f"{x['source']}　{when}")


# ---- 株価取得 ----
@st.cache_data(ttl=900, show_spinner=False)
def history(ticker, period="3mo"):
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        col = "Date" if "Date" in df.columns else "Datetime"
        df = df.rename(columns={col: "日付", "Close": "終値", "Volume": "出来高"})
        df["日付"] = pd.to_datetime(df["日付"]).dt.tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def daily_moves(tickers):
    """対象銘柄の直近終値と前日比(%)をまとめて取得する。"""
    tickers = list(tickers)
    try:
        data = yf.download(tickers, period="10d", interval="1d", group_by="ticker",
                           auto_adjust=True, progress=False, threads=True)
    except Exception:
        return pd.DataFrame()
    rows = []
    for t in tickers:
        try:
            close = data[t]["Close"].dropna()
            if len(close) >= 2:
                rows.append({"コード": t, "終値": float(close.iloc[-1]),
                             "前日比(%)": float((close.iloc[-1] / close.iloc[-2] - 1) * 100),
                             "日付": close.index[-1].strftime("%Y-%m-%d")})
        except Exception:
            continue
    return pd.DataFrame(rows)


with st.sidebar:
    st.markdown("## 📊 Market Lens")
    st.caption("日経ニュース × 値動き上位10社")
    market = st.radio("対象市場", ["日米まとめ", "日本株", "米国株"])
    if st.button("🔄 データを更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("無料公開データ中心。株価やニュースには遅延・欠損・取得制限が発生する場合があります。")

st.markdown("""<div class="hero"><div class="eyebrow">MARKET LENS · NIKKEI & MOVERS</div><h1>日経の最新ニュースと、値動きの大きい10社。</h1><p>日本経済新聞の最新記事と、前日比の動きが大きかった上位10社の株価・関連ニュースをまとめて確認できます。</p></div>""", unsafe_allow_html=True)

if market == "日本株":
    indexes = {"日経平均": "^N225", "TOPIX": "1306.T"}
elif market == "米国株":
    indexes = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "NYダウ": "^DJI"}
else:
    indexes = {"日経平均": "^N225", "S&P 500": "^GSPC", "NASDAQ": "^IXIC", "ドル円": "JPY=X"}
mc = st.columns(len(indexes))
for i, (label, ticker) in enumerate(indexes.items()):
    df = history(ticker, "7d")
    with mc[i]:
        if len(df) >= 2:
            p = df["終値"].dropna()
            st.metric(label, f"{p.iloc[-1]:,.2f}", f"{(p.iloc[-1] / p.iloc[-2] - 1) * 100:+.2f}%")
        else:
            st.metric(label, "取得不可")
st.caption(f"更新確認：{datetime.now(JST):%Y-%m-%d %H:%M} JST ・ 無料データのためリアルタイム配信を保証しません。")

t_news, t_stock = st.tabs(["📰 日経ニュース", "📈 値動き上位10社"])

with t_news:
    st.subheader("日本経済新聞 最新記事")
    limit = st.slider("表示件数", 10, 50, 20, step=5)
    show_news(latest_nikkei(2), limit)

with t_stock:
    st.subheader("値動きが激しかった上位10社と関連ニュース")
    st.caption("対象銘柄の前日比(%)の絶対値が大きい順に10社を表示します。関連ニュースは日経の記事のみです。")

    if market == "日本株":
        universe = {**JP}
    elif market == "米国株":
        universe = {**US}
    else:
        universe = {**JP, **US}

    with st.spinner("株価を取得しています…"):
        moves = daily_moves(tuple(universe))

    if moves.empty:
        st.warning("株価を取得できませんでした。しばらくしてから「データを更新」を押してください。")
    else:
        # 米国株は円換算して表示する（ドル円レートを使用）
        fx_df = history("JPY=X", "3mo")
        fx_df = fx_df[["日付", "終値"]].rename(columns={"終値": "レート"}).dropna() if not fx_df.empty else pd.DataFrame()
        if not fx_df.empty:
            fx_df["日付"] = fx_df["日付"].astype("datetime64[ns]")
            fx_df = fx_df.sort_values("日付")
        fx_rate = float(fx_df["レート"].iloc[-1]) if not fx_df.empty else None
        if fx_rate is None and market != "日本株":
            st.warning("ドル円レートを取得できなかったため、米国株はドル表示になります。")
        st.caption("米国株は円換算で表示しています" + (f"（1ドル＝{fx_rate:,.2f}円で換算）。" if fx_rate else "。") + "前日比(%)は各銘柄の現地価格ベースです。")

        moves["名称"] = moves["コード"].map(universe)
        moves["abs"] = moves["前日比(%)"].abs()
        top = moves.sort_values("abs", ascending=False).head(10).reset_index(drop=True)

        for rank, row in top.iterrows():
            code, name = row["コード"], row["名称"]
            is_jp = code.endswith(".T")
            to_yen = (not is_jp) and fx_rate is not None
            unit = "ドル" if ((not is_jp) and fx_rate is None) else "円"
            price = row["終値"] * fx_rate if to_yen else row["終値"]
            price_text = f"{price:,.0f} 円" if unit == "円" else f"{price:,.2f} ドル"
            with st.container(border=True):
                st.markdown(f"### {rank + 1}位　{name}（{code}）")
                left, right = st.columns([1.1, 1])
                with left:
                    m1, m2 = st.columns(2)
                    m1.metric("直近終値", price_text)
                    m2.metric("前日比", f"{row['前日比(%)']:+.2f}%")
                    h = history(code, "3mo")
                    if not h.empty and to_yen:
                        h["日付"] = h["日付"].astype("datetime64[ns]")
                        h = pd.merge_asof(h.sort_values("日付"), fx_df, on="日付", direction="backward")
                        h["レート"] = h["レート"].fillna(fx_rate)
                        h["終値"] = h["終値"] * h["レート"]
                    if not h.empty:
                        chart = alt.Chart(h).mark_line(strokeWidth=2.2).encode(
                            x=alt.X("日付:T", title=None),
                            y=alt.Y("終値:Q", title=f"終値（{unit}）", scale=alt.Scale(zero=False)),
                            tooltip=["日付:T", alt.Tooltip("終値:Q", format=",.0f" if unit == "円" else ",.2f")],
                        ).properties(height=200)
                        st.altair_chart(chart, use_container_width=True)
                with right:
                    st.markdown("**関連ニュース（日経）**")
                    items = nikkei_news(f'site:nikkei.com "{name}"', 14)
                    show_news(items, 4, empty_msg="直近2週間の日経の関連記事は見つかりませんでした。")

st.divider()
st.caption("このアプリは情報整理を支援するもので、投資助言ではありません。見出しから因果関係は断定できません。重要な情報は一次資料・複数の情報源で確認してください。")
