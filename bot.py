import discord
from elasticsearch import Elasticsearch
from discord.ext import commands
import datetime
import config
import logging
import re
from datetime import timezone

# ✅ ตั้งค่า Logging เพื่อ Debug
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ✅ ฟังก์ชันช่วย sanitize index name
def sanitize_index_name(name):
    return re.sub(r'[^a-z0-9_]', '_', name.lower())

# ✅ เชื่อมต่อ Elasticsearch พร้อมรหัสผ่าน
try:
    es = Elasticsearch(
        [config.ELASTICSEARCH_HOST],
        basic_auth=(config.ELASTICSEARCH_USER, config.ELASTICSEARCH_PASSWORD),
        verify_certs=False,
        request_timeout=30  # ✅ เปลี่ยนจาก timeout → request_timeout
    )

    if es.ping():
        logging.info("✅ Connected to Elasticsearch")
    else:
        raise ConnectionError("Elasticsearch did not respond")

except Exception as e:
    logging.error(f"❌ Elasticsearch Connection Failed: {e}")
    es = None

# ✅ ตั้งค่าบอท
intents = discord.Intents.default()
intents.message_content = True  
intents.members = True  
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        logging.info(f"🤖 Ignoring bot message from {message.author.name}")
        return  

    logging.info(f"📩 Message received from {message.author.name} in {message.channel.name}: {message.content}")

    # ✅ ตรวจสอบว่า Message มีข้อความหรือเป็น Embed
    text_content = message.content if message.content else "[No text content]"

    if message.embeds:
        embed_data = []

        for embed in message.embeds:
            embed_text = []
            embed_dict = embed.to_dict()

            if 'title' in embed_dict:
                embed_text.append(f"📌 Title: {embed_dict['title']}")
            if 'description' in embed_dict:
                embed_text.append(f"📝 Description: {embed_dict['description']}")
            if 'fields' in embed_dict:
                for field in embed_dict['fields']:
                    embed_text.append(f"🔹 {field['name']}: {field['value']}")
            if 'footer' in embed_dict and 'text' in embed_dict['footer']:
                embed_text.append(f"🦶 Footer: {embed_dict['footer']['text']}")
            if 'author' in embed_dict and 'name' in embed_dict['author']:
                embed_text.append(f"👤 Author: {embed_dict['author']['name']}")
            if 'url' in embed_dict:
                embed_text.append(f"🔗 URL: {embed_dict['url']}")
            if 'timestamp' in embed_dict:
                embed_text.append(f"⏱ Timestamp: {embed_dict['timestamp']}")
            if 'thumbnail' in embed_dict and 'url' in embed_dict['thumbnail']:
                embed_text.append(f"🖼 Thumbnail: {embed_dict['thumbnail']['url']}")
            if 'image' in embed_dict and 'url' in embed_dict['image']:
                embed_text.append(f"🖼 Image: {embed_dict['image']['url']}")
            if 'video' in embed_dict and 'url' in embed_dict['video']:
                embed_text.append(f"🎥 Video: {embed_dict['video']['url']}")

            if not embed_text:
                embed_text.append(f"[⚠️ Embed object with no common fields]\n{embed_dict}")

            logging.info(f"🔍 Raw Embed Data: {embed_dict}")
            embed_data.append("\n".join(embed_text))

        text_content = "\n\n".join(embed_data)

    # ✅ แปลงชื่อ Channel เป็น Index ที่ปลอดภัย
    index_name = sanitize_index_name(message.channel.name)

    log_data = {
        "log_id": str(message.id),
        "user": message.author.name,
        "user_id": str(message.author.id),
        "channel": message.channel.name,
        "channel_id": str(message.channel.id),
        "text": text_content,
        "timestamp": datetime.datetime.now(timezone.utc).isoformat()
    }

    logging.info(f"📝 Log Data: {log_data}")

    # ✅ เช็คว่า Elasticsearch ทำงานได้หรือไม่
    if es is None:
        logging.error("⚠️ Skipping log: Elasticsearch is not connected")
        return

    # ✅ เช็คว่า Index มีอยู่หรือไม่ ถ้าไม่มีให้สร้าง
    try:
        if not es.indices.exists(index=index_name):
            es.indices.create(index=index_name)
            logging.info(f"🆕 Created new index: {index_name}")
    except Exception as e:
        logging.error(f"⚠️ Failed to check/create index: {e}")

    # ✅ ส่ง log ไปยัง Elasticsearch
    try:
        response = es.index(index=index_name, document=log_data)
        if response and response.get("result") == "created":
            logging.info(f"📌 Log Sent to {index_name}: {log_data}")
        else:
            logging.warning(f"⚠️ Log may not be saved properly: {response}")
    except Exception as e:
        logging.error(f"❌ Failed to send log: {e}")

    # ✅ อย่าลืมประมวลผลคำสั่งจากบอทด้วย
    await bot.process_commands(message)

# ✅ เริ่มรันบอท
bot.run(config.TOKEN)
