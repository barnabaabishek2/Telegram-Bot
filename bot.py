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
from datetime import datetime, timedelta
import requests
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "7911278240:AAHHUKQb-TzknzOApSvhCZMZF-vBg-fPsDA"
API_ID = 24360857
API_HASH = "0924b59c45bf69cdfafd14188fb1b778"
OWNER_IDS = [5891854177]  # Your user ID
SHORTENER_API = "d2d9a81c236ad681edfbb260cb315628df46cc38"
SHORTENER_URL = "https://api.gplinks.com/api"
# Channel information
CHANNEL_USERNAME = "@solo_leveling_manhwa_tamil"
CHANNEL_ID = -1002662584633
CHANNEL_LINK = "https://t.me/solo_leveling_manhwa_tamil"
SOURCE_CHANNEL = "https://t.me/mangas_manhwas_tamil"
TUTORIAL_CHANNEL = "https://t.me/your_tutorial_channel"
JOIN_CHANNELS_LINK = "https://t.me/your_channels_folder"

# Initialize Firebase
try:
    firebase_config = os.getenv("FIREBASE_CONFIG")
    if not firebase_config:
        raise ValueError("FIREBASE_CONFIG environment variable is not set!")
    
    cred = credentials.Certificate(json.loads(firebase_config))
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://movie-or-anime-search-bot-default-rtdb.firebaseio.com"
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
        # Get all required channels from Firebase
        channels_ref = db.reference("channels")
        channels = channels_ref.get() or {}
        
        # If no channels are set, fall back to default channel
        if not channels:
            return await check_channel_membership(client, user_id, CHANNEL_ID)
        
        # Check membership in all required channels
        for channel_id in channels:
            if not await check_channel_membership(client, user_id, int(channel_id)):
                return False
        return True
    except Exception as e:
        logger.error(f"Error in is_user_joined: {e}")
        return True  # Allow access if we can't verify membership

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

# ====================== BATCH UPLOAD SYSTEM ======================

@app.on_message(filters.command("batch") & filters.user(OWNER_IDS))
async def batch_command(client, message):
    user_id = message.from_user.id
    user_states[user_id] = {
        "mode": "batch",
        "image": None,
        "titles": [],
        "files": {},
        "current_quality": None
    }
    
    await message.reply(
        "📤 *Batch Mode Activated!*\n\n"
        "1. Send /batch_image with movie poster (and info in caption)\n"
        "2. Send /batch_title with movie names (comma separated)\n"
        "3. Set quality with /batch_quality 480p\n"
        "4. Upload files for that quality\n"
        "5. Repeat steps 3-4 for other qualities\n"
        "6. Send /done when finished\n"
        "To cancel, send /cancel.",
        parse_mode=enums.ParseMode.MARKDOWN
    )

@app.on_message(filters.command("batch_image") & filters.user(OWNER_IDS))
async def batch_image_command(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id]["mode"] != "batch":
        await message.reply("❌ Please start with /batch first")
        return
    
    user_states[user_id]["image_mode"] = True
    await message.reply(
        "🖼 *Batch_Image Mode Activated!*\n\n"
        "Send me Movie or Anime Image Only with Caption (Movie/Anime information)\n"
        "When finished, send /done\n"
        "To cancel, send /cancel."
    )

