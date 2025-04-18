import asyncio
import random
import string
from pyrogram import Client, filters, enums
from pyrogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "7204884576:AAGLHvP_ALG_uWVG8YpFxRCvEDq3QXk9Kjw"
API_ID = 24360857
API_HASH = "0924b59c45bf69cdfafd14188fb1b778"
OWNER_IDS = [5891854177, 6611564855]

# Channel information
STORAGE_CHANNEL_ID = -1002585582507  # Your private channel for file storage
REQUIRED_CHANNEL = "@solo_leveling_manhwa_tamil"  # Only one required channel
REQUIRED_CHANNEL_LINK = "https://t.me/solo_leveling_manhwa_tamil"

app = Client("tdafilesharebot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# User state management (temporary, only for active sessions)
user_states = {}

def generate_unique_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

def get_media_info(message):
    media_info = None
    caption = message.caption if message.caption else None
    
    for media_type in ["document", "video", "photo", "audio"]:
        if media := getattr(message, media_type, None):
            media_info = {
                "file_id": media.file_id,
                "file_name": getattr(media, "file_name", f"{media_type}_{media.file_id[:6]}"),
                "file_type": media_type,
                "caption": caption
            }
            break
    
    return media_info

async def check_channel_membership(client, user_id, channel):
    try:
        member = await client.get_chat_member(channel, user_id)
        return member.status not in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]
    except Exception as e:
        logger.error(f"Error checking channel {channel}: {e}")
        return False

async def send_individual_file(client, chat_id, files):
    for file in files:
        try:
            if file["file_type"] == "text":
                await client.send_message(chat_id, file["file_name"])
            else:
                if file["file_type"] == "photo":
                    await client.send_photo(
                        chat_id=chat_id,
                        photo=file["file_id"],
                        caption=file.get("caption", None)
                    )
                elif file["file_type"] == "video":
                    await client.send_video(
                        chat_id=chat_id,
                        video=file["file_id"],
                        caption=file.get("caption", None)
                    )
                elif file["file_type"] == "document":
                    await client.send_document(
                        chat_id=chat_id,
                        document=file["file_id"],
                        caption=file.get("caption", None)
                    )
                elif file["file_type"] == "audio":
                    await client.send_audio(
                        chat_id=chat_id,
                        audio=file["file_id"],
                        caption=file.get("caption", None)
                    )
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await client.send_message(chat_id, f"Error sending file: {e}")

async def store_file_data(client, file_data):
    """Store file data permanently in the storage channel"""
    try:
        unique_id = generate_unique_id()
        # Store the complete file data as JSON in the channel
        storage_message = await client.send_message(
            STORAGE_CHANNEL_ID,
            f"FileID:{unique_id}\nFileData:{json.dumps(file_data)}"
        )
        # Store message ID for faster retrieval
        file_data["storage_message_id"] = storage_message.id
        return unique_id
    except Exception as e:
        logger.error(f"Error storing file data: {e}")
        return None

async def get_file_data(client, unique_id):
    """Retrieve file data from the storage channel with multiple fallback methods"""
    try:
        # Method 1: Try direct message access if we have message ID
        async for message in client.search_messages(
            STORAGE_CHANNEL_ID,
            query=f"FileID:{unique_id}",
            limit=1
        ):
            if message.text and message.text.startswith(f"FileID:{unique_id}"):
                try:
                    file_data_str = message.text.split("FileData:")[1]
                    file_data = json.loads(file_data_str)
                    file_data["storage_message_id"] = message.id  # Update with current message ID
                    return file_data
                except (IndexError, json.JSONDecodeError) as e:
                    logger.error(f"Error parsing file data: {e}")
                    continue
        
        # Method 2: Fallback to scanning recent messages
        async for message in client.get_chat_history(STORAGE_CHANNEL_ID, limit=100):
            if message.text and message.text.startswith(f"FileID:{unique_id}"):
                try:
                    file_data_str = message.text.split("FileData:")[1]
                    file_data = json.loads(file_data_str)
                    file_data["storage_message_id"] = message.id  # Update with current message ID
                    return file_data
                except (IndexError, json.JSONDecodeError) as e:
                    logger.error(f"Error parsing file data: {e}")
                    continue
        
        return None
    except Exception as e:
        logger.error(f"Error retrieving file data: {e}")
        return None

# Command Handlers
@app.on_message(filters.command("start"))
async def start(client, message):
    user = message.from_user
    has_joined = await check_channel_membership(client, user.id, REQUIRED_CHANNEL)
    
    image_id = "AgACAgUAAxkBAAMHZ_Kk0DMGWHUhuZrsCD58xrl1pf4AAjPCMRuztpBXjOL21dg7BiUACAEAAwIAA3gABx4E"
    
    join_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 JOIN CHANNEL", url=REQUIRED_CHANNEL_LINK)]
    ])
    
    if len(message.command) == 1:
        if not has_joined:
            caption = f"""
*Hᴇʟʟᴏ {user.first_name}*

*You must join our channel to get anime files*

*Please join the channel below:*
            """
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_id,
                caption=caption,
                reply_markup=join_button,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            caption = f"""
*Hᴇʟʟᴏ {user.first_name}*

*I Aᴍ Aɴɪᴍᴇ Bᴏᴛ I Wɪʟʟ Gɪᴠᴇ Yᴏᴜ Aɴɪᴍᴇ Fɪʟᴇs*
            """
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_id,
                caption=caption,
                parse_mode=enums.ParseMode.MARKDOWN
            )
    
    elif len(message.command) > 1:
        unique_id = message.command[1]
        
        if not has_joined:
            caption = f"""
*Hᴇʟʟᴏ {user.first_name}*

*You must join our channel to get this file*

*Please join the channel below:*
            """
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 JOIN CHANNEL", url=REQUIRED_CHANNEL_LINK)],
                [InlineKeyboardButton("📥 GET FILE", callback_data=f"getfile_{unique_id}")]
            ])
            
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_id,
                caption=caption,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            file_data = await get_file_data(client, unique_id)
            if file_data:
                await send_individual_file(client, message.chat.id, file_data["files"])
            else:
                await message.reply("❌ File not found! Please contact admin if this persists.")

@app.on_callback_query(filters.regex("^getfile_"))
async def handle_getfile(client, callback_query):
    user_id = callback_query.from_user.id
    unique_id = callback_query.data.split("_")[1]
    
    has_joined = await check_channel_membership(client, user_id, REQUIRED_CHANNEL)
    
    if has_joined:
        file_data = await get_file_data(client, unique_id)
        if file_data:
            await callback_query.message.delete()
            await send_individual_file(client, callback_query.message.chat.id, file_data["files"])
        else:
            await callback_query.answer("❌ File not found! Please contact admin.", show_alert=True)
    else:
        await callback_query.answer("❌ Please join our channel first!", show_alert=True)

# [Rest of your existing handlers remain the same...]

async def set_commands():
    await app.set_bot_commands([
        BotCommand("start", "Show start message"),
        BotCommand("batch", "Upload files (Owner)")
    ])

app.start()
print("Bot started!")
app.loop.run_until_complete(set_commands())

try:
    asyncio.get_event_loop().run_forever()
except KeyboardInterrupt:
    print("Bot stopped!")
