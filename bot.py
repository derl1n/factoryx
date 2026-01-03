import os
import time
import requests
import re
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
FLASK_API = os.getenv('FLASK_API_URL', 'http://127.0.0.1:5000/check')
TG_API = f"https://api.telegram.org/bot{TOKEN}"

print(f"🤖 Bot Token: {'OK' if TOKEN else 'MISSING'}")
print(f"📡 Flask API: {FLASK_API}")

user_states = {}

WELCOME_MSG = (
    "🔍 Factoryx — AI Fact-Checker Bot\n\n"
    "Перевіряю правдивість інформації за допомогою Perplexity AI!\n\n"
    "🔥 Можливості:\n"
    "✅ Перевіряю текстові твердження\n"
    "🔗 Аналізую статті за посиланням\n"
    "🌐 Працюю в групах\n"
    "🔍 Перевіряю небезпечні посилання\n\n"
    "👇 Обери дію:"
)

GROUP_WELCOME_MSG = (
    "🔍 Factoryx — AI Fact-Checker Bot\n\n"
    "Перевіряю правдивість інформації за допомогою Perplexity AI!\n\n"
    "🔥 Можливості:\n"
    "✅ Перевіряю текстові твердження\n"
    "🔗 Аналізую статті за посиланням\n"
    "🌐 Працюю в групах\n"
    "🔍 Перевіряю небезпечні посилання\n\n"
    "📋 Команди:\n"
    "/check — Розпочати перевірку\n"
    "/cancel — Скасувати перевірку\n"
    "/help — Докладна інструкція\n"
    "/stats — Статистика\n\n"
    "💬 Підтримка: @d2rl1n"
)

HELP_MSG = (
    "📖 Інструкція:\n\n"
    "Як перевірити:\n"
    "1️⃣ Натисни кнопку \"🔍 Перевірити\"\n"
    "2️⃣ Потім надішли:\n"
    " • Або текст для перевірки (мін. 10 символів)\n"
    " • Або посилання на статтю\n"
    " • Або текст і посилання одночасно\n\n"
    "В групах:\n"
    "• Команда /check працює так само\n"
    "• Бот запитає, що перевірити\n\n"
    "🎯 Оцінки:\n"
    "✅ 80-100 = Ймовірно правда\n"
    "⚠️ 50-79 = Потребує перевірки\n"
    "❌ 0-49 = Ймовірно неправда\n\n"
    "💬 Підтримка: @d2rl1n"
)

