import asyncio
import random
import string
import json
import os
import firebase_admin
from firebase_admin import credentials, db
from pyrogram import Client, filters, enums
from pyrogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import logging
from datetime import datetime
import requests
import urllib.parse

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
OWNER_IDS = [5891854177]
SHORTENER_API = "d2d9a81c236ad681edfbb260cb315628df46cc38"
SHORTENER_URL = "https://api.gplinks.com/api"

# Channel information (simplified to just one channel)
CHANNEL_USERNAME = "@solo_leveling_manhwa_tamil"
CHANNEL_ID = -1002662584633
CHANNEL_LINK = "https://t.me/solo_leveling_manhwa_tamil"
SOURCE_CHANNEL = "https://t.me/mangas_manhwas_tamil"

# Initialize Firebase
try:
    firebase_config = os.getenv("FIREBASE_CONFIG")
    if not firebase_config:
        raise ValueError("FIREBASE_CONFIG environment variable is not set!")
    
    cred = credentials.Certificate(json.loads(firebase_config))
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://my-telegram-bot-127da-default-rtdb.firebaseio.com"
    })
    logger.info("Firebase initialized successfully!")
except Exception as e:
    logger.error(f"Firebase initialization error: {e}")
    raise

app = Client("tdafilesharebot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# User state management
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

async def store_user_info(user_id, username, first_name, last_name):
    try:
        db.reference(f"users/{user_id}").set({
            "username": username or "",
            "first_name": first_name or "",
            "last_name": last_name or "",
            "last_seen": datetime.now().isoformat(),
            "registered_at": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error storing user info: {e}")

async def check_channel_membership(client, user_id, channel):
    try:
        member = await client.get_chat_member(channel, user_id)
        return member.status not in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]
    except Exception as e:
        logger.error(f"Error checking channel {channel}: {e}")
        return False

async def is_user_joined(client, user_id):
    try:
        return await check_channel_membership(client, user_id, CHANNEL_ID)
    except Exception as e:
        logger.error(f"Error in is_user_joined: {e}")
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

def shorten_url(long_url):
    try:
        encoded_url = urllib.parse.quote_plus(long_url)
        params = {
            'api': SHORTENER_API,
            'url': encoded_url,
            'format': 'json'
        }
        response = requests.get(SHORTENER_URL, params=params, timeout=10)
        try:
            response_data = response.json()
            if response.status_code == 200 and response_data.get("status") == "success":
                return response_data.get("shortenedUrl")
            else:
                error_msg = response_data.get("message", "Unknown error from GPLinks")
                logger.error(f"GPLinks API error: {error_msg}")
                return None
        except ValueError:
            logger.error("GPLinks API returned invalid JSON response")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while shortening URL: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error shortening URL: {e}")
        return None
        
# Command Handlers
@app.on_message(filters.command("start"))
async def start(client, message):
    user = message.from_user
    await store_user_info(user.id, user.username, user.first_name, user.last_name)
    
    # Show "Please wait" message
    wait_msg = await message.reply("⏳ Please wait while we process your request...")
    
    has_joined = await is_user_joined(client, user.id)
    image_id = "AgACAgUAAxkBAAMHZ_Kk0DMGWHUhuZrsCD58xrl1pf4AAjPCMRuztpBXjOL21dg7BiUACAEAAwIAA3gABx4E"
    image_id1 = "AgACAgUAAxkBAAMHZ_Kk0DMGWHUhuZrsCD58xrl1pf4AAjPCMRuztpBXjOL21dg7BiUACAEAAwIAA3gABx4E"
    
    if len(message.command) == 1:
        if not has_joined:
            caption = f"""
*Hᴇʟʟᴏ {user.first_name}*

*You must join our channel to get anime files*

*Please join the channel below:*
            """
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 JOIN CHANNEL", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ I'VE JOINED", callback_data="check_join")]
            ])
            
            await wait_msg.delete()
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_id,
                caption=caption,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            caption = f"""
*Hᴇʟʟᴏ {user.first_name}*

*I Aᴍ File Sharing  Bᴏᴛ I Wɪʟʟ Gɪᴠᴇ Yᴏᴜ  Mangas and Manhwas Fɪʟᴇs Fʀᴏᴍ* [MAnga And  Manhwa Tamil ]({SOURCE_CHANNEL})
            """
            await wait_msg.delete()
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_id1,
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
                [InlineKeyboardButton("📢 JOIN CHANNEL", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ GET FILE", callback_data=f"getfile_{unique_id}")]
            ])
            
            await wait_msg.delete()
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_id,
                caption=caption,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            file_data = db.reference(f"files/{unique_id}").get()
            if file_data and not file_data.get("deleted"):
                await wait_msg.edit_text("⏳ Preparing your file, please wait...")
                await send_individual_file(client, message.chat.id, file_data["files"])
                await wait_msg.delete()
            else:
                await wait_msg.edit_text("❌ File not found or deleted!")

