import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from datetime import timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "8738822295:AAHJDRFCGvBzd6qx5QXot9fTqfOoHSfoNm4")
ADMIN_ID = 565461273

# ─── ХРАНИЛИЩЕ ДАННЫХ ПОЛЬЗОВАТЕЛЯ ───
user_data = {}

def get_user(uid):
    if uid not in user_data:
        user_data[uid] = {"bill": None, "area": None, "heating": None, "phone": None, "step": None}
    return user_data[uid]

# ─── ОТПРАВКА УВЕДОМЛЕНИЯ АДМИНУ ───
async def notify_admin(context, text):
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")

# ─── РАСЧЁТ ───
AREA_DATA = {
    "area_100":     {"power": "3.5 кВт", "price": "85 000",  "saving": "5 200",  "income": "12 600", "payback": "12–16"},
    "area_180":     {"power": "7 кВт",   "price": "155 000", "saving": "9 800",  "income": "25 200", "payback": "13–17"},
    "area_300":     {"power": "10.5 кВт","price": "220 000", "saving": "14 300", "income": "37 800", "payback": "14–18"},
    "area_300plus": {"power": "14 кВт",  "price": "290 000", "saving": "18 500", "income": "50 400", "payback": "14–18"},
}

BILL_LABELS = {
    "bill_3000":  "до 3 000 ₽",
    "bill_6000":  "3 000–6 000 ₽",
    "bill_10000": "6 000–10 000 ₽",
    "bill_15000": "больше 10 000 ₽",
}

AREA_LABELS = {
    "area_100":     "до 100 м²",
    "area_180":     "100–180 м²",
    "area_300":     "180–300 м²",
    "area_300plus": "больше 300 м²",
}

HEATING_LABELS = {
    "heat_electric": "Электрокотёл",
    "heat_wood":     "Дрова / уголь",
    "heat_gas":      "Газгольдер",
    "heat_new":      "Строю дом",
}

