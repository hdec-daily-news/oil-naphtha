# -*- coding: utf-8 -*-
"""
나프타·원유 동향 — Daily Update
네이버 뉴스 API · 3일 이내 · 주요 언론사 · 3개 카테고리
  - 원유:   국제유가·수급·WTI·두바이유·Brent
  - 나프타: 나프타 수급·가격·정제마진
  - 중동영향: 이란·이스라엘·호르무즈 → 유가/나프타 영향
"""
import csv, os, re, sys, requests, urllib3
from datetime import datetime, timedelta, timezone
from html import unescape
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.stdout.reconfigure(encoding='utf-8')

KST = timezone(timedelta(hours=9))

# ──────────────────────────────────────
# 카테고리 설정
# ──────────────────────────────────────
CATEGORIES = {
    "나프타": {
        "label": "나프타 수급",
        "icon": "⛽",
        "keywords": [
            "나프타 수급", "나프타 공급", "나프타 수요", "나프타 재고",
            "나프타", "납사 수급", "납사", "정제마진",
            "석유화학 원료", "NCC 가동률", "NCC 가동",
            "나프타 수입", "나프타 수출",
        ],
        "must_include": ["나프타", "납사", "정제마진", "NCC", "석유화학"],
    },
    "원유": {
        "label": "원유 수급",
        "icon": "🛢️",
        "keywords": [
            # 수급/공급/수요/재고
            "원유 수급", "원유 공급", "원유 수요", "원유 재고",
            "원유 생산", "원유 생산량", "미국 원유 생산", "셰일오일",
            # OPEC+ 감산/증산
            "OPEC 감산", "OPEC 증산", "OPEC+ 감산", "OPEC+ 증산",
            "OPEC+ 생산", "OPEC 회의",
            # 수출입 물량
            "원유 수출", "원유 수입", "러시아 원유", "중국 원유 수입",
            # 전략비축유
            "전략비축유", "SPR",
        ],
        "must_include": ["원유", "OPEC", "셰일", "SPR", "전략비축유"],
        # 가격/시황 위주 기사 배제 — 수급 포커스
        "must_also_not_only": ["유가", "가격", "배럴당", "상승", "하락"],
    },
    "중동영향": {
        "label": "중동 정세 · 수급 영향",
        "icon": "🌍",
        "keywords": [
            "이란 원유", "이스라엘 원유", "중동 원유",
            "호르무즈", "호르무즈 해협", "호르무즈 통과", "호르무즈 봉쇄",
            "중동 정세 원유", "중동 전쟁 원유",
            "중동 석유 공급", "이란 석유 수출", "이란 제재",
            "홍해 원유", "홍해 통과", "홍해 항로", "수에즈 운하",
            "유조선 호르무즈", "유조선 홍해", "유조선 통과", "유조선 항로",
            "한국 유조선", "VLCC 호르무즈", "VLCC 홍해",
            "사우디 증산", "사우디 감산",
        ],
        "must_include": [
            "이란", "이스라엘", "호르무즈", "중동", "홍해", "사우디",
            "유조선", "VLCC", "수에즈",
        ],
        "must_also": [
            "원유", "나프타", "석유", "수급", "공급", "수출",
            "감산", "증산", "통과", "해협", "항로", "봉쇄",
        ],
    },
}

NAVER_CLIENT_ID = "4EpC74MmQmbBp2bpWpI5"
NAVER_CLIENT_SECRET = "uxqj17VklI"

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(OUTPUT_DIR, "index.html")
CSV_PATH = os.path.join(OUTPUT_DIR, "oil_naphtha.csv")

