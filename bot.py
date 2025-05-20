import datetime as dt
import pytz
import re
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import joinedload

from models import SessionLocal, Task, DailyStatus
import config

# -----------------------------------------------------------------------------
LAST_CHAT_ID: int = None
BOT = None
scheduler = None

# -----------------------------------------------------------------------------
def ensure_today(session):
    today = dt.date.today()
    for t in session.query(Task).all():
        if not session.query(DailyStatus).filter_by(task_id=t.id, date=today).first():
            session.add(DailyStatus(task_id=t.id, date=today, done=False))
    session.commit()

# -----------------------------------------------------------------------------
def do_reminder():
    global LAST_CHAT_ID, BOT
    if LAST_CHAT_ID is None:
        return

    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    undone = (
        session.query(DailyStatus)
        .options(joinedload(DailyStatus.task))
        .filter_by(date=today, done=False)
        .all()
    )
    session.close()

    if not undone:
        return

    text = "🔔 Bạn còn:\n" + "\n".join(
        f"{i+1}. {st.task.name}" for i, st in enumerate(undone)
    )
    BOT.send_message(chat_id=LAST_CHAT_ID, text=text)
    print(f"[Reminder] sent at {dt.datetime.now()}")

# -----------------------------------------------------------------------------
def parse_task_args(text: str):
    tokens = text.strip().split()[1:]
    name_parts, url, due_date, due_time = [], None, None, None

    for tok in tokens:
        if tok.startswith("http://") or tok.startswith("https://"):
            url = tok
        elif re.match(r"^\d{1,2}-\d{1,2}-\d{4}$", tok):
            due_date = dt.datetime.strptime(tok, "%d-%m-%Y").date()
        elif re.match(r"^\d{1,2}:\d{2}$", tok):
            h, m = map(int, tok.split(":"))
            due_time = dt.time(h, m)
        else:
            name_parts.append(tok)

    name = " ".join(name_parts).strip()
    return name, url, due_date, due_time

