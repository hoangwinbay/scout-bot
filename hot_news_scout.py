"""
BOT TÌM TIN TỨC GIẬT GÂN & NHIỀU TƯƠNG TÁC (HOT NEWS SCOUT) - KOYEB CLOUD EDITION
- Tự động cào RSS các đầu báo lớn (VnExpress, Tuổi Trẻ, Dân Trí, VietNamNet, Thanh Niên...).
- Lọc bài trong khoảng 6 đến 9 tiếng trước (linh hoạt mở rộng 1-14h khi cần).
- Dùng Gemini 3.5 Flash Lite chấm điểm giật gân, viral, kịch tính.
- Xuất TOP 5 bài hot kèm nút bấm sang Bot News @new3089bot.
"""

import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SCOUT_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "6368500019"))
NEWS_BOT_USERNAME = os.environ.get("NEWS_BOT_USERNAME", "new3089bot")
API_BASE = f"https://api.telegram.org/bot{SCOUT_BOT_TOKEN}"

FEEDS = [
    ("VnExpress", "https://vnexpress.net/rss/tin-moi-nhat.rss"),
    ("VnExpress Pháp luật", "https://vnexpress.net/rss/phap-luat.rss"),
    ("VnExpress Thời sự", "https://vnexpress.net/rss/thoi-su.rss"),
    ("Tuổi Trẻ", "https://tuoitre.vn/rss/tin-moi-nhat.rss"),
    ("Tuổi Trẻ Pháp luật", "https://tuoitre.vn/rss/phap-luat.rss"),
    ("Dân Trí", "https://dantri.com.vn/rss/tin-moi-nhat.rss"),
    ("Dân Trí Pháp luật", "https://dantri.com.vn/rss/phap-luat.rss"),
    ("Dân Trí Sự kiện", "https://dantri.com.vn/rss/su-kien.rss"),
    ("VietNamNet Thời sự", "https://vietnamnet.vn/rss/thoi-su.rss"),
    ("VietNamNet Pháp luật", "https://vietnamnet.vn/rss/phap-luat.rss"),
    ("Thanh Niên", "https://thanhnien.vn/rss/home.rss"),
    ("Thanh Niên Thời sự", "https://thanhnien.vn/rss/thoi-su.rss")
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

def fetch_feed_items(source_info):
    source_name, feed_url = source_info
    items_found = []
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return items_found
        root = ET.fromstring(resp.content)
        now_utc = datetime.now(timezone.utc)

        for item in root.findall('.//item'):
            title = item.find('title')
            link = item.find('link')
            pub_elem = item.find('pubDate')

            if title is None or not title.text or link is None or not link.text:
                continue
            if pub_elem is None or not pub_elem.text:
                continue

            try:
                pub_dt = parsedate_to_datetime(pub_elem.text)
                age_h = (now_utc - pub_dt.astimezone(timezone.utc)).total_seconds() / 3600.0
            except Exception:
                continue

            desc_elem = item.find('description')
            desc = desc_elem.text if desc_elem is not None and desc_elem.text else ''
            desc = re.sub(r'<[^>]+>', '', desc).strip()

            items_found.append({
                'source': source_name,
                'title': title.text.strip(),
                'link': link.text.strip(),
                'age_hours': round(age_h, 1),
                'desc': desc[:300]
            })
    except Exception:
        pass
    return items_found

def get_candidate_articles(hours_min=6.0, hours_max=9.0):
    all_items = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_feed_items, FEEDS)
        for r in results:
            all_items.extend(r)

    # Lọc theo khung giờ
    filtered = [
        item for item in all_items 
        if hours_min <= item['age_hours'] <= hours_max
    ]

    # Mở rộng dải giờ nếu ít hơn 5 bài
    if len(filtered) < 5:
        filtered = [
            item for item in all_items 
            if max(1.0, hours_min - 2.0) <= item['age_hours'] <= (hours_max + 2.5)
        ]
    if len(filtered) < 5:
        filtered = [
            item for item in all_items 
            if 1.0 <= item['age_hours'] <= 14.0
        ]

    # Khử trùng lặp
    seen_links = set()
    unique_items = []
    for it in filtered:
        clean_title = re.sub(r'[^\w\s]', '', it['title'].lower()).strip()
        if it['link'] not in seen_links and clean_title not in seen_links:
            seen_links.add(it['link'])
            seen_links.add(clean_title)
            unique_items.append(it)

    return unique_items

