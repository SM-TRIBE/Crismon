// index.js
// Main file for the Crimson City Chronicles Telegram Bot

import TelegramBot from 'node-telegram-bot-api';
import dotenv from 'dotenv';
import { I18n } from 'i18n';
import path from 'path';
import fs from 'fs';

// --- Basic Setup ---
dotenv.config();

// --- Configuration ---
// IMPORTANT: These should be set as environment variables on your hosting platform (like Render).
const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN || 'YOUR_TELEGRAM_BOT_TOKEN';
const ADMIN_USER_ID = parseInt(process.env.ADMIN_USER_ID || '123456789', 10);

// --- Localization (i18n) Setup ---
const i18n = new I18n({
    locales: ['en', 'fa'],
    directory: path.join(process.cwd(), 'locales'),
    defaultLocale: 'en',
    objectNotation: true,
});

// --- Database Management ---
const DB_FILE = './data/players.json';

// Ensure data directory exists
if (!fs.existsSync('./data')) {
    fs.mkdirSync('./data');
}

const loadPlayerData = () => {
    if (!fs.existsSync(DB_FILE)) {
        return {};
    }
    try {
        const data = fs.readFileSync(DB_FILE, 'utf-8');
        return JSON.parse(data);
    } catch (error) {
        console.error("Error loading player data:", error);
        return {};
    }
};

const savePlayerData = (data) => {
    try {
        fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
    } catch (error) {
        console.error("Error saving player data:", error);
    }
};

let players = loadPlayerData();

// --- Game World Definition ---
const GAME_MAP = {
    downtown: {
        connections: ["neon_district", "industrial_zone", "the_plaza"],
        locations: ["the_onyx_bar", "vip_lounge"]
    },
    neon_district: {
        connections: ["downtown"],
        locations: []
    },
    industrial_zone: {
        connections: ["downtown"],
        locations: []
    },
    the_plaza: {
        connections: ["downtown"],
        locations: []
    }
};

const LOCATIONS = {
    the_onyx_bar: {
        npcs: ["slick_the_bartender"]
    },
    vip_lounge: {
        npcs: [],
        requires_vip: true
    }
};

// --- Bot Initialization ---
const bot = new TelegramBot(TELEGRAM_TOKEN, { polling: true });
console.log("Crimson City Bot is running...");

// --- Helper Functions ---
const getPlayerState = (userId) => {
    const id = String(userId);
    if (!players[id]) {
        players[id] = {
            lang: 'en',
            approved: false,
            pending_approval: false,
            voice_file_id: null,
            character_created: false,
            name: null,
            profession: null,
            location: 'downtown',
            inventory: [],
            stats: { charm: 1, intellect: 1, street_smarts: 1 },
            currency: 100,
            is_vip: false,
            next_step: null,
        };
    }
    return players[id];
};

const updatePlayerState = (userId, state) => {
    players[String(userId)] = state;
    savePlayerData(players);
};

const isAdmin = (userId) => userId === ADMIN_USER_ID;

// --- Core Bot Logic ---

// '/start' command handler
bot.onText(/\/start/, (msg) => {
    const userId = msg.from.id;
    const playerState = getPlayerState(userId);
    const __ = (key, ...args) => i18n.__({ phrase: key, locale: playerState.lang }, ...args);

    if (playerState.approved) {
        if (playerState.character_created) {
            bot.sendMessage(userId, __("welcome_back", { name: playerState.name }));
            showMainMenu(userId);
        } else {
            characterCreationPrompt(userId);
        }
    } else if (playerState.pending_approval) {
        bot.sendMessage(userId, __("approval_pending"));
    } else {
        const opts = {
            reply_markup: {
                inline_keyboard: [
                    [{ text: "English", callback_data: 'set_lang_en' }],
                    [{ text: "فارسی (Persian)", callback_data: 'set_lang_fa' }]
                ]
            }
        };
        bot.sendMessage(userId, "Welcome to Crimson City. Please choose your language.\n\nبه شهر کریمسون خوش آمدید. لطفاً زبان خود را انتخاب کنید.", opts);
    }
});

