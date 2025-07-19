# main.py
# This is the main file to run your Telegram Bot.
# Make sure to install the required library: pip install python-telegram-bot

import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- Basic Setup ---
# Set up logging to see errors
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# IMPORTANT: These should be set as environment variables on your hosting platform (like Render).
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", 123456789)) # Replace with your Telegram User ID

# --- Database Management ---
# We'll use a simple JSON file as our database. For a larger game, consider a real database like SQLite.
DB_FILE = 'players.json'

def load_player_data():
    """Loads all player data from the JSON file."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_player_data(data):
    """Saves all player data to the JSON file."""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- Localization (i18n) ---
locales = {}

def load_locales():
    """Loads language strings from JSON files."""
    global locales
    for lang in ['en', 'fa']:
        try:
            with open(f'locales/{lang}.json', 'r', encoding='utf-8') as f:
                locales[lang] = json.load(f)
        except FileNotFoundError:
            logger.error(f"Locale file for '{lang}' not found!")
            locales[lang] = {}

def get_text(key, lang='en', **kwargs):
    """Gets a text string for a given key and language."""
    return locales.get(lang, {}).get(key, key).format(**kwargs)

# --- Game World Definition ---
GAME_MAP = {
    "downtown": {
        "name_en": "Downtown", "name_fa": "مرکز شهر",
        "description_en": "Towering skyscrapers and luxury apartments dominate the skyline. The air hums with power and ambition.",
        "description_fa": "آسمان‌خراش‌های سر به فلک کشیده و آپارتمان‌های لوکس، خط افق را تسخیر کرده‌اند. هوا از قدرت و جاه‌طلبی لبریز است.",
        "connections": ["neon_district", "industrial_zone", "the_plaza"],
        "locations": ["the_onyx_bar", "vip_lounge"]
    },
    "neon_district": {
        "name_en": "Neon District", "name_fa": "منطقه نئون",
        "description_en": "A vibrant, chaotic district buzzing with nightlife. Music spills from every doorway.",
        "description_fa": "منطقه‌ای پرجنب‌وجوش و پرهرج‌ومرج که با زندگی شبانه می‌تپد. موسیقی از هر دری به بیرون می‌ریزد.",
        "connections": ["downtown"],
        "locations": []
    },
    "industrial_zone": {
        "name_en": "Industrial Zone", "name_fa": "منطقه صنعتی",
        "description_en": "A gritty, working-class area of factories and warehouses. The smell of metal and sweat hangs in the air.",
        "description_fa": "منطقه‌ای زمخت و کارگری پر از کارخانه و انبار. بوی فلز و عرق در هوا پیچیده است.",
        "connections": ["downtown"],
        "locations": []
    },
    "the_plaza": {
        "name_en": "The Plaza", "name_fa": "پلازا",
        "description_en": "An open-air plaza with a grand fountain at its center. A place for the public to gather.",
        "description_fa": "یک میدانگاه با یک فواره بزرگ در مرکز آن. مکانی برای تجمع مردم.",
        "connections": ["downtown"],
        "locations": []
    }
}

LOCATIONS = {
    "the_onyx_bar": {
        "name_en": "The Onyx Bar", "name_fa": "بار اونیکس",
        "description_en": "A classy, dimly lit bar where the city's elite come to make deals in the shadows.",
        "description_fa": "یک بار شیک و کم‌نور که نخبگان شهر برای انجام معاملات در سایه‌ها به آنجا می‌آیند.",
        "npcs": ["slick_the_bartender"]
    },
    "vip_lounge": {
        "name_en": "The VIP Lounge", "name_fa": "سالن VIP",
        "description_en": "An exclusive, opulent lounge accessible only to the city's most influential.",
        "description_fa": "یک سالن مجلل و انحصاری که فقط برای افراد با نفوذ شهر قابل دسترسی است.",
        "npcs": [],
        "requires_vip": True
    }
}

NPCS = {
    "slick_the_bartender": {
        "name_en": "Slick, the Bartender", "name_fa": "اسلیک، متصدی بار",
        "dialogue_en": "'What can I get for you? See a lot of faces in here. Some win, some lose. The city always collects.'",
        "dialogue_fa": "'چی میل داری؟ چهره‌های زیادی اینجا می‌بینم. بعضی‌ها می‌برن، بعضی‌ها می‌بازن. شهر همیشه حقشو می‌گیره.'",
    }
}

# --- Helper Functions ---
def get_player_state(user_id):
    """Gets the current state for a player, creating a default if none exists."""
    players = load_player_data()
    user_id_str = str(user_id)
    if user_id_str not in players:
        players[user_id_str] = {
            "lang": "en",
            "approved": False,
            "pending_approval": False,
            "voice_file_id": None,
            "character_created": False,
            "name": None,
            "profession": None,
            "location": "downtown",
            "inventory": [],
            "stats": {"charm": 1, "intellect": 1, "street_smarts": 1},
            "currency": 100,
            "is_vip": False,
        }
    return players[user_id_str]

def update_player_state(user_id, state):
    """Updates and saves a player's state."""
    players = load_player_data()
    players[str(user_id)] = state
    save_player_data(players)

