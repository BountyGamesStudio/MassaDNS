import logging
import sqlite3
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties

# ===== КОНФИГ =====
BOT_TOKEN = "8909970277:AAGO2YaFzSUlqQenOlV7SLPTD7097s8t9z4"
ADMIN_IDS = [7728468302, 5674960579]
PHONE_NUMBER = "+79518368998"
BANK_NAME = "Т-Банк"

PRICES = {
    "3_days": 50,
    "7_days": 120,
    "21_days": 200,
    "31_days": 300,
}

# ===== БД =====
DB_NAME = "vpn_users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            username TEXT,
            subscription_end TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            days INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'waiting',
            created_at TEXT,
            confirmed_by INTEGER DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_user(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT tg_id, username, subscription_end FROM users WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    conn.close()
    return row

def create_user(tg_id, username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
    conn.commit()
    conn.close()

def set_subscription(tg_id, days):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    now = datetime.datetime.now()
    end_date = (now + datetime.timedelta(days=days)).isoformat()
    cur.execute("UPDATE users SET subscription_end = ? WHERE tg_id = ?", (end_date, tg_id))
    conn.commit()
    conn.close()

def add_payment(tg_id, days, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # Закрываем старые ожидающие платежи
    cur.execute("UPDATE payments SET status = 'cancelled' WHERE tg_id = ? AND status = 'waiting'", (tg_id,))
    cur.execute(
        "INSERT INTO payments (tg_id, days, amount, status, created_at) VALUES (?, ?, ?, 'waiting', ?)",
        (tg_id, days, amount, datetime.datetime.now().isoformat())
    )
    payment_id = cur.lastrowid
    conn.commit()
    conn.close()
    return payment_id

def update_payment_status(payment_id, status, admin_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if admin_id:
        cur.execute("UPDATE payments SET status = ?, confirmed_by = ? WHERE id = ?", (status, admin_id, payment_id))
    else:
        cur.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
    conn.commit()
    conn.close()

def get_payment(payment_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT tg_id, days, amount, status FROM payments WHERE id = ?", (payment_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_last_pending_payment(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, days, amount FROM payments WHERE tg_id = ? AND status = 'waiting' ORDER BY id DESC LIMIT 1",
        (tg_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row

def get_subscription_days_left(tg_id):
    user = get_user(tg_id)
    if not user or not user[2]:
        return 0
    end_date = datetime.datetime.fromisoformat(user[2])
    days_left = (end_date - datetime.datetime.now()).days
    return max(0, days_left)

# ===== КЛАВИАТУРЫ =====
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton(text="ℹ️ Мой статус", callback_data="status")]
    ])

def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="3 дня (50₽)", callback_data="buy_3")],
        [InlineKeyboardButton(text="7 дней (120₽)", callback_data="buy_7")],
        [InlineKeyboardButton(text="21 день (200₽)", callback_data="buy_21")],
        [InlineKeyboardButton(text="31 день (300₽)", callback_data="buy_31")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

def payment_menu(payment_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Я оплатил", callback_data=f"paid_{payment_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

def admin_confirm_menu(payment_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{payment_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{payment_id}")
        ]
    ])

def admin_disabled_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Обработано", callback_data="disabled")]
    ])

# ===== БОТ =====
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
init_db()

@dp.message(Command("start"))
async def start(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or "NoName"
    create_user(tg_id, username)
    days_left = get_subscription_days_left(tg_id)
    status_text = f"\n📅 Осталось дней: {days_left}" if days_left > 0 else "\n❌ Подписка неактивна"
    
    await message.answer(
        f"🚀 <b>Mass VPN — 0 пинг для игр Supersell!</b>\n\n"
        f"♾ Безлимит на 1 устройство\n"
        f"📍 Российские сервисы работают как обычно\n"
        f"💳 Оплата рублями через Т-Банк\n"
        f"{status_text}\n\n"
        f"Выбери действие:",
        reply_markup=main_menu()
    )

@dp.callback_query(lambda c: c.data == "back")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏠 Главное меню:",
        reply_markup=main_menu()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "status")
async def show_status(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user and user[2]:
        end_date = datetime.datetime.fromisoformat(user[2])
        days_left = (end_date - datetime.datetime.now()).days
        if days_left > 0:
            text = (
                f"✅ <b>Подписка активна</b>\n"
                f"📅 Осталось дней: {days_left}\n"
                f"📆 До: {end_date.strftime('%d.%m.%Y %H:%M')}"
            )
        else:
            text = "❌ <b>Подписка истекла</b>\nКупи новую!"
    else:
        text = "❌ <b>Нет активной подписки</b>"
    await callback.message.edit_text(text, reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "buy")
async def show_buy(callback: CallbackQuery):
    days_left = get_subscription_days_left(callback.from_user.id)
    extra = f"\n\n📅 У тебя активна подписка на {days_left} дн. Продли её!" if days_left > 0 else ""
    
    await callback.message.edit_text(
        f"💳 <b>Выбери срок подписки:</b>\n\n"
        f"Оплата через Т-Банк по номеру телефона{extra}",
        reply_markup=buy_menu()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    days = int(callback.data.split("_")[1])
    amount = PRICES.get(f"{days}_days", 0)
    tg_id = callback.from_user.id

    payment_id = add_payment(tg_id, days, amount)

    text = (
        f"💳 <b>Оплата {amount}₽ за {days} дн.</b>\n\n"
        f"📱 Переведи сумму на номер:\n"
        f"<b>{PHONE_NUMBER}</b>\n"
        f"🏦 Банк: {BANK_NAME}\n\n"
        f"📌 <b>Важно!</b> В комментарии к переводу укажи свой Telegram ID:\n"
        f"<code>{tg_id}</code>\n\n"
        f"После перевода нажми кнопку «Я оплатил» и отправь скриншот чека."
    )
    await callback.message.edit_text(text, reply_markup=payment_menu(payment_id))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def paid_click(callback: CallbackQuery):
    payment_id = int(callback.data.split("_")[1])
    
    # Проверяем, существует ли ещё этот платеж
    payment = get_payment(payment_id)
    if not payment:
        await callback.message.edit_text(
            "❌ Платёж не найден. Начни заново с /start",
            reply_markup=main_menu()
        )
        await callback.answer()
        return
    
    if payment[3] != "waiting":
        await callback.message.edit_text(
            f"⏳ Этот платёж уже {payment[3]}. Начни заново с /start",
            reply_markup=main_menu()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "📸 <b>Отправь скриншот чека</b>\n\n"
        "Пришли фото или документ с подтверждением перевода.\n"
        "Админы проверят и подтвердят оплату.\n\n"
        "⏳ Обычно это занимает до 5 минут."
    )
    await callback.answer()

# ===== ОБРАБОТКА СКРИНА =====
@dp.message(lambda msg: msg.photo or msg.document)
async def handle_screenshot(message: types.Message):
    tg_id = message.from_user.id
    pending = get_last_pending_payment(tg_id)

    if not pending:
        await message.answer(
            "❌ У тебя нет ожидающих платежей.\n\n"
            "Нажми /start и выбери «Купить подписку»"
        )
        return

    payment_id, days, amount = pending

    caption = (
        f"📩 <b>НОВЫЙ ПЛАТЁЖ НА ПОДТВЕРЖДЕНИЕ</b>\n\n"
        f"👤 Пользователь: @{message.from_user.username or 'NoName'}\n"
        f"🆔 ID: <code>{tg_id}</code>\n"
        f"📅 Срок: {days} дн.\n"
        f"💰 Сумма: {amount}₽\n"
        f"🔢 Платёж №{payment_id}\n"
        f"🕐 Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    # Отправляем ВСЕМ админам
    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(
                    admin_id,
                    message.photo[-1].file_id,
                    caption=caption,
                    reply_markup=admin_confirm_menu(payment_id)
                )
            elif message.document:
                await bot.send_document(
                    admin_id,
                    message.document.file_id,
                    caption=caption,
                    reply_markup=admin_confirm_menu(payment_id)
                )
        except Exception as e:
            logging.error(f"Не удалось отправить админу {admin_id}: {e}")

    await message.answer(
        "✅ <b>Скрин отправлен админам!</b>\n\n"
        "Ожидай подтверждения. Обычно это занимает до 5 минут.\n"
        "Как только админ подтвердит — ты получишь уведомление 🤝"
    )

# ===== АДМИН: ПОДТВЕРДИТЬ =====
@dp.callback_query(lambda c: c.data.startswith("confirm_"))
async def admin_confirm(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    payment_id = int(callback.data.split("_")[1])
    payment = get_payment(payment_id)
    
    if not payment:
        await callback.message.edit_text("❌ Платёж не найден")
        await callback.answer()
        return
    
    tg_id, days, amount, status = payment
    
    if status != "waiting":
        await callback.message.edit_text(
            f"⏳ Этот платёж уже {status}",
            reply_markup=admin_disabled_menu()
        )
        await callback.answer()
        return

    update_payment_status(payment_id, "confirmed", callback.from_user.id)
    set_subscription(tg_id, days)

    # Уведомление пользователю
    try:
        await bot.send_message(
            tg_id,
            "✅ <b>Спасибо за оплату, ожидайте 🤝</b>\n\n"
            f"📅 Подписка на {days} дн. активирована.\n"
            f"💰 Оплачено: {amount}₽\n"
            "Скоро придёт конфиг для подключения."
        )
    except:
        pass

    # Уведомление всем админам
    admin_name = callback.from_user.username or f"ID {callback.from_user.id}"
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ <b>Платёж №{payment_id} подтверждён</b>\n"
                f"👤 Админ: @{admin_name}\n"
                f"👤 Пользователь: ID {tg_id}\n"
                f"📅 Срок: {days} дн.\n"
                f"💰 Сумма: {amount}₽"
            )
        except:
            pass

    await callback.message.edit_text(
        f"✅ <b>Платёж №{payment_id} подтверждён</b>\n"
        f"👤 Админ: @{admin_name}\n"
        f"👤 Пользователь уведомлён.",
        reply_markup=admin_disabled_menu()
    )
    await callback.answer()

# ===== АДМИН: ОТКЛОНИТЬ =====
@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def admin_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    payment_id = int(callback.data.split("_")[1])
    payment = get_payment(payment_id)
    
    if not payment:
        await callback.message.edit_text("❌ Платёж не найден")
        await callback.answer()
        return
    
    tg_id, days, amount, status = payment
    
    if status != "waiting":
        await callback.message.edit_text(
            f"⏳ Этот платёж уже {status}",
            reply_markup=admin_disabled_menu()
        )
        await callback.answer()
        return

    update_payment_status(payment_id, "rejected", callback.from_user.id)

    # Уведомление пользователю
    try:
        await bot.send_message(
            tg_id,
            "❌ <b>Оплата не подтверждена</b>\n\n"
            "Возможные причины:\n"
            "• Неверная сумма перевода\n"
            "• Отсутствует комментарий с ID\n"
            "• Чек нечитаемый\n\n"
            "Проверь и попробуй снова."
        )
    except:
        pass

    # Уведомление всем админам
    admin_name = callback.from_user.username or f"ID {callback.from_user.id}"
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"❌ <b>Платёж №{payment_id} отклонён</b>\n"
                f"👤 Админ: @{admin_name}\n"
                f"👤 Пользователь: ID {tg_id}"
            )
        except:
            pass

    await callback.message.edit_text(
        f"❌ <b>Платёж №{payment_id} отклонён</b>\n"
        f"👤 Админ: @{admin_name}",
        reply_markup=admin_disabled_menu()
    )
    await callback.answer()

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("🚀 Mass VPN Bot запущен!")
    print(f"👥 Админы: {ADMIN_IDS}")
    print(f"💰 Цены: {PRICES}")
    dp.run_polling(bot)