# ──────────────────────────────────────
# 주요 언론사 화이트리스트
# ──────────────────────────────────────
# ──────────────────────────────────────
# 하드 제외 (주식/시세/스포츠/연재 등)
# ──────────────────────────────────────
HARD_EXCLUDE = [
    # 주식/증권/투자
    "장중", "주가", "목표가", "특징주", "관련주", "테마주", "에너지주",
    "급등주", "상한가", "하한가", "주봉", "매수", "매도", "증권사",
    "펀드", "ETF", "투자의견", "컨센서스", "종목분석", "리포트",
    "52주 신고가", "52주 신저가", "시가총액", "PER", "PBR",
    "이격도", "코스피", "코스닥", "[마감]", "[장마감]", "[장중]",
    "[주요공시]", "주요공시", "마감 시황", "증시 마감", "증시 전망",
    "주요 증시", "증권시장", "증시 브리핑", "코스피·코스닥",
    # 업계 나열식/시황 시리즈
    "[시황]", "[오늘의", "[주간", "[마켓워치]", "굿모닝",
    "오늘의 주요공시", "[에너지시황]",
    # 스포츠/사회
    "배구", "축구", "야구", "부고", "별세", "결혼", "장례",
    # 환율/금 등 단순 시세
    "[환율]", "[금값]", "달러 환율", "원·달러",
    # 광고성
    "보도자료", "기자간담회 개최",
]

# ──────────────────────────────────────
# 주요 언론사 화이트리스트
# ──────────────────────────────────────
MAJOR_PRESS = {
    # 경제지
    "매일경제", "한국경제", "서울경제", "서울경제TV", "파이낸셜뉴스",
    "머니투데이", "이데일리", "아시아경제", "헤럴드경제", "전자신문",
    "조선비즈",
    # 종합지
    "조선일보", "중앙일보", "동아일보", "한겨레", "경향신문",
    # 통신/방송
    "연합뉴스", "뉴시스", "뉴스1",
    # 에너지/경제 전문
    "에너지경제", "에너지데일리", "이투데이", "뉴스핌",
    "더벨", "비즈니스포스트", "MTN", "디지털타임스", "아주경제",
}

SOURCE_MAP = {
    "mk.co.kr": "매일경제", "hankyung.com": "한국경제",
    "yna.co.kr": "연합뉴스", "sedaily.com": "서울경제",
    "sentv.co.kr": "서울경제TV",
    "dnews.co.kr": "대한경제", "chosun.com": "조선일보",
    "realty.chosun.com": "조선비즈", "biz.chosun.com": "조선비즈",
    "khan.co.kr": "경향신문", "mt.co.kr": "머니투데이",
    "news.mt.co.kr": "머니투데이",
    "asiae.co.kr": "아시아경제", "view.asiae.co.kr": "아시아경제",
    "fnnews.com": "파이낸셜뉴스", "edaily.co.kr": "이데일리",
    "dt.co.kr": "디지털타임스", "news1.kr": "뉴스1",
    "newsis.com": "뉴시스", "ajunews.com": "아주경제",
    "donga.com": "동아일보", "joongang.co.kr": "중앙일보",
    "hani.co.kr": "한겨레", "heraldcorp.com": "헤럴드경제",
    "news.heraldcorp.com": "헤럴드경제",
    "etnews.com": "전자신문",
    "ekn.kr": "에너지경제", "energy.co.kr": "에너지데일리",
    "etoday.co.kr": "이투데이", "newspim.com": "뉴스핌",
    "thebell.co.kr": "더벨", "businesspost.co.kr": "비즈니스포스트",
    "mtn.co.kr": "MTN", "news.mtn.co.kr": "MTN",
}


# ──────────────────────────────────────
# 매체 가점 (대표 2장 선정 시 우선순위)
# ──────────────────────────────────────
TIER1_PRESS = {
    "매일경제", "한국경제", "서울경제", "파이낸셜뉴스", "머니투데이",
    "이데일리", "연합뉴스", "조선비즈", "중앙일보", "동아일보", "조선일보",
}
def _press_bonus(source):
    return 3 if source in TIER1_PRESS else 0


# ──────────────────────────────────────
# 유사도 기반 중복 제거
# ──────────────────────────────────────
def _tokens(title):
    clean = re.sub(r"[^가-힣a-zA-Z0-9]", " ", title)
    return {w for w in clean.split() if len(w) >= 2}

