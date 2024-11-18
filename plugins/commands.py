import os
import logging
import random
import asyncio
import json
import base64
from urllib.parse import quote_plus
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from pyrogram.errors import ChatAdminRequired, FloodWait
from validators import domain
from config import *
from Script import script
from plugins.dbusers import db
from plugins.users_api import get_user, update_user_info
from plugins.database import get_file_details
from utils import verify_user, check_token, check_verification, get_token
from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size

logger = logging.getLogger(__name__)
BATCH_FILES = {}

def get_readable_size(size):
    """Convert size to a readable format"""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} {units[-1]}"

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    user_id = message.from_user.id
    username = (await client.get_me()).username

    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)
        await client.send_message(
            LOG_CHANNEL,
            script.LOG_TEXT.format(user_id, message.from_user.mention),
        )

    if len(message.command) != 2:
        buttons = [
            [
                InlineKeyboardButton('💝 Subscribe YouTube', url='https://youtube.com/@Tech_VJ'),
            ],
            [
                InlineKeyboardButton('🔍 Support Group', url='https://t.me/vj_bot_disscussion'),
                InlineKeyboardButton('🤖 Update Channel', url='https://t.me/vj_botz'),
            ],
            [
                InlineKeyboardButton('💁‍♀️ Help', callback_data='help'),
                InlineKeyboardButton('😊 About', callback_data='about'),
            ],
        ]
        if CLONE_MODE:
            buttons.append([InlineKeyboardButton('🤖 Create Your Bot', callback_data='clone')])

        reply_markup = InlineKeyboardMarkup(buttons)
        bot_mention = (await client.get_me()).mention

        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, bot_mention),
            reply_markup=reply_markup,
        )
        return

    command_data = message.command[1]
    if command_data.startswith("verify"):
        await handle_verification(client, message, command_data)
    elif command_data.startswith("BATCH"):
        await handle_batch(client, message, command_data)
    else:
        await handle_file_request(client, message, command_data)

async def handle_verification(client, message, command_data):
    user_id, token = command_data.split("-", 2)[1:]
    if str(message.from_user.id) != str(user_id):
        await message.reply_text("<b>Invalid or Expired Link!</b>")
        return

    is_valid = await check_token(client, user_id, token)
    if is_valid:
        await message.reply_text(
            f"<b>Hey {message.from_user.mention}, verification successful!</b>"
        )
        await verify_user(client, user_id, token)
    else:
        await message.reply_text("<b>Invalid or Expired Link!</b>")

async def handle_batch(client, message, command_data):
    batch_id = command_data.split("-", 1)[1]
    user_id = message.from_user.id

    if VERIFY_MODE and not await check_verification(client, user_id):
        verify_button = [
            [
                InlineKeyboardButton("Verify", url=await get_token(client, user_id, f"https://telegram.me/{(await client.get_me()).username}?start=")),
            ],
            [InlineKeyboardButton("Verification Guide", url=VERIFY_TUTORIAL)],
        ]
        await message.reply_text(
            "<b>Please verify to continue.</b>",
            reply_markup=InlineKeyboardMarkup(verify_button),
        )
        return

    status_message = await message.reply("**🔺 Please wait...**")
    batch_files = BATCH_FILES.get(batch_id)

    if not batch_files:
        file = await client.download_media(batch_id)
        try:
            with open(file) as file_data:
                batch_files = json.loads(file_data.read())
        except Exception:
            await status_message.edit("Failed to load batch files.")
            return

        os.remove(file)
        BATCH_FILES[batch_id] = batch_files

    for batch_file in batch_files:
        await process_file(client, message, batch_file)

    await status_message.delete()

async def handle_file_request(client, message, command_data):
    file_details = await get_file_details(command_data)
    if not file_details:
        await message.reply_text("No such file exists.")
        return

    file_info = file_details[0]
    caption = CUSTOM_FILE_CAPTION.format(
        file_name=file_info.file_name or "",
        file_size=get_readable_size(file_info.file_size) or "",
        file_caption=file_info.caption or "",
    )
    await client.send_cached_media(
        chat_id=message.chat.id,
        file_id=file_info.file_id,
        caption=caption,
    )

async def process_file(client, message, file):
    file_size = get_readable_size(int(file.get("size", 0)))
    file_caption = file.get("caption", "")
    file_title = file.get("title", "Unknown")

    caption = BATCH_FILE_CAPTION.format(
        file_name=file_title,
        file_size=file_size,
        file_caption=file_caption,
    )

    await client.send_cached_media(
        chat_id=message.chat.id,
        file_id=file.get("file_id"),
        caption=caption,
    )
