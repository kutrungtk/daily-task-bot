import re
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from models import SessionLocal, Task, DailyStatus
import config

# ——————————————————————————————————————————————
# Utility: tách args của addtask/edittask
def parse_task_args(text: str):
    """
    Tách chuỗi "/cmd …" thành:
      - name
      - url (http…)
      - due_date (dd-mm-yyyy)
      - due_time (HH:MM)
    """
    tokens = text.strip().split()[1:]
    name_parts, url, due_date, due_time = [], None, None, None

    for tok in tokens:
        if tok.startswith("http://") or tok.startswith("https://"):
            url = tok
        elif re.match(r"^\d{1,2}-\d{1,2}-\d{4}$", tok):
            due_date = datetime.datetime.strptime(tok, "%d-%m-%Y").date()
        elif re.match(r"^\d{1,2}:\d{2}$", tok):
            h, m = map(int, tok.split(":"))
            due_time = datetime.time(h, m)
        else:
            name_parts.append(tok)

    name = " ".join(name_parts).strip()
    return name, url, due_date, due_time

# ——————————————————————————————————————————————
# Đảm bảo mỗi ngày có record status
def ensure_today(session):
    today = datetime.date.today()
    for t in session.query(Task).all():
        if not session.query(DailyStatus).filter_by(task_id=t.id, date=today).first():
            session.add(DailyStatus(task_id=t.id, date=today, done=False))
    session.commit()

# ——————————————————————————————————————————————
# START command
def start(update: Update, ctx: CallbackContext):
    chat_id = update.effective_chat.id
    print(f"[Start] chat_id = {chat_id}")

    # Chào + hướng dẫn
    text = (
        "👋 Xin chào! Tôi giúp bạn nhắc việc mỗi ngày.\n"
        "Hãy thêm công việc của bạn bằng lệnh:\n"
        "  /addtask <Tên công việc> [Link] [DD-MM-YYYY] [HH:MM]\n\n"
        "Sau đó dùng:\n"
        "  /tasks — xem công việc hôm nay\n"
        "  /list  — xem tất cả Task\n"
        "  /done <số> — đánh dấu/bỏ đánh dấu\n"
        "  /removetask <số> — xoá\n"
        "  /edittask <số> <Tên mới> [Link] [DD-MM-YYYY] [HH:MM]\n"
        "  /status — xem tiến độ\n"
        "  /help — hướng dẫn\n"
    )
    # Custom keyboard
    buttons = [
        ["/tasks", "/list"],
        ["/addtask", "/removetask"],
        ["/done", "/edittask"],
        ["/status", "/help"],
    ]
    update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))

    # Gửi nhắc ngay
    do_reminder(ctx)

