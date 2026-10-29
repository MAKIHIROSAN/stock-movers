import html
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import altair as alt
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

JST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0"}
st.set_page_config(page_title="Market Lens｜経済ニュースと株価", page_icon="📊", layout="wide")

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

GLOSSARY = {
"CPI":("消費者物価指数","商品やサービスの価格が全体としてどれくらい変化したかを示す指標。米国CPIは金融政策や金利見通しを通じて株価・為替に影響することがあります。"),
"GDP":("国内総生産","一定期間に国内で生み出された付加価値の合計。経済全体の規模や成長率を見る指標です。"),
"FOMC":("米連邦公開市場委員会","米国の金融政策を決める会合。政策金利や声明、議長会見が株式・債券・為替市場を動かすことがあります。"),
"政策金利":("中央銀行が金融政策で誘導する金利","借入コストや預金金利、為替などに影響します。株価への影響は景気や市場予想によって異なります。"),
"利上げ":("政策金利を引き上げること","借入コスト上昇や通貨高要因になり得ますが、株価への影響は景気や事前予想によって異なります。"),
"利下げ":("政策金利を引き下げること","資金調達をしやすくする効果が期待されます。一方、景気悪化への対応の場合は株価にマイナスとなることもあります。"),
"インフレ":("物価が継続的に上昇すること","同じお金で買える量が減る状態。企業コストや中央銀行の金利判断に影響します。"),
"円高":("円の価値が他通貨に対して上がること","例：1ドル150円から145円へ。輸入コストには追い風になりやすく、輸出企業には逆風となる場合があります。"),
"円安":("円の価値が他通貨に対して下がること","例：1ドル145円から150円へ。輸出企業には追い風となる場合がある一方、輸入コストは上がりやすくなります。"),
"PER":("株価収益率","株価が1株当たり利益の何倍かを示します。業種や成長期待によって適正水準は異なります。"),
"PBR":("株価純資産倍率","株価が1株当たり純資産の何倍かを示す指標。資産の質や収益性も合わせて確認します。"),
"出来高":("一定期間に売買された株数","増加は市場の関心が高まった可能性を示しますが、売買の方向そのものを示すわけではありません。"),
"ボラティリティ":("価格変動の大きさ","価格がどのくらい上下するかを表します。高いほど短期間で大きく動く傾向があります。"),
"関税":("輸入品に課される税金","輸入品の価格や企業の調達コスト、貿易関係に影響し、特定の業種の株価材料になることがあります。"),
"決算":("企業が業績や財務状況を公表すること","売上高、営業利益、純利益、会社予想などを確認します。市場予想との差が株価材料になることがあります。"),
"営業利益":("本業で稼いだ利益","売上高から売上原価や販売費・一般管理費などを差し引いた利益で、本業の収益力を見る際に使われます。"),
"ETF":("取引所に上場している投資信託","株式と同じように市場で売買できます。投資対象やリスクは商品ごとに異なります。"),
"リセッション":("景気後退","経済活動が広く弱まる局面。定義は国や機関によって異なることがあります。"),
"ガイダンス":("企業などが示す今後の見通し","過去の実績だけでなく、会社が示す将来予想が株価を大きく動かすことがあります。"),
}
JP = {"^N225":"日経平均","1306.T":"TOPIX","7203.T":"トヨタ自動車","6758.T":"ソニーグループ","9984.T":"ソフトバンクグループ","8306.T":"三菱UFJ FG","7974.T":"任天堂","8035.T":"東京エレクトロン","6857.T":"アドバンテスト","7011.T":"三菱重工業","9432.T":"NTT","8058.T":"三菱商事"}
US = {"^GSPC":"S&P 500","^IXIC":"NASDAQ","^DJI":"NYダウ","AAPL":"Apple","MSFT":"Microsoft","NVDA":"NVIDIA","AMZN":"Amazon","GOOGL":"Alphabet","META":"Meta","TSLA":"Tesla","JPM":"JPMorgan","AMD":"AMD"}
FEEDS = [
("NHK 経済","https://www3.nhk.or.jp/rss/news/cat5.xml"),
("Yahoo!ニュース 経済","https://news.yahoo.co.jp/rss/topics/business.xml"),
("Googleニュース 世界経済","https://news.google.com/rss/search?q="+quote("world economy markets inflation central bank")+"&hl=ja&gl=JP&ceid=JP:ja")
]