def is_admin(user_id):
    """Checks if a user is the admin."""
    return user_id == ADMIN_USER_ID

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command. Greets the user and guides them."""
    user = update.effective_user
    player_state = get_player_state(user.id)

    if player_state['approved']:
        if not player_state['character_created']:
            await character_creation_prompt(update, context, user.id)
        else:
            lang = player_state['lang']
            await update.message.reply_text(get_text('welcome_back', lang, name=player_state['name']))
            await show_main_menu(update, context, user.id)
    elif player_state['pending_approval']:
        lang = player_state['lang']
        await update.message.reply_text(get_text('approval_pending', lang))
    else:
        # New player flow: Language selection
        keyboard = [
            [InlineKeyboardButton("English", callback_data='set_lang_en')],
            [InlineKeyboardButton("فارسی (Persian)", callback_data='set_lang_fa')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Welcome to Crimson City. Please choose your language.\n\nبه شهر کریمسون خوش آمدید. لطفاً زبان خود را انتخاب کنید.",
            reply_markup=reply_markup
        )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Displays the main game menu."""
    player_state = get_player_state(user_id)
    lang = player_state['lang']

    keyboard = [
        [InlineKeyboardButton(get_text('menu_look', lang), callback_data='main_look')],
        [InlineKeyboardButton(get_text('menu_move', lang), callback_data='main_move')],
        [InlineKeyboardButton(get_text('menu_profile', lang), callback_data='main_profile')],
        [InlineKeyboardButton(get_text('menu_inventory', lang), callback_data='main_inventory')],
        [InlineKeyboardButton(get_text('menu_language', lang), callback_data='main_language')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if the message exists before trying to edit it
    message_text = get_text('main_menu_prompt', lang)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text=message_text, reply_markup=reply_markup)
        except Exception as e:
            logger.warning(f"Could not edit message, sending new one: {e}")
            await context.bot.send_message(chat_id=user_id, text=message_text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=user_id, text=message_text, reply_markup=reply_markup)

async def character_creation_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Asks the user for their character's name."""
    player_state = get_player_state(user_id)
    lang = player_state['lang']
    context.user_data['next_step'] = 'create_character_name'
    await context.bot.send_message(chat_id=user_id, text=get_text('character_creation_name', lang))

# --- Message & Voice Handlers ---

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages for character creation."""
    user_id = update.effective_user.id
    player_state = get_player_state(user_id)
    next_step = context.user_data.get('next_step')

    if not player_state['approved']:
        return # Ignore messages from unapproved users

    if next_step == 'create_character_name':
        lang = player_state['lang']
        player_state['name'] = update.message.text
        update_player_state(user_id, player_state)

        keyboard = [
            [InlineKeyboardButton(get_text('prof_hustler', lang), callback_data='set_prof_hustler')],
            [InlineKeyboardButton(get_text('prof_intellectual', lang), callback_data='set_prof_intellectual')],
            [InlineKeyboardButton(get_text('prof_charmer', lang), callback_data='set_prof_charmer')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(get_text('character_creation_profession', lang), reply_markup=reply_markup)
        context.user_data['next_step'] = None

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the voice message for verification."""
    user = update.effective_user
    player_state = get_player_state(user.id)
    lang = player_state['lang']

    if player_state['approved'] or player_state['pending_approval']:
        await update.message.reply_text(get_text('voice_already_submitted', lang))
        return

    player_state['pending_approval'] = True
    player_state['voice_file_id'] = update.message.voice.file_id
    update_player_state(user.id, player_state)

    # Notify user and admin
    await update.message.reply_text(get_text('approval_pending', lang))

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f'approve_{user.id}'),
            InlineKeyboardButton("❌ Reject", callback_data=f'reject_{user.id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"New user for approval: {user.full_name} (ID: {user.id})"
    )
    await context.bot.send_voice(
        chat_id=ADMIN_USER_ID,
        voice=player_state['voice_file_id'],
        reply_markup=reply_markup
    )