def _similar(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    return len(inter) / max(len(ta), len(tb))

def _dedupe_articles(arts):
    arts = sorted(arts, key=lambda a: (-a["_hits"], -a["datetime"].timestamp()))
    kept = []
    for art in arts:
        is_dup = False
        for k in kept:
            if _similar(art["title"], k["title"]) >= 0.35:
                is_dup = True
                k["_hits"] += art["_hits"]  # 유사기사 hits 합산
                break
        if not is_dup:
            kept.append(art)
    return kept


def get_source(link):
    import urllib.parse
    domain = urllib.parse.urlparse(link).netloc.replace("www.", "")
    if domain in SOURCE_MAP:
        return SOURCE_MAP[domain]
    parts = domain.split(".")
    if len(parts) > 2:
        root = ".".join(parts[-2:])
        if root in SOURCE_MAP:
            return SOURCE_MAP[root]
    return parts[0] if parts else domain


# ──────────────────────────────────────
# 수집
# ──────────────────────────────────────
def collect():
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    today_midnight = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = today_midnight - timedelta(days=1)  # 전일~금일

    all_results = {}

    for cat, config in CATEGORIES.items():
        print(f"\n=== [{cat}] ===")
        seen = {}

        for kw in config["keywords"]:
            print(f"  검색: '{kw}'", end="")
            kcount = 0
            for start in range(1, 300, 100):
                params = {"query": kw, "display": 100, "start": start, "sort": "date"}
                try:
                    r = requests.get(url, headers=headers, params=params, timeout=10, verify=False)
                    r.raise_for_status()
                    data = r.json()
                except Exception as e:
                    print(f" API오류: {e}")
                    break

                items = data.get("items", [])
                if not items:
                    break

                stop = False
                for it in items:
                    try:
                        pub = datetime.strptime(
                            it["pubDate"], "%a, %d %b %Y %H:%M:%S %z"
                        ).astimezone(KST)
                    except ValueError:
                        continue
                    if pub < cutoff:
                        stop = True
                        break

                    title = re.sub(r"<.*?>", "", unescape(it.get("title", "")))
                    link = it.get("originallink") or it.get("link", "")
                    desc = re.sub(r"<.*?>", "", unescape(it.get("description", "")))
                    text = title + " " + desc

                    # 하드 제외 (주식/시세/스포츠)
                    if any(ex in text for ex in HARD_EXCLUDE):
                        continue

                    # 카테고리 필터
                    if not any(w in text for w in config["must_include"]):
                        continue
                    if "must_also" in config:
                        if not any(w in text for w in config["must_also"]):
                            continue

                    if link in seen:
                        seen[link]["_hits"] += 1
                        continue

                    source = get_source(link)
                    if source not in MAJOR_PRESS:
                        continue

                    seen[link] = {
                        "category": cat,
                        "date": pub.strftime("%Y-%m-%d"),
                        "datetime": pub,
                        "title": title,
                        "link": link,
                        "description": desc[:200],
                        "source": source,
                        "_hits": 1,
                    }
                    kcount += 1

                if stop:
                    break
            print(f" → {kcount}건 신규")

        # 중복 제거 (제목 유사도 + 키워드 overlap)
        deduped = _dedupe_articles(list(seen.values()))

        # 품질 기준 (hit 많고 최신순 + 매체 가점), 섹터당 최소 4 ~ 최대 7
        def _score(a):
            return a["_hits"] * 2 + _press_bonus(a["source"])
        deduped.sort(key=lambda a: (-_score(a), -a["datetime"].timestamp()))
        MIN_N, MAX_N = 4, 7
        quality = [a for a in deduped if _score(a) >= 3]
        if len(quality) >= MIN_N:
            selected = quality[:MAX_N]
        else:
            # 품질 통과가 4건 미만이면 점수 무관 상위 4건으로 보충
            selected = deduped[:MIN_N]
        all_results[cat] = selected
        print(f"  [{cat}] 중복 제거 후 {len(deduped)}건 → 품질 통과 {len(quality)}건 → {len(selected)}건 표시")

    return all_results


# ──────────────────────────────────────
# CSV 저장
# ──────────────────────────────────────
def save_csv(results):
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "date", "source", "title", "link", "description", "hits"])
        for cat, arts in results.items():
            for a in arts:
                w.writerow([cat, a["date"], a["source"], a["title"], a["link"], a["description"], a["_hits"]])
    print(f"\nCSV 저장: {CSV_PATH}")