# ─── /start ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    get_user(uid)["step"] = "start"

    await notify_admin(context,
        f"👤 Новый пользователь!\n"
        f"Имя: {user.full_name}\n"
        f"Username: @{user.username or '—'}\n"
        f"ID: {uid}"
    )

    keyboard = [
        [InlineKeyboardButton("📊 Посчитать выгоду для моего дома", callback_data="calc_start")],
        [InlineKeyboardButton("📺 Посмотреть как это работает", callback_data="video")],
        [InlineKeyboardButton("❓ Это вообще законно?", callback_data="legal")],
    ]
    await update.message.reply_text(
        "👋 Привет! Я бот ЭВК.\n\n"
        "Помогу разобраться, как обычное отопление "
        "может приносить до <b>12 600 ₽ в месяц</b>.\n\n"
        "Это не реклама и не MLM — это физика. "
        "Тепло от вычислений греет ваш дом, "
        "а криптовалюта идёт вам на карту 💳\n\n"
        "Что хотите узнать первым? 👇",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Планируем реактивацию через 24 часа
    context.job_queue.run_once(
        reactivation,
        when=timedelta(hours=24),
        data={"uid": uid, "name": user.first_name},
        name=f"react_{uid}"
    )

# ─── РЕАКТИВАЦИЯ ЧЕРЕЗ 24 ЧАСА ───
async def reactivation(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    uid = data["uid"]
    name = data["name"]
    u = get_user(uid)

    # Не беспокоим если уже оставил телефон
    if u.get("phone"):
        return

    keyboard = [
        [InlineKeyboardButton("🔄 Пересчитать выгоду", callback_data="calc_start")],
        [InlineKeyboardButton("👨‍🔧 Поговорить с инженером", callback_data="engineer")],
    ]
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=f"👋 {name}, кстати...\n\n"
                 "Вы считали выгоду ЭВК для своего дома.\n\n"
                 "Сегодня курс биткоина вырос — "
                 "окупаемость стала на <b>2 месяца быстрее</b> 📈\n\n"
                 "Хотите пересчитать? Займёт 1 минуту 👇",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка реактивации: {e}")

# ─── ВОПРОС 1: СЧЁТ ───
async def calc_start(query, context):
    keyboard = [
        [InlineKeyboardButton("💸 до 3 000 ₽",        callback_data="bill_3000")],
        [InlineKeyboardButton("💸 3 000 — 6 000 ₽",   callback_data="bill_6000")],
        [InlineKeyboardButton("💸 6 000 — 10 000 ₽",  callback_data="bill_10000")],
        [InlineKeyboardButton("💸 больше 10 000 ₽",   callback_data="bill_15000")],
    ]
    await query.edit_message_text(
        "Хорошо, считаем! Пара вопросов — займёт <b>30 секунд</b> 👇\n\n"
        "<b>Вопрос 1 из 3</b>\n"
        "Сколько платите за отопление в самый холодный месяц?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── ВОПРОС 2: ПЛОЩАДЬ ───
async def ask_area(query, context, bill_key):
    get_user(query.from_user.id)["bill"] = bill_key
    keyboard = [
        [InlineKeyboardButton("🏡 до 100 м²",     callback_data="area_100")],
        [InlineKeyboardButton("🏠 100–180 м²",    callback_data="area_180")],
        [InlineKeyboardButton("🏘 180–300 м²",    callback_data="area_300")],
        [InlineKeyboardButton("🏛 больше 300 м²", callback_data="area_300plus")],
    ]
    await query.edit_message_text(
        "<b>Вопрос 2 из 3</b>\n"
        "Какая площадь вашего дома?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── ВОПРОС 3: ОТОПЛЕНИЕ ───
async def ask_heating(query, context, area_key):
    get_user(query.from_user.id)["area"] = area_key
    keyboard = [
        [InlineKeyboardButton("⚡ Электрокотёл",    callback_data="heat_electric")],
        [InlineKeyboardButton("🪵 Дрова / уголь",   callback_data="heat_wood")],
        [InlineKeyboardButton("💨 Газгольдер",       callback_data="heat_gas")],
        [InlineKeyboardButton("🏗 Строю дом",        callback_data="heat_new")],
    ]
    await query.edit_message_text(
        "<b>Вопрос 3 из 3</b>\n"
        "Как отапливаете сейчас?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── РЕЗУЛЬТАТ РАСЧЁТА ───
async def show_result(query, context, heating_key):
    uid = query.from_user.id
    u = get_user(uid)
    u["heating"] = heating_key

    area_key = u.get("area", "area_100")
    d = AREA_DATA[area_key]

    keyboard = [
        [InlineKeyboardButton("📋 Да, хочу смету!", callback_data="want_smet")],
        [InlineKeyboardButton("🤔 Есть вопросы",    callback_data="faq")],
        [InlineKeyboardButton("❓ А это законно?",   callback_data="legal")],
    ]
    await query.edit_message_text(
        "✅ <b>Расчёт готов!</b>\n\n"
        f"На основе ваших данных:\n\n"
        f"⚡ Рекомендуемый ЭВК: <b>{d['power']}</b>\n"
        f"📉 Экономия на свете: <b>~{d['saving']} ₽/мес</b>\n"
        f"📈 Доход с майнинга: <b>~{d['income']} ₽/мес</b>\n"
        f"💰 Стоимость от: <b>{d['price']} ₽</b>\n"
        f"⏱ Окупаемость: <b>{d['payback']} месяцев</b>\n\n"
        "То есть пока соседи <b>платят</b> за тепло — "
        "вы на нём <b>зарабатываете</b> 🔥\n\n"
        "Хотите получить полную PDF-смету "
        "с точными цифрами под ваш дом?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await notify_admin(context,
        f"📊 Прошёл расчёт в боте!\n"
        f"👤 {query.from_user.full_name} (@{query.from_user.username or '—'})\n"
        f"🏠 Площадь: {AREA_LABELS.get(area_key)}\n"
        f"💸 Счёт: {BILL_LABELS.get(u.get('bill'))}\n"
        f"🔥 Отопление: {HEATING_LABELS.get(heating_key)}\n"
        f"→ Рекомендован: {d['power']}"
    )

# ─── ЗАПРОС КОНТАКТА ───
async def want_smet(query, context):
    get_user(query.from_user.id)["step"] = "wait_phone"
    keyboard = [
        [InlineKeyboardButton("📱 Отправить мой номер", callback_data="share_phone")],
    ]
    await query.edit_message_text(
        "Отлично! Инженер подготовит для вас "
        "индивидуальную смету с учётом:\n\n"
        "✓ Вашей площади и тарифа\n"
        "✓ Текущего типа отопления\n"
        "✓ Стоимости монтажа под ключ\n"
        "✓ Точного срока окупаемости\n\n"
        "📞 Напишите ваш номер телефона "
        "и инженер свяжется с вами в течение <b>30 минут</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── ПОЛУЧЕНИЕ НОМЕРА ТЕЛЕФОНА ───
async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    if u.get("step") != "wait_phone":
        return

    phone = update.message.text.strip()
    u["phone"] = phone
    u["step"] = "done"

    # Отменяем реактивацию — контакт уже есть
    current_jobs = context.job_queue.get_jobs_by_name(f"react_{uid}")
    for job in current_jobs:
        job.schedule_removal()

    keyboard = [
        [InlineKeyboardButton("📺 Посмотреть видео котла", callback_data="video")],
        [InlineKeyboardButton("❓ Частые вопросы",          callback_data="faq")],
    ]
    await update.message.reply_text(
        "✅ <b>Принято!</b>\n\n"
        "Инженер свяжется с вами "
        "в течение <b>30 минут</b> в рабочее время.\n\n"
        "🕐 Пн–сб, 9:00–20:00\n\n"
        "Пока ждёте — посмотрите как выглядит "
        "котёл в реальной работе 👇",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    user = update.effective_user
    area_key = u.get("area", "—")
    await notify_admin(context,
        f"🔥 НОВЫЙ ЛИД!\n"
        f"👤 {user.full_name} (@{user.username or '—'})\n"
        f"📞 Телефон: {phone}\n"
        f"🏠 Площадь: {AREA_LABELS.get(area_key, '—')}\n"
        f"💸 Счёт: {BILL_LABELS.get(u.get('bill'), '—')}\n"
        f"🔥 Отопление: {HEATING_LABELS.get(u.get('heating'), '—')}"
    )

# ─── ВИДЕО ───
async def show_video(query, context):
    keyboard = [
        [InlineKeyboardButton("📊 Посчитать выгоду", callback_data="calc_start")],
        [InlineKeyboardButton("👨‍🔧 Связаться с инженером", callback_data="engineer")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="back")],
    ]
    await query.edit_message_text(
        "📺 <b>ЭВК в реальной работе</b>\n\n"
        "🌡 Температура на входе: <b>+45°C</b>\n"
        "🔥 Температура на выходе: <b>+51°C</b>\n"
        "⚡ Потребление: <b>3.5 кВт</b>\n"
        "💸 Расход в месяц: <b>7 200 ₽</b> (при 4 ₽/кВт)\n"
        "💰 Доход в месяц: <b>~12 600 ₽</b>\n\n"
        "🎬 Смотрите видео работающего котла:\n"
        "👉 https://youtube.com/shorts/h5Xkvbk4rKc\n\n"
        "Убедились? Посчитаем выгоду для вашего дома 👇",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── ЗАКОННО ЛИ? ───
async def show_legal(query, context):
    keyboard = [
        [InlineKeyboardButton("📊 Посчитать выгоду", callback_data="calc_start")],
        [InlineKeyboardButton("👨‍🔧 Поговорить с инженером", callback_data="engineer")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="back")],
    ]
    await query.edit_message_text(
        "✅ <b>Абсолютно законно.</b>\n\n"
        "Майнинг в России не запрещён для физических лиц "
        "(ФЗ №259 от 2024 г.)\n\n"
        "Котёл подключается как обычный электроприбор. "
        "Никаких лицензий и разрешений не нужно.\n\n"
        "🏭 Мы — <b>официальный представитель</b> "
        "завода Watermining в Москве и МО.\n"
        "✅ Более 140 установок\n"
        "✅ Работаем с 2022 года\n"
        "✅ Гарантия 5 лет\n\n"
        "Теперь давайте посчитаем вашу выгоду? 👇",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── FAQ ───
async def show_faq(query, context):
    keyboard = [
        [InlineKeyboardButton("🔇 Шумно ли работает?",        callback_data="faq_noise")],
        [InlineKeyboardButton("☀️ Что происходит летом?",     callback_data="faq_summer")],
        [InlineKeyboardButton("🛡 Насколько безопасно?",       callback_data="faq_safe")],
        [InlineKeyboardButton("💰 Сколько стоит установка?",  callback_data="faq_price")],
        [InlineKeyboardButton("⏱ Как быстро окупается?",      callback_data="faq_payback")],
        [InlineKeyboardButton("◀️ Главное меню",               callback_data="back")],
    ]
    await query.edit_message_text(
        "❓ <b>Частые вопросы</b>\n\nВыберите вопрос 👇",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

FAQ_ANSWERS = {
    "faq_noise": (
        "🔇 <b>Шумно ли работает?</b>\n\n"
        "Уровень шума — как у обычного холодильника. "
        "Котлы оснащены системой шумоподавления и "
        "жидкостным охлаждением. "
        "Можно устанавливать в жилых помещениях — "
        "никакого раздражающего гула."
    ),
    "faq_summer": (
        "☀️ <b>Что происходит летом?</b>\n\n"
        "Летом котёл работает в режиме майнинга "
        "без отопления. Тепло рассеивается через вентиляцию.\n\n"
        "Вы получаете доход <b>круглый год</b>, "
        "а не только в отопительный сезон. "
        "Летом даже выгоднее — нет нагрузки на охлаждение помещения."
    ),
    "faq_safe": (
        "🛡 <b>Насколько это безопасно?</b>\n\n"
        "Оборудование сертифицировано и соответствует "
        "всем нормам пожарной безопасности РФ.\n\n"
        "✓ Защита от перегрева\n"
        "✓ Автоматическое отключение\n"
        "✓ Мониторинг 24/7\n"
        "✓ Промышленный класс надёжности\n\n"
        "За 3 года работы — ни одного пожара или аварии."
    ),
    "faq_price": (
        "💰 <b>Сколько стоит установка?</b>\n\n"
        "Стоимость зависит от площади дома и "
        "готовности вашей котельной.\n\n"
        "Базовый модуль ЭВК 3.5 кВт — <b>от 85 000 ₽</b>\n\n"
        "Монтаж и пусконаладка рассчитываются "
        "индивидуально после бесплатного инженерного аудита.\n\n"
        "Система окупает себя за <b>12–18 месяцев</b>."
    ),
    "faq_payback": (
        "⏱ <b>Как быстро окупается?</b>\n\n"
        "Для дома 100 м² при тарифе 4 ₽/кВт:\n\n"
        "💸 Расход на свет: 7 200 ₽/мес\n"
        "📈 Доход с майнинга: 12 600 ₽/мес\n"
        "✅ Чистая прибыль: +5 400 ₽/мес\n\n"
        "Окупаемость: <b>12–16 месяцев</b>\n\n"
        "Дальше — чистый доход каждый месяц "
        "плюс бесплатное отопление."
    ),
}

# ─── ИНЖЕНЕР ───
async def show_engineer(query, context):
    get_user(query.from_user.id)["step"] = "wait_phone"
    keyboard = [[InlineKeyboardButton("◀️ Главное меню", callback_data="back")]]
    user = query.from_user
    await notify_admin(context,
        f"👨‍🔧 Хочет связаться с инженером!\n"
        f"👤 {user.full_name} (@{user.username or '—'})\n"
        f"ID: {user.id}"
    )
    await query.edit_message_text(
        "👨‍🔧 <b>Связь с инженером</b>\n\n"
        "Ваш запрос принят! Напишите ваш номер телефона — "
        "инженер перезвонит в течение <b>30 минут</b>.\n\n"
        "🕐 Рабочие часы: пн–сб, 9:00–20:00\n\n"
        "📞 Введите номер телефона:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── ГЛАВНОЕ МЕНЮ ───
def main_menu_markup():
    keyboard = [
        [InlineKeyboardButton("📊 Посчитать выгоду", callback_data="calc_start")],
        [InlineKeyboardButton("📺 Посмотреть как работает", callback_data="video")],
        [InlineKeyboardButton("❓ Частые вопросы", callback_data="faq")],
        [InlineKeyboardButton("👨‍🔧 Связаться с инженером", callback_data="engineer")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ─── CALLBACK HANDLER ───
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back":
        await query.edit_message_text(
            "Выберите что вас интересует 👇",
            reply_markup=main_menu_markup()
        )
    elif data == "calc_start":
        await calc_start(query, context)
    elif data in BILL_LABELS:
        await ask_area(query, context, data)
    elif data in AREA_LABELS:
        await ask_heating(query, context, data)
    elif data in HEATING_LABELS:
        await show_result(query, context, data)
    elif data == "want_smet":
        await want_smet(query, context)
    elif data == "video":
        await show_video(query, context)
    elif data == "legal":
        await show_legal(query, context)
    elif data == "faq":
        await show_faq(query, context)
    elif data in FAQ_ANSWERS:
        keyboard = [
            [InlineKeyboardButton("◀️ К вопросам", callback_data="faq")],
            [InlineKeyboardButton("📊 Посчитать выгоду", callback_data="calc_start")],
        ]
        await query.edit_message_text(
            FAQ_ANSWERS[data],
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "engineer":
        await show_engineer(query, context)
    elif data == "share_phone":
        await query.edit_message_text(
            "📞 Введите ваш номер телефона в формате:\n+7 999 123-45-67",
            parse_mode="HTML"
        )

# ─── MAIN ───
def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone))
    logger.info("✅ ЭВК бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
