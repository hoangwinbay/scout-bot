"""
ANTIGRAVITY SCOUT BOT - RENDER CLOUD 24/7 APPLICATION
Chuyên trách:
1. Web Health Check Server (Port 10000 / $PORT) để Render giữ service luôn sống 24/7.
2. Tự động gửi gói tin cho 4 VIDEO MỖI NGÀY vào đúng 4 khung giờ vàng:
   - 07:00 : Video 1/4 (Bản tin Sáng)
   - 11:30 : Video 2/4 (Bản tin Trưa)
   - 17:30 : Video 3/4 (Bản tin Chiều)
   - 20:30 : Video 4/4 (Bản tin Tối)
3. Cung cấp nút bấm 1-chạm (TinyURL) chuyển thẳng sang Bot News @new3089bot để dựng video Full HD 9:16.
4. Lắng nghe lệnh Telegram trực tiếp (/schedule, /hengio, /hot, /check, /start).
"""

import os
import re
import json
import time
import threading
import requests
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

VN_TZ = timezone(timedelta(hours=7))

from hot_news_scout import (
    scout_video_slot_news,
    scout_hot_news,
    scan_realtime_breaking_news,
    format_realtime_alert,
    create_realtime_markup,
    SCOUT_BOT_TOKEN as BOT_TOKEN, 
    ADMIN_CHAT_ID, 
    NEWS_BOT_USERNAME, 
    API_BASE
)

PORT = int(os.environ.get("PORT", 8000))
SCHEDULE_PATH = os.path.join(os.path.dirname(__file__), "scout_schedule.json")
REALTIME_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "realtime_config.json")

# --- Chẩn đoán từ xa (endpoint /diag) ---
START_TS = time.time()
DIAG = {
    "loop_started": False,
    "polls": 0,
    "last_status": None,
    "last_poll_at": None,
    "last_error": None,
    "self_ping": None,
    "self_ping_status": None,
}

def load_schedule():
    if os.path.exists(SCHEDULE_PATH):
        try:
            with open(SCHEDULE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "enabled": True,
        "slots": ["07:00", "11:30", "17:30", "20:30"],
        "last_triggered": {}
    }