// Voice message handler for verification
bot.on('voice', (msg) => {
    const userId = msg.from.id;
    const playerState = getPlayerState(userId);
    const __ = (key) => i18n.__({ phrase: key, locale: playerState.lang });

    if (playerState.next_step !== 'submit_voice' || playerState.approved || playerState.pending_approval) {
        bot.sendMessage(userId, __("voice_already_submitted"));
        return;
    }

    playerState.pending_approval = true;
    playerState.voice_file_id = msg.voice.file_id;
    playerState.next_step = null;
    updatePlayerState(userId, playerState);

    bot.sendMessage(userId, __("approval_pending"));

    const approvalKeyboard = {
        inline_keyboard: [
            [{ text: "✅ Approve", callback_data: `approve_${userId}` }],
            [{ text: "❌ Reject", callback_data: `reject_${userId}` }]
        ]
    };
    bot.sendMessage(ADMIN_USER_ID, `New user for approval: ${msg.from.first_name} ${msg.from.last_name || ''} (ID: ${userId})`);
    bot.sendVoice(ADMIN_USER_ID, playerState.voice_file_id, { reply_markup: approvalKeyboard });
});

// Text message handler for character creation
bot.on('message', (msg) => {
    // Ignore commands, voice, etc.
    if (msg.text.startsWith('/') || msg.voice) return;

    const userId = msg.from.id;
    const playerState = getPlayerState(userId);

    if (playerState.next_step === 'create_character_name') {
        playerState.name = msg.text;
        playerState.next_step = null;
        updatePlayerState(userId, playerState);

        const __ = (key) => i18n.__({ phrase: key, locale: playerState.lang });
        const opts = {
            reply_markup: {
                inline_keyboard: [
                    [{ text: __("prof.hustler"), callback_data: 'set_prof_hustler' }],
                    [{ text: __("prof.intellectual"), callback_data: 'set_prof_intellectual' }],
                    [{ text: __("prof.charmer"), callback_data: 'set_prof_charmer' }],
                ]
            }
        };
        bot.sendMessage(userId, __("character_creation_profession"), opts);
    }
});

// Callback query handler for all button presses
bot.on('callback_query', (callbackQuery) => {
    const msg = callbackQuery.message;
    const userId = callbackQuery.from.id;
    const data = callbackQuery.data;

    bot.answerCallbackQuery(callbackQuery.id); // Acknowledge the press

    const playerState = getPlayerState(userId);
    const __ = (key, ...args) => i18n.__({ phrase: key, locale: playerState.lang }, ...args);

    // --- Admin Approval Flow ---
    if (data.startsWith('approve_') || data.startsWith('reject_')) {
        if (!isAdmin(userId)) return;
        const [action, targetUserIdStr] = data.split('_');
        const targetUserId = parseInt(targetUserIdStr, 10);
        const targetPlayerState = getPlayerState(targetUserId);
        const target__ = (key) => i18n.__({ phrase: key, locale: targetPlayerState.lang });

        if (action === 'approve') {
            targetPlayerState.approved = true;
            targetPlayerState.pending_approval = false;
            updatePlayerState(targetUserId, targetPlayerState);
            bot.editMessageReplyMarkup({ inline_keyboard: [] }, { chat_id: msg.chat.id, message_id: msg.message_id });
            bot.sendMessage(ADMIN_USER_ID, `User ${targetUserId} approved.`);
            bot.sendMessage(targetUserId, target__("approval_success"));
            characterCreationPrompt(targetUserId);
        } else { // Reject
            delete players[String(targetUserId)];
            savePlayerData(players);
            bot.editMessageReplyMarkup({ inline_keyboard: [] }, { chat_id: msg.chat.id, message_id: msg.message_id });
            bot.sendMessage(ADMIN_USER_ID, `User ${targetUserId} rejected and data deleted.`);
        }
        return;
    }
    
    // --- Language Selection ---
    if (data.startsWith('set_lang_')) {
        playerState.lang = data.split('_')[2];
        playerState.next_step = 'submit_voice';
        updatePlayerState(userId, playerState);
        bot.editMessageText(__("voice_prompt"), { chat_id: msg.chat.id, message_id: msg.message_id });
        return;
    }

    // --- Character Creation ---
    if (data.startsWith('set_prof_')) {
        playerState.profession = data.split('_')[2];
        if (playerState.profession === 'hustler') playerState.stats.street_smarts += 2;
        else if (playerState.profession === 'intellectual') playerState.stats.intellect += 2;
        else if (playerState.profession === 'charmer') playerState.stats.charm += 2;
        
        playerState.character_created = true;
        updatePlayerState(userId, playerState);
        bot.editMessageText(__("character_creation_complete", { name: playerState.name }), { chat_id: msg.chat.id, message_id: msg.message_id });
        showMainMenu(userId);
        return;
    }

    // --- Main Menu Navigation ---
    switch (data) {
        case 'main_look':
            handleLook(userId, msg);
            break;
        case 'main_move':
            handleMove(userId, msg);
            break;
        case 'main_profile':
            handleProfile(userId, msg);
            break;
        case 'main_inventory':
            handleInventory(userId, msg);
            break;
        case 'main_language':
            // Re-show language selection
            const opts = {
                chat_id: msg.chat.id,
                message_id: msg.message_id,
                reply_markup: {
                    inline_keyboard: [
                        [{ text: "English", callback_data: 'set_lang_en' }],
                        [{ text: "فارسی (Persian)", callback_data: 'set_lang_fa' }]
                    ]
                }
            };
            bot.editMessageText("Choose your language / زبان خود را انتخاب کنید", opts);
            break;
        case 'main_back':
            showMainMenu(userId, msg.chat.id, msg.message_id);
            break;
    }

    // --- Movement & Interaction ---
    if (data.startsWith('move_to_')) {
        const destinationKey = data.replace('move_to_', '');
        playerState.location = destinationKey;
        updatePlayerState(userId, playerState);
        const locationName = __( `map.${destinationKey}.name`);
        bot.editMessageText(__("move_success", { location: locationName }), { chat_id: msg.chat.id, message_id: msg.message_id });
        showMainMenu(userId);
    }
    
    if (data.startsWith('talk_')) {
        const npcKey = data.replace('talk_', '');
        const dialogue = __(`npcs.${npcKey}.dialogue`);
        bot.editMessageText(`_${dialogue}_`, { chat_id: msg.chat.id, message_id: msg.message_id, parse_mode: 'Markdown' });
        setTimeout(() => showMainMenu(userId, msg.chat.id, msg.message_id), 2000); // Go back to menu after a delay
    }
});


