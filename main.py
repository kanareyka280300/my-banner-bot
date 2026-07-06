import discord
from discord.ext import commands, tasks
import io
import os
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Код веб-сервера для круглосуточной работы хостинга Render
class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    server = HTTPServer(('0.0.0.0', 8080), WebServer)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
intents.voice_states = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# --- НАЛАШТУВАННЯ АНКЕТИ РЕКРУТИНГУ GTA ---
QUESTIONS = [
    "1. Як Ваше ім'я?",
    "2. Який Ваш статичний ID у грі?",
    "3. Який саме нікнейм Ви будете ставити при заході в гру (пам'ятайте про прізвище Kage)?",
    "4. Вкажіть Ваш нікнейм у Telegram (наприклад, @ua_vasilivna):"
]
active_interviews = set()

# =========================================================================
# ⚠️ ОБОВ'ЯЗКОВО ПЕРЕВІР СВОЇ ТРИ ID НИЖЧЕ:
# =========================================================================
GTA_ROLE_ID = 1489687778710130728          
TICKET_CATEGORY_ID = 1489687778710130728   
ADMIN_LOG_CHANNEL_ID = 1489687778710130728 
# =========================================================================

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успішно запущений і готовий!')
    if not update_banner_loop.is_running():
        update_banner_loop.start()

# --- АВТОМАТИЧНИЙ РЕКРУТИНГ GTA ПРИ НАДАННІ РОЛІ ---
@bot.event
async def on_member_update(before, after):
    gta_role = discord.utils.get(after.guild.roles, id=GTA_ROLE_ID)
    if gta_role in after.roles and gta_role not in before.roles:
        if after.id in active_interviews: return
        active_interviews.add(after.id)
        guild = after.guild
        category = discord.utils.get(guild.categories, id=TICKET_CATEGORY_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            after: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(name=f"анкета-{after.name}", category=category, overwrites=overwrites)
        embed_rules = discord.Embed(
            title="⚔️ ВІТАЄМО У СІМ'Ї KAGE | РЕКРУТИНГ ⚔️",
            description=f"Привіт, {after.mention}! Ти обрав роль гравця GTA.\n"
                        f"Зараз бот проведе автоматичне опитування. Будь ласка, відповідай на кожне питання одним повідомленням. Починаємо!",
            color=0x00ffff
        )
        await ticket_channel.send(embed=embed_rules)
        bot.loop.create_task(run_interview(ticket_channel, after))

async def run_interview(channel, member):
    answers = []
    def check(m): return m.author == member and m.channel == channel
    for question in QUESTIONS:
        await channel.send(f"**{question}**")
        try:
            msg = await bot.wait_for('message', check=check, timeout=600.0)
            answers.append(msg.content)
        except:
            active_interviews.discard(member.id)
            await channel.delete()
            return
            
    await channel.send("🎉 **Дякуємо! Анкету успішно заповнено.**\nДані надіслані керівництву!")
    
    result_embed = discord.Embed(title=f"📋 НОВА АНКЕТА ВІД: {member.name}", color=0x00ff00)
    for q, a in zip(QUESTIONS, answers): 
        result_embed.add_field(name=q, value=a, inline=False)
        
    admin_channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
    if admin_channel: 
        await admin_channel.send(content="🔔 **Надійшла нова анкетна заявка GTA!**", embed=result_embed)
        
    active_interviews.discard(member.id)
    try:
        await channel.delete(reason="Анкета успішно заповнена")
    except:
        pass

# --- АВТОМАТИЧНИЙ БАННЕР (НОВІ КОРДИНАТИ ПІД САМУРАЯ) ---
@tasks.loop(minutes=3)
async def update_banner_loop():
    GUILD_ID = 1489687778710130728 
    try:
        guild = await bot.fetch_guild(GUILD_ID)
        full_guild = bot.get_guild(GUILD_ID)
        total_members = full_guild.member_count if full_guild else guild.member_count
    except: return
    try:
        # Проверяем файлы картинок (ищет background.png или фон.png)
        try: image = Image.open('background.png')
        except: image = Image.open('фон.png')
        draw = ImageDraw.Draw(image)
        voice_members = 0
        if full_guild:
            for channel in full_guild.voice_channels: voice_members += len(channel.members)
            
        icon_user, icon_voice = "\uf0c0", "\uf130"
        num_user, num_voice = f"{total_members}", f"{voice_members}"
        
        try: font_icons = ImageFont.truetype('iconfont.ttf', size=70)
        except: font_icons = ImageFont.load_default()
        try: font_nums = ImageFont.truetype('myfont.ttf', size=70)
        except: font_nums = ImageFont.load_default()
        
        # НОВЫЕ КООРДИНАТЫ (Смещаем текст в свободную левую часть, делаем красивый отступ)
        # Строка 1: Участники (Иконка на X=100, Цифры на X=200, Высота Y=180)
        draw.text((100, 180), icon_user, fill=(255, 255, 255), font=font_icons)
        draw.text((200, 180), num_user, fill=(255, 255, 255), font=font_nums)

        # Строка 2: Голосовой онлайн (Иконка на X=105, Цифры на X=200, Высота Y=280)
        draw.text((105, 280), icon_voice, fill=(255, 255, 255), font=font_icons)
        draw.text((200, 280), num_voice, fill=(255, 255, 255), font=font_nums)
        
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        await guild.edit(banner=img_byte_arr.read())
    except: pass

@bot.command()
async def forcebanner(ctx):
    await update_banner_loop()
    await ctx.send("Готово!")

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
