"""
ANTIGRAVITY SCOUT BOT - KOYEB CLOUD 24/7 APPLICATION
Tích hợp:
1. Web Health Check Server (Port 8000) để Koyeb kiểm tra trạng thái hoạt động liên tục.
2. Vòng lặp hẹn giờ tự động quét tin tức mỗi ngày (07:00, 11:30, 17:30, 21:00).
3. Lắng nghe lệnh Telegram trực tiếp (/hot, /schedule, /hengio, /start).
"""

import os
import re
import json
import time
import threading
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from hot_news_scout import (
    scout_hot_news, 
    SCOUT_BOT_TOKEN as BOT_TOKEN, 
    ADMIN_CHAT_ID, 
    NEWS_BOT_USERNAME, 
    API_BASE
)

PORT = int(os.environ.get("PORT", 8000))
SCHEDULE_PATH = os.path.join(os.path.dirname(__file__), "scout_schedule.json")

def load_schedule():
    if os.path.exists(SCHEDULE_PATH):
        try:
            with open(SCHEDULE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "enabled": True,
        "slots": ["07:00", "11:30", "17:30", "21:00"],
        "last_triggered": {}
    }

def save_schedule(sched):
    try:
        with open(SCHEDULE_PATH, "w", encoding="utf-8") as f:
            json.dump(sched, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[SCOUT_SCHEDULER] Lỗi lưu schedule:", e)

def send_msg(text, chat_id=ADMIN_CHAT_ID, reply_to=None, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    if reply_markup:
        payload["reply_markup"] = reply_markup
    for _ in range(3):
        try:
            r = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=25)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print("[SCOUT_BOT] Lỗi gửi tin, retry:", e)
            time.sleep(1)
    return None

def daily_scheduler_loop():
    print("[SCOUT_SCHEDULER] ✅ Tiến trình quét tin tự động 24/7 trên Koyeb Cloud đã kích hoạt!")
    while True:
        try:
            sched = load_schedule()
            if sched.get("enabled", True):
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                today_str = now.strftime("%Y-%m-%d")
                slots = sched.get("slots", ["07:00", "11:30", "17:30", "21:00"])
                last_trig = sched.get("last_triggered", {})

                if current_time in slots and last_trig.get(current_time) != today_str:
                    print(f"[SCOUT_SCHEDULER] ⏰ Đến giờ quét tin tự động: {current_time} ngày {today_str}!")

                    send_msg(
                        f"⏰ <b>[BẢN TIN TỰ ĐỘNG KOYEB CLOUD 24/7 - KHUNG GIỜ {current_time}]</b>\n\n"
                        f"🔥 Radar săn tin giật gân & tương tác cao đang quét các báo lớn cho ngày hôm nay ({now.strftime('%d/%m/%Y')})...\n"
                        f"⏳ Đang xử lý qua Gemini AI, bản tin TOP 5 sẽ gửi ngay bên dưới!"
                    )
                    try:
                        res_hot = scout_hot_news(
                            hours_min=6.0,
                            hours_max=9.0,
                            send_to_telegram=True,
                            bot_token=BOT_TOKEN,
                            chat_id=ADMIN_CHAT_ID
                        )
                        if res_hot and len(res_hot) > 0:
                            last_trig[current_time] = today_str
                            sched["last_triggered"] = last_trig
                            save_schedule(sched)
                            print(f"[SCOUT_SCHEDULER] ✅ Đã gửi thành công {len(res_hot)} bài hot cho khung giờ {current_time}!")
                    except Exception as err:
                        print("[SCOUT_SCHEDULER] Lỗi khi quét định kỳ:", err)
        except Exception as e:
            print("[SCOUT_SCHEDULER] Exception trong loop scheduler:", e)
        time.sleep(25)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        response_html = """
        <html>
            <head><title>Antigravity Scout Bot</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 50px;">
                <h1 style="color: #00aa00;">✅ Antigravity Scout Bot is Running 24/7 on Koyeb!</h1>
                <p>Status: Healthy | Scheduler Active (07:00, 11:30, 17:30, 21:00)</p>
            </body>
        </html>
        """
        self.wfile.write(response_html.encode('utf-8'))

    def log_message(self, format, *args):
        # Tắt bớt log HTTP để terminal gọn gàng
        return

def run_health_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, HealthHandler)
    print(f"[HTTP] ✅ Health Check server đang lắng nghe tại port {PORT}...")
    httpd.serve_forever()