# -----------------------------------------------------------------------------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global LAST_CHAT_ID, BOT, scheduler

    LAST_CHAT_ID = update.effective_chat.id
    BOT = ctx.bot
    print(f"[Start] chat_id = {LAST_CHAT_ID}")

    # nhắc ngay
    do_reminder()

    # set up scheduler lần đầu
    if scheduler is None:
        scheduler = BackgroundScheduler()
        trigger = CronTrigger(
            hour="9-23", minute=0,
            timezone=pytz.timezone("Asia/Ho_Chi_Minh")
        )
        scheduler.add_job(do_reminder, trigger=trigger)
        scheduler.start()
        print("[Scheduler] started (9–23h mỗi giờ)")

    kb = [
        ["/tasks", "/list"],
        ["/addtask", "/removetask"],
        ["/done", "/edittask"],
        ["/status", "/help"],
    ]
    await update.message.reply_text(
        "👋 Xin chào! Tôi nhắc việc mỗi ngày.\n\n"
        "Thêm công việc:\n"
        "  /addtask Tên [Link] [DD-MM-YYYY] [HH:MM]\n\n"
        "Các lệnh:\n"
        "  /tasks     — hôm nay\n"
        "  /list      — tất cả\n"
        "  /done      — đánh dấu\n"
        "  /removetask — xóa\n"
        "  /edittask  — sửa\n"
        "  /status    — tiến độ\n"
        "  /help      — hướng dẫn",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# -----------------------------------------------------------------------------
async def tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = (
        session.query(DailyStatus)
        .options(joinedload(DailyStatus.task))
        .filter_by(date=today)
        .all()
    )
    session.close()

    if not statuses:
        return await update.message.reply_text("Bạn chưa có công việc. /addtask để thêm.")

    lines = [
        f"{i+1}. {'✅' if st.done else '❌'} {st.task.name}"
        for i, st in enumerate(statuses)
    ]
    await update.message.reply_text("📋 Hôm nay:\n" + "\n".join(lines))

# -----------------------------------------------------------------------------
async def list_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    all_tasks = session.query(Task).all()
    session.close()

    if not all_tasks:
        return await update.message.reply_text("Bạn chưa có Task. /addtask để thêm.")

    lines = [f"{i+1}. {t.name}" + (f" (due {t.due_date:%d-%m-%Y}" +
             (f" {t.due_time:%H:%M}" if t.due_time else "") + ")"
             if t.due_date else "")
             for i, t in enumerate(all_tasks)]
    await update.message.reply_text("📁 Toàn bộ:\n" + "\n".join(lines))

# -----------------------------------------------------------------------------
async def addtask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name, url, due_date, due_time = parse_task_args(update.message.text)
    if not name:
        return await update.message.reply_text(
            "❗️Dùng /addtask Tên [Link] [DD-MM-YYYY] [HH:MM]"
        )
    session = SessionLocal()
    session.add(Task(name=name, url=url, due_date=due_date, due_time=due_time))
    session.commit()
    session.close()
    await update.message.reply_text(f"✅ Đã thêm: {name}")

# -----------------------------------------------------------------------------
async def removetask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗️Dùng /removetask <số hôm nay>")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if 0 <= idx < len(statuses):
        name = statuses[idx].task.name
        session.delete(statuses[idx].task)
        session.commit()
        session.close()
        await update.message.reply_text(f"🗑️ Đã xóa: {name}")
    else:
        session.close()
        await update.message.reply_text("❌ Số không hợp lệ.")

# -----------------------------------------------------------------------------
async def edittask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await update.message.reply_text(
            "❗️Dùng /edittask <số hôm nay> <Tên mới> [Link] [DD-MM-YYYY] [HH:MM]"
        )
    idx = int(parts[1]) - 1
    name, url, due_date, due_time = parse_task_args(update.message.text)

    session = SessionLocal()
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if idx<0 or idx>=len(statuses):
        session.close()
        return await update.message.reply_text("❗️Số không hợp lệ.")

    task = statuses[idx].task
    if name:      task.name = name
    if url is not None:   task.url = url
    if due_date:  task.due_date = due_date
    task.due_time = due_time
    session.commit()
    session.close()
    await update.message.reply_text(f"✏️ Đã sửa: {task.name}")

# -----------------------------------------------------------------------------
async def done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗️Dùng /done <số hôm nay>")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if 0 <= idx < len(statuses):
        st = statuses[idx]
        st.done = not st.done
        session.commit()
        emoji = "✅" if st.done else "❌"
        await update.message.reply_text(f"{emoji} {st.task.name}")
    else:
        await update.message.reply_text("❌ Số không hợp lệ.")
    session.close()

# -----------------------------------------------------------------------------
async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    today = dt.date.today()
    statuses = (
        session.query(DailyStatus)
        .options(joinedload(DailyStatus.task))
        .filter_by(date=today)
        .all()
    )
    session.close()
    if not statuses:
        return await update.message.reply_text("Chưa có công việc. /addtask để thêm.")
    lines = [
        f"{'✅' if st.done else '❌'} {st.task.name} "
        + ("— Bạn siêu!" if st.done else "— Mau làm!")
        for st in statuses
    ]
    await update.message.reply_text("📊 Tiến độ:\n" + "\n".join(lines))

# -----------------------------------------------------------------------------
async def testreminder(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if LAST_CHAT_ID is None:
        return await update.message.reply_text("❗️Dùng /start trước.")
    do_reminder()
    await update.message.reply_text("🔔 (Test) Đã gửi nhắc")

# -----------------------------------------------------------------------------
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/addtask, /tasks, /list, /done, /removetask, /edittask, /status, /testreminder, /help"
    )

# -----------------------------------------------------------------------------
def main():
    app = ApplicationBuilder().token(config.API_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtask", addtask))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("removetask", removetask))
    app.add_handler(CommandHandler("edittask", edittask))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("testreminder", testreminder))
    app.add_handler(CommandHandler("help", help_cmd))

    # đảm bảo không dùng webhook
    app.bot.delete_webhook()

    app.run_polling()

if __name__ == "__main__":
    main()
