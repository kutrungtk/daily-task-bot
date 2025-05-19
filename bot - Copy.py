import datetime
import pytz
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
from models import SessionLocal, Task, DailyStatus
import config

def ensure_today(session):
    today = datetime.date.today()
    for t in session.query(Task).all():
        if not session.query(DailyStatus).filter_by(task_id=t.id, date=today).first():
            session.add(DailyStatus(task_id=t.id, date=today, done=False))
    session.commit()

def start(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    if session.query(Task).count() == 0:
        for name in ["Săn airdrop", "Research", "Viết bài X.com", "Chạy automation"]:
            session.add(Task(name=name))
        session.commit()
    session.close()
    update.message.reply_text(
        "Chào! Dùng /tasks xem danh sách, /done <số> đánh dấu công việc, /status xem tiến độ."
    )

def tasks(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    ensure_today(session)
    statuses = session.query(DailyStatus).filter_by(date=datetime.date.today()).all()
    text = "\n".join(
        f"{i+1}. {'✅' if st.done else '❌'} {st.task.name}"
        for i, st in enumerate(statuses)
    )
    update.message.reply_text("Công việc hôm nay:\n" + text)
    session.close()

def done(update: Update, ctx: CallbackContext):
    if not ctx.args or not ctx.args[0].isdigit():
        return update.message.reply_text("Dùng /done <số thứ tự>")
    idx = int(ctx.args[0]) - 1
    session = SessionLocal()
    statuses = session.query(DailyStatus).filter_by(date=datetime.date.today()).all()
    if 0 <= idx < len(statuses):
        statuses[idx].done = True
        session.commit()
        update.message.reply_text(f"Đã hoàn thành ✅ {statuses[idx].task.name}")
    else:
        update.message.reply_text("Số không hợp lệ.")
    session.close()

def status(update: Update, ctx: CallbackContext):
    session = SessionLocal()
    statuses = session.query(DailyStatus).filter_by(date=datetime.date.today()).all()
    report = "\n".join(
        f"{'✅' if st.done else '❌'} {st.task.name}"
        for st in statuses
    )
    update.message.reply_text(
        "Tiến độ hôm nay:\n" + (report or "Không có công việc.")
    )
    session.close()

def schedule_reminder(updater):
    # Tạo scheduler với múi giờ Việt Nam
    sched = BackgroundScheduler(timezone=pytz.timezone('Asia/Ho_Chi_Minh'))
    sched.add_job(
        lambda: updater.bot.send_message(
            chat_id=config.CHAT_ID,
            text="🔔 Nhắc bạn kiểm tra công việc hôm nay! Dùng /tasks"
        ),
        trigger='cron',
        hour=9,
        minute=0
    )
    sched.start()

def main():
    updater = Updater(token=config.API_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("tasks", tasks))
    dp.add_handler(CommandHandler("done", done))
    dp.add_handler(CommandHandler("status", status))
    schedule_reminder(updater)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