# --- Callback Query Handlers (for buttons) ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all button presses."""
    query = update.callback_query
    await query.answer()
    user_id = query.effective_user.id
    player_state = get_player_state(user_id)
    lang = player_state.get('lang', 'en')
    
    # --- Admin Approval ---
    if query.data.startswith('approve_') or query.data.startswith('reject_'):
        if not is_admin(user_id): return
        action, target_user_id_str = query.data.split('_')
        target_user_id = int(target_user_id_str)
        target_player_state = get_player_state(target_user_id)
        
        if action == 'approve':
            target_player_state['approved'] = True
            target_player_state['pending_approval'] = False
            update_player_state(target_user_id, target_player_state)
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"User {target_user_id} approved.")
            target_lang = target_player_state['lang']
            await context.bot.send_message(chat_id=target_user_id, text=get_text('approval_success', target_lang))
            await character_creation_prompt(update, context, target_user_id)
        else: # Reject
            players = load_player_data()
            del players[target_user_id_str]
            save_player_data(players)
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"User {target_user_id} rejected and data deleted.")
            # We don't need to notify the rejected user.
        return

    # --- Language Selection ---
    if query.data.startswith('set_lang_'):
        lang_code = query.data.split('_')[-1]
        player_state['lang'] = lang_code
        update_player_state(user_id, player_state)
        await query.edit_message_text(text=get_text('voice_prompt', lang_code))
        context.user_data['next_step'] = 'submit_voice'
        return

    # --- Character Profession ---
    if query.data.startswith('set_prof_'):
        # ... (same as before) ...
        profession = query.data.split('_')[-1]
        player_state['profession'] = profession
        if profession == 'hustler': player_state['stats']['street_smarts'] += 2
        elif profession == 'intellectual': player_state['stats']['intellect'] += 2
        elif profession == 'charmer': player_state['stats']['charm'] += 2
        player_state['character_created'] = True
        update_player_state(user_id, player_state)
        await query.edit_message_text(text=get_text('character_creation_complete', lang, name=player_state['name']))
        await show_main_menu(update, context, user_id)
        return

    # --- Main Menu Actions ---
    if query.data == 'main_look':
        current_location_key = player_state['location']
        location_info = GAME_MAP[current_location_key]
        location_name = location_info[f'name_{lang}']
        location_desc = location_info[f'description_{lang}']
        
        text = f"📍 *{location_name}*\n\n{location_desc}"

        # Check if God is here
        admin_state = get_player_state(ADMIN_USER_ID)
        if admin_state.get('location') == current_location_key and not is_admin(user_id):
            text += f"\n\n_{get_text('god_presence', lang)}_"

        # Show locations within the district
        keyboard = [[InlineKeyboardButton(f"« {get_text('back_button', lang)}", callback_data='main_back')]]
        if location_info['locations']:
             text += f"\n\n{get_text('places_in_district', lang)}:"
             for loc_key in location_info['locations']:
                 # Check for VIP restriction
                 if LOCATIONS[loc_key].get('requires_vip', False) and not player_state['is_vip']:
                     continue
                 loc_name = LOCATIONS[loc_key][f'name_{lang}']
                 text += f"\n- {loc_name}"
        
        # Show NPCs in the area
        if LOCATIONS.get(current_location_key) and LOCATIONS[current_location_key]['npcs']:
            text += f"\n\n{get_text('npcs_in_area', lang)}:"
            for npc_key in LOCATIONS[current_location_key]['npcs']:
                npc_name = NPCS[npc_key][f'name_{lang}']
                keyboard.insert(0, [InlineKeyboardButton(f"🗣️ {get_text('talk_to', lang)} {npc_name}", callback_data=f'talk_{npc_key}')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'main_move':
        # ... (same as before) ...
        current_location_key = player_state['location']
        connections = GAME_MAP[current_location_key]['connections']
        keyboard = []
        for conn_key in connections:
            conn_name = GAME_MAP[conn_key][f'name_{lang}']
            keyboard.append([InlineKeyboardButton(conn_name, callback_data=f'move_to_{conn_key}')])
        keyboard.append([InlineKeyboardButton(f"« {get_text('back_button', lang)}", callback_data='main_back')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=get_text('move_prompt', lang), reply_markup=reply_markup)

    elif query.data == 'main_profile':
        stats = player_state['stats']
        vip_status = get_text('vip_status_yes', lang) if player_state['is_vip'] else get_text('vip_status_no', lang)
        profile_text = get_text(
            'profile_view', lang,
            name=player_state['name'],
            profession=get_text(f"prof_{player_state['profession']}", lang),
            charm=stats['charm'], intellect=stats['intellect'], street_smarts=stats['street_smarts'],
            currency=player_state['currency'], vip_status=vip_status
        )
        await query.edit_message_text(text=profile_text, parse_mode='Markdown')
        await show_main_menu(update, context, user_id)

    elif query.data == 'main_inventory':
        inventory = player_state.get('inventory', [])
        if not inventory:
            text = get_text('inventory_empty', lang)
        else:
            text = f"*{get_text('menu_inventory', lang)}*\n"
            for item in inventory:
                text += f"- {item}\n"
        await query.edit_message_text(text=text, parse_mode='Markdown')
        await show_main_menu(update, context, user_id)

    elif query.data == 'main_language':
        # ... (same as before) ...
        keyboard = [[InlineKeyboardButton("English", callback_data='set_lang_en')], [InlineKeyboardButton("فارسی (Persian)", callback_data='set_lang_fa')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Choose your language / زبان خود را انتخاب کنید", reply_markup=reply_markup)

    elif query.data == 'main_back':
        await show_main_menu(update, context, user_id)
        
    # --- Movement & Interaction ---
    if query.data.startswith('move_to_'):
        destination_key = query.data.replace('move_to_', '')
        player_state['location'] = destination_key
        update_player_state(user_id, player_state)
        destination_name = GAME_MAP[destination_key][f'name_{lang}']
        await query.edit_message_text(text=get_text('move_success', lang, location=destination_name))
        await show_main_menu(update, context, user_id)

    if query.data.startswith('talk_'):
        npc_key = query.data.replace('talk_', '')
        npc_dialogue = NPCS[npc_key][f'dialogue_{lang}']
        await query.edit_message_text(text=f"_{npc_dialogue}_", parse_mode='Markdown')
        await show_main_menu(update, context, user_id)


# --- Admin "God Mode" Commands ---

async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows admin help."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not worthy.")
        return
    
    help_text = """
    *Crimson City God Mode*
    /adminhelp - This message
    /broadcast <msg> - Send message to all players
    /playerinfo <id> - Get player's data
    /setstat <id> <stat> <val> - Set a player's stat
    /giveitem <id> <item> - Give item to player
    /givemoney <id> <amount> - Give currency to player
    /setvip <id> <on|off> - Set VIP status for a player
    /teleport <id> <loc_key> - Teleport a player
    /whisper <id> <msg> - Send a private message to a player
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ... (broadcast_command, player_info_command, set_stat_command are mostly the same)
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts a message to all players."""
    if not is_admin(update.effective_user.id): return
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    players = load_player_data()
    count = 0
    for user_id, p_data in players.items():
        if p_data.get('approved'):
            try:
                lang = p_data.get('lang', 'en')
                broadcast_header = get_text('broadcast_header', lang)
                await context.bot.send_message(chat_id=user_id, text=f"{broadcast_header}\n\n{message}")
                count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user_id}: {e}")
    await update.message.reply_text(f"Broadcast sent to {count} players.")

async def player_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gets info for a specific player."""
    if not is_admin(update.effective_user.id): return
    try:
        target_user_id = context.args[0]
        player_data = get_player_state(target_user_id)
        info_text = json.dumps(player_data, indent=2, ensure_ascii=False)
        await update.message.reply_text(f"<code>{info_text}</code>", parse_mode='HTML')
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /playerinfo <user_id>")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def set_stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to set a player's stat."""
    if not is_admin(update.effective_user.id): return
    try:
        target_user_id, stat_name, value = context.args
        value = int(value)
        stat_name = stat_name.lower()
        players = load_player_data()
        target_user_id_str = str(target_user_id)
        if target_user_id_str not in players:
            await update.message.reply_text(f"Player {target_user_id} not found.")
            return
        if stat_name not in players[target_user_id_str]['stats']:
            await update.message.reply_text(f"Invalid stat. Use: charm, intellect, street_smarts.")
            return
        players[target_user_id_str]['stats'][stat_name] = value
        save_player_data(players)
        await update.message.reply_text(f"Set {stat_name} to {value} for player {target_user_id}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /setstat <user_id> <stat_name> <value>")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")

async def give_item_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gives an item to a player."""
    if not is_admin(update.effective_user.id): return
    try:
        target_user_id, item_name = context.args[0], " ".join(context.args[1:])
        if not item_name: raise ValueError
        
        players = load_player_data()
        target_user_id_str = str(target_user_id)
        if target_user_id_str not in players:
            await update.message.reply_text(f"Player {target_user_id} not found.")
            return
        
        players[target_user_id_str]['inventory'].append(item_name)
        save_player_data(players)
        await update.message.reply_text(f"Gave '{item_name}' to player {target_user_id}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /giveitem <user_id> <item_name>")

async def give_money_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gives currency to a player."""
    if not is_admin(update.effective_user.id): return
    try:
        target_user_id, amount = context.args
        amount = int(amount)
        players = load_player_data()
        target_user_id_str = str(target_user_id)
        if target_user_id_str not in players:
            await update.message.reply_text(f"Player {target_user_id} not found.")
            return
        players[target_user_id_str]['currency'] += amount
        save_player_data(players)
        await update.message.reply_text(f"Gave {amount} CC to player {target_user_id}. New balance: {players[target_user_id_str]['currency']}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /givemoney <user_id> <amount>")

async def set_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets VIP status for a player."""
    if not is_admin(update.effective_user.id): return
    try:
        target_user_id, status = context.args
        if status.lower() not in ['on', 'off']: raise ValueError
        
        is_vip = status.lower() == 'on'
        players = load_player_data()
        target_user_id_str = str(target_user_id)
        if target_user_id_str not in players:
            await update.message.reply_text(f"Player {target_user_id} not found.")
            return
        
        players[target_user_id_str]['is_vip'] = is_vip
        save_player_data(players)
        await update.message.reply_text(f"Set VIP status for player {target_user_id} to {status.upper()}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /setvip <user_id> <on|off>")

async def teleport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Teleports a player to a new location."""
    if not is_admin(update.effective_user.id): return
    try:
        target_user_id, location_key = context.args
        if location_key not in GAME_MAP:
            await update.message.reply_text(f"Invalid location key. Valid keys: {', '.join(GAME_MAP.keys())}")
            return

        players = load_player_data()
        target_user_id_str = str(target_user_id)
        if target_user_id_str not in players:
            await update.message.reply_text(f"Player {target_user_id} not found.")
            return
        
        players[target_user_id_str]['location'] = location_key
        save_player_data(players)
        await update.message.reply_text(f"Teleported player {target_user_id} to {location_key}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /teleport <user_id> <location_key>")

async def whisper_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a private message to a player."""
    if not is_admin(update.effective_user.id): return
    try:
        target_user_id, message = context.args[0], " ".join(context.args[1:])
        if not message: raise ValueError
        
        target_player_state = get_player_state(target_user_id)
        lang = target_player_state.get('lang', 'en')
        whisper_header = get_text('whisper_header', lang)

        await context.bot.send_message(chat_id=target_user_id, text=f"{whisper_header}\n\n_{message}_", parse_mode='Markdown')
        await update.message.reply_text(f"Whisper sent to {target_user_id}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /whisper <user_id> <message>")
    except Exception as e:
        await update.message.reply_text(f"Could not send whisper: {e}")

def main():
    """Start the bot."""
    # Create necessary directories and files
    if not os.path.exists('locales'): os.makedirs('locales')
    
    # Create/Update English locale file
    en_locale = {
        "voice_prompt": "To ensure the quality of our community, you must be approved by an admin. Please send a voice message stating your character name and age.",
        "approval_pending": "Your request has been sent for approval. Please wait for an admin to review it. You will be notified.",
        "approval_success": "✅ You have been approved! Welcome to Crimson City. Let's create your character.",
        "voice_already_submitted": "You have already submitted a voice message for approval.",
        "welcome_back": "Welcome back, {name}. The city awaits.",
        "language_set": "Language set to English.",
        "character_creation_name": "The city doesn't know you yet. What name will you be known by?",
        "character_creation_profession": "And what is your trade? How did you make your way in this world?",
        "prof_hustler": "Street Hustler", "prof_intellectual": "Intellectual", "prof_charmer": "Charmer",
        "character_creation_complete": "Very well, {name}. Your story in Crimson City begins now.",
        "main_menu_prompt": "What's your next move?",
        "menu_look": "🔎 Look Around", "menu_move": "🗺️ Move", "menu_profile": "👤 Profile", "menu_language": "🌐 Language", "menu_inventory": "🎒 Inventory",
        "profile_view": "👤 *Profile*\n\n*Name:* {name}\n*Profession:* {profession}\n*VIP Status:* {vip_status}\n\n*Currency:* {currency} CC\n\n*Stats:*\n- Charm: {charm}\n- Intellect: {intellect}\n- Street Smarts: {street_smarts}",
        "move_prompt": "Where do you want to go?",
        "move_success": "You arrive at {location}.",
        "back_button": "Back",
        "places_in_district": "You see a few places of interest:",
        "npcs_in_area": "People here:",
        "talk_to": "Talk to",
        "god_presence": "You feel an overwhelming presence. The God of this City is here.",
        "inventory_empty": "Your pockets are empty.",
        "vip_status_yes": "Yes", "vip_status_no": "No",
        "broadcast_header": "A message echoes through the city:",
        "whisper_header": "A voice whispers directly into your mind:"
    }
    with open('locales/en.json', 'w', encoding='utf-8') as f: json.dump(en_locale, f, indent=4)

    # Create/Update Persian locale file
    fa_locale = {
        "voice_prompt": "برای اطمینان از کیفیت جامعه ما، باید توسط ادمین تأیید شوید. لطفاً یک پیام صوتی ارسال کنید و نام شخصیت و سن خود را بیان کنید.",
        "approval_pending": "درخواست شما برای تأیید ارسال شد. لطفاً منتظر بمانید تا ادمین آن را بررسی کند. به شما اطلاع داده خواهد شد.",
        "approval_success": "✅ شما تأیید شدید! به شهر کریمسون خوش آمدید. بیایید شخصیت خود را بسازیم.",
        "voice_already_submitted": "شما قبلاً یک پیام صوتی برای تأیید ارسال کرده‌اید.",
        "welcome_back": "خوش برگشتی، {name}. شهر منتظر توست.",
        "language_set": "زبان به فارسی تغییر کرد.",
        "character_creation_name": "این شهر هنوز تو را نمی‌شناسد. به چه نامی شناخته خواهی شد؟",
        "character_creation_profession": "و حرفه‌ات چیست؟ چگونه در این دنیا راه خود را پیدا کرده‌ای؟",
        "prof_hustler": "کلاهبردار خیابانی", "prof_intellectual": "روشنفکر", "prof_charmer": "جذاب و دلربا",
        "character_creation_complete": "بسیار خب، {name}. داستان تو در شهر کریمسون اکنون آغاز می‌شود.",
        "main_menu_prompt": "حرکت بعدی‌ات چیست؟",
        "menu_look": "🔎 اطراف را نگاه کن", "menu_move": "🗺️ حرکت کن", "menu_profile": "👤 پروفایل", "menu_language": "🌐 زبان", "menu_inventory": "🎒 کوله‌پشتی",
        "profile_view": "👤 *پروفایل*\n\n*نام:* {name}\n*حرفه:* {profession}\n*وضعیت VIP:* {vip_status}\n\n*پول:* {currency} CC\n\n*آمار:*\n- جذابیت: {charm}\n- هوش: {intellect}\n- زرنگی خیابانی: {street_smarts}",
        "move_prompt": "کجا می‌خواهی بروی؟",
        "move_success": "به {location} رسیدی.",
        "back_button": "بازگشت",
        "places_in_district": "چند مکان جالب توجه می‌بینی:",
        "npcs_in_area": "افراد حاضر:",
        "talk_to": "صحبت با",
        "god_presence": "حضوری قدرتمند را حس می‌کنی. خدای این شهر اینجاست.",
        "inventory_empty": "جیب‌هایت خالی است.",
        "vip_status_yes": "بله", "vip_status_no": "خیر",
        "broadcast_header": "پیامی در سراسر شهر طنین‌انداز می‌شود:",
        "whisper_header": "صدایی مستقیماً در ذهن تو زمزمه می‌کند:"
    }
    with open('locales/fa.json', 'w', encoding='utf-8') as f: json.dump(fa_locale, f, indent=4, ensure_ascii=False)

    load_locales()
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Register Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    # Admin commands
    application.add_handler(CommandHandler("adminhelp", admin_help_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("playerinfo", player_info_command))
    application.add_handler(CommandHandler("setstat", set_stat_command))
    application.add_handler(CommandHandler("giveitem", give_item_command))
    application.add_handler(CommandHandler("givemoney", give_money_command))
    application.add_handler(CommandHandler("setvip", set_vip_command))
    application.add_handler(CommandHandler("teleport", teleport_command))
    application.add_handler(CommandHandler("whisper", whisper_command))

    # Message and Voice handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))

    # Callback handler for all buttons
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
