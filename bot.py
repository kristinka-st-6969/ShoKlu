import logging
import os
import sys
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')  # вместо прямого указания
ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID')

# Проверяем наличие токена
if not BOT_TOKEN:
    print("❌ ОШИБКА: Токен бота не найден!")
    sys.exit(1)

print("🚀 Запуск бота...")
print(f"✅ Токен загружен: {BOT_TOKEN[:15]}...")
print(f"👥 Группа админов: {ADMIN_GROUP_ID or 'не указана'}")

# Предупреждение о неправильном формате группы
if ADMIN_GROUP_ID and ('@' in ADMIN_GROUP_ID or 't.me' in ADMIN_GROUP_ID or '+' in ADMIN_GROUP_ID):
    print("⚠️ ВНИМАНИЕ: ADMIN_GROUP_ID должен быть числовым ID!")
    ADMIN_GROUP_ID = None

# Отключаем лишние логи
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# Состояния для ConversationHandler
BOX_SIZE, CHOCOLATE, COLOR, TOPPING, PHONE, DETAILS = range(6)

# Данные пользователей
user_data = {}

# Варианты размера коробки
BOX_SIZES = {
    '5': '📦 5 штук',
    '10': '📦 10 штук'
}

# Варианты шоколада
CHOCOLATE_TYPES = {
    'milk': '🥛 Молочный шоколад',
    'dark': '🍫 Темный шоколад',
    'white': '🤍 Белый шоколад',
    'colored': '🌈 Цветной шоколад'
}

# Варианты цветов для цветного шоколада
COLOR_TYPES = {
    'yellow': '💛 Жёлтый',
    'green': '💚 Зелёный',
    'blue': '💙 Синий',
    'black': '🖤 Чёрный',
    'red': '❤️ Красный',
    'pink': '💗 Розовый'
}

# Варианты посыпки
TOPPING_TYPES = {
    'hearts': '💗 Сердечки',
    'gold': '✨ Золото пищевое',
    'nuts': '🥜 Арахис',
    'raspberry': '🔴 Малина'
}

def validate_phone(phone):
    """Проверяет корректность номера телефона"""
    cleaned = re.sub(r'\D', '', phone)
    return 10 <= len(cleaned) <= 15

def format_phone(phone):
    """Форматирует номер телефона"""
    cleaned = re.sub(r'\D', '', phone)
    if len(cleaned) == 11 and cleaned.startswith('8'):
        cleaned = '7' + cleaned[1:]
    return cleaned

def get_moscow_time(utc_time):
    """Конвертирует UTC время в московское (UTC+3)"""
    return utc_time + timedelta(hours=3)

def create_box_keyboard(selected):
    """Создание клавиатуры для выбора размера коробки"""
    keyboard = []
    for size_id, size_name in BOX_SIZES.items():
        if size_id == selected:
            button_text = f"✅ {size_name}"
        else:
            button_text = f"◻️ {size_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'box_{size_id}')])
    
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ (к шоколаду)", callback_data='box_next')])
    return InlineKeyboardMarkup(keyboard)

def create_chocolate_keyboard(selected):
    """Создание клавиатуры для выбора шоколада"""
    keyboard = []
    for choc_id, choc_name in CHOCOLATE_TYPES.items():
        if choc_id in selected:
            button_text = f"✅ {choc_name}"
        else:
            button_text = f"◻️ {choc_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'choc_{choc_id}')])
    
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ (к посыпке)", callback_data='choc_next')])
    return InlineKeyboardMarkup(keyboard)

def create_color_keyboard(selected):
    """Создание клавиатуры для выбора цвета"""
    keyboard = []
    for color_id, color_name in COLOR_TYPES.items():
        if color_id in selected:
            button_text = f"✅ {color_name}"
        else:
            button_text = f"◻️ {color_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'color_{color_id}')])
    
    nav_buttons = [
        InlineKeyboardButton("⬅️ НАЗАД к шоколаду", callback_data='back_to_chocolate'),
        InlineKeyboardButton("➡️ ДАЛЕЕ к посыпке", callback_data='color_next')
    ]
    keyboard.append(nav_buttons)
    return InlineKeyboardMarkup(keyboard)