# ==========================================================
# КНОПКИ
# ==========================================================
def get_main_keyboard():
    """Головна клавіатура для приватних чатів"""
    return {
        "keyboard": [
            [{"text": "🔍 Перевірити"}],
            [{"text": "📖 Інструкція"}, {"text": "📊 Статистика"}],
            [{"text": "❌ Скасувати"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_cancel_keyboard():
    """Клавіатура зі скасуванням"""
    return {
        "keyboard": [
            [{"text": "❌ Скасувати"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# ==========================================================
# TELEGRAM API
# ==========================================================
def get_updates(offset=None):
    params = {'offset': offset, 'timeout': 30}
    r = requests.get(f"{TG_API}/getUpdates", params=params, timeout=40)
    return r.json() if r.ok else {'ok': False}

def send_msg(chat_id, text, parse_mode='HTML', reply_to=None, keyboard=None):
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    if reply_to:
        data['reply_to_message_id'] = reply_to
    if keyboard:
        data['reply_markup'] = keyboard
    response = requests.post(f"{TG_API}/sendMessage", json=data)
    return response.json() if response.ok else None

def set_bot_commands():
    """Встановлює команди для груп"""
    commands = [
        {"command": "check", "description": "🔍 Розпочати перевірку"},
        {"command": "cancel", "description": "❌ Скасувати перевірку"},
        {"command": "help", "description": "📖 Інструкція"},
        {"command": "stats", "description": "📊 Статистика"}
    ]
    try:
        requests.post(f"{TG_API}/setMyCommands", json={"commands": commands})
        print("✅ Команди встановлено")
    except Exception as e:
        print(f"⚠️ Помилка команд: {e}")

# ==========================================================
# HELPERS
# ==========================================================
def extract_text_and_link(message):
    """Витягує текст та посилання з повідомлення"""
    urls = re.findall(r'https?://[^\s]+', message)
    link = urls[0] if urls else ""
    text = re.sub(r'https?://[^\s]+', '', message).strip()
    return text, link

def normalize_command(text):
    """Прибирає @mention з команд"""
    return re.sub(r'@\w+', '', text).strip()

def escape_html(text):
    """Екранує спецсимволи для HTML"""
    if not text:
        return text
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def get_domain_name(url):
    """Отримує доменне ім'я з URL для відображення"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        if 'wikipedia' in domain:
            return 'Wikipedia'
        return domain
    except:
        return 'Джерело'

def is_gibberish(text):
    """Перевіряє чи текст є білібердою (ВИПРАВЛЕНА ВЕРСІЯ)"""
    if not text or len(text.strip()) < 5:
        return True
    
    # Видаляємо пробіли для аналізу
    text_no_spaces = text.replace(' ', '').replace('\n', '')
    
    # Якщо занадто короткий після очищення
    if len(text_no_spaces) < 5:
        return True
    
    # Перевірка на наявність нормальних слів (мінімум 2 літери)
    words = re.findall(r'[a-zA-Zа-яА-ЯіїєґІЇЄҐ]{2,}', text)
    if len(words) >= 3:  # Якщо є хоча б 3 нормальні слова - не білиберда
        return False
    
    # Багато однакових символів підряд (ааааааа)
    if re.search(r'(.)\1{5,}', text):
        return True
    
    # Клавіатурні патерни (тільки якщо текст дуже короткий)
    if len(text) < 20:
        keyboard_patterns = ['qwerty', 'asdfgh', 'zxcvbn', 'йцукен', 'фывап', 'ячсмит']
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in keyboard_patterns):
            return True
    
    # Перевірка на відсутність голосних (але тільки для коротких текстів)
    if len(text_no_spaces) < 30:
        vowels = 'aeiouаеєиіїоуюя'
        has_vowels = any(char.lower() in vowels for char in text)
        if not has_vowels:
            return True
    
    # ВИДАЛЕНО ПЕРЕВІРКУ НА УНІКАЛЬНІСТЬ - вона помилково блокувала нормальні тексти
    
    return False

# ==========================================================
# FACT CHECK
# ==========================================================
def check_fact(text, link, chat_id, chat_type):
    try:
        # ❌ ВАЛІДАЦІЯ
        if text and is_gibberish(text):
            send_msg(chat_id, "❌ Введіть твердження для перевірки", 
                    keyboard=get_main_keyboard() if chat_type == 'private' else None)
            return
        
        # 🔍 ТІЛЬКИ ТЕПЕР ПОКАЗУЄМО "Перевіряю"
        send_msg(chat_id, "🔍 Перевіряю...", 
                keyboard=get_main_keyboard() if chat_type == 'private' else None)
        
        payload = {'text': text, 'link': link, 'lang': 'uk'}
        r = requests.post(FLASK_API, json=payload, timeout=30)
        
        if r.status_code != 200:
            try:
                error_data = r.json()
                error = error_data.get('error', 'Невідома помилка')
            except:
                error = f"Помилка сервера (код {r.status_code})"
            send_msg(chat_id, escape_html(error), 
                    keyboard=get_main_keyboard() if chat_type == 'private' else None)
            return
        
        data = r.json()
        if 'error' in data:
            send_msg(chat_id, escape_html(data['error']), 
                    keyboard=get_main_keyboard() if chat_type == 'private' else None)
            return
        
        score = data.get('score', 50)
        gemini = data.get('gemini', {})
        explanation = gemini.get('explanation', '')[:400]
        sources = gemini.get('sources', [])
        google_fc = data.get('google_factcheck', [])
        google_s = data.get('google_search', [])
        domain_check = data.get('domain_check', {})
        
        emoji = "✅" if score >= 80 else "⚠️" if score >= 50 else "❌"
        label = "Ймовірно правда" if score >= 80 else "Потребує перевірки" if score >= 50 else "Ймовірно неправда"
        
        reply = f"{emoji} {label}\n\n"
        reply += f"📊 Оцінка: {score}/100\n\n"
        
        if explanation:
            explanation_clean = escape_html(explanation)
            reply += f"💬 Пояснення:\n{explanation_clean}\n\n"
        
        if sources:
            reply += f"🔗 Джерела перевірки:\n"
            for i, src in enumerate(sources[:5], 1):
                domain = get_domain_name(src)
                reply += f'{i}. <a href="{src}">{domain}</a>\n'
            reply += "\n"
        
        if google_fc:
            reply += f"📰 Фактчеків: {len(google_fc)}\n"
        if google_s:
            reply += f"🔍 Джерел: {len(google_s)}\n"
        
        if link and domain_check:
            sb = domain_check.get('safe_browsing', {})
            spam = domain_check.get('spamhaus', {})
            if not sb.get('safe', True):
                reply += f"\n⚠️ Небезпечне посилання!"
            if spam.get('listed', False):
                reply += f"\n⚠️ Домен у спам-списку!"
        
        result = send_msg(chat_id, reply, parse_mode='HTML', 
                         keyboard=get_main_keyboard() if chat_type == 'private' else None)
        
        if not result:
            print("⚠️ Помилка HTML, відправляю без форматування")
            reply_plain = re.sub(r'<[^>]+>', '', reply)
            send_msg(chat_id, reply_plain, parse_mode=None, 
                    keyboard=get_main_keyboard() if chat_type == 'private' else None)
        
        print("✅ Перевірку завершено")
        
    except requests.exceptions.Timeout:
        send_msg(chat_id, "⏱️ Таймаут запиту. Спробуй ще раз.", 
                keyboard=get_main_keyboard() if chat_type == 'private' else None)
    except requests.exceptions.ConnectionError:
        send_msg(chat_id, "❌ Сервер не відповідає. Перевір, чи запущено app.py", 
                keyboard=get_main_keyboard() if chat_type == 'private' else None)
    except Exception as e:
        print(f"💥 Помилка перевірки: {e}")
        import traceback
        traceback.print_exc()
        send_msg(chat_id, "❌ Помилка перевірки. Спробуй ще раз або напиши @d2rl1n", 
                keyboard=get_main_keyboard() if chat_type == 'private' else None)

# ==========================================================
# MAIN
# ==========================================================
def main():
    offset = None
    set_bot_commands()
    print("🚀 Factoryx Bot запущено!")
    
    while True:
        updates = get_updates(offset)
        if not updates.get('ok', False) or not updates.get('result'):
            time.sleep(2)
            continue
        
        for u in updates['result']:
            offset = u['update_id'] + 1
            message = u.get('message', {})
            chat = message.get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type', 'private')
            text = message.get('text', '').strip()
            new_chat_member = message.get('new_chat_member')
            
            if not chat_id:
                continue
            
            # Додавання в групу
            if new_chat_member:
                bot_info_response = requests.get(f"{TG_API}/getMe").json()
                bot_id = bot_info_response.get('result', {}).get('id')
                if new_chat_member.get('id') == bot_id:
                    send_msg(chat_id, GROUP_WELCOME_MSG)
                    print(f"✅ Додано в групу: {chat_id}")
                continue
            
            original_text = text
            text_lower = text.lower()
            
            # Нормалізація команд для груп
            if chat_type in ['group', 'supergroup']:
                text = normalize_command(text)
            
            print(f"📨 [{chat_type}] {chat_id}: {text[:40]}...")
            
            # ===========================================
            # ОБРОБКА КНОПОК (тільки для приватних чатів)
            # ===========================================
            if chat_type == 'private':
                if text_lower == '🔍 перевірити' or text == '/check':
                    user_states[chat_id] = 'waiting_for_input'
                    send_msg(
                        chat_id,
                        "🔍 Що перевірити?\n\n"
                        "Надішли:\n"
                        "• Або текст для перевірки (мін. 10 символів)\n"
                        "• Або посилання на статтю\n"
                        "• Або текст і посилання одночасно\n\n"
                        "Для скасування натисни \"❌ Скасувати\"",
                        keyboard=get_cancel_keyboard()
                    )
                    continue
                
                elif text_lower == '❌ скасувати' or text == '/cancel':
                    if chat_id in user_states:
                        user_states.pop(chat_id, None)
                        send_msg(chat_id, "❌ Перевірку скасовано.", keyboard=get_main_keyboard())
                    else:
                        send_msg(chat_id, "💡 Немає активної перевірки.", keyboard=get_main_keyboard())
                    continue
                
                elif text_lower == '📖 інструкція' or text == '/help':
                    send_msg(chat_id, HELP_MSG, keyboard=get_main_keyboard())
                    continue
                
                elif text_lower == '📊 статистика' or text == '/stats':
                    try:
                        stats = requests.get(f"{FLASK_API.replace('/check', '/stats')}", timeout=10).json()
                        total = stats.get('total_checks', 0)
                        today = stats.get('today', 0)
                        week = stats.get('week', 0)
                        reply = f"📊 Статистика Factoryx:\n\n"
                        reply += f"📈 Всього перевірок: {total}\n"
                        reply += f"🗓 Сьогодні: {today}\n"
                        reply += f"📅 За тиждень: {week}"
                        send_msg(chat_id, reply, keyboard=get_main_keyboard())
                    except Exception as e:
                        print(f"Помилка статистики: {e}")
                        send_msg(chat_id, "📊 Статистика тимчасово недоступна", keyboard=get_main_keyboard())
                    continue
                
                elif text == '/start':
                    user_states.pop(chat_id, None)
                    send_msg(chat_id, WELCOME_MSG, keyboard=get_main_keyboard())
                    continue
            
            # ===========================================
            # ОБРОБКА КОМАНД ДЛЯ ГРУП
            # ===========================================
            if chat_type in ['group', 'supergroup']:
                if text == '/start':
                    user_states.pop(chat_id, None)
                    send_msg(chat_id, GROUP_WELCOME_MSG)
                    continue
                
                elif text == '/check':
                    user_states[chat_id] = 'waiting_for_input'
                    send_msg(
                        chat_id,
                        "🔍 Що перевірити?\n\n"
                        "Надішли:\n"
                        "• Або текст для перевірки (мін. 10 символів)\n"
                        "• Або посилання на статтю\n"
                        "• Або текст і посилання одночасно\n\n"
                        "Для скасування: /cancel"
                    )
                    continue
                
                elif text == '/cancel':
                    if chat_id in user_states:
                        user_states.pop(chat_id, None)
                        send_msg(chat_id, "❌ Перевірку скасовано.\n\nДля нової перевірки: /check")
                    else:
                        send_msg(chat_id, "💡 Немає активної перевірки.\n\nРозпочати: /check")
                    continue
                
                elif text == '/help':
                    send_msg(chat_id, HELP_MSG.replace('<', '').replace('>', ''))
                    continue
                
                elif text == '/stats':
                    try:
                        stats = requests.get(f"{FLASK_API.replace('/check', '/stats')}", timeout=10).json()
                        total = stats.get('total_checks', 0)
                        today = stats.get('today', 0)
                        week = stats.get('week', 0)
                        reply = f"📊 Статистика Factoryx:\n\n"
                        reply += f"📈 Всього перевірок: {total}\n"
                        reply += f"🗓 Сьогодні: {today}\n"
                        reply += f"📅 За тиждень: {week}"
                        send_msg(chat_id, reply)
                    except Exception as e:
                        print(f"Помилка статистики: {e}")
                        send_msg(chat_id, "📊 Статистика тимчасово недоступна")
                    continue
                
                # Ігноруємо не-команди в групах
                if not original_text.startswith('/'):
                    if user_states.get(chat_id) != 'waiting_for_input':
                        continue
            
            # ===========================================
            # ОБРОБКА ВВЕДЕННЯ ТЕКСТУ/ПОСИЛАННЯ
            # ===========================================
            if user_states.get(chat_id) == 'waiting_for_input':
                check_text = original_text
                
                if not check_text or len(check_text.strip()) < 10:
                    send_msg(chat_id, "❌ Текст занадто короткий (мінімум 10 символів)", 
                            keyboard=get_main_keyboard() if chat_type == 'private' else None)
                    continue
                
                extracted_text, link = extract_text_and_link(check_text)
                check_fact(extracted_text, link, chat_id, chat_type)
                user_states.pop(chat_id, None)
                continue
            
            # ✅ НОВИЙ КОД: якщо текст без команди/кнопки в приватному чаті
            if chat_type == 'private' and not text.startswith('/'):
                send_msg(
                    chat_id,
                    "💡 Щоб перевірити інформацію:\n\n"
                    "Натисни \"🔍 Перевірити\"",
                    keyboard=get_main_keyboard()
                )
                continue

if __name__ == '__main__':
    # ✅ СПОЧАТКУ запускаємо Flask в окремому потоці
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # ✅ ПОТІМ запускаємо бота
    main()