@app.on_callback_query(filters.regex("^check_join$"))
async def handle_check_join(client, callback_query):
    user_id = callback_query.from_user.id
    await callback_query.answer("⏳ Checking your channel status...")
    
    wait_msg = await callback_query.message.reply("⏳ Please wait while we verify your channel membership...")
    
    has_joined = await is_user_joined(client, user_id)
    
    if has_joined:
        await wait_msg.edit_text("✅ Thank you for joining! Now you can access all files.")
        await callback_query.message.delete()
        
        caption = f"""
*Hᴇʟʟᴏ {callback_query.from_user.first_name}*

*I Aᴍ Aɴɪᴍᴇ Bᴏᴛ I Wɪʟʟ Gɪᴠᴇ Yᴏᴜ Aɴɪᴍᴇ Fɪʟᴇs Fʀᴏᴍ* [Tᴀᴍɪʟ Dubbed Aɴɪᴍᴇ]({SOURCE_CHANNEL})
        """
        image_id = "AgACAgUAAxkBAAMMZ-liXpvWGCRtUVvzNSmdX62f0jkAAknIMRvOgUBX60loZgKrC-kACAEAAwIAA3gABx4E"
        
        await client.send_photo(
            chat_id=callback_query.message.chat.id,
            photo=image_id,
            caption=caption,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    else:
        await wait_msg.edit_text("❌ You haven't joined our channel yet. Please join first!")
    
    await asyncio.sleep(5)
    await wait_msg.delete()

@app.on_callback_query(filters.regex("^getfile_"))
async def handle_getfile(client, callback_query):
    user_id = callback_query.from_user.id
    unique_id = callback_query.data.split("_")[1]
    
    await callback_query.answer("⏳ Please wait while we check your access...")
    
    wait_msg = await callback_query.message.reply("⏳ Verifying your channel membership...")
    
    has_joined = await is_user_joined(client, user_id)
    
    if has_joined:
        file_data = db.reference(f"files/{unique_id}").get()
        if file_data and not file_data.get("deleted"):
            await wait_msg.edit_text("⏳ Preparing your file, please wait...")
            await callback_query.message.delete()
            await send_individual_file(client, callback_query.message.chat.id, file_data["files"])
        else:
            await wait_msg.edit_text("❌ File not found or deleted!")
    else:
        await wait_msg.edit_text("❌ Please join our channel first!")
    
    await asyncio.sleep(5)
    await wait_msg.delete()

# [Rest of the code remains the same as your original...]
# Only the channel-related parts were modified, other functions remain unchanged

@app.on_message(filters.command("batch") & filters.user(OWNER_IDS))
async def batch_command(client, message):
    user_id = message.from_user.id
    user_states[user_id] = {"mode": "batch", "files": []}
    await message.reply(
        "📤 *Batch Mode Activated!*\n\n"
        "Send me multiple files (documents, videos, photos, audio, or text).\n"
        "When finished, send /done to generate a link.\n"
        "To cancel, send /cancel.",
        parse_mode=enums.ParseMode.MARKDOWN
    )

@app.on_message(filters.private & ~filters.user(OWNER_IDS) & ~filters.command("start"))
async def reject_messages(client, message):
    await message.reply("❌ Don't Send Me Messages Directly. I'm Only a File Sharing Bot!")

@app.on_message(filters.command("broadcast") & filters.user(OWNER_IDS))
async def broadcast_command(client, message):
    user_id = message.from_user.id
    user_states[user_id] = {"mode": "broadcast", "content": []}
    await message.reply(
        "📢 *Broadcast Mode Activated!*\n\n"
        "Send me the message or media you want to broadcast to all users.\n"
        "When finished, send /done to send to all users.\n"
        "To cancel, send /cancel.",
        parse_mode=enums.ParseMode.MARKDOWN
    )

@app.on_message(filters.command("users") & filters.user(OWNER_IDS))
async def list_users(client, message):
    try:
        users_ref = db.reference("users")
        users = users_ref.get() or {}
        
        if not users:
            await message.reply("No users found in the database!")
            return
        
        response = "📊 *Registered Users*\n\n"
        for user_id, user_data in users.items():
            username = user_data.get('username', 'N/A')
            first_name = user_data.get('first_name', '')
            last_name = user_data.get('last_name', '')
            name = f"{first_name} {last_name}".strip()
            
            response += f"🆔: `{user_id}`\n"
            response += f"👤: {name}\n"
            response += f"📛: @{username}\n"
            response += "――――――――――――――――――\n"
        
        for i in range(0, len(response), 4096):
            part = response[i:i+4096]
            await message.reply(part, parse_mode=enums.ParseMode.MARKDOWN)
            
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        await message.reply(f"❌ Error listing users: {e}")

@app.on_message(filters.command("shortener") & filters.user(OWNER_IDS))
async def shortener_command(client, message):
    if len(message.command) < 2:
        await message.reply(
            "🔗 *URL Shortener*\n\n"
            "Usage: `/shortener <long_url>`\n"
            "Example: `/shortener https://example.com/very/long/url`\n\n"
            "Note: This uses GPLinks API to shorten URLs",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    
    long_url = ' '.join(message.command[1:])
    if not (long_url.startswith('http://') or long_url.startswith('https://')):
        await message.reply("❌ Please provide a valid URL starting with http:// or https://")
        return
    
    processing_msg = await message.reply("⏳ Shortening URL using GPLinks, please wait...")
    
    short_url = shorten_url(long_url)
    if short_url:
        await processing_msg.edit_text(
            f"✅ *URL Shortened Successfully!*\n\n"
            f"🔗 Original URL: `{long_url}`\n"
            f"🪄 Short URL: `{short_url}`\n\n"
            f"Click to copy: `{short_url}`",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    else:
        await processing_msg.edit_text("❌ Failed to shorten URL. Please try again later.")

@app.on_message(filters.command(["done", "cancel"]) & filters.user(OWNER_IDS))
async def handle_actions(client, message):
    user_id = message.from_user.id
    if user_id not in user_states:
        await message.reply("❌ No active operation to complete or cancel.")
        return

    state = user_states[user_id]
    action = message.command[0]

    if action == "done":
        if state["mode"] == "batch":
            if not state["files"]:
                await message.reply("❌ No files or text received! Batch canceled.")
                user_states.pop(user_id, None)
                return

            unique_id = generate_unique_id()
            file_data = {
                "files": state["files"],
                "uploaded_by": user_id,
                "deleted": False,
                "created_at": datetime.now().isoformat()
            }

            try:
                db.reference(f"files/{unique_id}").set(file_data)
            except Exception as e:
                await message.reply(f"❌ Error saving file: {e}")
                return

            bot_username = (await client.get_me()).username
            share_link = f"https://t.me/{bot_username}?start={unique_id}"
            
            short_link = shorten_url(share_link) or share_link
            
            await message.reply(
                f"✅ *Batch Upload Complete!*\n\n"
                f"🔗 Original Link: `{share_link}`\n"
                f"🪄 Short Link: `{short_link}`\n\n"
                f"📌 Files will be stored permanently until deleted.",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            user_states.pop(user_id, None)

        elif state["mode"] == "broadcast":
            if not state["content"]:
                await message.reply("❌ No content to broadcast! Operation canceled.")
                user_states.pop(user_id, None)
                return

            users_ref = db.reference("users")
            users = users_ref.get() or {}
            
            if not users:
                await message.reply("❌ No users to broadcast to!")
                user_states.pop(user_id, None)
                return
            
            total_users = len(users)
            success = 0
            failed = 0
            
            status_msg = await message.reply(f"📢 Starting broadcast to {total_users} users...")
            
            for user_id in users.keys():
                try:
                    for item in state["content"]:
                        if item["type"] == "text":
                            await client.send_message(int(user_id), item["content"])
                        else:
                            method = {
                                "document": client.send_document,
                                "video": client.send_video,
                                "photo": client.send_photo,
                                "audio": client.send_audio
                            }.get(item["type"])
                            if method:
                                await method(
                                    int(user_id),
                                    item["file_id"],
                                    caption=item.get("caption", None)
                                )
                    success += 1
                except Exception as e:
                    logger.error(f"Error broadcasting to {user_id}: {e}")
                    failed += 1
                await asyncio.sleep(0.5)
            
            await status_msg.edit_text(
                f"✅ Broadcast completed!\n\n"
                f"• Total users: {total_users}\n"
                f"• Successfully sent: {success}\n"
                f"• Failed: {failed}"
            )
            user_states.pop(user_id, None)
    
    elif action == "cancel":
        user_states.pop(user_id, None)
        await message.reply("❌ Operation canceled.")

@app.on_message(filters.private & (filters.media | filters.text) & filters.user(OWNER_IDS))
async def media_text_handler(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id, {})

    if not state:
        await message.reply("ℹ Please use /batch or /broadcast first to start uploading.")
        return

    if state["mode"] == "batch":
        if message.text and not message.text.startswith('/'):
            state["files"].append({
                "file_id": None, 
                "file_name": message.text, 
                "file_type": "text",
                "caption": None
            })
            await message.reply(f"✅ Text added to batch! Total items: {len(state['files'])}\nSend /done when ready.")
        
        elif media := get_media_info(message):
            state["files"].append(media)
            reply_text = f"✅ Media added to batch! Total items: {len(state['files'])}"
            if media["caption"]:
                reply_text += f"\nCaption: {media['caption']}"
            reply_text += "\nSend /done when ready."
            await message.reply(reply_text)

    elif state["mode"] == "broadcast":
        if message.text and not message.text.startswith('/'):
            state["content"].append({
                "type": "text", 
                "content": message.text,
                "caption": None
            })
            await message.reply(f"✅ Text added to broadcast! Total items: {len(state['content'])}\nSend /done when ready.")
        
        elif media := get_media_info(message):
            state["content"].append({
                "type": media["file_type"],
                "file_id": media["file_id"],
                "file_name": media["file_name"],
                "caption": media["caption"]
            })
            reply_text = f"✅ Media added to broadcast! Total items: {len(state['content'])}"
            if media["caption"]:
                reply_text += f"\nCaption: {media['caption']}"
            reply_text += "\nSend /done when ready."
            await message.reply(reply_text)

async def set_commands():
    await app.set_bot_commands([
        BotCommand("start", "Show start message"),
        BotCommand("batch", "Upload files (Owner)"),
        BotCommand("broadcast", "Send to all users (Owner)"),
        BotCommand("users", "List users (Owner)"),
        BotCommand("shortener", "Shorten URLs using GPLinks (Owner)")
    ])

app.start()
print("Bot started!")
app.loop.run_until_complete(set_commands())

try:
    asyncio.get_event_loop().run_forever()
except KeyboardInterrupt:
    print("Bot stopped!")
