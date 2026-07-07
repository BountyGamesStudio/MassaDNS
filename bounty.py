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
    "1_day": 49,
    "7_days": 249,
    "30_days": 799,
    "90_days": 1999,
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
            status TEXT DEFAULT 'waiting',
            created_at TEXT
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

def add_payment(tg_id, days):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (tg_id, days, status, created_at) VALUES (?, ?, 'waiting', ?)",
        (tg_id, days, datetime.datetime.now().isoformat())
    )
    payment_id = cur.lastrowid
    conn.commit()
    conn.close()
    return payment_id

def update_payment_status(payment_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
    conn.commit()
    conn.close()

def get_payment(payment_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT tg_id, days FROM payments WHERE id = ?", (payment_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_last_pending_payment(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, days FROM payments WHERE tg_id = ? AND status = 'waiting' ORDER BY id DESC LIMIT 1",
        (tg_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row

# ===== КЛАВИАТУРЫ =====
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton(text="ℹ️ Мой статус", callback_data="status")]
    ])

def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день (49₽)", callback_data="buy_1")],
        [InlineKeyboardButton(text="7 дней (249₽)", callback_data="buy_7")],
        [InlineKeyboardButton(text="30 дней (799₽)", callback_data="buy_30")],
        [InlineKeyboardButton(text="90 дней (1999₽)", callback_data="buy_90")],
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
    await message.answer(
        "🚀 <b>Mass VPN — 0 пинг для игр Supersell!</b>\n\n"
        "♾ Безлимит на 1 устройство\n"
        "📍 Российские сервисы работают как обычно\n"
        "💳 Оплата рублями через Т-Банк\n\n"
        "Выбери действие:",
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
            text = f"✅ Подписка активна\nОсталось дней: {days_left}\nДо: {end_date.strftime('%d.%m.%Y %H:%M')}"
        else:
            text = "❌ Подписка истекла. Купи новую!"
    else:
        text = "❌ Нет активной подписки."
    await callback.message.edit_text(text, reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "buy")
async def show_buy(callback: CallbackQuery):
    await callback.message.edit_text(
        "💳 <b>Выбери срок подписки:</b>\n\n"
        "Оплата через Т-Банк по номеру телефона",
        reply_markup=buy_menu()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    days = int(callback.data.split("_")[1])
    amount = PRICES.get(f"{days}_days", 0)
    tg_id = callback.from_user.id

    payment_id = add_payment(tg_id, days)

    text = (
        f"💳 <b>Оплата {amount}₽ за {days} дн.</b>\n\n"
        f"Переведи сумму на номер:\n"
        f"<b>{PHONE_NUMBER}</b>\n"
        f"Банк: {BANK_NAME}\n\n"
        f"После перевода нажми кнопку «Я оплатил» и отправь скриншот чека."
    )
    await callback.message.edit_text(text, reply_markup=payment_menu(payment_id))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def paid_click(callback: CallbackQuery):
    payment_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        "📸 <b>Отправь скриншот чека</b>\n\n"
        "Пришли фото или документ с подтверждением перевода.\n"
        "Админ проверит и подтвердит оплату."
    )
    await callback.answer()

# ===== ОБРАБОТКА СКРИНА =====
@dp.message(lambda msg: msg.photo or msg.document)
async def handle_screenshot(message: types.Message):
    tg_id = message.from_user.id
    pending = get_last_pending_payment(tg_id)

    if not pending:
        await message.answer("❌ У тебя нет ожидающих платежей. Начни с /start")
        return

    payment_id, days = pending

    caption = (
        f"📩 <b>Новый платёж на подтверждение</b>\n"
        f"Пользователь: @{message.from_user.username or 'NoName'} (ID: {tg_id})\n"
        f"Срок: {days} дн.\n"
        f"Сумма: {PRICES.get(f'{days}_days', 0)}₽\n"
        f"Платёж №{payment_id}"
    )

    if message.photo:
        await bot.send_photo(
            ADMIN_IDS[0],  # отправляем первому админу, но видят оба
            message.photo[-1].file_id,
            caption=caption,
            reply_markup=admin_confirm_menu(payment_id)
        )
    elif message.document:
        await bot.send_document(
            ADMIN_IDS[0],
            message.document.file_id,
            caption=caption,
            reply_markup=admin_confirm_menu(payment_id)
        )

    await message.answer("✅ Скрин отправлен админу. Ожидай подтверждения.")

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

    tg_id, days = payment
    update_payment_status(payment_id, "confirmed")
    set_subscription(tg_id, days)

    try:
        await bot.send_message(
            tg_id,
            "✅ <b>Спасибо за оплату, ожидайте 🤝</b>\n\n"
            f"Подписка на {days} дн. активирована.\n"
            "Скоро придёт конфиг для подключения."
        )
    except:
        pass

    await callback.message.edit_text(
        f"✅ Платёж №{payment_id} подтверждён. Пользователь уведомлён."
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

    tg_id, _ = payment
    update_payment_status(payment_id, "rejected")

    try:
        await bot.send_message(
            tg_id,
            "❌ <b>Оплата не подтверждена</b>\n\n"
            "Проверь правильность перевода и попробуй снова."
        )
    except:
        pass

    await callback.message.edit_text(
        f"❌ Платёж №{payment_id} отклонён. Пользователь уведомлён."
    )
    await callback.answer()

# ===== ЗАПУСК =====
if __name__ == "__main__":
    dp.run_polling(bot)
