
import os
import math
import sqlite3
import telebot
from telebot import types

# ================== الإعدادات ==================

BOT_TOKEN = "8849458576:AAFad2wahrxhMcKULo4Bhn7SsvecV4bauFo"
ADMIN_ID = 8287216333
PAYMENT_NUMBER = "01285663869"
STORE_NAME = "BDAWY STORE"

PRICE_PER_15 = 10

bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = "votes_orders.db"

SERVICES = [f"اختيار_{i}" for i in range(1, 11)]
user_states = {}


# ================== قاعدة البيانات ==================

def db():
    conn = sqlite3.connect(DB_FILE, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                service TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                link TEXT NOT NULL,
                price REAL NOT NULL,
                sender_phone TEXT,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def get_order(order_id):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()


def money(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def cancel_keyboard():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True, one_time_keyboard=False
    )
    kb.row("❌ إلغاء الطلب", "🏠 القائمة الرئيسية")
    return kb


def main_keyboard():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True, row_width=2
    )
    kb.add(
        types.KeyboardButton("🛒 اطلب خدمة"),
        types.KeyboardButton("📦 طلباتي"),
        types.KeyboardButton("ℹ️ الأسعار"),
    )
    return kb


def services_keyboard():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True, row_width=2
    )
    buttons = [types.KeyboardButton(s) for s in SERVICES]
    kb.add(*buttons)
    kb.row("❌ إلغاء الطلب", "🏠 القائمة الرئيسية")
    return kb


def admin_keyboard(order_id):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(
            "✅ تأكيد الطلب", callback_data=f"approve:{order_id}"
        ),
        types.InlineKeyboardButton(
            "❌ إلغاء الطلب", callback_data=f"reject:{order_id}"
        )
    )
    return kb


def user_confirmation_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(
            "✅ تأكيد ومتابعة", callback_data="confirm_payment"
        ),
        types.InlineKeyboardButton(
            "❌ إلغاء", callback_data="cancel_order"
        )
    )
    return kb


def clear_state(user_id):
    user_states.pop(user_id, None)


# ================== بدء البوت ==================

@bot.message_handler(commands=["start"])
def start(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"أهلاً بيك في {STORE_NAME} 🎮\n\n"
        "اختار الخدمة اللي محتاجها من القائمة.\n"
        "مش محتاج تعمل حساب أو تسجل دخول.",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["cancel"])
def cancel_command(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "تم إلغاء العملية.",
        reply_markup=main_keyboard()
    )


# ================== الأسعار والطلبات ==================

@bot.message_handler(func=lambda m: m.text == "ℹ️ الأسعار")
def prices(message):
    text = (
        "💰 قائمة الخدمات والأسعار\n\n"
        + "\n".join(f"• {s}" for s in SERVICES)
        + f"\n\nالسعر: كل 15 صوتًا = {PRICE_PER_15} جنيه."
        "\nالسعر يُحسب تناسبيًا حسب الكمية."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())


@bot.message_handler(func=lambda m: m.text == "🛒 اطلب خدمة")
def choose_service(message):
    clear_state(message.from_user.id)
    user_states[message.from_user.id] = {"step": "service"}
    bot.send_message(
        message.chat.id,
        "اختار الخدمة المطلوبة:",
        reply_markup=services_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "🏠 القائمة الرئيسية")
def go_home(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "القائمة الرئيسية:",
        reply_markup=main_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "❌ إلغاء الطلب")
def cancel_text(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "تم إلغاء الطلب.",
        reply_markup=main_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "📦 طلباتي")
def my_orders(message):
    with db() as conn:
        rows = conn.execute(
            """SELECT id, service, quantity, price, status
               FROM orders WHERE user_id = ?
               ORDER BY id DESC LIMIT 10""",
            (message.from_user.id,)
        ).fetchall()

    if not rows:
        bot.send_message(
            message.chat.id, "لسه معندكش طلبات.",
            reply_markup=main_keyboard()
        )
        return

    lines = ["📦 آخر طلباتك:\n"]
    for r in rows:
        lines.append(
            f"طلب #{r['id']}\n"
            f"الخدمة: {r['service']}\n"
            f"الكمية: {r['quantity']}\n"
            f"السعر: {money(r['price'])} جنيه\n"
            f"الحالة: {r['status']}\n"
        )

    bot.send_message(
        message.chat.id, "\n".join(lines),
        reply_markup=main_keyboard()
    )


