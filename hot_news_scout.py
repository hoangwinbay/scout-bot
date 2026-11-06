"""
BOT TÌM TIN TỨC GIẬT GÂN & SẢN XUẤT 4 VIDEO/NGÀY (HOT NEWS SCOUT) - CLOUD EDITION
- Tự động cào RSS các đầu báo lớn (VnExpress, Tuổi Trẻ, Dân Trí, VietNamNet, Thanh Niên...).
- Lọc bài theo 4 khung giờ phát sóng vàng tương đương 4 video mỗi ngày (07:00, 11:30, 17:30, 20:30).
- Dùng Gemini AI chấm điểm kịch tính, viral, tít hook 9:16 và chọn ra bài #1 xuất sắc nhất kèm 2-3 bài dự phòng.
- Tạo nút bấm 1-chạm (TinyURL) chuyển thẳng sang Bot News @new3089bot để dựng video hoàn chỉnh.
"""

import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
from google import genai

VN_TZ = timezone(timedelta(hours=7))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
SCOUT_BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("SCOUT_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or ""
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "6368500019"))
NEWS_BOT_USERNAME = os.environ.get("NEWS_BOT_USERNAME", "new3089bot")
API_BASE = f"https://api.telegram.org/bot{SCOUT_BOT_TOKEN}"

SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_articles.json")

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
    ("Thanh Niên Thời sự", "https://thanhnien.vn/rss/thoi-su.rss"),
    ("Tiền Phong", "https://tienphong.vn/rss/phap-luat-12.rss"),
    ("Tiền Phong Xã hội", "https://tienphong.vn/rss/xa-hoi-2.rss")
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

def load_seen_articles():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except Exception:
            pass
    return set()

def save_seen_articles(seen_set):
    try:
        items = list(seen_set)[-3000:]
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
    except Exception as e:
        print("[HOT_NEWS] Lỗi lưu seen_articles:", e)

def get_clean_key(title, link):
    norm_t = re.sub(r'[^\w\s]', '', title.lower()).strip()
    return f"{link}|{norm_t[:60]}"

def make_short_code(url):
    """Tạo mã ngắn TinyURL để truyền nguyên vẹn URL qua Telegram Deep-link /start tu_..."""
    if not url:
        return None
    for _ in range(2):
        try:
            r = requests.get(f"https://tinyurl.com/api-create.php?url={url}", timeout=5)
            if r.status_code == 200 and "tinyurl.com/" in r.text:
                return r.text.strip().split("/")[-1]
        except Exception:
            time.sleep(0.5)
    return None

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

def get_candidate_articles(hours_min=0.5, hours_max=8.0, exclude_seen=False):
    seen_articles = load_seen_articles() if exclude_seen else set()
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
            if max(0.1, hours_min - 1.0) <= item['age_hours'] <= (hours_max + 3.0)
        ]
    if len(filtered) < 5:
        filtered = [
            item for item in all_items 
            if 0.1 <= item['age_hours'] <= 16.0
        ]

    # Khử trùng lặp nội bộ và loại trừ bài đã thấy nếu có yêu cầu
    seen_links = set()
    unique_items = []
    for it in filtered:
        clean_title = re.sub(r'[^\w\s]', '', it['title'].lower()).strip()
        clean_key = get_clean_key(it['title'], it['link'])

        if exclude_seen:
            if clean_key in seen_articles or it['link'] in seen_articles:
                continue

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
Hãy chọn ra đúng {top_n} bài báo GIẬT GÂN NHẤT, KỊCH TÍNH NHẤT, VÀ CÓ TIỀM NĂNG TẠO LƯỢNG TƯƠNG TÁC CAO NHẤT ĐỂ LÀM VIDEO 9:16.
Xếp hạng bài #1 là bài xuất sắc nhất (được chọn làm video chính của khung giờ này), các bài #2, #3, #4 làm lựa chọn dự phòng.

TIÊU CHÍ:
1. Độ kịch tính: Án điểm, lừa đảo chấn động, bạo lực, bắt giữ, khởi tố, tai nạn, tranh chấp gay gắt, sự cố hy hữu, đời sống gây sốt.
2. Tiềm năng viral: Gây sốc, tò mò, phẫn nộ, đồng cảm sâu sắc, kích thích tranh luận và chia sẻ mạnh mẽ.
3. Rất phù hợp dựng video ngắn 9:16 phong cách Theanh28/TikTok.