def analyze_and_rank_sensational_news(candidates, top_n=5):
    if not candidates:
        return []

    client_genai = genai.Client(api_key=GEMINI_API_KEY)
    candidates_sample = candidates[:40]
    articles_text = ""
    for idx, c in enumerate(candidates_sample, 1):
        articles_text += f"[{idx}] Nguồn: {c['source']} | Đăng cách đây: {c['age_hours']}h\n"
        articles_text += f"Tiêu đề: {c['title']}\n"
        articles_text += f"Link: {c['link']}\n"
        articles_text += f"Mô tả: {c['desc']}\n\n"

    prompt = f"""
Bạn là Tổng biên tập tin tức mạng xã hội & Giám đốc nội dung kênh tin tức TikTok/Reels/Shorts triệu view.
Dưới đây là danh sách các bài báo tiếng Việt được đăng gần đây:

{articles_text}

NHIỆM VỤ:
Hãy chọn ra đúng {top_n} bài báo GIẬT GÂN NHẤT, KỊCH TÍNH NHẤT, VÀ CÓ TIỀM NĂNG TẠO LƯỢNG TƯƠNG TÁC CAO NHẤT.

TIÊU CHÍ:
1. Độ kịch tính: Án điểm, lừa đảo chấn động, bạo lực, bắt giữ, khởi tố, tai nạn, tranh chấp gay gắt, hiện tượng lạ.
2. Tiềm năng viral: Gây sốc, tò mò, bức xúc, muốn bình luận/chia sẻ.
3. Phù hợp làm video ngắn 9:16.

YÊU CẦU ĐẦU RA (CHỈ XUẤT JSON):
{{
  "trending_news": [
    {{
      "rank": 1,
      "title": "Tiêu đề gốc",
      "source": "Tên báo",
      "url": "URL bài báo gốc",
      "hours_ago": 6.5,
      "viral_score": 9.8,
      "sensational_hook": "Câu giật tít 1 dòng cực mạnh",
      "why_hot": "Lý do bài này hot",
      "summary": "Tóm tắt trong 2 câu"
    }}
  ]
}}
"""
    resp = None
    for m in ['gemini-3.5-flash-lite', 'gemini-flash-lite-latest', 'gemini-3.5-flash', 'gemini-2.5-flash']:
        try:
            resp = client_genai.models.generate_content(
                model=m,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            if resp and resp.text:
                break
        except Exception:
            pass

    if not resp or not resp.text:
        return []
    try:
        data = json.loads(resp.text)
        return data.get("trending_news", [])
    except Exception:
        return []

def format_telegram_digest(ranked_news, hours_min=6, hours_max=9):
    now_str = datetime.now().strftime("%H:%M - %d/%m/%Y")
    text = (
        f"🔥 <b>BẢN TIN GIẬT GÂN & TƯƠNG TÁC CAO NHẤT</b>\n"
        f"<i>(Đăng trong khung giờ: cách đây {hours_min} - {hours_max} tiếng)</i>\n"
        f"⏱️ <i>Cập nhật: {now_str} (Koyeb Cloud 24/7)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
    )

    for item in ranked_news:
        rank = item.get("rank", 1)
        score = item.get("viral_score", 9.0)
        title = item.get("title", "")
        source = item.get("source", "")
        hook = item.get("sensational_hook", "")
        why = item.get("why_hot", "")
        url = item.get("url", "")
        hours_ago = item.get("hours_ago", 0.0)

        medals = {1: "🥇 TOP 1", 2: "🥈 TOP 2", 3: "🥉 TOP 3", 4: "🎖️ TOP 4", 5: "🎖️ TOP 5"}
        medal_str = medals.get(rank, f"#{rank}")

        text += (
            f"<b>{medal_str} | ⭐ {score}/10</b> ({hours_ago:.1f}h trước)\n"
            f"📰 <b>{title}</b>\n"
            f"🏢 <b>Nguồn:</b> {source}\n"
            f"⚡ <b>Tít video:</b> <i>\"{hook}\"</i>\n"
            f"💬 <b>Điểm nóng:</b> {why}\n"
            f"🔗 <a href=\"{url}\">Đọc bài báo gốc</a>\n\n"
        )

    text += "👉 <i>Nhấn nút bên dưới để chuyển sang Bot News dựng video TikTok/Reels 9:16 ngay!</i>"
    return text

def scout_hot_news(hours_min=6.0, hours_max=9.0, send_to_telegram=False, bot_token=None, chat_id=None):
    token = bot_token or SCOUT_BOT_TOKEN
    target_chat = chat_id or ADMIN_CHAT_ID
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    print(f"[*] Đang quét RSS các đầu báo trong khung giờ {hours_min}h - {hours_max}h...")
    candidates = get_candidate_articles(hours_min=hours_min, hours_max=hours_max)
    print(f"[*] Tìm thấy {len(candidates)} bài báo phù hợp trong khung giờ.")

    if not candidates:
        if send_to_telegram:
            try:
                requests.post(api_url, json={
                    "chat_id": target_chat,
                    "text": f"⚠️ Không tìm thấy bài báo nào trong khung giờ {hours_min:g}h - {hours_max:g}h trước. Hệ thống sẽ thử lại sau ít phút!"
                }, timeout=25)
            except Exception:
                pass
        return []

    print("[*] Gemini AI đang phân tích độ giật gân...")
    ranked = analyze_and_rank_sensational_news(candidates, top_n=5)
    print(f"[+] Đã chọn ra {len(ranked)} bài báo giật gân nhất!")

    if send_to_telegram and ranked:
        msg = format_telegram_digest(ranked, int(hours_min), int(hours_max))
        inline_buttons = []
        for it in ranked:
            rank_num = it.get('rank', 1)
            row = [
                {
                    "text": f"🎬 Dựng video #{rank_num}",
                    "url": f"https://t.me/{NEWS_BOT_USERNAME}?start=news_{rank_num}"
                },
                {
                    "text": "📖 Đọc bài",
                    "url": it.get('url', 'https://google.com')
                }
            ]
            inline_buttons.append(row)

        payload = {
            "chat_id": target_chat,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {
                "inline_keyboard": inline_buttons
            }
        }
        for _ in range(3):
            try:
                r = requests.post(api_url, json=payload, timeout=30)
                if r.status_code == 200:
                    print(f"[+] Đã gửi bản tin giật gân sang Telegram chat {target_chat} thành công!")
                    return ranked
            except Exception as e:
                print("[!] Lỗi gửi Telegram, retry:", e)
                time.sleep(2)

    return ranked