# ──────────────────────────────────────
# HTML 생성
# ──────────────────────────────────────
def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_html(results):
    now = datetime.now(KST)
    today = now.strftime("%Y년 %m월 %d일 %H:%M")
    d_range = f"{(now - timedelta(days=1)).strftime('%m.%d')} ~ {now.strftime('%m.%d')}"
    total = sum(len(v) for v in results.values())

    sections_html = []
    for cat, config in CATEGORIES.items():
        arts = results.get(cat, [])
        top = arts[:2]
        rest = arts[2:]

        top_cards = ""
        for a in top:
            top_cards += f'''
        <a class="top-card" href="{esc(a['link'])}" target="_blank" rel="noopener">
          <div class="top-card-source">{esc(a['source'])} · {a['date'][5:].replace('-', '.')}</div>
          <h3 class="top-card-title">{esc(a['title'])}</h3>
          <p class="top-card-desc">{esc(a['description'])}</p>
          <span class="top-card-more">원문 기사 보기 →</span>
        </a>'''

        rest_list = ""
        for a in rest:
            rest_list += f'''
          <li class="headline">
            <a href="{esc(a['link'])}" target="_blank" rel="noopener">
              <span class="hl-title">{esc(a['title'])}</span>
              <span class="hl-meta">{esc(a['source'])} · {a['date'][5:].replace('-', '.')}</span>
            </a>
          </li>'''

        if not arts:
            empty = '<div class="empty">최근 3일 내 주요 기사 없음</div>'
            body_html = empty
        else:
            body_html = ""
            if top:
                body_html += f'<div class="top-cards">{top_cards}</div>'
            if rest:
                body_html += f'<ul class="headlines">{rest_list}</ul>'

        sections_html.append(f'''
    <section class="section" data-cat="{esc(cat)}">
      <div class="section-head">
        <div class="section-icon">{config["icon"]}</div>
        <div class="section-meta">
          <h2 class="section-title">{esc(config["label"])}</h2>
          <div class="section-count">{len(arts)}건</div>
        </div>
      </div>
      {body_html}
    </section>''')

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>나프타·원유 동향 Daily | HDEC Daily News</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head>
<body>

<div class="bg-wrap">
  <div class="bg-overlay"></div>
</div>

<main class="container">

  <header class="site-header">
    <a href="https://hdec-daily-news.github.io/landing/" class="brand">
      <span class="brand-dot"></span>
      <span class="brand-name">HDEC Daily News</span>
    </a>
    <div class="site-meta">
      <span>수집기간 {d_range}</span>
      <span class="sep">·</span>
      <span class="auto-badge">🔄 매일 07시 / 12시 2회 자동 업데이트</span>
    </div>
  </header>

  <section class="hero">
    <div class="hero-tag">⛽ DAILY UPDATE</div>
    <h1>
      <span class="hero-sub">매일 업데이트되는</span>
      <span class="hero-main">나프타 · 원유 동향</span>
    </h1>
    <p class="hero-desc">
      나프타·원유 수급, 중동 정세에 따른 가격 영향 기사를<br>
      <strong>주요 경제지 · 종합지</strong>에서 선별, 최근 3일 내 기사를 정리합니다.
    </p>
    <div class="hero-stats">
      <div class="stat"><span class="stat-num">{total}</span><span class="stat-lab">TOTAL</span></div>
      <div class="stat"><span class="stat-num">{len(results.get("나프타", []))}</span><span class="stat-lab">나프타</span></div>
      <div class="stat"><span class="stat-num">{len(results.get("원유", []))}</span><span class="stat-lab">원유</span></div>
      <div class="stat"><span class="stat-num">{len(results.get("중동영향", []))}</span><span class="stat-lab">중동영향</span></div>
    </div>
  </section>

  {''.join(sections_html)}

  <footer class="site-footer">
    <div>현대건설 글로벌사업부 · 내부 업무용</div>
    <div class="tech">Powered by Naver News API · GitHub Pages</div>
  </footer>

</main>

</body>
</html>
'''

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML 저장: {HTML_PATH}")


def main():
    results = collect()
    save_csv(results)
    generate_html(results)
    print("\n완료!")


if __name__ == "__main__":
    main()
