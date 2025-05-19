import datetime as dt
from datetime import datetime
import pytz
from telegram import (
    Update, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
from models import SessionLocal, Task, DailyStatus
import config

def ensure_today(session):
    today = dt.date.today()
    for t in session.query(Task).all():
        if not session.query(DailyStatus).filter_by(task_id=t.id, date=today).first():
            session.add(DailyStatus(task_id=t.id, date=today, done=False))
    session.commit()

def start(update: Update, ctx: CallbackContext):
    user = update.effective_user
    name = user.first_name or user.username or "bạn"
    session = SessionLocal()
    if session.query(Task).count() == 0:
        for n in ["Săn airdrop", "Research", "Viết bài X.com", "Chạy automation"]:
            session.add(Task(name=n))
        session.commit()
    session.close()

    text = (
        f"👋 Xin chào *{name}*!\n"
        "Dùng các lệnh:\n\n"
        "• 📋 `/tasks`                      — Xem công việc hôm nay\n"
        "• 📜 `/list`                       — Xem toàn bộ Task\n"
        "• ➕ `/addtask Tên URL [DD-MM-YYYY] [HH:MM]` — Thêm Task mới\n"
        "• ➖ `/removetask <số>`            — Xóa Task theo thứ tự hôm nay\n"
        "• ✅ `/done <số>`                   — Đánh dấu / bỏ đánh dấu\n"
        "• 📊 `/status`                    — Xem tiến độ hôm nay\n"
        "• 🔔 `/testreminder`              — Test nhắc ngay lập tức\n"
        "• ❓ `/help`                       — Hướng dẫn sử dụng\n"
    )
    update.message.reply_text(text, parse_mode="Markdown")

    keyboard = [
        ["/tasks", "/status", "/list"],
        ["/addtask", "/removetask", "/done"],
        ["/testreminder", "/help"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    update.message.reply_text("Hoặc bấm nhanh một trong các nút:", reply_markup=reply_markup)

def tasks(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    for i, st in enumerate(statuses):
        t = st.task
        icon = "✅" if st.done else "❌"
        line = f"{i+1}. {icon} *{t.name}*"
        if t.deadline:
            line += f" _(due {t.deadline:%d-%m-%Y %H:%M})_"
        buttons = []
        if t.link:
            buttons.append(InlineKeyboardButton("🔗 Hướng dẫn", url=t.link))
        if buttons:
            update.message.reply_text(
                line,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([buttons])
            )
        else:
            update.message.reply_text(line, parse_mode="Markdown")
    session.close()

def list_tasks(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    tasks = session.query(Task).all()
    if not tasks:
        session.close()
        return update.message.reply_text("📜 Chưa có Task nào cả.")
    for t in tasks:
        line = f"*{t.id}.* {t.name}"
        if t.deadline:
            line += f" _(due {t.deadline:%d-%m-%Y %H:%M})_"
        buttons = []
        if t.link:
            buttons.append(InlineKeyboardButton("🔗 Hướng dẫn", url=t.link))
        if buttons:
            update.message.reply_text(
                line,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([buttons])
            )
        else:
            update.message.reply_text(line, parse_mode="Markdown")
    session.close()

def addtask(update: Update, ctx: CallbackContext):
    args = ctx.args
    link_idx = next((i for i,a in enumerate(args) if a.startswith("http")), None)
    if link_idx is None or link_idx == 0:
        return update.message.reply_text(
            "❗️ Dùng: `/addtask Tên công việc URL [DD-MM-YYYY] [HH:MM]`",
            parse_mode="Markdown"
        )
    name = " ".join(args[:link_idx])
    link = args[link_idx]
    deadline = None
    tail = args[link_idx+1:]
    if tail:
        ds = " ".join(tail)
        for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                deadline = datetime.strptime(ds, fmt)
                break
            except ValueError:
                continue
        else:
            return update.message.reply_text(
                "❗️ Định dạng deadline sai, phải `DD-MM-YYYY` hoặc `DD-MM-YYYY HH:MM`",
                parse_mode="Markdown"
            )
    session = SessionLocal()
    if session.query(Task).filter_by(name=name).first():
        msg = f"⚠️ Task *{name}* đã tồn tại."
    else:
        task = Task(name=name, link=link, deadline=deadline)
        session.add(task)
        session.commit()
        msg = f"✅ Đã thêm Task: *{name}*"
    session.close()
    update.message.reply_text(msg, parse_mode="Markdown")

def removetask(update: Update, ctx: CallbackContext):
    if not ctx.args or not ctx.args[0].isdigit():
        return update.message.reply_text("❗️ Dùng `/removetask <số>` nhé!", parse_mode="Markdown")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if not (0 <= idx < len(statuses)):
        session.close()
        return update.message.reply_text(
            "⚠️ Số không hợp lệ. Nhớ xem `/tasks`.",
            parse_mode="Markdown"
        )
    task = statuses[idx].task
    session.delete(task)
    session.commit()
    session.close()
    update.message.reply_text(f"🗑️ Đã xoá: *{task.name}*", parse_mode="Markdown")

def done(update: Update, ctx: CallbackContext):
    if not ctx.args or not ctx.args[0].isdigit():
        return update.message.reply_text("❗️ Dùng `/done <số>` nhé!", parse_mode="Markdown")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if not (0 <= idx < len(statuses)):
        session.close()
        return update.message.reply_text("⚠️ Số không hợp lệ.", parse_mode="Markdown")
    st = statuses[idx]
    if st.done:
        st.done = False
        session.commit()
        text = f"↩️ Bỏ dấu *{st.task.name}*."
    else:
        st.done = True
        session.commit()
        text = f"🎉 *{st.task.name}* xong!"
    session.close()
    update.message.reply_text(text, parse_mode="Markdown")

def status(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    ensure_today(session)
    today = dt.date.today()
    statuses = session.query(DailyStatus).filter_by(date=today).all()
    if not statuses:
        session.close()
        return update.message.reply_text("Bạn chưa có công việc nào 🤷‍♂️")
    for i, st in enumerate(statuses):
        t = st.task
        icon = "✅" if st.done else "❌"
        line = f"{i+1}. {icon} *{t.name}*"
        if t.deadline:
            line += f" _(due {t.deadline:%d-%m-%Y %H:%M})_"
        buttons = []
        if t.link:
            buttons.append(InlineKeyboardButton("🔗 Hướng dẫn", url=t.link))
        if buttons:
            update.message.reply_text(
                line,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([buttons])
            )
        else:
            update.message.reply_text(line, parse_mode="Markdown")
    session.close()

def help_command(update: Update, ctx: CallbackContext):
    text = (
        "❓ *Hướng dẫn sử dụng Bot*:\n\n"
        "• `/start` — Khởi động bot & menu\n"
        "• `/tasks` — Xem công việc hôm nay\n"
        "• `/list`  — Xem toàn bộ Task\n"
        "• `/addtask Tên URL [DD-MM-YYYY] [HH:MM]` — Thêm Task\n"
        "• `/removetask <số>` — Xóa Task trong danh sách hôm nay\n"
        "• `/done <số>` — Đánh dấu / bỏ đánh dấu hoàn thành\n"
        "• `/status` — Xem tiến độ hôm nay\n"
        "• `/testreminder` — Gửi ngay nhắc việc để test\n\n"
        "Bạn có thể bấm các nút bên dưới hoặc gõ lệnh."
    )
    update.message.reply_text(text, parse_mode="Markdown")

def testreminder(update: Update, ctx: CallbackContext):
    update.message.reply_text("🔔 (Test) Nhắc bạn kiểm tra công việc! Dùng /tasks")

def schedule_reminder(updater):
    def reminder_job():
        session = SessionLocal()
        ensure_today(session)
        today = dt.date.today()
        undone = session.query(DailyStatus).filter_by(date=today, done=False).all()
        session.close()
        if not undone:
            return
        lines = [f"{i+1}. {st.task.name}" for i, st in enumerate(undone)]
        text = "🔔 Bạn vẫn còn công việc chưa hoàn thành hôm nay:\n" + "\n".join(lines)
        updater.bot.send_message(chat_id=config.CHAT_ID, text=text)

    sched = BackgroundScheduler(timezone=pytz.timezone('Asia/Ho_Chi_Minh'))
    sched.add_job(reminder_job, trigger='cron', hour='9-23', minute=0)
    sched.start()

def main():
    updater = Updater(token=config.API_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start",       start))
    dp.add_handler(CommandHandler("tasks",       tasks))
    dp.add_handler(CommandHandler("list",        list_tasks))
    dp.add_handler(CommandHandler("addtask",     addtask))
    dp.add_handler(CommandHandler("removetask",  removetask))
    dp.add_handler(CommandHandler("done",        done))
    dp.add_handler(CommandHandler("status",      status))
    dp.add_handler(CommandHandler("help",        help_command))
    dp.add_handler(CommandHandler("testreminder",testreminder))
    schedule_reminder(updater)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