@st.cache_data(ttl=900, show_spinner=False)
def feed(url):
    try:
        r=requests.get(url,headers=UA,timeout=15); r.raise_for_status()
        root=ET.fromstring(r.content); out=[]
        for it in root.iter("item"):
            out.append({"title":it.findtext("title",""),"link":it.findtext("link",""),"published":it.findtext("pubDate",""),"source":it.findtext("source","")})
        return out
    except Exception: return []

@st.cache_data(ttl=900, show_spinner=False)
def history(ticker, period="3mo"):
    try:
        df=yf.Ticker(ticker).history(period=period,interval="1d")
        if df.empty: return pd.DataFrame()
        df=df.reset_index()
        col="Date" if "Date" in df.columns else "Datetime"
        df=df.rename(columns={col:"日付","Close":"終値","Volume":"出来高"})
        df["日付"]=pd.to_datetime(df["日付"]).dt.tz_localize(None)
        return df
    except Exception: return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def search_news(q, days=7):
    url="https://news.google.com/rss/search?q="+quote(f"{q} when:{days}d")+"&hl=ja&gl=JP&ceid=JP:ja"
    return feed(url)[:15]

def term_buttons(text):
    found=[t for t in GLOSSARY if t.lower() in text.lower()]
    if not found: return
    cols=st.columns(min(4,len(found)))
    for i,t in enumerate(found[:8]):
        with cols[i%len(cols)]:
            with st.popover("❔ "+t,use_container_width=True):
                st.markdown("**"+GLOSSARY[t][0]+"**")
                st.write(GLOSSARY[t][1])

def show_news(items, limit=15):
    if not items:
        st.info("ニュースを取得できませんでした。検索語や期間を変えてください。")
        return
    for x in items[:limit]:
        title=x.get("title","")
        st.markdown(f"**{title}**")
        st.caption(f'{x.get("source") or "ニュース配信元"}　{x.get("published","")}')
        if x.get("link"): st.markdown(f"[元記事を読む ↗]({x['link']})")
        term_buttons(title)
        st.divider()