def save_schedule(sched):
    try:
        with open(SCHEDULE_PATH, "w", encoding="utf-8") as f:
            json.dump(sched, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[SCOUT_SCHEDULER] Lỗi lưu schedule:", e)

def get_slot_info(slot_str, all_slots):
    """Xác định số thứ tự video (1..4) và tên bản tin theo khung giờ."""
    sorted_slots = sorted(list(set(all_slots)))
    idx = sorted_slots.index(slot_str) + 1 if slot_str in sorted_slots else 1
    names = {
        "07:00": "Bản Tin Sáng",
        "11:30": "Bản Tin Trưa",
        "17:30": "Bản Tin Chiều",
        "20:30": "Bản Tin Tối",
        "21:00": "Bản Tin Tối",
    }
    name = names.get(slot_str, f"Bản Tin Khung Giờ {slot_str}")
    return idx, name

def load_realtime_config():
    if os.path.exists(REALTIME_CONFIG_PATH):
        try:
            with open(REALTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "enabled": False,        # Mặc định TẮT quét liên tục để tránh bắn tin làm phiền
        "interval_seconds": 300,
        "threshold": 8.0,
        "max_age_hours": 2.0
    }

def save_realtime_config(cfg):
    try:
        with open(REALTIME_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[REALTIME] Lỗi lưu realtime_config:", e)

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
    """
    Tiến trình hẹn giờ chính:
    Chỉ gửi tin đúng vào 4 khung giờ vàng mỗi ngày (tương ứng 4 video 9:16).
    """
    print("[SCOUT_SCHEDULER] ✅ Tiến trình tự động gửi 4 Video/ngày (GMT+7) đã kích hoạt!")
    while True:
        try:
            sched = load_schedule()
            if sched.get("enabled", True):
                now = datetime.now(VN_TZ)
                current_time = now.strftime("%H:%M")
                today_str = now.strftime("%Y-%m-%d")
                slots = sched.get("slots", ["07:00", "11:30", "17:30", "20:30"])
                last_trig = sched.get("last_triggered", {})

                if current_time in slots and last_trig.get(current_time) != today_str:
                    video_num, session_name = get_slot_info(current_time, slots)
                    total_slots = len(slots)
                    print(f"[SCOUT_SCHEDULER] ⏰ Đến giờ gửi tin Video {video_num}/{total_slots}: {session_name} ({current_time}) ngày {today_str}!")

                    send_msg(
                        f"⏰ <b>[BẮT ĐẦU KHUNG GIỜ VIDEO {video_num}/{total_slots} • {session_name.upper()} ({current_time})]</b>\n\n"
                        f"🔍 Gemini AI đang quét các đầu báo lớn và chọn bài giật gân, viral nhất cho video này...\n"
                        f"⏳ Gói tin Video hoàn chỉnh sẽ gửi ngay dưới đây trong giây lát!"
                    )

                    try:
                        res = scout_video_slot_news(
                            slot_time=current_time,
                            video_num=video_num,
                            session_name=session_name,
                            send_to_telegram=True,
                            bot_token=BOT_TOKEN,
                            chat_id=ADMIN_CHAT_ID
                        )
                        if res:
                            last_trig[current_time] = today_str
                            sched["last_triggered"] = last_trig
                            save_schedule(sched)
                            print(f"[SCOUT_SCHEDULER] ✅ Đã gửi thành công gói tin Video {video_num}/{total_slots} cho khung giờ {current_time}!")
                    except Exception as err:
                        print(f"[SCOUT_SCHEDULER] Lỗi khi xử lý gói tin video {current_time}:", err)
        except Exception as e:
            print("[SCOUT_SCHEDULER] Ngoại lệ trong loop scheduler:", e)
        time.sleep(20)

def realtime_monitor_loop():
    """Vòng lặp rà soát liên tục (chỉ chạy khi người dùng chủ động bật /realtime on)."""
    while True:
        try:
            cfg = load_realtime_config()
            if cfg.get("enabled", False):
                threshold = float(cfg.get("threshold", 8.0))
                max_age = float(cfg.get("max_age_hours", 2.0))

                hot_items = scan_realtime_breaking_news(
                    threshold=threshold,
                    max_age_hours=max_age
                )
                if hot_items:
                    for item in hot_items:
                        text = format_realtime_alert(item)
                        markup = create_realtime_markup(item)
                        send_msg(text, chat_id=ADMIN_CHAT_ID, reply_markup=markup)
                        time.sleep(1.2)
        except Exception as e:
            print("[REALTIME_MONITOR] Ngoại lệ:", e)

        cfg = load_realtime_config()
        sleep_sec = max(60, int(cfg.get("interval_seconds", 300)))
        time.sleep(sleep_sec)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/healthz', '/ping', '/live']:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"OK")
            return

        if self.path == '/diag':
            import platform
            sched = load_schedule()
            cfg = load_realtime_config()
            info = {
                "ok": True,
                "uptime_seconds": int(time.time() - START_TS),
                "python": platform.python_version(),
                "port": PORT,
                "bot_token_set": bool(BOT_TOKEN),
                "bot_token_len": len(BOT_TOKEN or ""),
                "api_base": (API_BASE.replace(BOT_TOKEN, BOT_TOKEN[:6] + "***") if BOT_TOKEN else "https://api.telegram.org/bot<EMPTY>"),
                "loop_started": DIAG["loop_started"],
                "polls": DIAG["polls"],
                "last_status": DIAG["last_status"],
                "last_poll_at": DIAG["last_poll_at"],
                "last_error": DIAG["last_error"],
                "self_ping": DIAG["self_ping"],
                "self_ping_status": DIAG["self_ping_status"],
                "render_url_set": bool(os.environ.get("RENDER_EXTERNAL_URL")),
                "server_time_vn": datetime.now(VN_TZ).strftime('%H:%M:%S %d/%m/%Y'),
                "schedule_enabled": sched.get("enabled", True),
                "video_slots": sched.get("slots", []),
                "last_triggered": sched.get("last_triggered", {}),
                "realtime_auto_enabled": cfg.get("enabled", False),
            }
            if BOT_TOKEN:
                try:
                    r = requests.get(f"{API_BASE}/getMe", timeout=10)
                    info["getme_http"] = r.status_code
                    if r.status_code == 200:
                        info["getme"] = r.json().get("result", {}).get("username")
                    else:
                        info["getme_body"] = r.text[:200]
                except Exception as e:
                    info["getme_error"] = str(e)[:200]
            body = json.dumps(info, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        now_vn = datetime.now(VN_TZ).strftime('%H:%M:%S - %d/%m/%Y')
        sched = load_schedule()
        slots_str = ", ".join(sched.get("slots", []))
        response_html = f"""
        <html>
            <head><title>Antigravity Scout Bot - 4 Videos/Day</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 50px;">
                <h1 style="color: #0088cc;">🎬 Antigravity Scout Bot is Running 24/7!</h1>
                <p>⏰ <b>Lịch gửi tin 4 Video mỗi ngày:</b> <code>{slots_str}</code> (Giờ VN)</p>
                <p>Server Time (Vietnam GMT+7): <b>{now_vn}</b></p>
                <p style="color: #666; font-size: 13px;">Health Check Endpoint: <code>/healthz</code> | Diag: <code>/diag</code></p>
            </body>
        </html>
        """
        self.wfile.write(response_html.encode('utf-8'))

    def log_message(self, format, *args):
        return

def run_health_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, HealthHandler)
    print(f"[HTTP] ✅ Health Check server đang lắng nghe tại port {PORT}...")
    httpd.serve_forever()

def self_ping_loop():
    """Tự gọi healthz của chính mình mỗi 10 phút để Render free không spin-down."""
    base = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base:
        print("[SELF-PING] Không có RENDER_EXTERNAL_URL -> bỏ qua tự ping.")
        return
    if not BOT_TOKEN:
        print("[SELF-PING] Không có BOT_TOKEN -> bỏ qua tự ping.")
        return
    print(f"[SELF-PING] Tự ping {base}/healthz mỗi 10 phút để giữ service thức 24/7.")
    first = True
    while True:
        time.sleep(60 if first else 600)
        first = False
        try:
            r = requests.get(f"{base}/healthz", timeout=20)
            DIAG["self_ping"] = datetime.now(VN_TZ).strftime('%H:%M:%S')
            DIAG["self_ping_status"] = r.status_code
        except Exception as e:
            DIAG["self_ping"] = "lỗi: " + str(e)[:80]

def start_scout_bot():
    print("======================================================")
    print("   SCOUT BOT RENDER CLOUD 24/7 (@findnew009bot)       ")
    print("   CHẾ ĐỘ: 4 KHUNG GIỜ VÀNG = 4 VIDEO / NGÀY        ")
    print("======================================================")
    if not BOT_TOKEN:
        print("❌ [LỖI NGHIÊM TRỌNG] Biến môi trường BOT_TOKEN đang bị TRỐNG!")
    else:
        print(f"-> Bot Token: {BOT_TOKEN[:10]}... (OK)")

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        print("⚠️ [CẢNH BÁO] Biến GEMINI_API_KEY đang bị TRỐNG!")
    else:
        print("-> Gemini API Key: (Đã cấu hình)")

    print(f"-> Admin ID: {ADMIN_CHAT_ID}")
    print(f"-> Liên kết Bot News: @{NEWS_BOT_USERNAME}")
    print(f"-> Giờ Việt Nam hiện tại: {datetime.now(VN_TZ).strftime('%H:%M:%S %d/%m/%Y')}")

    sched = load_schedule()
    slots_str = ", ".join(sched.get("slots", []))
    print(f"-> 4 Khung giờ gửi tin Video: {slots_str}")

    # 1. Bật Health Server
    t_http = threading.Thread(target=run_health_server, daemon=True)
    t_http.start()

    # 2. Tự giữ service thức trên Render free
    t_ping = threading.Thread(target=self_ping_loop, daemon=True)
    t_ping.start()

    # 3. Bật Scheduler tự động gửi tin 4 Video mỗi ngày
    t_sched = threading.Thread(target=daily_scheduler_loop, daemon=True)
    t_sched.start()

    # 4. Bật thread radar liên tục (chỉ chạy nếu được bật)
    t_realtime = threading.Thread(target=realtime_monitor_loop, daemon=True)
    t_realtime.start()

    offset = None
    last_err_time = 0
    DIAG["loop_started"] = True

    while True:
        try:
            DIAG["polls"] += 1
            DIAG["last_poll_at"] = datetime.now(VN_TZ).strftime('%H:%M:%S')
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=35)
            DIAG["last_status"] = resp.status_code
            if resp.status_code != 200:
                cur_t = time.time()
                if cur_t - last_err_time > 15:
                    print(f"[SCOUT_BOT CẢNH BÁO] getUpdates thất bại (HTTP {resp.status_code}): {resp.text}")
                    last_err_time = cur_t
                time.sleep(3)
                continue

            updates = resp.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1

                # 1. Callback query
                if "callback_query" in u:
                    cq = u["callback_query"]
                    try:
                        requests.post(f"{API_BASE}/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "Đã ghi nhận yêu cầu!"})
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
                        "👋 <b>Chào mừng bạn đến với Scout Bot (@findnew009bot)!</b>\n\n"
                        "🎬 <b>Quy trình sản xuất 4 Video Tin Tức / Ngày:</b>\n"
                        "Bot chỉ gửi tin tức vào đúng <b>4 khung giờ phát sóng vàng</b> trong ngày (tương ứng 4 video 9:16):\n"
                        "1️⃣ <b>07:00</b> • Video 1/4 (Bản tin Sáng)\n"
                        "2️⃣ <b>11:30</b> • Video 2/4 (Bản tin Trưa)\n"
                        "3️⃣ <b>17:30</b> • Video 3/4 (Bản tin Chiều)\n"
                        "4️⃣ <b>20:30</b> • Video 4/4 (Bản tin Tối)\n\n"
                        "✨ <b>Cách sử dụng:</b> Mỗi thông báo gồm Bài báo #1 đề xuất làm video chính + các bài dự phòng. Nhấn nút <b>🎬 DỰNG VIDEO NGAY (1 CHẠM)</b> để tự động chuyển sang Bot News dựng video ngay trên máy!\n\n"
                        "📋 <b>Lệnh điều khiển:</b>\n"
                        "• <code>/schedule</code> : Xem lịch phát sóng 4 video\n"
                        "• <code>/hengio 07:00, 11:30, 17:30, 20:30</code> : Đổi khung giờ theo ý muốn\n"
                        "• <code>/hot</code> : Quét và xuất ngay 1 gói tin Video tại thời điểm này\n"
                        "• <code>/check</code> : Kiểm tra nhanh các bài báo mới nhất"
                    )
                    send_msg(welcome, chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/schedule", "lich quet", "lịch quét", "/lich"]:
                    sched = load_schedule()
                    slots = sched.get("slots", ["07:00", "11:30", "17:30", "20:30"])
                    status_str = "🟢 Đang hoạt động" if sched.get("enabled", True) else "🔴 Đang tạm dừng"
                    lines = []
                    for s in slots:
                        idx, name = get_slot_info(s, slots)
                        lines.append(f"  • <b>{s}</b> : Video {idx}/{len(slots)} ({name})")
                    slots_display = "\n".join(lines)
                    msg_sched = (
                        f"⏰ <b>LỊCH GỬI TIN 4 VIDEO MỖI NGÀY (CLOUD 24/7)</b>\n\n"
                        f"• <b>Trạng thái:</b> {status_str}\n"
                        f"• <b>Các khung giờ phát sóng:</b>\n{slots_display}\n\n"
                        f"💡 <b>Muốn đổi khung giờ?</b>\n"
                        f"Gõ lệnh: <code>/hengio 07:00, 11:30, 17:30, 20:30</code>\n\n"
                        f"⚙️ <code>/schedule on</code> : Bật tự động | <code>/schedule off</code> : Tắt tự động"
                    )
                    send_msg(msg_sched, chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/schedule on", "bat lich", "bật lịch"]:
                    sched = load_schedule()
                    sched["enabled"] = True
                    save_schedule(sched)
                    send_msg("🟢 <b>Đã BẬT lịch tự động gửi tin 4 Video mỗi ngày!</b>", chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/schedule off", "tat lich", "tắt lịch"]:
                    sched = load_schedule()
                    sched["enabled"] = False
                    save_schedule(sched)
                    send_msg("🔴 <b>Đã TẮT lịch tự động gửi tin.</b> Bạn vẫn có thể dùng lệnh <code>/hot</code> để quét thủ công bất kỳ lúc nào.", chat_id=chat_id, reply_to=msg_id)
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

                            lines = []
                            for s in valid_slots:
                                idx, name = get_slot_info(s, valid_slots)
                                lines.append(f"  • <b>{s}</b> : Video {idx}/{len(valid_slots)} ({name})")
                            slots_display = "\n".join(lines)

                            send_msg(
                                f"✅ <b>ĐÃ CẬP NHẬT LỊCH PHÁT SÓNG MỚI:</b>\n\n"
                                f"{slots_display}\n\n"
                                f"🟢 Bot sẽ tự động gửi gói tin đúng vào các khung giờ trên!",
                                chat_id=chat_id,
                                reply_to=msg_id
                            )
                            continue
                    send_msg(
                        "⚠️ <b>Cú pháp không đúng!</b>\nVí dụ: <code>/hengio 07:00, 11:30, 17:30, 20:30</code>",
                        chat_id=chat_id,
                        reply_to=msg_id
                    )
                    continue

                if lower_text.startswith("/hot"):
                    send_msg(
                        f"🔍 <b>Đang quét tin tức nóng và chuẩn bị gói tin Video theo yêu cầu...</b>\n"
                        f"⏳ Gemini AI đang chọn bài báo giật gân nhất và tạo nút dựng video 1-chạm, vui lòng chờ trong giây lát!",
                        chat_id=chat_id,
                        reply_to=msg_id
                    )
                    def run_manual_hot(target_c=chat_id):
                        now_h = datetime.now(VN_TZ).strftime("%H:%M")
                        scout_video_slot_news(
                            slot_time=now_h,
                            video_num="Yêu cầu",
                            session_name="Tuyển Chọn Nóng",
                            send_to_telegram=True,
                            bot_token=BOT_TOKEN,
                            chat_id=target_c
                        )
                    threading.Thread(target=run_manual_hot, daemon=True).start()
                    continue

                if lower_text in ["/check", "kiem tra", "kiểm tra", "check"]:
                    send_msg("🔍 <b>Đang kích hoạt quét rà soát toàn bộ các báo lớn ngay lập tức...</b>", chat_id=chat_id, reply_to=msg_id)
                    def run_manual_check(target_c=chat_id):
                        cfg = load_realtime_config()
                        found = scan_realtime_breaking_news(
                            threshold=float(cfg.get("threshold", 7.8)),
                            max_age_hours=float(cfg.get("max_age_hours", 2.0)),
                            force_evaluate=True
                        )
                        if found:
                            send_msg(f"🎯 <b>Tìm thấy {len(found)} bài báo nóng đột biến:</b>", chat_id=target_c)
                            for it in found:
                                txt = format_realtime_alert(it)
                                mk = create_realtime_markup(it)
                                send_msg(txt, chat_id=target_c, reply_markup=mk)
                                time.sleep(1.2)
                        else:
                            send_msg("✅ <b>Không có tin nóng đột biến mới nào vượt ngưỡng tại thời điểm này.</b>", chat_id=target_c)
                    threading.Thread(target=run_manual_check, daemon=True).start()
                    continue

                if lower_text in ["/realtime", "radar", "realtime", "trang thai"]:
                    cfg = load_realtime_config()
                    st_str = "🟢 Đang BẬT rà soát liên tục" if cfg.get("enabled", False) else "🔴 Đang TẮT (chỉ gửi theo 4 khung giờ cố định)"
                    inter = cfg.get("interval_seconds", 300)
                    thresh = cfg.get("threshold", 8.0)
                    msg_rt = (
                        f"⚡ <b>TRẠNG THÁI RADAR SĂN TIN LIÊN TỤC</b>\n\n"
                        f"• <b>Trạng thái:</b> {st_str}\n"
                        f"• <b>Chu kỳ:</b> Mỗi {inter}s\n"
                        f"• <b>Ngưỡng điểm kịch tính:</b> {thresh}/10\n\n"
                        f"<i>Lưu ý: Mặc định tính năng này đã TẮT để bot CHỈ gửi tin vào đúng 4 thời điểm cố định trong ngày tương đương 4 video.</i>\n\n"
                        f"• <code>/realtime on</code> : Bật quét liên tục\n"
                        f"• <code>/realtime off</code> : Tắt quét liên tục"
                    )
                    send_msg(msg_rt, chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/realtime on", "bat realtime", "bật realtime"]:
                    cfg = load_realtime_config()
                    cfg["enabled"] = True
                    save_realtime_config(cfg)
                    send_msg("🟢 <b>Đã BẬT tính năng quét liên tục ngoài 4 khung giờ cố định.</b>", chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/realtime off", "tat realtime", "tắt realtime"]:
                    cfg = load_realtime_config()
                    cfg["enabled"] = False
                    save_realtime_config(cfg)
                    send_msg("🔴 <b>Đã TẮT quét liên tục.</b> Bot sẽ CHỈ gửi tin đúng 4 thời điểm trong ngày tương đương 4 video.", chat_id=chat_id, reply_to=msg_id)
                    continue

                # Mặc định hướng dẫn
                send_msg(
                    f"🤖 Bạn vừa gửi: <i>\"{text}\"</i>\n\n"
                    f"👉 Bot được cài đặt <b>chỉ gửi tin vào 4 khung giờ phát sóng vàng</b> tương đương 4 video mỗi ngày (07:00, 11:30, 17:30, 20:30).\n"
                    f"👉 Gõ <b>/schedule</b> để xem hoặc <b>/hengio</b> để đổi giờ.\n"
                    f"👉 Gõ <b>/hot</b> nếu muốn lấy ngay gói tin Video tại thời điểm này.",
                    chat_id=chat_id,
                    reply_to=msg_id
                )

        except requests.exceptions.RequestException as e:
            DIAG["last_error"] = "RequestException: " + str(e)[:180]
            time.sleep(3)
        except Exception as e:
            DIAG["last_error"] = "Exception: " + str(e)[:180]
            print(f"[SCOUT_BOT] Lỗi loop: {e}")
            time.sleep(3)

if __name__ == "__main__":
    start_scout_bot()