// --- Menu Handlers ---
const showMainMenu = (userId, chatId, messageId) => {
    const playerState = getPlayerState(userId);
    const __ = (key) => i18n.__({ phrase: key, locale: playerState.lang });

    const keyboard = {
        inline_keyboard: [
            [{ text: __("menu.look"), callback_data: 'main_look' }],
            [{ text: __("menu.move"), callback_data: 'main_move' }],
            [{ text: __("menu.profile"), callback_data: 'main_profile' }],
            [{ text: __("menu.inventory"), callback_data: 'main_inventory' }],
            [{ text: __("menu.language"), callback_data: 'main_language' }]
        ]
    };

    const text = __("main_menu_prompt");

    if (chatId && messageId) {
        bot.editMessageText(text, { chat_id: chatId, message_id: messageId, reply_markup: keyboard });
    } else {
        bot.sendMessage(userId, text, { reply_markup: keyboard });
    }
};

const characterCreationPrompt = (userId) => {
    const playerState = getPlayerState(userId);
    playerState.next_step = 'create_character_name';
    updatePlayerState(userId, playerState);
    const __ = (key) => i18n.__({ phrase: key, locale: playerState.lang });
    bot.sendMessage(userId, __("character_creation_name"));
};

const handleLook = (userId, msg) => {
    const playerState = getPlayerState(userId);
    const __ = (key, ...args) => i18n.__({ phrase: key, locale: playerState.lang }, ...args);
    const currentLocationKey = playerState.location;
    const locationInfo = GAME_MAP[currentLocationKey];

    let text = `📍 *${__(`map.${currentLocationKey}.name`)}*\n\n${__(`map.${currentLocationKey}.description`)}`;

    const adminState = getPlayerState(ADMIN_USER_ID);
    if (adminState.location === currentLocationKey && !isAdmin(userId)) {
        text += `\n\n_${__("god_presence")}_`;
    }

    let keyboard = [[{ text: `« ${__("back_button")}`, callback_data: 'main_back' }]];
    
    if (locationInfo.locations && locationInfo.locations.length > 0) {
        text += `\n\n${__("places_in_district")}:`;
        locationInfo.locations.forEach(locKey => {
            const locData = LOCATIONS[locKey];
            if (locData.requires_vip && !playerState.is_vip) return;
            text += `\n- ${__(`locations.${locKey}.name`)}`;
        });
    }

    const currentFullLocation = LOCATIONS[currentLocationKey];
    if (currentFullLocation && currentFullLocation.npcs && currentFullLocation.npcs.length > 0) {
        text += `\n\n${__("npcs_in_area")}:`;
        currentFullLocation.npcs.forEach(npcKey => {
            const npcName = __(`npcs.${npcKey}.name`);
            keyboard.unshift([{ text: `🗣️ ${__("talk_to")} ${npcName}`, callback_data: `talk_${npcKey}` }]);
        });
    }

    bot.editMessageText(text, { chat_id: msg.chat.id, message_id: msg.message_id, parse_mode: 'Markdown', reply_markup: { inline_keyboard: keyboard } });
};