# ================== استقبال بيانات الطلب ==================

@bot.message_handler(
    func=lambda m: m.from_user.id in user_states,
    content_types=["text"]
)
def handle_order(message):
    uid = message.from_user.id
    state = user_states.get(uid)

    if not state:
        return

    text = (message.text or "").strip()

    if text in ("❌ إلغاء الطلب", "/cancel"):
        clear_state(uid)
        bot.send_message(
            message.chat.id, "تم إلغاء الطلب.",
            reply_markup=main_keyboard()
        )
        return

    step = state.get("step")

    if step == "service":
        if text not in SERVICES:
            bot.send_message(
                message.chat.id,
                "من فضلك اختار خدمة من القائمة.",
                reply_markup=services_keyboard()
            )
            return

        state["service"] = text
        state["step"] = "quantity"

        bot.send_message(
            message.chat.id,
            f"الخدمة: {text}\n"
            f"السعر: كل 15 صوتًا بـ {PRICE_PER_15} جنيه.\n\n"
            "اكتب الكمية المطلوبة بالأرقام، مثال: 30",
            reply_markup=cancel_keyboard()
        )
        return

    if step == "quantity":
        try:
            quantity = int(text)
            if quantity < 1 or quantity > 1000000:
                raise ValueError
        except ValueError:
            bot.send_message(
                message.chat.id,
                "اكتب كمية صحيحة أكبر من صفر."
            )
            return

        price = round(quantity * PRICE_PER_15 / 15, 2)
        state["quantity"] = quantity
        state["price"] = price
        state["step"] = "link"

        bot.send_message(
            message.chat.id,
            f"✅ الخدمة: {state['service']}\n"
            f"🔢 الكمية: {quantity}\n"
            f"💰 السعر الإجمالي: {money(price)} جنيه\n\n"
            "ابعت رابط التصويت المطلوب، أو اضغط إلغاء الطلب.",
            reply_markup=cancel_keyboard()
        )
        return

    if step == "link":
        if len(text) < 5 or not (
            text.startswith("https://") or text.startswith("http://")
        ):
            bot.send_message(
                message.chat.id,
                "ابعت الرابط كاملًا ويبدأ بـ https:// أو http://"
            )
            return

        state["link"] = text
        state["step"] = "payment_confirmation"

        bot.send_message(
            message.chat.id,
            "📋 مراجعة الطلب\n\n"
            f"🛍 الخدمة: {state['service']}\n"
            f"🔢 الكمية: {state['quantity']}\n"
            f"🔗 الرابط:\n{state['link']}\n\n"
            f"💰 السعر: {money(state['price'])} جنيه\n\n"
            f"لإكمال الطلب، حوّل المبلغ إلى فودافون كاش:\n"
            f"`{PAYMENT_NUMBER}`\n\n"
            "بعد التحويل اضغط تأكيد ومتابعة، "
            "أو اضغط إلغاء.",
            reply_markup=user_confirmation_keyboard()
        )
        return

    if step == "sender_phone":
        phone = "".join(c for c in text if c.isdigit() or c == "+")
        if len(phone) < 8 or len(phone) > 16:
            bot.send_message(
                message.chat.id,
                "رقم غير صحيح. ابعت رقم الهاتف الذي حوّلت منه."
            )
            return

        with db() as conn:
            cursor = conn.execute(
                """INSERT INTO orders
                (user_id, username, service, quantity, link,
                 price, sender_phone, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    uid,
                    message.from_user.username or "",
                    state["service"],
                    state["quantity"],
                    state["link"],
                    state["price"],
                    phone,
                    "بانتظار مراجعة الإدارة"
                )
            )
            order_id = cursor.lastrowid

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            f"✅ تم تسجيل طلبك رقم #{order_id}.\n"
            "الطلب بانتظار مراجعة الإدارة والتحقق من الدفع.\n"
            "هنبلغك بالنتيجة.",
            reply_markup=main_keyboard()
        )

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username else "بدون اسم مستخدم"
        )

        admin_text = (
            f"🆕 طلب جديد #{order_id}\n\n"
            f"👤 المستخدم: {username}\n"
            f"🆔 Telegram ID: {uid}\n"
            f"🛍 الخدمة: {state['service']}\n"
            f"🔢 الكمية: {state['quantity']}\n"
            f"🔗 الرابط:\n{state['link']}\n"
            f"💰 السعر: {money(state['price'])} جنيه\n"
            f"📱 رقم المحوِّل: {phone}\n"
            f"💳 رقم الدفع: {PAYMENT_NUMBER}\n"
            "⏳ الحالة: بانتظار مراجعة الإدارة\n\n"
            "تحقق من وصول التحويل قبل تأكيد الطلب."
        )

        try:
            bot.send_message(
                ADMIN_ID,
                admin_text,
                reply_markup=admin_keyboard(order_id)
            )
        except Exception:
            bot.send_message(
                message.chat.id,
                "تم حفظ الطلب، لكن تعذر إرسال إشعار الإدارة. "
                "يرجى التواصل مع الدعم."
            )


# ================== تأكيد أو إلغاء الدفع ==================

@bot.callback_query_handler(
    func=lambda call: call.data in ("confirm_payment", "cancel_order")
)
def payment_callback(call):
    uid = call.from_user.id
    state = user_states.get(uid)

    if not state or state.get("step") != "payment_confirmation":
        bot.answer_callback_query(call.id, "انتهت صلاحية العملية.")
        return

    if call.data == "cancel_order":
        clear_state(uid)
        bot.answer_callback_query(call.id, "تم إلغاء الطلب.")
        bot.send_message(
            call.message.chat.id,
            "تم إلغاء الطلب.",
            reply_markup=main_keyboard()
        )
        return

    state["step"] = "sender_phone"
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "📱 ابعت رقم الهاتف الذي حوّلت منه المبلغ.\n"
        "سيتم إرسال البيانات للإدارة لمراجعة الدفع.",
        reply_markup=cancel_keyboard()
    )


# ================== قرارات الإدارة ==================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("approve:")
    or call.data.startswith("reject:")
)
def admin_decision(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(
            call.id, "الزر ده خاص بالأدمن فقط.", show_alert=True
        )
        return

    action, order_id_text = call.data.split(":", 1)

    try:
        order_id = int(order_id_text)
    except ValueError:
        bot.answer_callback_query(call.id, "رقم طلب غير صحيح.")
        return

    order = get_order(order_id)

    if not order:
        bot.answer_callback_query(call.id, "الطلب غير موجود.")
        return

    if order["status"] != "بانتظار مراجعة الإدارة":
        bot.answer_callback_query(
            call.id, "تم اتخاذ قرار بشأن الطلب بالفعل.", show_alert=True
        )
        return

    if action == "approve":
        new_status = "تم تأكيد الطلب"
        customer_text = (
            f"✅ تم تأكيد طلبك رقم #{order_id} من الإدارة.\n"
            "تابع مع الإدارة لمعرفة حالة تنفيذ الخدمة."
        )
        result_text = f"✅ تم تأكيد الطلب #{order_id}"
    else:
        new_status = "تم إلغاء الطلب"
        customer_text = (
            f"❌ تم إلغاء طلبك رقم #{order_id} من الإدارة.\n"
            "لو كنت قد حولت المبلغ بالفعل، تواصل مع الإدارة."
        )
        result_text = f"❌ تم إلغاء الطلب #{order_id}"

    with db() as conn:
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id)
        )

    try:
        bot.send_message(order["user_id"], customer_text)
    except Exception:
        pass

    try:
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
    except Exception:
        pass

    bot.answer_callback_query(call.id, result_text)
    bot.send_message(ADMIN_ID, result_text)


# ================== تشغيل البوت ==================

init_db()

print(f"{STORE_NAME} bot is running...")

bot.infinity_polling(
    skip_pending=True,
    timeout=30,
    long_polling_timeout=30
)