# ——————————————————————————————————————————————
# Xem danh sách hôm nay
def tasks(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    ensure_today(session)
    today = datetime.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()

    lines = []
    for i, st in enumerate(statuses):
        icon = "✅" if st.done else "❌"
        lines.append(f"{i+1}. {icon} {st.task.name}")

    update.message.reply_text("📋 Công việc hôm nay:\n" + "\n".join(lines))
    session.close()

# ——————————————————————————————————————————————
# Xem toàn bộ Task (không theo ngày)
def list_tasks(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    tasks = session.query(Task).all()
    lines = [f"{i+1}. {t.name}"]
    update.message.reply_text("📁 Toàn bộ Task:\n" + "\n".join(lines))
    session.close()

# ——————————————————————————————————————————————
# Thêm Task mới
def addtask(update: Update, ctx: CallbackContext):
    text = update.message.text
    name, url, due_date, due_time = parse_task_args(text)
    if not name:
        return update.message.reply_text("❗️Dùng /addtask <Tên> [Link] [DD-MM-YYYY] [HH:MM]")

    session = SessionLocal()
    # Tạo record Task
    t = Task(name=name, url=url, due_date=due_date, due_time=due_time)
    session.add(t)
    session.commit()
    session.close()
    update.message.reply_text(f"✅ Đã thêm Task: {name}")

# ——————————————————————————————————————————————
# Xoá Task hôm nay
def removetask(update: Update, ctx: CallbackContext):
    if not ctx.args or not ctx.args[0].isdigit():
        return update.message.reply_text("❗️Dùng /removetask <số thứ tự hôm nay>")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    today = datetime.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if idx<0 or idx>=len(statuses):
        session.close()
        return update.message.reply_text("❗️Số không hợp lệ.")
    t = statuses[idx].task
    session.delete(t)
    session.commit()
    session.close()
    update.message.reply_text(f"✅ Đã xoá Task: {t.name}")

# ——————————————————————————————————————————————
# Đánh dấu hoặc bỏ dấu
def done(update: Update, ctx: CallbackContext):
    if not ctx.args or not ctx.args[0].isdigit():
        return update.message.reply_text("❗️Dùng /done <số thứ tự hôm nay>")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    today = datetime.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if idx<0 or idx>=len(statuses):
        session.close()
        return update.message.reply_text("❗️Số không hợp lệ.")
    st = statuses[idx]
    st.done = not st.done
    session.commit()
    emoji = "✅" if st.done else "❌"
    update.message.reply_text(f"{emoji} {st.task.name}")
    session.close()

# ——————————————————————————————————————————————
# Chỉnh sửa Task
def edittask(update: Update, ctx: CallbackContext):
    text = update.message.text
    parts = text.strip().split()
    if len(parts)<2 or not parts[1].isdigit():
        return update.message.reply_text("❗️Dùng /edittask <số hôm nay> <Tên mới> [Link] [DD-MM-YYYY] [HH:MM]")
    idx = int(parts[1]) - 1
    # parse phần còn lại
    name, url, due_date, due_time = parse_task_args(text.partition(" ")[2])

    session = SessionLocal()
    today = datetime.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if idx<0 or idx>=len(statuses):
        session.close()
        return update.message.reply_text("❗️Số không hợp lệ.")

    st = statuses[idx]
    if name:      st.task.name = name
    if url:       st.task.url = url
    if due_date:  st.task.due_date = due_date
    if due_time:  st.task.due_time = due_time
    session.commit()
    session.close()
    update.message.reply_text(f"✅ Đã sửa Task #{idx+1}: {name}")

# ——————————————————————————————————————————————
# Xem tiến độ hôm nay (text vui)
def status(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    today = datetime.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    lines = []
    for st in statuses:
        if st.done:
            lines.append(f"✅ {st.task.name} — Bạn siêu đấy! 😉")
        else:
            lines.append(f"❌ {st.task.name} — Mau làm đi bạn ơi! 😜")
    update.message.reply_text("📊 Tiến độ hôm nay:\n" + "\n".join(lines))
    session.close()

# ——————————————————————————————————————————————
# Gửi nhắc lập tức
def do_reminder(ctx: CallbackContext):
    job = []
    session = SessionLocal()
    ensure_today(session)
    today = datetime.date.today()
    undone = session.query(DailyStatus).filter_by(date=today, done=False).all()
    session.close()

    if not undone:
        return
    lines = [f"{i+1}. {st.task.name}" for i, st in enumerate(undone)]
    text = "🔔 Bạn vẫn còn task chưa hoàn thành:\n" + "\n".join(lines)
    ctx.bot.send_message(chat_id=config.CHAT_ID, text=text)

# ——————————————————————————————————————————————
# Lịch nhắc 9–23h, mỗi giờ 1 lần
def schedule_cron(updater: Updater):
    sched = BackgroundScheduler()
    trigger = CronTrigger(hour="9-23", minute=0, timezone="Asia/Ho_Chi_Minh")
    sched.add_job(lambda: do_reminder(updater.dispatcher), trigger=trigger)
    sched.start()
    print("[Scheduler] cron 9–23h mỗi giờ")

# ——————————————————————————————————————————————
def help_cmd(update: Update, ctx: CallbackContext):
    update.message.reply_text("Bạn có thể dùng các lệnh: /tasks, /list, /addtask, /done, /removetask, /edittask, /status")

# ——————————————————————————————————————————————
def main():
    updater = Updater(token=config.API_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start",   start))
    dp.add_handler(CommandHandler("tasks",   tasks))
    dp.add_handler(CommandHandler("list",    list_tasks))
    dp.add_handler(CommandHandler("addtask", addtask))
    dp.add_handler(CommandHandler("removetask", removetask))
    dp.add_handler(CommandHandler("done",    done))
    dp.add_handler(CommandHandler("edittask", edittask))
    dp.add_handler(CommandHandler("status",  status))
    dp.add_handler(CommandHandler("help",    help_cmd))

    # khởi cron
    schedule_cron(updater)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