YÊU CẦU ĐẦU RA (CHỈ XUẤT JSON HỢP LỆ):
{{
  "trending_news": [
    {{
      "rank": 1,
      "title": "Tiêu đề gốc bài báo",
      "source": "Tên báo",
      "url": "URL bài báo gốc",
      "hours_ago": 3.5,
      "viral_score": 9.8,
      "sensational_hook": "Câu giật tít 1 dòng cực mạnh mở đầu video 9:16 gây sốc và kích thích xem hết",
      "why_hot": "Lý do vì sao bài này sẽ bùng nổ tương tác",
      "summary": "Tóm tắt sự việc trong 2 câu ngắn gọn, súc tích"
    }}
  ]
}}
"""
    resp = None
    for m in ['gemini-2.5-flash', 'gemini-3.5-flash-lite', 'gemini-1.5-flash']:
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

def scout_video_slot_news(slot_time="07:00", video_num=1, session_name="Bản Tin Sáng", send_to_telegram=True, bot_token=None, chat_id=None):
    """
    Tuyển chọn gói tin tức cho 1 Video chuẩn trong 4 khung giờ vàng mỗi ngày:
    - Tìm bài báo nóng nhất từ các báo lớn chưa từng gửi trước đó.
    - Chọn Bài #1 làm bài chính để dựng Video (kèm nút bấm 1-chạm).
    - Cung cấp 2-3 bài dự phòng bên dưới để người dùng có thể đổi bài nếu muốn.
    - Lưu vào seen_articles để các khung giờ sau không bao giờ bị trùng.
    """
    token = bot_token or SCOUT_BOT_TOKEN
    target_chat = chat_id or ADMIN_CHAT_ID
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Định cấu hình dải thời gian theo từng khung giờ
    if slot_time == "07:00":
        h_min, h_max = 0.5, 9.0   # Bao quát tin đêm muộn & sáng sớm
    elif slot_time == "11:30":
        h_min, h_max = 0.5, 5.0   # Tin sáng từ 07h đến trưa
    elif slot_time == "17:30":
        h_min, h_max = 0.5, 6.0   # Tin chiều từ trưa đến tan tầm
    elif slot_time in ["20:30", "21:00"]:
        h_min, h_max = 0.5, 4.5   # Tin tối sau 17h30
    else:
        h_min, h_max = 0.5, 7.0

    print(f"[*] [VIDEO {video_num}/4] Bắt đầu quét tin cho {session_name} ({slot_time}) trong dải {h_min}h - {h_max}h...")
    candidates = get_candidate_articles(hours_min=h_min, hours_max=h_max, exclude_seen=True)
    if len(candidates) < 5:
        # Mở rộng dải giờ nếu chưa đủ bài
        candidates = get_candidate_articles(hours_min=0.2, hours_max=14.0, exclude_seen=True)

    print(f"[*] Tìm thấy {len(candidates)} bài báo mới chưa qua sử dụng.")

    if not candidates:
        if send_to_telegram:
            try:
                requests.post(api_url, json={
                    "chat_id": target_chat,
                    "text": f"⚠️ <b>[VIDEO {video_num}/4 • {session_name.upper()} - {slot_time}]</b>\n\nKhông tìm thấy bài báo mới phù hợp lúc này. Hệ thống sẽ tự động thử lại sau ít phút!"
                }, timeout=25)
            except Exception:
                pass
        return []

    print("[*] Gemini AI đang chấm điểm và chọn ra bài báo số 1...")
    ranked = analyze_and_rank_sensational_news(candidates, top_n=4)
    if not ranked:
        print("[!] Gemini không trả về bài xếp hạng.")
        return []

    top1 = ranked[0]
    backups = ranked[1:4]

    # Lưu ngay các bài đã chọn vào seen_articles để các slot sau không trùng
    seen = load_seen_articles()
    seen.add(get_clean_key(top1.get("title", ""), top1.get("url", "")))
    seen.add(top1.get("url", ""))
    for b in backups:
        seen.add(get_clean_key(b.get("title", ""), b.get("url", "")))
        seen.add(b.get("url", ""))
    save_seen_articles(seen)

    now_vn = datetime.now(VN_TZ)
    date_str = now_vn.strftime("%d/%m/%Y")
    age_h = top1.get("hours_ago", 0.0)
    age_str = f"{age_h:.1f} tiếng trước" if age_h > 0 else "vừa xuất bản"

    # Soạn nội dung thông điệp Telegram chuẩn broadcast
    msg = (
        f"🎬 <b>[VIDEO {video_num}/4 • {session_name.upper()} - {slot_time}]</b>\n"
        f"⏱️ <i>Khung giờ phát sóng: {slot_time} • Ngày {date_str}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔥 <b>BÀI BÁO ĐỀ XUẤT DỰNG VIDEO:</b>\n"
        f"📰 <b>{top1.get('title', '')}</b>\n"
        f"🏢 <b>Nguồn:</b> {top1.get('source', '')} | ⏳ <i>{age_str}</i>\n"
        f"⭐ <b>Độ kịch tính / Viral:</b> <b>{top1.get('viral_score', 9.0)}/10</b> 🔥🔥🔥\n\n"
        f"🎯 <b>Tít Hook 9:16 gợi ý:</b>\n"
        f"<i>\"{top1.get('sensational_hook', '')}\"</i>\n\n"
        f"💥 <b>Điểm nóng gây sốt:</b>\n"
        f"👉 {top1.get('why_hot', '')}\n\n"
        f"📝 <b>Tóm tắt cốt lõi:</b>\n"
        f"<i>{top1.get('summary', '')}</i>\n\n"
        f"📋 <b>Link bài báo gốc:</b>\n"
        f"<code>{top1.get('url', '')}</code>"
    )

    if backups:
        msg += "\n\n━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🔄 <b>LỰA CHỌN DỰ PHÒNG CHO VIDEO {video_num}:</b>\n"
        medals = ["🥈 #2", "🥉 #3", "🎖️ #4"]
        for idx, b in enumerate(backups):
            medal = medals[idx] if idx < len(medals) else f"#{idx+2}"
            msg += f"{medal}: <b>{b.get('title', '')}</b>\n   <i>(⭐ {b.get('viral_score', 8.5)}/10 - {b.get('source', '')})</i>\n"

    # Xây dựng nút bấm 1-chạm (TinyURL)
    top1_short = make_short_code(top1.get("url", ""))
    buttons = []
    if top1_short:
        buttons.append([
            {
                "text": f"🎬 DỰNG VIDEO {video_num}/4 NGAY (1 CHẠM)",
                "url": f"https://t.me/{NEWS_BOT_USERNAME}?start=tu_{top1_short}"
            }
        ])
    else:
        buttons.append([
            {
                "text": f"🎬 Mở Bot News dựng Video {video_num}/4",
                "url": f"https://t.me/{NEWS_BOT_USERNAME}"
            }
        ])

    buttons.append([
        {
            "text": "📖 Đọc bài chính",
            "url": top1.get("url", "https://google.com")
        },
        {
            "text": "📤 Chuyển tiếp",
            "url": f"https://t.me/share/url?url={top1.get('url', '')}&text=Dựng%20video%20{video_num}/4"
        }
    ])

    backup_btns = []
    for idx, b in enumerate(backups):
        b_code = make_short_code(b.get("url", ""))
        rank_label = f"#{idx+2}"
        if b_code:
            backup_btns.append({
                "text": f"🎬 Dựng bài {rank_label}",
                "url": f"https://t.me/{NEWS_BOT_USERNAME}?start=tu_{b_code}"
            })
    if backup_btns:
        buttons.append(backup_btns)

    payload = {
        "chat_id": target_chat,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": buttons
        }
    }

    if send_to_telegram:
        for attempt in range(3):
            try:
                r = requests.post(api_url, json=payload, timeout=30)
                if r.status_code == 200:
                    print(f"[+] Đã gửi gói tin Video {video_num}/4 sang Telegram chat {target_chat} thành công!")
                    return ranked
                else:
                    print(f"[!] Telegram trả mã {r.status_code}: {r.text}")
            except Exception as e:
                print(f"[!] Lỗi gửi Telegram (lần {attempt+1}):", e)
                time.sleep(2)

    return ranked

def format_telegram_digest(ranked_news, hours_min=1, hours_max=8):
    now_str = datetime.now(VN_TZ).strftime("%H:%M - %d/%m/%Y")
    text = (
        f"🔥 <b>BẢN TIN GIẬT GÂN & TƯƠNG TÁC CAO (YÊU CẦU THỦ CÔNG)</b>\n"
        f"<i>(Đăng trong khoảng: cách đây {hours_min} - {hours_max} tiếng)</i>\n"
        f"⏱️ <i>Cập nhật: {now_str} (Cloud 24/7)</i>\n"
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

    text += "👉 <i>Nhấn nút 'Dựng video' bên dưới để chuyển sang Bot News tạo video 9:16 ngay!</i>"
    return text

def scout_hot_news(hours_min=1.0, hours_max=8.0, send_to_telegram=False, bot_token=None, chat_id=None):
    token = bot_token or SCOUT_BOT_TOKEN
    target_chat = chat_id or ADMIN_CHAT_ID
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    print(f"[*] Đang quét RSS các đầu báo trong khung giờ {hours_min}h - {hours_max}h...")
    candidates = get_candidate_articles(hours_min=hours_min, hours_max=hours_max, exclude_seen=False)
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
            sc = make_short_code(it.get('url', ''))
            build_url = f"https://t.me/{NEWS_BOT_USERNAME}?start=tu_{sc}" if sc else f"https://t.me/{NEWS_BOT_USERNAME}"
            row = [
                {
                    "text": f"🎬 Dựng video #{rank_num} (1 chạm)",
                    "url": build_url
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

# ==============================================================================
# HỖ TRỢ LỆNH /check THỦ CÔNG
# ==============================================================================

def scan_realtime_breaking_news(threshold=7.8, max_age_hours=2.5, force_evaluate=False):
    """Quét tức thì theo yêu cầu của lệnh /check."""
    seen_articles = load_seen_articles()
    all_items = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_feed_items, FEEDS)
        for r in results:
            all_items.extend(r)

    all_items.sort(key=lambda x: x.get('age_hours', 99))
    candidates = [item for item in all_items if 0.0 <= item.get('age_hours', 99) <= max_age_hours]

    unique_candidates = []
    seen_in_batch = set()
    for item in candidates:
        key = get_clean_key(item['title'], item['link'])
        if key not in seen_in_batch and item['link'] not in seen_in_batch:
            seen_in_batch.add(key)
            seen_in_batch.add(item['link'])
            unique_candidates.append(item)

    new_unseen = []
    for item in unique_candidates:
        key = get_clean_key(item['title'], item['link'])
        if force_evaluate or (key not in seen_articles and item['link'] not in seen_articles):
            new_unseen.append(item)

    if not new_unseen:
        return []

    ranked = analyze_and_rank_sensational_news(new_unseen, top_n=3)
    return [it for it in ranked if float(it.get("viral_score", 0)) >= threshold]

def format_realtime_alert(item):
    now_time = datetime.now(VN_TZ).strftime("%H:%M")
    title = item.get("title", "")
    source = item.get("source", "")
    url = item.get("url", "")
    score = item.get("viral_score", 8.5)
    hook = item.get("sensational_hook", "")
    why = item.get("why_hot", "")
    summary = item.get("summary", "")
    age_h = item.get("hours_ago", 0)

    age_str = f"{age_h:.1f}h trước" if age_h > 0 else "vừa xuất bản"

    msg = (
        f"🚨 <b>[TIN NÓNG ĐỘT BIẾN - KIỂM TRA THỦ CÔNG]</b>\n"
        f"⏱️ <i>Lúc: {now_time} (Giờ VN)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📰 <b>{title}</b>\n"
        f"🏢 <b>Nguồn:</b> {source} | ⏳ <i>{age_str}</i>\n"
        f"⭐ <b>Điểm kịch tính:</b> <b>{score}/10</b> 🔥🔥🔥\n\n"
        f"🎯 <b>Tít hook video:</b>\n"
        f"<i>\"{hook}\"</i>\n\n"
        f"💥 <b>Điểm nóng gây sốt:</b>\n"
        f"👉 {why}\n\n"
        f"📝 <b>Tóm lược sự việc:</b>\n"
        f"<i>{summary}</i>\n\n"
        f"📋 <b>Link bài báo:</b>\n"
        f"<code>{url}</code>"
    )
    return msg

def create_realtime_markup(item):
    url = item.get("url", "")
    short_code = make_short_code(url)
    buttons = []
    if short_code:
        buttons.append([
            {
                "text": "🎬 Dựng video 9:16 ngay (1 chạm)",
                "url": f"https://t.me/{NEWS_BOT_USERNAME}?start=tu_{short_code}"
            }
        ])
    else:
        buttons.append([
            {
                "text": "🎬 Mở Bot Dựng Video 9:16 (@new3089bot)",
                "url": f"https://t.me/{NEWS_BOT_USERNAME}"
            }
        ])

    buttons.append([
        {
            "text": "📤 Chuyển tiếp link",
            "url": f"https://t.me/share/url?url={url}&text=Dựng%20video%209:16"
        },
        {
            "text": "📖 Đọc bài báo gốc",
            "url": url if url else "https://google.com"
        }
    ])
    return {"inline_keyboard": buttons}