const handleMove = (userId, msg) => {
    const playerState = getPlayerState(userId);
    const __ = (key) => i18n.__({ phrase: key, locale: playerState.lang });
    const connections = GAME_MAP[playerState.location].connections;

    const keyboard = connections.map(connKey => ([{
        text: __(`map.${connKey}.name`),
        callback_data: `move_to_${connKey}`
    }]));

    keyboard.push([{ text: `« ${__("back_button")}`, callback_data: 'main_back' }]);
    bot.editMessageText(__("move_prompt"), { chat_id: msg.chat.id, message_id: msg.message_id, reply_markup: { inline_keyboard: keyboard } });
};

const handleProfile = (userId, msg) => {
    const playerState = getPlayerState(userId);
    const __ = (key, ...args) => i18n.__({ phrase: key, locale: playerState.lang }, ...args);

    const profileText = __("profile_view", {
        name: playerState.name,
        profession: __(`prof.${playerState.profession}`),
        vip_status: playerState.is_vip ? __("vip_status.yes") : __("vip_status.no"),
        currency: playerState.currency,
        charm: playerState.stats.charm,
        intellect: playerState.stats.intellect,
        street_smarts: playerState.stats.street_smarts
    });
    bot.editMessageText(profileText, { chat_id: msg.chat.id, message_id: msg.message_id, parse_mode: 'Markdown' });
    setTimeout(() => showMainMenu(userId, msg.chat.id, msg.message_id), 4000);
};

const handleInventory = (userId, msg) => {
    const playerState = getPlayerState(userId);
    const __ = (key) => i18n.__({ phrase: key, locale: playerState.lang });
    let text;
    if (playerState.inventory.length === 0) {
        text = `_${__("inventory_empty")}_`;
    } else {
        text = `*${__("menu.inventory")}*\n` + playerState.inventory.map(item => `- ${item}`).join('\n');
    }
    bot.editMessageText(text, { chat_id: msg.chat.id, message_id: msg.message_id, parse_mode: 'Markdown' });
    setTimeout(() => showMainMenu(userId, msg.chat.id, msg.message_id), 3000);
};