with st.sidebar:
    st.markdown("## 📊 Market Lens")
    st.caption("経済ニュース × 株価分析")
    market=st.radio("対象市場",["日米まとめ","日本市場","米国市場"])
    days=st.select_slider("ニュース対象期間",[1,3,7,14],value=7,format_func=lambda x:f"過去{x}日")
    search_q=st.text_input("ニュース検索",placeholder="例：日銀、半導体、NVIDIA")
    if st.button("🔄 データを更新",use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.divider()
    st.caption("無料公開データ中心。株価やニュースには遅延・欠損・取得制限が発生する場合があります。")

st.markdown("""<div class="hero"><div class="eyebrow">MARKET LENS · ECONOMY & EQUITIES</div><h1>経済ニュースを、株価の理解につなげる。</h1><p>日本と世界のニュース、主要市場の動き、銘柄別の材料をひとつに。わからない用語はボタンを押すだけで簡単に確認できます。</p></div>""",unsafe_allow_html=True)

if market=="日本市場": indexes={"日経平均":"^N225","TOPIX":"1306.T"}
elif market=="米国市場": indexes={"S&P 500":"^GSPC","NASDAQ":"^IXIC","NYダウ":"^DJI"}
else: indexes={"日経平均":"^N225","S&P 500":"^GSPC","NASDAQ":"^IXIC","ドル円":"JPY=X"}
mc=st.columns(len(indexes))
for i,(label,ticker) in enumerate(indexes.items()):
    df=history(ticker,"7d")
    with mc[i]:
        if len(df)>=2:
            p=df["終値"].dropna(); st.metric(label,f"{p.iloc[-1]:,.2f}",f"{(p.iloc[-1]/p.iloc[-2]-1)*100:+.2f}%")
        else: st.metric(label,"取得不可")
st.caption(f"更新確認：{datetime.now(JST):%Y-%m-%d %H:%M} JST ・ 無料データのためリアルタイム配信を保証しません。")

t_home,t_news,t_stock,t_events,t_glossary,t_watch=st.tabs(["🏠 概要","📰 経済ニュース","📈 株価分析","🗓️ 指標・イベント","📖 用語辞典","⭐ マイ銘柄"])

with t_home:
    a,b=st.columns([1.3,1])
    with a:
        st.subheader("今日の主なニュース")
        chosen=FEEDS[2:] if market=="米国市場" else FEEDS[:2]
        for name,url in chosen:
            st.markdown("**"+name+"**")
            items=feed(url)
            if items:
                for x in items[:5]:
                    st.markdown(f"- [{x['title']}]({x['link']})")
                    term_buttons(x["title"])
            else: st.caption("ニュースを取得できませんでした。")
    with b:
        st.subheader("ニュースを見るときのポイント")
        st.markdown("- 金利：中央銀行の政策や物価指標を確認\n- 為替：円高・円安が企業に与える影響を確認\n- 業績：決算や会社予想も確認\n- 市場予想との差：予想と発表内容の違いに注目")
        with st.expander("初めての方向け：確認リスト"):
            st.checkbox("発表元と記事日時を確認した")
            st.checkbox("予想と実績を区別した")
            st.checkbox("株価がすでに反応していないか確認した")
            st.checkbox("別の情報源でも確認した")

with t_news:
    st.subheader("ニュース検索・テーマ別チェック")
    q=search_q or st.text_input("企業名・テーマ",placeholder="例：米国CPI、日銀、半導体、原油",key="news_q")
    n_days=st.selectbox("対象期間（日）",[1,3,7,14],index=2)
    if q: items=search_news(q,n_days)
    else:
        items=[]
        for name,url in FEEDS:
            items += [{**x,"source":x.get("source") or name} for x in feed(url)[:8]]
    theme=st.selectbox("テーマで絞り込み",["すべて","金融政策・金利","物価・景気","企業決算","為替・貿易","地政学・資源"])
    keywords={"金融政策・金利":["金利","日銀","FRB","FOMC","利上げ","利下げ"],"物価・景気":["CPI","物価","インフレ","GDP","景気","雇用"],"企業決算":["決算","業績","利益","売上","見通し"],"為替・貿易":["円高","円安","為替","関税","貿易","ドル"],"地政学・資源":["原油","中東","戦争","制裁","資源"]}
    if theme!="すべて": items=[x for x in items if any(k.lower() in x["title"].lower() for k in keywords[theme])]
    show_news(items,25)

with t_stock:
    st.subheader("銘柄の値動きと関連ニュース")
    group=st.radio("市場",["日本株","米国株"],horizontal=True)
    stocks=JP if group=="日本株" else US
    tickers=[x for x in stocks if not x.startswith("^") and x!="1306.T"]
    ticker=st.selectbox("銘柄",tickers,format_func=lambda x:f"{stocks[x]}（{x}）")
    period=st.selectbox("チャート期間",["1mo","3mo","6mo","1y"],index=1,format_func=lambda x:{"1mo":"1か月","3mo":"3か月","6mo":"6か月","1y":"1年"}[x])
    df=history(ticker,period)
    if not df.empty:
        p=df["終値"].dropna()
        if len(p)>=2:
            m1,m2,m3=st.columns(3)
            m1.metric("直近終値",f"{p.iloc[-1]:,.2f}")
            m2.metric("前日比",f"{(p.iloc[-1]/p.iloc[-2]-1)*100:+.2f}%")
            m3.metric("期間変化率",f"{(p.iloc[-1]/p.iloc[0]-1)*100:+.2f}%")
        chart=alt.Chart(df).mark_line(strokeWidth=2.5).encode(x=alt.X("日付:T",title=None),y=alt.Y("終値:Q",title="終値"),tooltip=["日付:T",alt.Tooltip("終値:Q",format=",.2f")]).properties(height=300)
        st.altair_chart(chart,use_container_width=True)
    else: st.warning("株価履歴を取得できませんでした。")
    st.markdown("#### 関連ニュース")
    show_news(search_news(stocks[ticker],days),8)

with t_events:
    st.subheader("経済指標・イベント")
    st.info("無料版ではイベント関連ニュースを検索して補助します。正確な発表時刻・市場予想・実績を保証する専用カレンダーAPIは未接続です。")
    eq=st.text_input("イベントを検索",value="米国 CPI FOMC 日銀 GDP 雇用統計")
    show_news(search_news(eq,14),15)
    st.markdown("#### 定期的に確認したい指標")
    st.dataframe(pd.DataFrame([["米国","CPI","物価・金利見通し"],["米国","雇用統計","雇用・景気・金融政策"],["米国","FOMC","政策金利と金融政策"],["日本","日銀会合","日本の金利・円相場"],["世界","GDP","経済成長"]],columns=["地域","指標","見るポイント"]),hide_index=True,use_container_width=True)

with t_glossary:
    st.subheader("クリックして学べる経済・投資用語")
    st.caption("用語のボタンを押すと、短い説明がその場で開きます。")
    cols=st.columns(3)
    for i,(term,(title,desc)) in enumerate(GLOSSARY.items()):
        with cols[i%3]:
            with st.popover("❔ "+term,use_container_width=True):
                st.markdown("### "+term)
                st.markdown("**"+title+"**")
                st.write(desc)
    st.divider()
    q=st.text_input("用語を検索",placeholder="例：PER、円高、GDP",key="glossary_q")
    if q:
        hits=[(k,v) for k,v in GLOSSARY.items() if q.lower() in k.lower() or q.lower() in v[0].lower() or q.lower() in v[1].lower()]
        if hits:
            for k,(title,desc) in hits:
                with st.expander(f"{k} — {title}",expanded=True): st.write(desc)
        else: st.warning("登録されていない用語です。追加候補にできます。")

with t_watch:
    st.subheader("マイ銘柄ウォッチリスト")
    st.caption("コードをカンマ区切りで入力。日本株は末尾に .T を付けます。現時点では入力したリストを一時的に表示します。")
    raw=st.text_input("銘柄コード",value="7203.T,NVDA,8306.T,AAPL")
    watch=[x.strip().upper() for x in raw.split(",") if x.strip()]
    rows=[]
    for code in watch:
        df=history(code,"7d")
        if len(df)>=2:
            p=df["終値"].dropna()
            rows.append({"コード":code,"終値":round(float(p.iloc[-1]),2),"前日比(%)":round((p.iloc[-1]/p.iloc[-2]-1)*100,2),"日付":df["日付"].iloc[-1].strftime("%Y-%m-%d")})
    if rows:
        wd=pd.DataFrame(rows); st.dataframe(wd,hide_index=True,use_container_width=True)
        st.download_button("CSVでダウンロード",wd.to_csv(index=False).encode("utf-8-sig"),"market_watchlist.csv","text/csv")
    else: st.warning("データを取得できません。銘柄コードをご確認ください。")

st.divider()
st.caption("このアプリは情報整理を支援するもので、投資助言ではありません。見出しから因果関係は断定できません。重要な情報は一次資料・複数の情報源で確認してください。")