def create_topping_keyboard(selected, user_id):
    """Создание клавиатуры для выбора посыпки"""
    keyboard = []
    for top_id, top_name in TOPPING_TYPES.items():
        if top_id in selected:
            button_text = f"✅ {top_name}"
        else:
            button_text = f"◻️ {top_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'top_{top_id}')])
    
    # Умная навигация - если был выбран цветной шоколад, кнопка ведет к цветам
    if user_id in user_data and 'colored' in user_data[user_id].get('chocolates', []):
        back_button = InlineKeyboardButton("⬅️ НАЗАД к цветам", callback_data='back_to_color')
    else:
        back_button = InlineKeyboardButton("⬅️ НАЗАД к шоколаду", callback_data='back_to_chocolate')
    
    nav_buttons = [
        back_button,
        InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data='top_next')
    ]
    keyboard.append(nav_buttons)
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_message = (
        f"👋 Добро пожаловать, {user.first_name}!\n\n"
        "🍓 Здесь вы можете оформить заказ на клубнику в шоколаде.\n"
        "Нажмите кнопку ниже, чтобы начать оформление заказа."
    )
    
    keyboard = [[InlineKeyboardButton("🛒 Оформить заказ", callback_data='start_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    user_id = query.from_user.id
    callback_data = query.data
    
    # МГНОВЕННЫЙ ОТВЕТ
    await query.answer()
    
    # Инициализация данных пользователя
    if user_id not in user_data:
        user_data[user_id] = {
            'box_size': '', 
            'chocolates': [], 
            'colors': [], 
            'toppings': [], 
            'phone': ''
        }
    
    # СПЕЦИАЛЬНЫЕ КНОПКИ
    if callback_data == 'start_order' or callback_data == 'restart_order':
        user_data[user_id] = {
            'box_size': '', 
            'chocolates': [], 
            'colors': [], 
            'toppings': [], 
            'phone': ''
        }
        text = "📦 ВЫБЕРИТЕ РАЗМЕР КОРОБКИ:\n\n"
        for size_name in BOX_SIZES.values():
            text += f"◻️ {size_name}\n"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_box_keyboard('')
        )
        return BOX_SIZE
    
    elif callback_data.startswith('box_') and callback_data != 'box_next':
        size = callback_data.replace('box_', '')
        user_data[user_id]['box_size'] = size
        
        text = "📦 ВАШ ВЫБОР:\n\n"
        text += f"✅ {BOX_SIZES[size]}\n\n"
        text += "➡️ Нажмите ДАЛЕЕ для выбора шоколада"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_box_keyboard(size)
        )
        return BOX_SIZE
    
    elif callback_data == 'box_next':
        if not user_data[user_id]['box_size']:
            await query.answer("❌ Выберите размер коробки!", show_alert=True)
            return BOX_SIZE
        else:
            # Переходим к выбору шоколада
            text = "🍫 ВЫБЕРИТЕ ШОКОЛАД:\n\n"
            for choc_name in CHOCOLATE_TYPES.values():
                text += f"◻️ {choc_name}\n"
            text += f"\n🔹 Выбрано: 0"
            
            await query.edit_message_text(
                text, 
                reply_markup=create_chocolate_keyboard([])
            )
            return CHOCOLATE
    
    # КНОПКИ ВЫБОРА ШОКОЛАДА
    elif callback_data.startswith('choc_') and callback_data not in ['choc_next', 'choc_back']:
        choc_type = callback_data.replace('choc_', '')
        
        if choc_type in user_data[user_id]['chocolates']:
            user_data[user_id]['chocolates'].remove(choc_type)
            # Если убрали цветной шоколад, очищаем цвета
            if choc_type == 'colored':
                user_data[user_id]['colors'] = []
        else:
            user_data[user_id]['chocolates'].append(choc_type)
        
        selected = user_data[user_id]['chocolates']
        
        text = "🍫 ВЫБЕРИТЕ ШОКОЛАД:\n\n"
        for choc_id, choc_name in CHOCOLATE_TYPES.items():
            if choc_id in selected:
                text += f"✅ {choc_name}\n"
            else:
                text += f"◻️ {choc_name}\n"
        text += f"\n🔹 Выбрано: {len(selected)}"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_chocolate_keyboard(selected)
        )
        return CHOCOLATE
    
    elif callback_data == 'choc_next':
        if not user_data[user_id]['chocolates']:
            await query.answer("❌ Выберите хотя бы один вид шоколада!", show_alert=True)
            return CHOCOLATE
        
        # Если выбран цветной шоколад, переходим к выбору цвета
        if 'colored' in user_data[user_id]['chocolates']:
            text = "🌈 ВЫБЕРИТЕ ЦВЕТА для цветного шоколада:\n\n"
            for color_name in COLOR_TYPES.values():
                text += f"◻️ {color_name}\n"
            text += f"\n🔹 Выбрано: {len(user_data[user_id]['colors'])}"
            
            await query.edit_message_text(
                text, 
                reply_markup=create_color_keyboard(user_data[user_id]['colors'])
            )
            return COLOR
        else:
            # Если цветной не выбран, сразу к посыпке
            chocolates = user_data[user_id]['chocolates']
            selected = user_data[user_id]['toppings']
            
            box_size_text = f"📦 {BOX_SIZES[user_data[user_id]['box_size']]}\n\n"
            text = box_size_text + "📋 ВАШ ШОКОЛАД:\n"
            for choc_id in chocolates:
                text += f"   • {CHOCOLATE_TYPES[choc_id]}\n"
            
            text += "\n✨ ВЫБЕРИТЕ ПОСЫПКУ:\n\n"
            for top_name in TOPPING_TYPES.values():
                text += f"◻️ {top_name}\n"
            text += f"\n🔹 Выбрано: {len(selected)}"
            
            await query.edit_message_text(
                text, 
                reply_markup=create_topping_keyboard(selected, user_id)
            )
            return TOPPING
    
    # КНОПКИ ВЫБОРА ЦВЕТА
    elif callback_data.startswith('color_') and callback_data not in ['color_next', 'color_back']:
        color_type = callback_data.replace('color_', '')
        
        if color_type in user_data[user_id]['colors']:
            user_data[user_id]['colors'].remove(color_type)
        else:
            user_data[user_id]['colors'].append(color_type)
        
        selected = user_data[user_id]['colors']
        
        text = "🌈 ВЫБЕРИТЕ ЦВЕТА для цветного шоколада:\n\n"
        for color_id, color_name in COLOR_TYPES.items():
            if color_id in selected:
                text += f"✅ {color_name}\n"
            else:
                text += f"◻️ {color_name}\n"
        text += f"\n🔹 Выбрано: {len(selected)}"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_color_keyboard(selected)
        )
        return COLOR
    
    elif callback_data == 'color_next':
        if not user_data[user_id]['colors'] and 'colored' in user_data[user_id]['chocolates']:
            await query.answer("❌ Выберите хотя бы один цвет!", show_alert=True)
            return COLOR
        
        # Переходим к посыпке
        chocolates = user_data[user_id]['chocolates']
        selected = user_data[user_id]['toppings']
        
        box_size_text = f"📦 {BOX_SIZES[user_data[user_id]['box_size']]}\n\n"
        text = box_size_text + "📋 ВАШ ШОКОЛАД:\n"
        for choc_id in chocolates:
            text += f"   • {CHOCOLATE_TYPES[choc_id]}\n"
        
        if user_data[user_id]['colors']:
            text += "   🎨 Цвета:\n"
            for color_id in user_data[user_id]['colors']:
                text += f"       {COLOR_TYPES[color_id]}\n"
        
        text += "\n✨ ВЫБЕРИТЕ ПОСЫПКУ:\n\n"
        for top_name in TOPPING_TYPES.values():
            text += f"◻️ {top_name}\n"
        text += f"\n🔹 Выбрано: {len(selected)}"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_topping_keyboard(selected, user_id)
        )
        return TOPPING
    
    elif callback_data == 'back_to_chocolate':
        selected = user_data[user_id]['chocolates']
        
        text = "🍫 ВЫБЕРИТЕ ШОКОЛАД:\n\n"
        for choc_id, choc_name in CHOCOLATE_TYPES.items():
            if choc_id in selected:
                text += f"✅ {choc_name}\n"
            else:
                text += f"◻️ {choc_name}\n"
        text += f"\n🔹 Выбрано: {len(selected)}"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_chocolate_keyboard(selected)
        )
        return CHOCOLATE
    
    elif callback_data == 'back_to_color':
        selected = user_data[user_id]['colors']
        
        text = "🌈 ВЫБЕРИТЕ ЦВЕТА для цветного шоколада:\n\n"
        for color_id, color_name in COLOR_TYPES.items():
            if color_id in selected:
                text += f"✅ {color_name}\n"
            else:
                text += f"◻️ {color_name}\n"
        text += f"\n🔹 Выбрано: {len(selected)}"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_color_keyboard(selected)
        )
        return COLOR
    
    # КНОПКИ ВЫБОРА ПОСЫПКИ
    elif callback_data.startswith('top_') and callback_data not in ['top_next', 'top_back']:
        top_type = callback_data.replace('top_', '')
        
        if top_type in user_data[user_id]['toppings']:
            user_data[user_id]['toppings'].remove(top_type)
        else:
            user_data[user_id]['toppings'].append(top_type)
        
        selected = user_data[user_id]['toppings']
        chocolates = user_data[user_id]['chocolates']
        
        box_size_text = f"📦 {BOX_SIZES[user_data[user_id]['box_size']]}\n\n"
        text = box_size_text + "📋 ВАШ ШОКОЛАД:\n"
        for choc_id in chocolates:
            text += f"   • {CHOCOLATE_TYPES[choc_id]}\n"
        
        if user_data[user_id]['colors']:
            text += "   🎨 Цвета:\n"
            for color_id in user_data[user_id]['colors']:
                text += f"       {COLOR_TYPES[color_id]}\n"
        
        text += "\n✨ ВЫБЕРИТЕ ПОСЫПКУ:\n\n"
        for top_id, top_name in TOPPING_TYPES.items():
            if top_id in selected:
                text += f"✅ {top_name}\n"
            else:
                text += f"◻️ {top_name}\n"
        text += f"\n🔹 Выбрано: {len(selected)}"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_topping_keyboard(selected, user_id)
        )
        return TOPPING
    
    elif callback_data == 'top_next':
        # Переходим к запросу телефона
        text = (
            "📞 Введите ваш номер телефона\n\n"
            "Мы свяжемся с вами для подтверждения заказа.\n\n"
            "✏️ Например: +7 (999) 123-45-67 или 89991234567\n\n"
            "Напишите номер в любом формате:"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ НАЗАД к посыпке", callback_data='back_to_topping')]]
        
        await query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PHONE
    
    elif callback_data == 'back_to_topping':
        selected = user_data[user_id]['toppings']
        chocolates = user_data[user_id]['chocolates']
        
        box_size_text = f"📦 {BOX_SIZES[user_data[user_id]['box_size']]}\n\n"
        text = box_size_text + "📋 ВАШ ШОКОЛАД:\n"
        for choc_id in chocolates:
            text += f"   • {CHOCOLATE_TYPES[choc_id]}\n"
        
        if user_data[user_id]['colors']:
            text += "   🎨 Цвета:\n"
            for color_id in user_data[user_id]['colors']:
                text += f"       {COLOR_TYPES[color_id]}\n"
        
        text += "\n✨ ВЫБЕРИТЕ ПОСЫПКУ:\n\n"
        for top_id, top_name in TOPPING_TYPES.items():
            if top_id in selected:
                text += f"✅ {top_name}\n"
            else:
                text += f"◻️ {top_name}\n"
        text += f"\n🔹 Выбрано: {len(selected)}"
        
        await query.edit_message_text(
            text, 
            reply_markup=create_topping_keyboard(selected, user_id)
        )
        return TOPPING
    
    return ConversationHandler.END

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода номера телефона"""
    user_id = update.effective_user.id
    phone_input = update.message.text.strip()
    
    if user_id not in user_data:
        await update.message.reply_text("Пожалуйста, начните с команды /start")
        return ConversationHandler.END
    
    if not validate_phone(phone_input):
        await update.message.reply_text(
            "❌ Неверный формат номера телефона!\n\n"
            "Пожалуйста, введите корректный номер (10-15 цифр).\n"
            "Например: +7 (999) 123-45-67 или 89991234567"
        )
        return PHONE
    
    user_data[user_id]['phone'] = format_phone(phone_input)
    choices = user_data[user_id]
    
    text = f"📋 ВАШ ЗАКАЗ:\n\n"
    text += f"📦 {BOX_SIZES[choices['box_size']]}\n\n"
    text += "🍫 Шоколад:\n"
    for choc_id in choices['chocolates']:
        text += f"   • {CHOCOLATE_TYPES[choc_id]}\n"
    
    if choices['colors']:
        text += "   🎨 Цвета:\n"
        for color_id in choices['colors']:
            text += f"       {COLOR_TYPES[color_id]}\n"
    
    if choices['toppings']:
        text += "\n✨ Посыпка:\n"
        for top_id in choices['toppings']:
            text += f"   • {TOPPING_TYPES[top_id]}\n"
    
    text += f"\n📞 Телефон: {choices['phone']}\n"
    text += f"\n\n📝 ОПИШИТЕ ВАШ ЗАКАЗ ПОДРОБНО:\n"
    text += "Напишите количество, особенности и пожелания.\n"
    text += "Например: Хочу набор из 5 штук клубники. Две из них должны быть розового шоколада: одну посыпать пищевым золотом, вторую малиной. Три из них должны быть в молочном шоколаде, одну из которых нужно посыпать орехами."
    
    keyboard = [[InlineKeyboardButton("🔄 Начать заново", callback_data='restart_order')]]
    
    await update.message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return DETAILS

async def details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (детали заказа)"""
    user_id = update.effective_user.id
    user_details = update.message.text
    
    if user_id not in user_data:
        await update.message.reply_text("Пожалуйста, начните с команды /start")
        return ConversationHandler.END
    
    choices = user_data[user_id]
    user_info = update.effective_user
    username = user_info.username or f"{user_info.first_name} {user_info.last_name or ''}".strip()
    
    # ИСПРАВЛЕНИЕ: Конвертируем UTC в московское время (+3 часа)
    moscow_time = get_moscow_time(update.message.date)
    
    final_message = f"🆕 НОВЫЙ ЗАКАЗ\n"
    final_message += f"{'='*30}\n\n"
    final_message += f"👤 От: @{username} (ID: {user_id})\n"
    final_message += f"📅 Время: {moscow_time.strftime('%d.%m.%Y %H:%M')} МСК\n"
    final_message += f"📞 Телефон: {choices['phone']}\n\n"
    
    final_message += f"📦 {BOX_SIZES[choices['box_size']]}\n\n"
    final_message += "🍫 Шоколад:\n"
    for choc_id in choices['chocolates']:
        final_message += f"   • {CHOCOLATE_TYPES[choc_id]}\n"
    
    if choices['colors']:
        final_message += "   🎨 Цвета:\n"
        for color_id in choices['colors']:
            final_message += f"       {COLOR_TYPES[color_id]}\n"
    
    if choices['toppings']:
        final_message += "\n✨ Посыпка:\n"
        for top_id in choices['toppings']:
            final_message += f"   • {TOPPING_TYPES[top_id]}\n"
    
    final_message += f"\n📝 Детали заказа:\n{user_details}\n"
    final_message += f"\n{'='*30}"
    
    # Отправляем в группу администраторов
    if ADMIN_GROUP_ID and ADMIN_GROUP_ID.strip().lstrip('-').isdigit():
        try:
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID.strip(),
                text=final_message
            )
            print(f"✅ Заказ отправлен в группу админов {ADMIN_GROUP_ID}")
        except Exception as e:
            print(f"❌ Ошибка отправки в группу админов: {e}")
    else:
        print(f"⚠️ ADMIN_GROUP_ID не настроен")
    
    # Отправляем подтверждение пользователю
    await update.message.reply_text(
        f"✅ Ваш заказ принят!\n\n{final_message}\n\nС вами свяжутся для подтверждения.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🆕 Новый заказ", callback_data='restart_order')
        ]])
    )
    
    del user_data[user_id]
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена заказа"""
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    await update.message.reply_text("❌ Заказ отменен. Чтобы начать заново, нажмите /start")
    return ConversationHandler.END

async def get_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для получения ID текущего чата"""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    message = f"📊 Информация о чате:\n"
    message += f"🆔 ID: {chat_id}\n"
    message += f"📋 Тип: {chat_type}\n"
    message += f"\n💡 Скопируйте этот ID в файл .env как ADMIN_GROUP_ID={chat_id}"
    
    await update.message.reply_text(message)

async def post_init(application: Application):
    """После инициализации бота"""
    print(f"✅ Бот @{application.bot.username} запущен!")
    print(f"👥 Ожидаем заказы в группе админов: {ADMIN_GROUP_ID or 'не указана'}")

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^(start_order|restart_order)$')],
        states={
            BOX_SIZE: [CallbackQueryHandler(button_handler)],
            CHOCOLATE: [CallbackQueryHandler(button_handler)],
            COLOR: [CallbackQueryHandler(button_handler)],
            TOPPING: [CallbackQueryHandler(button_handler)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler)],
            DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, details_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("groupid", get_group_id))
    application.add_handler(conv_handler)
    
    print("✅ Бот готов к работе! (с коробкой, цветами и телефоном)")
    print("📱 Нажмите Ctrl+C для остановки")
    print("💡 Чтобы получить ID группы, добавьте бота в группу и отправьте /groupid")
    
    application.run_polling()

if __name__ == '__main__':
    main()