// --- Admin Commands ---
const adminCommands = {
    '/adminhelp': (msg) => {
        const helpText = `
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
        `;
        bot.sendMessage(msg.chat.id, helpText, { parse_mode: 'Markdown' });
    },
    '/broadcast': (msg, match) => {
        const message = match[1];
        if (!message) {
            bot.sendMessage(msg.chat.id, "Usage: /broadcast <message>");
            return;
        }
        let count = 0;
        Object.entries(players).forEach(([id, pData]) => {
            if (pData.approved) {
                const p_ = (key) => i18n.__({ phrase: key, locale: pData.lang });
                bot.sendMessage(id, `${p_("broadcast_header")}\n\n${message}`).catch(err => console.error(`Failed to broadcast to ${id}: ${err.message}`));
                count++;
            }
        });
        bot.sendMessage(msg.chat.id, `Broadcast sent to ${count} players.`);
    },
    '/playerinfo': (msg, match) => {
        const targetId = match[1];
        if (!targetId) {
            bot.sendMessage(msg.chat.id, "Usage: /playerinfo <user_id>");
            return;
        }
        const playerData = players[targetId];
        if (!playerData) {
            bot.sendMessage(msg.chat.id, `Player ${targetId} not found.`);
            return;
        }
        const infoText = `<code>${JSON.stringify(playerData, null, 2)}</code>`;
        bot.sendMessage(msg.chat.id, infoText, { parse_mode: 'HTML' });
    },
    '/setstat': (msg, match) => {
        const [, targetId, stat, value] = match;
        if (!targetId || !stat || !value) {
            bot.sendMessage(msg.chat.id, "Usage: /setstat <id> <stat> <value>");
            return;
        }
        const pState = players[targetId];
        if (!pState) {
            bot.sendMessage(msg.chat.id, `Player ${targetId} not found.`);
            return;
        }
        if (!['charm', 'intellect', 'street_smarts'].includes(stat.toLowerCase())) {
            bot.sendMessage(msg.chat.id, "Invalid stat. Use: charm, intellect, street_smarts.");
            return;
        }
        pState.stats[stat.toLowerCase()] = parseInt(value, 10);
        updatePlayerState(targetId, pState);
        bot.sendMessage(msg.chat.id, `Set ${stat} to ${value} for player ${targetId}.`);
    },
    '/giveitem': (msg, match) => {
        const [, targetId, ...itemNameParts] = match.input.split(' ');
        const itemName = itemNameParts.join(' ');
        if (!targetId || !itemName) {
            bot.sendMessage(msg.chat.id, "Usage: /giveitem <id> <item name>");
            return;
        }
        const pState = players[targetId];
        if (!pState) {
            bot.sendMessage(msg.chat.id, `Player ${targetId} not found.`);
            return;
        }
        pState.inventory.push(itemName);
        updatePlayerState(targetId, pState);
        bot.sendMessage(msg.chat.id, `Gave '${itemName}' to player ${targetId}.`);
    },
    '/givemoney': (msg, match) => {
        const [, targetId, amount] = match;
        if (!targetId || !amount) {
            bot.sendMessage(msg.chat.id, "Usage: /givemoney <id> <amount>");
            return;
        }
        const pState = players[targetId];
        if (!pState) {
            bot.sendMessage(msg.chat.id, `Player ${targetId} not found.`);
            return;
        }
        pState.currency += parseInt(amount, 10);
        updatePlayerState(targetId, pState);
        bot.sendMessage(msg.chat.id, `Gave ${amount} CC to player ${targetId}. New balance: ${pState.currency}.`);
    },
    '/setvip': (msg, match) => {
        const [, targetId, status] = match;
        if (!targetId || !status || !['on', 'off'].includes(status.toLowerCase())) {
            bot.sendMessage(msg.chat.id, "Usage: /setvip <id> <on|off>");
            return;
        }
        const pState = players[targetId];
        if (!pState) {
            bot.sendMessage(msg.chat.id, `Player ${targetId} not found.`);
            return;
        }
        pState.is_vip = status.toLowerCase() === 'on';
        updatePlayerState(targetId, pState);
        bot.sendMessage(msg.chat.id, `Set VIP status for player ${targetId} to ${status.toUpperCase()}.`);
    },
    '/teleport': (msg, match) => {
        const [, targetId, locKey] = match;
        if (!targetId || !locKey) {
            bot.sendMessage(msg.chat.id, "Usage: /teleport <id> <location_key>");
            return;
        }
        if (!GAME_MAP[locKey]) {
            bot.sendMessage(msg.chat.id, `Invalid location key. Valid keys: ${Object.keys(GAME_MAP).join(', ')}`);
            return;
        }
        const pState = players[targetId];
        if (!pState) {
            bot.sendMessage(msg.chat.id, `Player ${targetId} not found.`);
            return;
        }
        pState.location = locKey;
        updatePlayerState(targetId, pState);
        bot.sendMessage(msg.chat.id, `Teleported player ${targetId} to ${locKey}.`);
    },
    '/whisper': (msg, match) => {
        const [, targetId, ...messageParts] = match.input.split(' ');
        const message = messageParts.join(' ');
        if (!targetId || !message) {
            bot.sendMessage(msg.chat.id, "Usage: /whisper <id> <message>");
            return;
        }
        const pState = players[targetId];
        if (!pState) {
            bot.sendMessage(msg.chat.id, `Player ${targetId} not found.`);
            return;
        }
        const p_ = (key) => i18n.__({ phrase: key, locale: pState.lang });
        bot.sendMessage(targetId, `${p_("whisper_header")}\n\n_${message}_`, { parse_mode: 'Markdown' })
            .then(() => bot.sendMessage(msg.chat.id, `Whisper sent to ${targetId}.`))
            .catch(err => bot.sendMessage(msg.chat.id, `Could not send whisper: ${err.message}`));
    }
};

// Register admin command handlers
Object.entries(adminCommands).forEach(([command, handler]) => {
    const regex = new RegExp(`^${command}(?: (.*))?$`);
    bot.onText(regex, (msg, match) => {
        if (isAdmin(msg.from.id)) {
            handler(msg, match);
        } else {
            bot.sendMessage(msg.chat.id, "You are not worthy.");
        }
    });
});
