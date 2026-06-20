import discord
from discord.ext import commands, tasks
import io
import os
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

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

# --- НОВІ ПИТАННЯ ДЛЯ АНКЕТИ (УКРАЇНСЬКОЮ) ---
QUESTIONS = [
    "1. Як Ваше ім'я?",
    "2. Який Ваш статичний ID у грі?",
    "3. Який саме нікнейм Ви будете ставити при заході в гру (пам'ятайте про прізвище Kage)?",
    "4. Вкажіть Ваш нікнейм у Telegram (наприклад, @ua_vasilivna):"
]

active_interviews = set()

# --- ТРИ НАЙВАЖЛИВІШІ ID ДЛЯ РЕКРУТИНГУ ---
GTA_ROLE_ID = 1516860422613897216       # 1. ВСТАВТЕ СЮДИ ID РОЛІ GTA
TICKET_CATEGORY_ID = 1516864730436862173 # 2. ВСТАВТЕ СЮДИ ID КАТЕГОРІЇ ДЛЯ ЗАЯВОК
ADMIN_LOG_CHANNEL_ID = 1516871322729447464 # 3. ВСТАВТЕ СЮДИ ID КАНАЛУ "керівництво"

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успішно запущений і готовий!')
    if not update_banner_loop.is_running():
        update_banner_loop.start()

# --- АВТОМАТИЧНЕ СТВОРЕННЯ КАНАЛУ ПРИ НАДАННІ РОЛІ ---
@bot.event
async def on_member_update(before, after):
    gta_role = discord.utils.get(after.guild.roles, id=GTA_ROLE_ID)
    
    if gta_role in after.roles and gta_role not in before.roles:
        if after.id in active_interviews:
            return
            
        active_interviews.add(after.id)
        guild = after.guild
        category = discord.utils.get(guild.categories, id=TICKET_CATEGORY_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            after: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(
            name=f"анкета-{after.name}",
            category=category,
            overwrites=overwrites
        )
        
        # Перше повідомлення з описом умов та посиланням на сайт реєстрації
        embed_rules = discord.Embed(
            title="⚔️ ВІТАЄМО У СІМ'Ї KAGE | РЕКРУТИНГ ⚔️",
            description=f"Привіт, {after.mention}! Ти обрав роль гравця GTA.\n\n"
                        f"📌 **Головні умови вступу до нашої родини:**\n"
                        f"1. Кожен учасник або учасниця при заході в гру обов'язково повинен ставити прізвище **Kage**.\n"
                        f"2. Тобі необхідно перейти на наш сайт та зареєструватися за цим посиланням:\n"
                        f"🔗 [**ПОСИЛАННЯ_НА_ВАШ_САЙТ_ТУТ**](https://ng-gta5.com/)\n"
                        f"3. Обов'язково зайди в канал **<#1516861856080330813>** та ознайомся з важливою інформацією.\n\n"
                        f"Зараз бот проведе автоматичне опитування. Будь ласка, відповідай на кожне питання одним повідомленням. Починаємо!",
            color=0x00ffff
        )
        await ticket_channel.send(embed=embed_rules)
        
        bot.loop.create_task(run_interview(ticket_channel, after))

# --- ЛОГІКА ПРОВЕДЕННЯ СПІВБЕСІДИ ---
async def run_interview(channel, member):
    answers = []
    
    def check(m):
        return m.author == member and m.channel == channel

    for question in QUESTIONS:
        await channel.send(f"**{question}**")
        try:
            msg = await bot.wait_for('message', check=check, timeout=600.0)
            answers.append(msg.content)
        except:
            await channel.send("⏱️ Час очікування відповіді вичерпано. Канал буде видалено.")
            active_interviews.discard(member.id)
            await channel.delete()
            return

    await channel.send("🎉 **Дякуємо! Анкету успішно заповнено.**\nКерівництво сім'ї KAGE розглядає Вашу заявку. Цей канал автоматично закриється через 10 секунд.")
    
    # Картка-звіт для каналу "керівництво"
    result_embed = discord.Embed(
        title=f"📋 НОВА АНКЕТА ВІД: {member.name}", 
        description=f"Користувач: {member.mention}\nID Дискорду: {member.id}",
        color=0x00ff00
    )
    for q, a in zip(QUESTIONS, answers):
        result_embed.add_field(name=q, value=a, inline=False)
    
    admin_channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
    if admin_channel:
        await admin_channel.send(content="🔔 **Надійшла нова анкетна заявка GTA!**", embed=result_embed)
    
    active_interviews.discard(member.id)
    await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.Duration(seconds=10))
    try:
        await channel.delete()
    except:
        pass

# --- АВТОМАТИЧНИЙ БАННЕР ---
@tasks.loop(minutes=3)
async def update_banner_loop():
    GUILD_ID = 1489687778710130728 
    try:
        guild = await bot.fetch_guild(GUILD_ID)
        full_guild = bot.get_guild(GUILD_ID)
        if full_guild: total_members = full_guild.member_count
        else: total_members = guild.member_count
    except: return

    try:
        try: image = Image.open('background.png')
        except: image = Image.open('фон.png')
        draw = ImageDraw.Draw(image)
        voice_members = 0
        if full_guild:
            for channel in full_guild.voice_channels: voice_members += len(channel.members)

        icon_user, icon_voice = "\uf0c0", "\uf130"
        num_user, num_voice = f"{total_members}", f"{voice_members}"

        try: font_icons = ImageFont.truetype('iconfont.ttf', size=46)
        except: font_icons = ImageFont.load_default(size=46)
        try: font_nums = ImageFont.load_default(size=54)
        except: font_nums = ImageFont.load_default()
        
        draw.text((160, 390), icon_user, fill=(255, 255, 255), font=font_icons)
        draw.text((280, 390), num_user, fill=(255, 255, 255), font=font_nums)
        draw.text((165, 520), icon_voice, fill=(255, 255, 255), font=font_icons)
        draw.text((280, 520), num_voice, fill=(255, 255, 255), font=font_nums)

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
