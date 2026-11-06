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
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

VN_TZ = timezone(timedelta(hours=7))

from hot_news_scout import (
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

# --- Chan doan tu xa (endpoint /diag) ---
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
        "slots": ["07:00", "11:30", "17:30", "21:00"],
        "last_triggered": {}
    }

def save_schedule(sched):
    try:
        with open(SCHEDULE_PATH, "w", encoding="utf-8") as f:
            json.dump(sched, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[SCOUT_SCHEDULER] Lỗi lưu schedule:", e)

REALTIME_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "realtime_config.json")

def load_realtime_config():
    if os.path.exists(REALTIME_CONFIG_PATH):
        try:
            with open(REALTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "enabled": True,
        "interval_seconds": 180,  # Quét liên tục mỗi 3 phút
        "threshold": 7.0,         # Điểm kịch tính viral >= 7.0/10
        "max_age_hours": 2.0
    }

def save_realtime_config(cfg):
    try:
        with open(REALTIME_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[REALTIME] Lỗi lưu realtime_config:", e)

def realtime_monitor_loop():
    print("[REALTIME_MONITOR] 🚀 Tiến trình rà soát tin nóng liên tục 24/7 (Real-time Scout) đã kích hoạt!")
    time.sleep(3)
    while True:
        try:
            cfg = load_realtime_config()
            if cfg.get("enabled", True):
                threshold = float(cfg.get("threshold", 7.0))
                max_age = float(cfg.get("max_age_hours", 2.0))

                hot_items = scan_realtime_breaking_news(
                    threshold=threshold,
                    max_age_hours=max_age
                )

                if hot_items:
                    print(f"[REALTIME_MONITOR] 🔥 BÙNG NỔ TIN NÓNG! Tìm thấy {len(hot_items)} bài kịch tính >= {threshold}. Đang gửi cảnh báo...")
                    for item in hot_items:
                        text = format_realtime_alert(item)
                        markup = create_realtime_markup(item)
                        send_msg(text, chat_id=ADMIN_CHAT_ID, reply_markup=markup)
                        time.sleep(1.2)
        except Exception as e:
            print("[REALTIME_MONITOR] Ngoại lệ trong loop rà soát:", e)

        cfg = load_realtime_config()
        sleep_sec = max(30, int(cfg.get("interval_seconds", 180)))
        time.sleep(sleep_sec)

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
    print("[SCOUT_SCHEDULER] ✅ Tiến trình quét tin tự động 24/7 (GMT+7) đã kích hoạt!")
    while True:
        try:
            sched = load_schedule()
            if sched.get("enabled", True):
                now = datetime.now(VN_TZ)
                current_time = now.strftime("%H:%M")
                today_str = now.strftime("%Y-%m-%d")
                slots = sched.get("slots", ["07:00", "11:30", "17:30", "21:00"])
                last_trig = sched.get("last_triggered", {})

                if current_time in slots and last_trig.get(current_time) != today_str:
                    print(f"[SCOUT_SCHEDULER] ⏰ Đến giờ quét tin tự động: {current_time} ngày {today_str} (Giờ VN)!")

                    send_msg(
                        f"⏰ <b>[BẢN TIN TỰ ĐỘNG CLOUD 24/7 - KHUNG GIỜ {current_time}]</b>\n\n"
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
        if self.path in ['/healthz', '/ping', '/live']:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"OK")
            return

        if self.path == '/diag':
            import platform
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
        cfg = load_realtime_config()
        rt_status = "🟢 Đang quét liên tục" if cfg.get("enabled", True) else "🔴 Đang tắt"
        rt_interval = cfg.get("interval_seconds", 180)
        rt_thresh = cfg.get("threshold", 7.8)
        response_html = f"""
        <html>
            <head><title>Antigravity Scout Bot - Real-time 24/7</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 50px;">
                <h1 style="color: #00aa00;">✅ Antigravity Scout Bot is Running 24/7!</h1>
                <p>⚡ <b>Radar săn tin tức liên tục:</b> {rt_status} (Quét mỗi {rt_interval}s, Ngưỡng: {rt_thresh}/10)</p>
                <p>⏰ <b>Bản tin tổng hợp định kỳ:</b> Active (07:00, 11:30, 17:30, 21:00 GMT+7)</p>
                <p>Server Time (Vietnam GMT+7): <b>{now_vn}</b></p>
                <p style="color: #666; font-size: 13px;">Uptime Ping Endpoint: <code>/ping</code></p>
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

def self_ping_loop():
    """Tu goi healthz cua chinh minh moi 10 phut de Render free khong spin-down."""
    base = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base:
        print("[SELF-PING] Không có RENDER_EXTERNAL_URL -> bỏ qua tự ping.")
        return
    if not BOT_TOKEN:
        print("[SELF-PING] Không có BOT_TOKEN -> không tự ping (tránh tốn giờ free vô ích).")
        return
    print(f"[SELF-PING] Tự ping {base}/healthz mỗi 10 phút để giữ service thức.")
    while True:
        time.sleep(600)
        try:
            r = requests.get(f"{base}/healthz", timeout=20)
            DIAG["self_ping"] = datetime.now(VN_TZ).strftime('%H:%M:%S')
            DIAG["self_ping_status"] = r.status_code
        except Exception as e:
            DIAG["self_ping"] = "lỗi: " + str(e)[:80]

def start_scout_bot():
    print("======================================================")
    print("   SCOUT BOT CLOUD 24/7 (@findnew009bot)              ")
    print("======================================================")
    if not BOT_TOKEN:
        print("❌ [LỖI NGHIÊM TRỌNG] Biến môi trường BOT_TOKEN đang bị TRỐNG!")
        print("   -> Bạn cần thêm biến BOT_TOKEN vào phần Environment trên Render/Koyeb!")
    else:
        print(f"-> Bot Token: {BOT_TOKEN[:10]}... (OK)")

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        print("⚠️ [CẢNH BÁO] Biến môi trường GEMINI_API_KEY đang bị TRỐNG!")
        print("   -> Cần thêm GEMINI_API_KEY vào Environment để phân tích tin tức!")
    else:
        print("-> Gemini API Key: (Đã cấu hình)")

    print(f"-> Admin ID: {ADMIN_CHAT_ID}")
    print(f"-> Liên kết Bot News: @{NEWS_BOT_USERNAME}")
    print(f"-> Giờ Việt Nam hiện tại: {datetime.now(VN_TZ).strftime('%H:%M:%S %d/%m/%Y')}")
    print("-> Bot đang lắng nghe tin nhắn Telegram...")

    # Bật Health Server
    t_http = threading.Thread(target=run_health_server, daemon=True)
    t_http.start()

    # Tu giu service thuc tren Render free (khong de bi spin-down sau 15 phut)
    t_ping = threading.Thread(target=self_ping_loop, daemon=True)
    t_ping.start()

    # Bật Radar rà soát tin nóng liên tục 24/7 (Real-time Scout)
    t_realtime = threading.Thread(target=realtime_monitor_loop, daemon=True)
    t_realtime.start()

    # Bật Scheduler tự động gửi báo cáo định kỳ
    t_sched = threading.Thread(target=daily_scheduler_loop, daemon=True)
    t_sched.start()

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
                        "👋 <b>Chào mừng bạn đến với Scout Bot Cloud 24/7 (@findnew009bot)!</b>\n\n"
                        "🔥 <b>Cơ chế hoạt động kép:</b>\n"
                        "1. ⚡ <b>Radar Quét Liên Tục (Real-time):</b> Quét liên tục các báo lớn cứ mỗi 3 phút. Cứ có bài nào vừa đăng mà THỰC SỰ GIẬT GÂN, KỊCH TÍNH, ĐỘT BIẾN là bắn tin ngay lập tức (bất kể ngày đêm)!\n"
                        "2. ⏰ <b>Bản tin định kỳ:</b> Tự động tổng hợp TOP 5 bài nóng nhất vào 07:00, 11:30, 17:30, 21:00.\n\n"
                        "📋 <b>Lệnh điều khiển Radar Liên Tục:</b>\n"
                        "• <code>/realtime</code> : Xem trạng thái radar liên tục\n"
                        "• <code>/realtime on</code> / <code>/realtime off</code> : Bật/tắt quét liên tục\n"
                        "• <code>/interval 3</code> : Đổi chu kỳ quét (ví dụ mỗi 3 phút)\n"
                        "• <code>/threshold 8.0</code> : Đổi ngưỡng điểm kịch tính (thang 1 - 10)\n"
                        "• <code>/check</code> : Quét kiểm tra ngay 1 vòng và báo tin tức\n\n"
                        "📋 <b>Lệnh khác:</b>\n"
                        "• <code>/hot</code> : Quét TOP 5 tin nóng trong 6-9h trước\n"
                        "• <code>/schedule</code> : Xem lịch tổng hợp định kỳ\n\n"
                        f"🎬 Khi có tin ưng ý, chạm vào nút <b>Dựng video</b> để chuyển sang @{NEWS_BOT_USERNAME} tạo video 9:16!"
                    )
                    send_msg(welcome, chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/realtime", "radar", "realtime", "trang thai"]:
                    cfg = load_realtime_config()
                    st_str = "🟢 Đang BẬT rà soát liên tục" if cfg.get("enabled", True) else "🔴 Đang TẮT"
                    inter = cfg.get("interval_seconds", 180)
                    thresh = cfg.get("threshold", 7.8)
                    msg_rt = (
                        f"⚡ <b>RADAR SĂN TIN NÓNG LIÊN TỤC 24/7 (REAL-TIME SCOUT)</b>\n\n"
                        f"• <b>Trạng thái:</b> {st_str}\n"
                        f"• <b>Chu kỳ quét:</b> Mỗi <code>{inter}</code> giây ({inter//60} phút)\n"
                        f"• <b>Ngưỡng kịch tính/hot:</b> <code>{thresh}/10</code>\n"
                        f"• <b>Cơ chế:</b> Tự động cào VnExpress, Dân trí, Tuổi Trẻ, VietNamNet, Thanh Niên, Tiền Phong. Cứ có tin nào mới xuất bản và đạt điểm kịch tính là lập tức bắn tin về Telegram!\n\n"
                        f"⚙️ <b>Lệnh điều khiển:</b>\n"
                        f"• <code>/realtime on</code> : Bật quét liên tục\n"
                        f"• <code>/realtime off</code> : Tắt quét liên tục\n"
                        f"• <code>/interval 3</code> : Đổi chu kỳ quét (ví dụ 3 phút)\n"
                        f"• <code>/threshold 8.0</code> : Đổi ngưỡng điểm kịch tính (1 - 10)\n"
                        f"• <code>/check</code> : Quét kiểm tra ngay lập tức 1 vòng"
                    )
                    send_msg(msg_rt, chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/realtime on", "bat realtime", "bật realtime", "bat radar"]:
                    cfg = load_realtime_config()
                    cfg["enabled"] = True
                    save_realtime_config(cfg)
                    send_msg("🟢 <b>ĐÃ BẬT RADAR SĂN TIN NÓNG LIÊN TỤC 24/7!</b>\nBot sẽ tự động quét báo định kỳ và bắn tin nóng ngay khi vừa xuất bản.", chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text in ["/realtime off", "tat realtime", "tắt realtime", "tat radar"]:
                    cfg = load_realtime_config()
                    cfg["enabled"] = False
                    save_realtime_config(cfg)
                    send_msg("🔴 <b>Đã TẮT tính năng săn tin liên tục.</b>", chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text.startswith("/interval"):
                    parts = text.split()
                    if len(parts) >= 2:
                        try:
                            val = float(parts[1])
                            sec = int(val * 60) if val < 30 else int(val)
                            sec = max(30, min(1800, sec))
                            cfg = load_realtime_config()
                            cfg["interval_seconds"] = sec
                            save_realtime_config(cfg)
                            send_msg(f"✅ <b>Đã cập nhật chu kỳ quét liên tục:</b> <code>{sec}</code> giây ({sec//60} phút)!", chat_id=chat_id, reply_to=msg_id)
                            continue
                        except ValueError:
                            pass
                    send_msg("⚠️ Cú pháp: <code>/interval 3</code> (quét mỗi 3 phút) hoặc <code>/interval 180</code>", chat_id=chat_id, reply_to=msg_id)
                    continue

                if lower_text.startswith("/threshold") or lower_text.startswith("/diem"):
                    parts = text.split()
                    if len(parts) >= 2:
                        try:
                            val = float(parts[1])
                            if 5.0 <= val <= 10.0:
                                cfg = load_realtime_config()
                                cfg["threshold"] = val
                                save_realtime_config(cfg)
                                send_msg(f"✅ <b>Đã cập nhật ngưỡng điểm kịch tính:</b> <code>{val}/10</code>!\nChỉ những bài có điểm >= {val} mới được gửi cảnh báo.", chat_id=chat_id, reply_to=msg_id)
                                continue
                        except ValueError:
                            pass
                    send_msg("⚠️ Cú pháp: <code>/threshold 8.0</code> (ngưỡng từ 5.0 đến 10.0)", chat_id=chat_id, reply_to=msg_id)
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
                            send_msg("✅ <b>Không có tin nóng đột biến mới nào vượt ngưỡng tại thời điểm này.</b> Radar vẫn tiếp tục rình 24/7!", chat_id=target_c)
                    threading.Thread(target=run_manual_check, daemon=True).start()
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

        except requests.exceptions.RequestException as e:
            DIAG["last_error"] = "RequestException: " + str(e)[:180]
            time.sleep(3)
        except Exception as e:
            DIAG["last_error"] = "Exception: " + str(e)[:180]
            print(f"[SCOUT_BOT] Lỗi loop: {e}")
            time.sleep(3)

if __name__ == "__main__":
    start_scout_bot()
