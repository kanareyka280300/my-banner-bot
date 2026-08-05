import discord
from discord.ext import commands, tasks
import io
import os
import json
import urllib.request
import urllib.parse
import asyncio
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from datetime import datetime, timezone

# Код веб-сервера для стабільної цілодобової роботи хостинга Render
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
intents.invites = True  # ДОЗВОЛЯЄ БОТУ БАЧИТИ ПОСИЛАННЯ

bot = commands.Bot(command_prefix="!", intents=intents)

# Словник для кешування інваїтів у пам'яті бота
invites_cache = {}

# --- НАЛАШТУВАННЯ АНКЕТИ РЕКРУТИНГУ GTA ---
QUESTIONS = [
    "1. Як Ваше ім'я?",
    "2. Який Ваш статичний ID у грі?",
    "3. Який саме нікнейм Ви будете ставити при заході в гру (пам'ятайте про прізвище Kage)?",
    "4. Вкажіть Ваш нікнейм у Telegram (наприклад, @ua_vasilivna):"
]
active_interviews = set()

# =========================================================================
# ⚠️ НАЛАШТУВАННЯ ID КАНАЛІВ ТА РОЛЕЙ (ТВІЙ НОВИЙ КАНАЛ ВЖЕ ТУТ):
# =========================================================================
GUILD_ID = 1489687778710130728             # ID твого сервера для баннера
GTA_ROLE_ID = 1516860422613897216          # ID ролі GTA
TICKET_CATEGORY_ID = 1489687779960033381   # ID категорії для анкет рекрутингу
ADMIN_LOG_CHANNEL_ID = 1524836308332187699 # ID каналу "керівництво" для рекрутингу
SECURITY_LOG_CHANNEL_ID = 1524853896822915173 # Канал для звітів про інвайти та анти-твінків
# =========================================================================

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успішно запущений і готовий до роботи!')
    
    # Завантажуємо інвайти сервера в пам'ять бота при старті
    for guild in bot.guilds:
        try:
            invites_cache[guild.id] = await guild.invites()
        except:
            pass
            
    if not update_banner_loop.is_running():
        update_banner_loop.start()

# --- ФУНКЦІЯ ГЛИБОКОЇ ПЕРЕВІРКИ НОВИХ УЧАСНИКІВ ---
@bot.event
async def on_member_join(member):
    guild = member.guild
    security_channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)
    
    inviter_text = "Не вдалося визначити (можливо, офіційне посилання Discord або додано адміном)"
    invite_code_text = "Невідомо"
    invite_uses_text = "Невідомо"
    invite_used = None
    
    try:
        current_invites = await guild.invites()
    except:
        return 

    if guild.id in invites_cache:
        for old_inv in invites_cache[guild.id]:
            for new_inv in current_invites:
                if old_inv.code == new_inv.code and new_inv.uses > old_inv.uses:
                    invite_used = new_inv
                    inviter_text = f"{new_inv.inviter.mention} (`{new_inv.inviter.name}`)"
                    invite_code_text = f"`{new_inv.code}`"
                    invite_uses_text = f"`{new_inv.uses}` користувачів"
                    break
            if invite_used:
                break

    if not invite_used and guild.vanity_url_code:
        inviter_text = "Офіційне кастомне посилання сервера (Vanity URL)"
        invite_code_text = f"`{guild.vanity_url_code}`"

    invites_cache[guild.id] = current_invites

    created_at = member.created_at.strftime("%d.%m.%Y %H:%M")
    now = datetime.now(timezone.utc)
    account_age_days = (now - member.created_at).days

    if account_age_days <= 14:
        security_status = f"🚨 **ПІДОЗРА НА ТВІНК!** Акаунту всього **{account_age_days} днів**!"
        embed_color = 0xff0000 
    else:
        security_status = f"✅ Надійний акаунт (Вік: {account_age_days} днів)"
        embed_color = 0x00ff00 

    if security_channel:
        embed = discord.Embed(
            title="🔍 ДЕТАЛЬНИЙ ЗВІТ ПРО НОВОГО УЧАСНИКА",
            description=f"Користувач {member.mention} приєднався до спільноти KAGE.",
            color=embed_color
        )
        embed.add_field(name="👤 Учасник:", value=f"• Нік: `{member.name}`\n• ID: `{member.id}`", inline=False)
        embed.add_field(name="📅 Дата створення акаунта:", value=f"• Створено: `{created_at}`\n• Статус: {security_status}", inline=False)
        embed.add_field(name="🔗 Хто запросив за посиланнями:", value=f"• Автор: {inviter_text}", inline=False)
        embed.add_field(name="📊 Статистика посилання:", value=f"• Код: {invite_code_text}\n• Всього зайшло за ним: {invite_uses_text}", inline=False)
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"KAGE Security System • {datetime.now().strftime('%H:%M:%S')}")
        await security_channel.send(embed=embed)

@bot.event
async def on_invite_create(invite):
    try: invites_cache[invite.guild.id] = await invite.guild.invites()
    except: pass

@bot.event
async def on_invite_delete(invite):
    try: invites_cache[invite.guild.id] = await invite.guild.invites()
    except: pass

# --- АВТОМАТИЧНЕ СТВОРЕННЯ КАНАЛУ РЕКРУТИНГУ GTA ---
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
    for q, a in zip(QUESTIONS, answers): result_embed.add_field(name=q, value=a, inline=False)
    admin_channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
    if admin_channel: await admin_channel.send(content="🔔 **Надійшла нова анкетна заявка GTA!**", embed=result_embed)
    active_interviews.discard(member.id)
    try: await channel.delete(reason="Анкета успішно заповнена")
    except: pass

# --- АВТОМАТИЧНИЙ БАННЕР ---
@tasks.loop(minutes=3)
async def update_banner_loop():
    try:
        guild = await bot.fetch_guild(GUILD_ID)
        full_guild = bot.get_guild(GUILD_ID)
        total_members = full_guild.member_count if full_guild else guild.member_count
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
        
        try: font_icons = ImageFont.truetype('iconfont.ttf', size=95)
        except: font_icons = ImageFont.load_default()
        try: font_nums = ImageFont.truetype('myfont.ttf', size=95)
        except: font_nums = ImageFont.load_default()
        
        draw.text((220, 380), icon_user, fill=(255, 255, 255), font=font_icons)
        draw.text((350, 380), num_user, fill=(255, 255, 255), font=font_nums)
        draw.text((225, 510), icon_voice, fill=(255, 255, 255), font=font_icons)
        draw.text((350, 510), num_voice, fill=(255, 255, 255), font=font_nums)
        
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
