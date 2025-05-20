import os
import asyncio
import datetime as dt

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from models import SessionLocal, Task, DailyStatus
import config  # chứa API_TOKEN, CHAT_ID

# --- database helpers ---

def ensure_today(session):
    today = dt.date.today()
    for t in session.query(Task).all():
        if not session.query(DailyStatus).filter_by(task_id=t.id, date=today).first():
            session.add(DailyStatus(task_id=t.id, date=today, done=False))
    session.commit()

# --- reminder logic ---

def do_reminder(updater: Updater):
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    undone = session.query(DailyStatus).filter_by(date=today, done=False).all()
    session.close()

    if not undone:
        return  # không còn task nào
    lines = [f"{i+1}. {st.task.name}" for i, st in enumerate(undone)]
    text = "🔔 Bạn vẫn còn task chưa hoàn thành:\n" + "\n".join(lines)
    updater.bot.send_message(chat_id=config.CHAT_ID, text=text)

def schedule_reminder(updater: Updater):
    sched = BackgroundScheduler()
    # từ 9h đến 23h, mỗi giờ 0 phút
    trig = CronTrigger(hour="9-23", minute=0, timezone="Asia/Ho_Chi_Minh")
    sched.add_job(lambda: do_reminder(updater), trigger=trig)
    sched.start()
    print("[Scheduler] scheduled 9–23h hourly")

# --- command handlers ---

def start(update: Update, ctx: CallbackContext):
    # gửi lời chào + hướng dẫn
    name = update.effective_user.first_name or "bạn"
    text = (
        f"👋 Xin chào {name}!\n"
        "Tôi giúp bạn nhắc công việc mỗi ngày.\n"
        "Hãy thêm công việc của bạn bằng:\n"
        "  /addtask Tên công việc | [Link] | [DD-MM-YYYY HH:MM]\n\n"
        "Các lệnh khác:\n"
        "  /tasks    — Xem công việc hôm nay\n"
        "  /list     — Xem tất cả Task\n"
        "  /removetask  — Xóa Task\n"
        "  /edittask   — Sửa Task\n"
        "  /done     — Đánh dấu/bỏ đánh dấu\n"
        "  /status   — Xem tiến độ hôm nay\n"
        "  /help     — Hướng dẫn sử dụng\n"
    )
    reply_markup = ReplyKeyboardMarkup(
        [["/tasks","/list","/addtask"], ["/removetask","/edittask","/done"], ["/status","/help"]],
        resize_keyboard=True
    )
    update.message.reply_text(text, reply_markup=reply_markup)

    # nhắc ngay
    do_reminder(ctx.bot.updater)

def addtask(update: Update, ctx: CallbackContext):
    """ /addtask Tên | Link | DD-MM-YYYY HH:MM """
    raw = update.message.text.partition(" ")[2]
    parts = [p.strip() for p in raw.split("|")]
    if not parts or not parts[0]:
        return update.message.reply_text("❗ Dùng: /addtask Tên | [Link] | [DD-MM-YYYY HH:MM]")
    name = parts[0]
    url = parts[1] if len(parts) > 1 else None
    due = None
    if len(parts) > 2:
        try:
            due = dt.datetime.strptime(parts[2], "%d-%m-%Y %H:%M")
        except:
            return update.message.reply_text("❗ Ngày sai định dạng, dùng DD-MM-YYYY HH:MM")
    session = SessionLocal()
    task = Task(name=name, url=url, due=due)
    session.add(task); session.commit()
    session.close()
    update.message.reply_text(f"✅ Đã thêm Task: {name}")

def removetask(update: Update, ctx: CallbackContext):
    if not ctx.args or not ctx.args[0].isdigit():
        return update.message.reply_text("❗ Dùng: /removetask SỐ")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if idx<0 or idx>=len(statuses):
        session.close()
        return update.message.reply_text("❗ Số không hợp lệ")
    ts = statuses[idx].task
    session.delete(ts)
    session.commit()
    session.close()
    update.message.reply_text(f"🗑️ Đã xóa Task: {ts.name}")

def edittask(update: Update, ctx: CallbackContext):
    """ /edittask SỐ | Tên mới """
    raw = update.message.text.partition(" ")[2]
    if "|" not in raw:
        return update.message.reply_text("❗ Dùng: /edittask SỐ | Tên mới")
    num, new = [p.strip() for p in raw.split("|",1)]
    if not num.isdigit():
        return update.message.reply_text("❗ Số không hợp lệ")
    idx = int(num)-1
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if idx<0 or idx>=len(statuses):
        session.close()
        return update.message.reply_text("❗ Số không hợp lệ")
    task = statuses[idx].task
    task.name = new
    session.commit()
    session.close()
    update.message.reply_text(f"✏️ Đã sửa Task #{num} thành: {new}")

def tasks(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    session.expunge_all()
    session.close()
    lines = [
        f"{i+1}. {'✅' if st.done else '❌'} {st.task.name}"
        for i, st in enumerate(statuses)
    ]
    text = "🗒️ Công việc hôm nay:\n" + "\n".join(lines)
    update.message.reply_text(text)

def list_all(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    tasks = session.query(Task).all()
    session.close()
    if not tasks:
        return update.message.reply_text("Bạn chưa có Task nào.")
    lines = []
    for i, t in enumerate(tasks):
        s = f"{i+1}. {t.name}"
        if t.due:
            s += f" (due {t.due.strftime('%d-%m-%Y %H:%M')})"
        lines.append(s)
    text = "📋 Toàn bộ Task:\n" + "\n".join(lines)
    update.message.reply_text(text)

def done(update: Update, ctx: CallbackContext):
    if not ctx.args or not ctx.args[0].isdigit():
        return update.message.reply_text("❗ Dùng: /done SỐ")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if idx<0 or idx>=len(statuses):
        session.close()
        return update.message.reply_text("❗ Số không hợp lệ")
    status = statuses[idx]
    status.done = not status.done
    session.commit()
    session.close()
    icon = "✅" if status.done else "❌"
    update.message.reply_text(f"{icon} {status.task.name}")

def status(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    session.expunge_all()
    session.close()
    lines = [
        f"{'✅' if st.done else '❌'} {st.task.name}"
        for st in statuses
    ]
    text = "📊 Tiến độ hôm nay:\n" + ("\n".join(lines) if lines else "Không có công việc.")
    update.message.reply_text(text)

def help_cmd(update: Update, ctx: CallbackContext):
    update.message.reply_text("Xem hướng dẫn sử dụng tại README của project trên GitHub.")

# --- main ---

def main():
    updater = Updater(config.API_TOKEN, use_context=True)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addtask", addtask))
    dp.add_handler(CommandHandler("removetask", removetask))
    dp.add_handler(CommandHandler("edittask", edittask))
    dp.add_handler(CommandHandler("tasks", tasks))
    dp.add_handler(CommandHandler("list", list_all))
    dp.add_handler(CommandHandler("done", done))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("help", help_cmd))

    # xóa webhook trước khi polling
    asyncio.get_event_loop().run_until_complete(
        updater.bot.delete_webhook()
    )
    print("[Start] chat_id =", config.CHAT_ID)

    # lập lịch nhắc
    schedule_reminder(updater)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
