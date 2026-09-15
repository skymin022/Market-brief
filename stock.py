#!/usr/bin/env python3
# 장 브리핑 대시보드
# 국내/미국 증권 뉴스 RSS를 모아 → 헤드라인에서 '가장 많이 언급된 종목'을 세고
# → 랭킹 + 그 종목 관련 뉴스로 docs/index.html 를 만든다.
# 로컬 실행 없이 GitHub Actions에서만 돎. (Discord 없음, 스냅샷형)

import os
import re
import html
import time
import calendar
import datetime

import feedparser

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; market-brief/1.0)"

# ============ ✏️ 편집 영역 ============
LOOKBACK_HOURS = 24     # 장 마감~다음 오픈 사이 뉴스 범위
TOP_N = 10              # 시장별로 보여줄 상위 종목 수
MAX_NEWS_PER = 4        # 종목당 뉴스 링크 수
MAX_PER_FEED = 60       # 피드당 최대 수집 헤드라인

# --- 국내 증권 뉴스 피드 (한국경제 증권/경제는 확인됨) ---
FEEDS_KR = [
    "https://www.hankyung.com/feed/finance",
    "https://www.hankyung.com/feed/economy",
    "https://www.asiae.co.kr/rss/stock.htm",   # 안 되면 로그에 뜸 → 지워도 됨
]

# --- 미국 증권 뉴스 피드 (CNBC 공개 무료 RSS) ---
# ⚠ 첫 실행 로그에서 [ok]/[warn] 확인하고, 막히는 건 교체하세요.
FEEDS_US = [
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # Top News (확인됨)
    "https://www.cnbc.com/id/20409666/device/rss/rss.html",   # Market Insider
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",   # Earnings(실적, 종목명 풍부)
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,NVDA,MSFT,TSLA,AMZN,GOOGL,META,AVGO,AMD,NFLX,PLTR,ORCL&region=US&lang=en-US",  # Yahoo 티커 뉴스
]

# 셀 종목 목록: (표시이름, [헤드라인에서 찾을 표현들])
# 종목을 늘리거나 별칭을 추가하면 그만큼 잘 잡힘.
WATCH_KR = [
    ("삼성전자", ["삼성전자", "삼전"]),
    ("SK하이닉스", ["SK하이닉스", "하이닉스"]),
    ("현대차", ["현대차", "현대자동차"]),
    ("기아", ["기아"]),
    ("LG에너지솔루션", ["LG에너지솔루션", "LG엔솔", "엘지엔솔"]),
    ("삼성바이오로직스", ["삼성바이오"]),
    ("네이버", ["네이버", "NAVER"]),
    ("카카오", ["카카오"]),
    ("셀트리온", ["셀트리온"]),
    ("포스코", ["포스코", "POSCO"]),
    ("삼성SDI", ["삼성SDI"]),
    ("현대모비스", ["현대모비스"]),
    ("삼성전기", ["삼성전기"]),
    ("SK이노베이션", ["SK이노베이션", "SK이노"]),
    ("한화에어로스페이스", ["한화에어로"]),
    ("두산에너빌리티", ["두산에너빌리티", "두산에너"]),
    ("KB금융", ["KB금융"]),
    ("신한지주", ["신한지주", "신한금융"]),
    ("에코프로", ["에코프로"]),
    ("크래프톤", ["크래프톤"]),
    ("하이브", ["하이브", "HYBE"]),
    ("한미반도체", ["한미반도체"]),
    ("미래에셋", ["미래에셋"]),
]

WATCH_US = [
    ("Nvidia", ["Nvidia", "NVDA"]),
    ("Apple", ["Apple", "AAPL"]),
    ("Microsoft", ["Microsoft", "MSFT"]),
    ("Tesla", ["Tesla", "TSLA"]),
    ("Amazon", ["Amazon", "AMZN"]),
    ("Alphabet", ["Alphabet", "Google", "GOOGL", "GOOG"]),
    ("Meta", ["Meta", "META"]),
    ("Broadcom", ["Broadcom", "AVGO"]),
    ("AMD", ["AMD"]),
    ("Netflix", ["Netflix", "NFLX"]),
    ("Micron", ["Micron"]),
    ("Intel", ["Intel", "INTC"]),
    ("Palantir", ["Palantir", "PLTR"]),
    ("Oracle", ["Oracle", "ORCL"]),
    ("JPMorgan", ["JPMorgan", "JPMorgan Chase"]),
]
# =====================================

KST = datetime.timezone(datetime.timedelta(hours=9))
DOCS_DIR = "docs"


def collect(feeds):
    cutoff = time.time() - LOOKBACK_HOURS * 3600
    items = []
    for url in feeds:
        try:
            d = feedparser.parse(url)
            src = (d.feed.get("title") or url)[:50]
            n = 0
            for e in d.entries:
                if n >= MAX_PER_FEED:
                    break
                title = (e.get("title") or "").strip()
                link = e.get("link") or ""
                if not title or not link:
                    continue
                tp = e.get("published_parsed") or e.get("updated_parsed")
                ts = calendar.timegm(tp) if tp else time.time()
                if tp and ts < cutoff:
                    continue
                items.append({"title": title, "link": link, "ts": ts})
                n += 1
            print(f"[ok] {src}: {n}건")
        except Exception as ex:
            print(f"[warn] 피드 실패: {url} :: {ex}")
    return items