@app.on_message(filters.photo & filters.user(OWNER_IDS) & filters.private)
async def handle_image_upload(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or not user_states[user_id].get("image_mode"):
        return
    
    user_states[user_id]["image"] = {
        "file_id": message.photo.file_id,
        "caption": message.caption or ""
    }
    user_states[user_id]["image_mode"] = False
    
    await message.reply(
        "✅ Image added to batch!\n"
        "Send /done when ready or /cancel to start over."
    )

@app.on_message(filters.command("done") & filters.user(OWNER_IDS))
async def handle_image_done(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or not user_states[user_id].get("image_mode", False):
        return
    
    if not user_states[user_id]["image"]:
        await message.reply("❌ No image received! Send /cancel to abort.")
        return
    
    await message.reply(
        "✅ Image set with Captions..\n"
        "Now Send /batch_title with movie names (comma separated)"
    )
    user_states[user_id]["image_mode"] = False

@app.on_message(filters.command("batch_title") & filters.user(OWNER_IDS))
async def batch_title_command(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id]["mode"] != "batch":
        await message.reply("❌ Please start with /batch first")
        return
    
    if len(message.command) < 2:
        await message.reply("❌ Usage: /batch_title Leo,leo,LEO")
        return
    
    titles = [t.strip() for t in ' '.join(message.command[1:]).split(',')]
    user_states[user_id]["titles"] = titles
    
    await message.reply(
        f"✅ Titles set: {', '.join(titles)}\n"
        "Now set quality with /batch_quality 480p"
    )

@app.on_message(filters.command("batch_quality") & filters.user(OWNER_IDS))
async def batch_quality_command(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id]["mode"] != "batch":
        await message.reply("❌ Please start with /batch first")
        return
    
    if len(message.command) < 2:
        await message.reply("❌ Usage: /batch_quality 480p (or 720p/1080p)")
        return
    
    quality = message.command[1].lower()
    if quality not in ["480p", "720p", "1080p"]:
        await message.reply("❌ Invalid quality! Use 480p, 720p or 1080p")
        return
    
    user_states[user_id]["current_quality"] = quality
    if quality not in user_states[user_id]["files"]:
        user_states[user_id]["files"][quality] = []
    
    await message.reply(
        f"✅ Quality set to {quality}. Now send files for this quality.\n"
        "Send /done when ready or /batch_quality for another quality."
    )

@app.on_message(filters.media & filters.user(OWNER_IDS) & filters.private)
async def handle_file_upload(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id]["mode"] != "batch":
        return
    
    if not user_states[user_id]["current_quality"]:
        await message.reply("❌ Please set quality first with /batch_quality")
        return
    
    quality = user_states[user_id]["current_quality"]
    media_info = get_media_info(message)
    
    if not media_info:
        await message.reply("❌ Unsupported media type!")
        return
    
    user_states[user_id]["files"][quality].append(media_info)
    count = len(user_states[user_id]["files"][quality])
    
    await message.reply(
        f"✅ Media added to {quality} batch! Total files: {count}\n"
        "Send /done when ready or /batch_quality for another quality."
    )

@app.on_message(filters.command("done") & filters.user(OWNER_IDS))
async def finalize_batch(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id]["mode"] != "batch":
        await message.reply("❌ No active batch to complete")
        return
    
    state = user_states[user_id]
    
    if not state["titles"] or not state["files"]:
        await message.reply("❌ Missing titles or files! Batch not saved.")
        user_states.pop(user_id, None)
        return
    
    unique_id = generate_unique_id()
    bot_username = (await client.get_me()).username
    
    batch_data = {
        "titles": state["titles"],
        "image": state["image"],
        "files": state["files"],
        "uploaded_by": user_id,
        "created_at": datetime.now().isoformat(),
        "deleted": False
    }
    
    db.reference(f"batches/{unique_id}").set(batch_data)
    
    qualities = ", ".join(state["files"].keys())
    titles = ", ".join(state["titles"])
    
    response = (
        f"✅ *Batch Upload Complete!*\n\n"
        f"🎬 Titles: {titles}\n"
        f"📌 Qualities: {qualities}\n"
        f"🖼 Poster: {'Yes' if state['image'] else 'No'}\n\n"
        f"🔗 Share Link: https://t.me/{bot_username}?start={unique_id}"
    )
    
    await message.reply(response, parse_mode=enums.ParseMode.MARKDOWN)
    user_states.pop(user_id, None)

# ====================== GROUP SEARCH FUNCTIONALITY ======================

@app.on_message(filters.group & ~filters.command)
async def handle_group_search(client, message):
    if message.from_user.id in OWNER_IDS or not message.text:
        return
    
    search_query = message.text.strip().lower()
    if len(search_query) < 3:
        if search_query in ["hi", "hello", "hey"]:
            await send_random_movie(client, message.chat.id)
        return
    
    batches_ref = db.reference("batches")
    all_batches = batches_ref.get() or {}
    
    matches = []
    for batch_id, batch_data in all_batches.items():
        if batch_data.get("deleted"):
            continue
            
        for title in batch_data.get("titles", []):
            if search_query in title.lower():
                matches.append((batch_id, batch_data))
                break
    
    if not matches:
        return
    
    for batch_id, batch_data in matches[:3]:
        buttons = []
        for quality in batch_data.get("files", {}).keys():
            share_link = f"https://t.me/{(await client.get_me()).username}?start={batch_id}_{quality}"
            short_link = shorten_url(share_link) or share_link
            buttons.append([InlineKeyboardButton(f"📥 {quality}", url=short_link)])
        
        buttons.append([
            InlineKeyboardButton("❓ How to Download", url=TUTORIAL_CHANNEL),
            InlineKeyboardButton("📢 Join Channels", url=JOIN_CHANNELS_LINK)
        ])
        
        if batch_data.get("image"):
            await client.send_photo(
                chat_id=message.chat.id,
                photo=batch_data["image"]["file_id"],
                caption=batch_data["image"]["caption"],
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await client.send_message(
                chat_id=message.chat.id,
                text=f"🎬 {batch_data['titles'][0]}\n\n📌 Available in: {', '.join(batch_data['files'].keys())}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

async def send_random_movie(client, chat_id):
    batches_ref = db.reference("batches")
    all_batches = batches_ref.get() or {}
    
    if not all_batches:
        return
    
    batch_id, batch_data = random.choice(list(all_batches.items()))
    
    if batch_data.get("deleted"):
        return
    
    qualities = list(batch_data.get("files", {}).keys())
    if not qualities:
        return
    
    quality = qualities[0]
    share_link = f"https://t.me/{(await client.get_me()).username}?start={batch_id}_{quality}"
    short_link = shorten_url(share_link) or share_link
    
    buttons = [
        [InlineKeyboardButton(f"📥 {quality}", url=short_link)],
        [
            InlineKeyboardButton("❓ How to Download", url=TUTORIAL_CHANNEL),
            InlineKeyboardButton("📢 Join Channels", url=JOIN_CHANNELS_LINK)
        ]
    ]
    
    if batch_data.get("image"):
        await client.send_photo(
            chat_id=chat_id,
            photo=batch_data["image"]["file_id"],
            caption=f"🎬 {batch_data['titles'][0]}\n\n{batch_data['image']['caption']}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await client.send_message(
            chat_id=chat_id,
            text=f"🎬 {batch_data['titles'][0]}\n\nAvailable in: {quality}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# ====================== START COMMAND (ORIGINAL VERSION - NO CHANGES) ======================

@app.on_message(filters.command("start"))
async def start(client, message):
    # Check if user is banned
    if db.reference(f"banned_users/{message.from_user.id}").get():
        await message.reply("🚫 You are banned from using this bot.")
        return
    
    user = message.from_user
    await store_user_info(user.id, user.username, user.first_name, user.last_name)
    
    wait_msg = await message.reply("⏳ Please wait while we process your request...")
    
    # Get all required channels
    channels_ref = db.reference("channels")
    channels = channels_ref.get() or {}
    channel_list = []
    for cid, data in channels.items():
        channel_list.append({
            "id": int(cid),
            "username": data.get("username"),
            "title": data.get("title", "Unknown Channel")
        })
    
    # If no channels are set, use the default channel
    if not channel_list:
        channel_list.append({
            "id": CHANNEL_ID,
            "username": CHANNEL_USERNAME,
            "title": "Solo Leveling Manhwa Tamil"
        })

    # Check membership
    has_joined = True
    if channel_list:
        has_joined = await is_user_joined(client, user.id)

    image_id = "AgACAgUAAxkBAAODaC1qWLvvXeuS_6G-CdAZ9ddPfLYAApHAMRsMImlVEq4iRgAB0ucVAAgBAAMCAAN4AAceBA"
    image_id1 = "AgACAgUAAxkBAAOGaC1qZawX7EK9SP09ZFUJM7_TScAAApLAMRsMImlVWCz45ax3wUAACAEAAwIAA3gABx4E"
    
    if len(message.command) == 1:
        if not has_joined:
            buttons = []
            for chan in channel_list:
                if chan["username"]:
                    url = f"https://t.me/{chan['username']}"
                else:
                    url = f"https://t.me/c/{str(chan['id']).replace('-100', '')}"
                buttons.append([InlineKeyboardButton(f"Join {chan['title']}", url=url)])
            buttons.append([InlineKeyboardButton("✅ Verify Join", callback_data="check_join")])
            
            caption = f"""
*Hᴇʟʟᴏ {user.first_name}*

*You must join our channels to get anime files*

*Please join all channels below:*
            """
            await wait_msg.delete()
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_id,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            caption = f"""
*Hᴇʟʟᴏ {user.first_name}*

*I Aᴍ File Sharing Bᴏᴛ I Wɪʟʟ Gɪᴠᴇ Yᴏᴜ Mangas and Manhwas Fɪʟᴇs Fʀᴏᴍ* [Manga And Manhwa Tamil]({SOURCE_CHANNEL})
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
            buttons = []
            for chan in channel_list:
                if chan["username"]:
                    url = f"https://t.me/{chan['username']}"
                else:
                    url = f"https://t.me/c/{str(chan['id']).replace('-100', '')}"
                buttons.append([InlineKeyboardButton(f"Join {chan['title']}", url=url)])
            buttons.append([InlineKeyboardButton("✅ GET FILE", callback_data=f"getfile_{unique_id}")])
            
            caption = f"""
*Hᴇʟʟᴏ {user.first_name}*

*You must join our channels to get this file*

*Please join all channels below:*
            """
            await wait_msg.delete()
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_id,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            if '_' in unique_id:
                batch_id, quality = unique_id.split('_')
                batch_data = db.reference(f"batches/{batch_id}").get()
                if batch_data and not batch_data.get("deleted"):
                    files = batch_data["files"].get(quality, [])
                    if files:
                        await wait_msg.edit_text("⏳ Preparing your file, please wait...")
                        await send_individual_file(client, message.chat.id, files)
                        await wait_msg.delete()
                        return
            else:
                batch_data = db.reference(f"batches/{unique_id}").get()
                if batch_data and not batch_data.get("deleted"):
                    buttons = []
                    for quality in batch_data["files"].keys():
                        buttons.append([InlineKeyboardButton(
                            f"📥 {quality}", 
                            url=f"https://t.me/{(await client.get_me()).username}?start={unique_id}_{quality}"
                        )])
                    
                    await wait_msg.delete()
                    if batch_data.get("image"):
                        await client.send_photo(
                            chat_id=message.chat.id,
                            photo=batch_data["image"]["file_id"],
                            caption=batch_data["image"]["caption"],
                            reply_markup=InlineKeyboardMarkup(buttons)
                        )
                    else:
                        await client.send_message(
                            chat_id=message.chat.id,
                            text=f"🎬 {batch_data['titles'][0]}\n\nSelect quality:",
                            reply_markup=InlineKeyboardMarkup(buttons)
                        )
                    return
            
            await wait_msg.edit_text("❌ File not found or deleted!")

# ====================== CALLBACK HANDLERS ======================

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
        image_id = "AgACAgUAAxkBAAODaC1qWLvvXeuS_6G-CdAZ9ddPfLYAApHAMRsMImlVEq4iRgAB0ucVAAgBAAMCAAN4AAceBA"
        
        await client.send_photo(
            chat_id=callback_query.message.chat.id,
            photo=image_id,
            caption=caption,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    else:
        await wait_msg.edit_text("❌ You haven't joined all required channels yet. Please join them first!")
    
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
        if '_' in unique_id:
            batch_id, quality = unique_id.split('_')
            batch_data = db.reference(f"batches/{batch_id}").get()
            if batch_data and not batch_data.get("deleted"):
                files = batch_data["files"].get(quality, [])
                if files:
                    await wait_msg.edit_text("⏳ Preparing your file, please wait...")
                    await callback_query.message.delete()
                    await send_individual_file(client, callback_query.message.chat.id, files)
                    await wait_msg.delete()
                    return
        else:
            batch_data = db.reference(f"batches/{unique_id}").get()
            if batch_data and not batch_data.get("deleted"):
                buttons = []
                for quality in batch_data["files"].keys():
                    buttons.append([InlineKeyboardButton(
                        f"📥 {quality}", 
                        url=f"https://t.me/{(await client.get_me()).username}?start={unique_id}_{quality}"
                    )])
                
                await callback_query.message.delete()
                if batch_data.get("image"):
                    await client.send_photo(
                        chat_id=callback_query.message.chat.id,
                        photo=batch_data["image"]["file_id"],
                        caption=batch_data["image"]["caption"],
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    await client.send_message(
                        chat_id=callback_query.message.chat.id,
                        text=f"🎬 {batch_data['titles'][0]}\n\nSelect quality:",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                await wait_msg.delete()
                return
        
        await wait_msg.edit_text("❌ File not found or deleted!")
    else:
        await wait_msg.edit_text("❌ Please join all required channels first!")
    
    await asyncio.sleep(5)
    await wait_msg.delete()

# ====================== ADMIN COMMANDS ======================

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

@app.on_message(filters.command("broadcast_delete") & filters.user(OWNER_IDS))
async def broadcast_delete(client, message):
    try:
        broadcasts_ref = db.reference("broadcasts")
        broadcasts = broadcasts_ref.get() or {}
        
        if not broadcasts:
            await message.reply("ℹ No active broadcasts found.")
            return
        
        if len(message.command) > 1:
            original_message_id = int(message.command[1])
            if str(original_message_id) not in broadcasts:
                await message.reply("❌ No broadcast found with that ID.")
                return
            
            delete_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 DELETE THIS BROADCAST", callback_data=f"delete_broadcast_{original_message_id}")]
            ])
            
            broadcast_data = broadcasts[str(original_message_id)]
            await message.reply(
                f"📢 Broadcast Message ID: `{original_message_id}`\n\n"
                f"• Recipients: {len(broadcast_data.get('recipients', []))}\n"
                f"• Sent at: {broadcast_data.get('timestamp', 'N/A')}\n\n"
                "Click the button below to delete this broadcast from all users:",
                reply_markup=delete_button,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return
        
        response = "📢 *Active Broadcasts*\n\n"
        for msg_id, broadcast_data in broadcasts.items():
            response += (
                f"📌 Message ID: `{msg_id}`\n"
                f"• Recipients: {len(broadcast_data.get('recipients', []))}\n"
                f"• Sent at: {broadcast_data.get('timestamp', 'N/A')}\n"
            )
            
            delete_button = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🗑 Delete Broadcast {msg_id}", callback_data=f"delete_broadcast_{msg_id}")]
            ])
            
            await message.reply(
                response,
                reply_markup=delete_button,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            response = ""
            await asyncio.sleep(0.5)
        
    except ValueError:
        await message.reply("❌ Invalid message ID. Must be a numeric value.")
    except Exception as e:
        logger.error(f"Error in broadcast_delete: {e}")
        await message.reply(f"❌ Error processing broadcast delete: {e}")

@app.on_message(filters.command("stats") & filters.user(OWNER_IDS))
async def stats_command(client, message):
    try:
        processing_msg = await message.reply("📊 Gathering statistics, please wait...")
        
        users_ref = db.reference("users")
        users = users_ref.get() or {}
        total_users = len(users)
        
        active_users = 0
        thirty_days_ago = datetime.now() - timedelta(days=30)
        for user_data in users.values():
            last_seen_str = user_data.get("last_seen", "")
            if last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    if last_seen > thirty_days_ago:
                        active_users += 1
                except ValueError:
                    continue
        
        batches_ref = db.reference("batches")
        batches = batches_ref.get() or {}
        total_batches = len(batches)
        active_batches = sum(1 for b in batches.values() if not b.get("deleted", False))
        
        try:
            channel = await client.get_chat(CHANNEL_ID)
            channel_members = channel.members_count if hasattr(channel, 'members_count') else "N/A"
        except Exception as e:
            channel_members = f"Error: {str(e)}"
        
        banned_users_ref = db.reference("banned_users")
        banned_users = banned_users_ref.get() or {}
        total_banned = len(banned_users)
        
        channels_ref = db.reference("channels")
        channels = channels_ref.get() or {}
        
        stats_message = f"""
📊 *Bot Statistics Report*

👥 *Users:*
• Total Users: `{total_users}`
• Active Users (last 30 days): `{active_users}`
• Banned Users: `{total_banned}`

📂 *Files:*
• Total Batches: `{total_batches}`
• Active Batches: `{active_batches}`
• Deleted Batches: `{total_batches - active_batches}`

📢 *Channel Stats:*
• Main Channel Members: `{channel_members}`
• Required Channels: `{len(channels)}`
        """
        
        await processing_msg.edit_text(stats_message, parse_mode=enums.ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Error generating stats: {e}")
        await message.reply(f"❌ Error generating statistics: {e}")

@app.on_message(filters.command("file_delete") & filters.user(OWNER_IDS))
async def file_delete_command(client, message):
    batches_ref = db.reference("batches")
    all_batches = batches_ref.get() or {}
    
    if not all_batches:
        await message.reply("❌ No batches found in the database!")
        return
    
    active_batches = [(bid, bdata) for bid, bdata in all_batches.items() if not bdata.get("deleted")]
    
    if not active_batches:
        await message.reply("ℹ No active batches found in database.")
        return
    
    if len(message.command) > 1:
        query = ' '.join(message.command[1:]).lower()
        matches = []
        
        for batch_id, batch_data in active_batches:
            if query in batch_id.lower():
                matches.append((batch_id, batch_data))
            else:
                for title in batch_data.get("titles", []):
                    if query in title.lower():
                        matches.append((batch_id, batch_data))
                        break
        
        if not matches:
            await message.reply("❌ No active batches found matching your query.")
            return
            
        batches_to_show = matches
    else:
        batches_to_show = active_batches
    
    total_batches = len(batches_to_show)
    processing_msg = await message.reply(f"⏳ Preparing {total_batches} batches for deletion...")
    
    for batch_id, batch_data in batches_to_show:
        uploader_id = batch_data.get("uploaded_by", "")
        uploader_info = db.reference(f"users/{uploader_id}").get() or {}
        uploader_name = uploader_info.get("first_name", "Unknown") + " " + uploader_info.get("last_name", "")
        uploader_username = f"@{uploader_info.get('username', '')}" if uploader_info.get("username") else "No username"
        
        created_at = batch_data.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created_at)
            created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            created_str = "Unknown"
        
        qualities = batch_data.get("files", {}).keys()
        file_counts = [f"{q}: {len(files)}" for q, files in batch_data.get("files", {}).items()]
        
        response = (
            f"📁 *Batch Details*\n\n"
            f"🆔 *Batch ID:* `{batch_id}`\n"
            f"🕒 *Created:* `{created_str}`\n"
            f"👤 *Uploader:* {uploader_name} ({uploader_username})\n"
            f"📌 *Qualities:* {', '.join(qualities)}\n"
            f"📂 *Files:* {', '.join(file_counts)}\n\n"
            f"🗑 *Click below to delete this batch permanently*"
        )

        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚠️ DELETE THIS BATCH", callback_data=f"delete_batch_{batch_id}")
        ]])
        
        try:
            await client.send_message(
                chat_id=message.chat.id,
                text=response,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Error sending batch info: {e}")
    
    await processing_msg.delete()
    
    if len(message.command) == 1:
        await message.reply(f"✅ Showing all {total_batches} active batches. Use `/file_delete <query>` to search for specific batches.")

@app.on_message(filters.command("add_joined_channel") & filters.user(OWNER_IDS))
async def add_joined_channel(client, message):
    if len(message.command) < 2:
        await message.reply("❌ Usage: /add_joined_channel <channel_link_or_username>")
        return

    try:
        channel_input = message.command[1].strip()
        if channel_input.startswith("https://t.me/"):
            channel_input = channel_input.split("/")[-1]
        
        chat = await client.get_chat(channel_input)
        if chat.type not in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
            await message.reply("❌ Only channels can be added!")
            return

        try:
            bot_member = await client.get_chat_member(chat.id, (await client.get_me()).id)
            if bot_member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                await message.reply("❌ I must be an admin in this channel!")
                return
        except Exception as e:
            await message.reply(f"❌ Admin check failed: {str(e)}")
            return

        channels_ref = db.reference("channels")
        channels_ref.child(str(chat.id)).set({
            "title": chat.title,
            "username": chat.username,
            "added_by": message.from_user.id,
            "added_at": datetime.now().isoformat()
        })

        await message.reply(
            f"✅ Added channel:\n"
            f"📢 **{chat.title}**\n"
            f"🆔 `{chat.id}`\n"
            f"🌐 @{chat.username or 'N/A'}"
        )
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command("delete_joined_channel") & filters.user(OWNER_IDS))
async def delete_joined_channel(client, message):
    if len(message.command) < 2:
        await message.reply("❌ Usage: /delete_joined_channel <channel_link_or_id>")
        return

    try:
        channel_input = message.command[1].strip()
        chat = await client.get_chat(channel_input)
        
        channels_ref = db.reference("channels")
        channel_ref = channels_ref.child(str(chat.id))
        
        if not channel_ref.get():
            await message.reply("❌ Channel not in list!")
            return

        channel_ref.delete()
        await message.reply(f"✅ Removed channel: {chat.title} (ID: {chat.id})")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ====================== CALLBACK HANDLERS ======================

@app.on_callback_query(filters.regex("^delete_broadcast_"))
async def handle_delete_broadcast(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in OWNER_IDS:
        await callback_query.answer("❌ You're not authorized to perform this action!", show_alert=True)
        return
    
    original_message_id = int(callback_query.data.split("_")[2])
    await callback_query.answer("⏳ Deleting broadcast from all users...")
    
    processing_msg = await callback_query.message.reply("🔄 Deleting broadcast messages from users...")
    
    broadcast_ref = db.reference(f"broadcasts/{original_message_id}")
    broadcast_data = broadcast_ref.get()
    
    if not broadcast_data:
        await processing_msg.edit_text("❌ Broadcast data not found!")
        return
    
    recipient_ids = broadcast_data.get("recipients", [])
    sent_messages_dict = broadcast_data.get("sent_messages", {})
    total_recipients = len(recipient_ids)
    success = 0
    failed = 0
    
    for user_id in recipient_ids:
        try:
            message_ids = sent_messages_dict.get(str(user_id), [])
            message_ids = [int(msg_id) for msg_id in message_ids if msg_id is not None]
            
            if message_ids:
                await client.delete_messages(chat_id=int(user_id), message_ids=message_ids)
                success += 1
            else:
                failed += 1
                logger.warning(f"No valid message IDs found for user {user_id}")
        except Exception as e:
            logger.error(f"Could not delete messages for {user_id}: {e}")
            failed += 1
        await asyncio.sleep(0.3)
    
    result_message = (
        f"✅ Broadcast message deletion completed!\n\n"
        f"• Total recipients: {total_recipients}\n"
        f"• Successfully deleted: {success}\n"
        f"• Failed: {failed}"
    )
    
    await processing_msg.edit_text(result_message)
    broadcast_ref.delete()
    
    await callback_query.message.edit_text(
        f"🗑 Broadcast Message ID: `{original_message_id}`\n\n"
        f"• Deletion completed at: {datetime.now().isoformat()}\n"
        f"• Successfully deleted from {success} users\n\n"
        "This broadcast has been fully deleted.",
        reply_markup=None
    )

@app.on_callback_query(filters.regex("^delete_batch_"))
async def handle_delete_batch(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in OWNER_IDS:
        await callback_query.answer("❌ Authorization required!", show_alert=True)
        return

    batch_id = callback_query.data.split("_")[2]
    batch_ref = db.reference(f"batches/{batch_id}")
    
    if not batch_ref.get():
        await callback_query.answer("❌ Batch already deleted!", show_alert=True)
        return

    batch_ref.update({"deleted": True, "deleted_at": datetime.now().isoformat()})
    
    await callback_query.answer("✅ Batch deleted successfully!", show_alert=True)
    await callback_query.message.edit_text(
        f"🗑 *DELETED BATCH*\nID: `{batch_id}`\n\nThis batch is no longer accessible.",
        reply_markup=None
    )

# ====================== MESSAGE HANDLERS ======================

@app.on_message(filters.private & ~filters.user(OWNER_IDS) & ~filters.command("start"))
async def reject_messages(client, message):
    if db.reference(f"banned_users/{message.from_user.id}").get():
        await message.reply("🚫 You are banned from using this bot.")
        return
    
    await message.reply("❌ Don't Send Me Messages Directly. I'm Only a File Sharing Bot!")

# ====================== BOT SETUP ======================

async def set_commands():
    await app.set_bot_commands([
        BotCommand("start", "Show start message"),
        BotCommand("batch", "Upload files (Owner)"),
        BotCommand("broadcast", "Send to all users (Owner)"),
        BotCommand("broadcast_delete", "Delete a broadcast (Owner)"),
        BotCommand("stats", "Show bot statistics (Owner)"),
        BotCommand("file_delete", "Delete a file (Owner)"),
        BotCommand("add_joined_channel", "Add required channel (Owner)"),
        BotCommand("delete_joined_channel", "Remove required channel (Owner)")
    ])

app.start()
print("Bot started!")
app.loop.run_until_complete(set_commands())

try:
    asyncio.get_event_loop().run_forever()
except KeyboardInterrupt:
    print("Bot stopped!")