def start_scout_bot():
    print("======================================================")
    print("   SCOUT BOT KOYEB CLOUD 24/7 (@findnew009bot)       ")
    print("======================================================")
    print(f"-> Bot Token: {BOT_TOKEN[:10]}... (OK)")
    print(f"-> Admin ID: {ADMIN_CHAT_ID}")
    print(f"-> Liên kết Bot News: @{NEWS_BOT_USERNAME}")
    print("-> Bot đang lắng nghe tin nhắn Telegram...")

    # Bật Health Server cho Koyeb
    t_http = threading.Thread(target=run_health_server, daemon=True)
    t_http.start()

    # Bật Scheduler tự động
    t_sched = threading.Thread(target=daily_scheduler_loop, daemon=True)
    t_sched.start()

    offset = None
    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=35)
            if resp.status_code != 200:
                time.sleep(2)
                continue

            updates = resp.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1

                # 1. Xử lý Callback Query (nếu người dùng bấm inline button)
                if "callback_query" in u:
                    cq = u["callback_query"]
                    cq_id = cq["id"]
                    cq_data = cq.get("data", "")
                    try:
                        requests.post(f"{API_BASE}/answerCallbackQuery", json={"callback_query_id": cq_id, "text": f"Đã nhận lệnh: {cq_data}"})
                    except Exception:
                        pass
                    continue

                if "message" not in u:
                    continue

                msg = u["message"]
                chat_id = msg.get("chat", {}).get("id")
                msg_id = msg.get("message_id")
                text = msg.get("text", "").strip()

                if not text:
                    continue

                lower_text = text.lower().strip()

                if lower_text in ["/start", "start", "bat dau", "bắt đầu"]:
                    welcome = (
                        "👋 <b>Chào mừng bạn đến với Scout Bot (Koyeb Cloud 24/7)!</b>\n\n"
                        "🔥 <b>Nhiệm vụ của bot:</b>\n"
                        "• Tự động quét và tìm kiếm tin tức giật gân, nhiều tương tác trong 6 - 9 tiếng trước.\n"
                        "• Đánh giá và lọc ra TOP 5 bài báo hot nhất qua Gemini AI.\n"
                        "• Gửi báo cáo định kỳ mỗi ngày hoặc theo lệnh của bạn!\n\n"
                        "📋 <b>Các lệnh điều khiển:</b>\n"
                        "• <code>/hot</code> : Quét tin giật gân ngay lập tức (6-9h trước)\n"
                        "• <code>/hot 3 6</code> : Quét tin trong khoảng 3 đến 6 tiếng trước\n"
                        "• <code>/schedule</code> : Xem lịch tự động quét mỗi ngày\n"
                        "• <code>/hengio 07:00, 11:30, 17:30, 21:00</code> : Đổi lịch quét tự động\n"
                        "• <code>/schedule on</code> hoặc <code>/schedule off</code> : Bật/tắt tự động\n\n"
                        f"🎬 Khi chọn được bài ưng ý, chạm vào <b>Dựng video</b> để chuyển sang @{NEWS_BOT_USERNAME} tạo video 9:16!"
                    )
                    send_msg(welcome, chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/schedule", "lich quet", "lịch quét", "/lich"]:
                    sched = load_schedule()
                    status_str = "🟢 Đang bật" if sched.get("enabled", True) else "🔴 Đang tắt"
                    slots_str = ", ".join(sched.get("slots", []))
                    msg_sched = (
                        f"⏰ <b>LỊCH TỰ ĐỘNG QUÉT TIN MỖI NGÀY (KOYEB CLOUD 24/7)</b>\n\n"
                        f"• <b>Trạng thái:</b> {status_str}\n"
                        f"• <b>Các khung giờ quét:</b> <code>{slots_str}</code>\n\n"
                        f"💡 <b>Muốn đổi giờ quét?</b>\n"
                        "Gõ lệnh: <code>/hengio 07:00, 11:30, 17:30, 21:00</code>\n\n"
                        "⚙️ <b>Bật/Tắt:</b>\n"
                        "  <code>/schedule on</code> : Bật tự động\n"
                        "  <code>/schedule off</code> : Tắt tự động"
                    )
                    send_msg(msg_sched, chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/schedule on", "bat lich", "bật lịch"]:
                    sched = load_schedule()
                    sched["enabled"] = True
                    save_schedule(sched)
                    send_msg("🟢 <b>Đã BẬT tính năng tự động quét và gửi tin giật gân mỗi ngày!</b>", chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/schedule off", "tat lich", "tắt lịch"]:
                    sched = load_schedule()
                    sched["enabled"] = False
                    save_schedule(sched)
                    send_msg("🔴 <b>Đã TẮT tính năng tự động quét mỗi ngày.</b> Bạn vẫn có thể dùng lệnh <code>/hot</code> để quét thủ công bất kỳ lúc nào.", chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text.startswith("/hengio") or lower_text.startswith("/settime"):
                    args = text.split(maxsplit=1)
                    if len(args) > 1:
                        raw_times = re.findall(r'(\b\d{1,2}:\d{2}\b)', args[1])
                        valid_slots = []
                        for t in raw_times:
                            parts = t.split(":")
                            h = int(parts[0])
                            m = int(parts[1])
                            if 0 <= h <= 23 and 0 <= m <= 59:
                                valid_slots.append(f"{h:02d}:{m:02d}")
                        if valid_slots:
                            valid_slots = sorted(list(set(valid_slots)))
                            sched = load_schedule()
                            sched["slots"] = valid_slots
                            sched["enabled"] = True
                            save_schedule(sched)
                            send_msg(
                                f"✅ <b>ĐÃ CẬP NHẬT LỊCH TỰ ĐỘNG QUÉT MỖI NGÀY:</b>\n\n"
                                f"⏰ Các khung giờ: <code>{', '.join(valid_slots)}</code>\n"
                                f"🟢 Bot sẽ tự động chạy đúng các khung giờ trên!",
                                chat_id=chat_id,
                                reply_to=msg_id
                            )
                            continue
                    send_msg(
                        "⚠️ <b>Cú pháp không đúng!</b>\nVí dụ: <code>/hengio 07:00, 11:30, 17:30, 21:00</code>",
                        chat_id=chat_id,
                        reply_to=msg_id
                    )
                    continue

                if lower_text.startswith("/hot"):
                    parts = text.split()
                    h_min, h_max = 6.0, 9.0
                    if len(parts) >= 3:
                        try:
                            h_min = float(parts[1])
                            h_max = float(parts[2])
                            if h_min > h_max:
                                h_min, h_max = h_max, h_min
                        except ValueError:
                            pass
                    elif len(parts) == 2:
                        try:
                            val = float(parts[1])
                            h_min = max(1.0, val - 1.5)
                            h_max = val + 1.5
                        except ValueError:
                            pass

                    send_msg(
                        f"🔍 <b>Đang kích hoạt radar quét tin nóng ({h_min:g}h - {h_max:g}h trước)...</b>\n"
                        f"⏳ Đang lọc các báo lớn và phân tích qua Gemini AI, vui lòng chờ trong giây lát!",
                        chat_id=chat_id,
                        reply_to=msg_id
                    )
                    threading.Thread(
                        target=scout_hot_news,
                        kwargs={"hours_min": h_min, "hours_max": h_max, "send_to_telegram": True, "bot_token": BOT_TOKEN, "chat_id": chat_id},
                        daemon=True
                    ).start()
                    continue

                # Mặc định hướng dẫn
                send_msg(
                    f"🤖 Bạn vừa gửi: <i>\"{text}\"</i>\n\n"
                    f"👉 Gõ <b>/hot</b> để quét tin tức giật gân trong 6-9 tiếng trước!\n"
                    f"👉 Gõ <b>/schedule</b> để xem lịch tự động quét mỗi ngày.\n"
                    f"👉 Hoặc mở trực tiếp <b>@{NEWS_BOT_USERNAME}</b> nếu bạn muốn gửi link bài báo cụ thể để dựng video.",
                    chat_id=chat_id,
                    reply_to=msg_id
                )

        except requests.exceptions.RequestException:
            time.sleep(3)
        except Exception as e:
            print(f"[SCOUT_BOT] Lỗi loop: {e}")
            time.sleep(3)

if __name__ == "__main__":
    start_scout_bot()