def count_mentions(items, watchlist, korean):
    ranked = []
    for name, patterns in watchlist:
        matched = []
        for it in items:
            t = it["title"]
            hit = False
            for p in patterns:
                if korean:
                    if p in t:
                        hit = True
                        break
                else:
                    if re.search(r"\b" + re.escape(p) + r"\b", t, re.I):
                        hit = True
                        break
            if hit:
                matched.append(it)
        if matched:
            matched.sort(key=lambda x: x["ts"], reverse=True)
            ranked.append({"name": name, "count": len(matched), "items": matched})
    ranked.sort(key=lambda x: x["count"], reverse=True)
    return ranked[:TOP_N]


def render_section(flag, label, ranked):
    if not ranked:
        return (f'<section><h2>{flag} {label}</h2>'
                f'<p class="empty">수집된 뉴스가 없습니다. Actions 로그에서 '
                f'어느 피드가 실패했는지 확인하세요.</p></section>')
    blocks = []
    for i, r in enumerate(ranked, 1):
        news = "".join(
            f'<li><a href="{html.escape(it["link"])}" target="_blank" '
            f'rel="noopener">{html.escape(it["title"])}</a></li>'
            for it in r["items"][:MAX_NEWS_PER]
        )
        blocks.append(
            f'<li><div class="head"><span class="rk">{i}</span>'
            f'<span class="nm">{html.escape(r["name"])}</span>'
            f'<span class="ct">{r["count"]}</span></div>'
            f'<ul class="news">{news}</ul></li>'
        )
    return (f'<section><h2>{flag} {label}</h2>'
            f'<ol class="rank">{"".join(blocks)}</ol></section>')


TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>장 브리핑</title>
<style>
  :root{ --bg:#f7f8f8; --fg:#14181a; --muted:#67727a;
         --line:#e3e7e8; --accent:#b4451f; --chip:#efe7e2; }
  @media (prefers-color-scheme: dark){
    :root{ --bg:#0f1214; --fg:#e7ebec; --muted:#8b959c;
           --line:#20272b; --accent:#e08a5f; --chip:#241c18; } }
  *{box-sizing:border-box}
  body{margin:0; background:var(--bg); color:var(--fg);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif;}
  .wrap{max-width:680px; margin:0 auto; padding:32px 20px 80px}
  header{border-bottom:2px solid var(--fg); padding-bottom:14px}
  h1{margin:0; font-size:22px; font-weight:700; letter-spacing:-.01em}
  .updated{color:var(--muted); font-size:13px; margin-top:8px}
  section{margin-top:34px}
  h2{font-size:16px; margin:0 0 6px; padding-bottom:8px; border-bottom:1px solid var(--line)}
  ol.rank{list-style:none; margin:0; padding:0}
  ol.rank>li{padding:14px 0; border-bottom:1px solid var(--line)}
  .head{display:flex; align-items:baseline; gap:10px}
  .rk{color:var(--muted); font-size:13px; font-variant-numeric:tabular-nums; min-width:16px}
  .nm{font-weight:700; font-size:17px; flex:1}
  .ct{color:var(--accent); font-weight:700; font-variant-numeric:tabular-nums}
  .ct::after{content:"회"; color:var(--muted); font-weight:400; font-size:12px; margin-left:2px}
  ul.news{list-style:none; margin:8px 0 0; padding:0 0 0 26px}
  ul.news li{padding:3px 0}
  ul.news a{color:var(--muted); text-decoration:none; font-size:14px; line-height:1.45}
  ul.news a:hover{color:var(--accent); text-decoration:underline; text-underline-offset:2px}
  ul.news a:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:2px}
  .empty{color:var(--muted)}
  footer{margin-top:40px; color:var(--muted); font-size:12px}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>장 브리핑 — 많이 언급된 종목</h1>
      <div class="updated">업데이트 __UPDATED__ · 최근 __HOURS__시간 뉴스 기준</div>
    </header>
    __KR__
    __US__
    <footer>뉴스 보도량(헤드라인 언급 횟수) 기준. GitHub Actions가 자동 갱신합니다.</footer>
  </div>
</body>
</html>
"""


def main():
    kr_items = collect(FEEDS_KR)
    us_items = collect(FEEDS_US)
    kr_rank = count_mentions(kr_items, WATCH_KR, korean=True)
    us_rank = count_mentions(us_items, WATCH_US, korean=False)

    os.makedirs(DOCS_DIR, exist_ok=True)
    updated = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    page = (TEMPLATE
            .replace("__UPDATED__", updated)
            .replace("__HOURS__", str(LOOKBACK_HOURS))
            .replace("__KR__", render_section("🇰🇷", "국내 · 장 마감 브리핑", kr_rank))
            .replace("__US__", render_section("🇺🇸", "미국 · 장 마감 브리핑", us_rank)))
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)

    print(f"KR 뉴스 {len(kr_items)}건 / 종목 {len(kr_rank)}개  |  "
          f"US 뉴스 {len(us_items)}건 / 종목 {len(us_rank)}개")


if __name__ == "__main__":
    main()
