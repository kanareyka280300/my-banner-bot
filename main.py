import discord
from discord.ext import commands, tasks
import io
import os
import asyncio
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone

# ВКЛЮЧАЕМ ВСЕ ИНТЕНТЫ ДЛЯ ЛОГИРОВАНИЯ
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Словники для кешування
invites_cache = {}
member_inviters = {}

# --- НАЛАШТУВАННЯ АНКЕТИ РЕКРУТИНГУ GTA ---
QUESTIONS = [
    "1. Як Ваше ім'я?",
    "2. Який Ваш статичний ID у грі?",
    "3. Який саме нікнейм Ви будете ставити при заході в гру (пам'ятайте про прізвище Kage)?",
    "4. Вкажіть Ваш нікнейм у Telegram (наприклад, @ua_vasilivna):"
]
active_interviews = set()

# =========================================================================
# ⚠️ НАЛАШТУВАННЯ ID КАНАЛІВ ДЛЯ ТВОЇХ СЕМИ ПАПОК ЛОГІВ:
# =========================================================================
GUILD_ID = 1489687778710130728             # ID твого сервера KAGE
GTA_ROLE_ID = 1516860422613897216          # ID ролі GTA
TICKET_CATEGORY_ID = 1489687779960033381   # ID категорії для анкет

# Твої нові канали під кожну вкладку (впиши сюди свої ID замість цифр нижче):
LOG_BANS_ID = 1489741516971966655              # 1. Папка Бан
SECURITY_LOG_CHANNEL_ID = 1524853896822915173 # 2. Зайшов / Вийшов (+ Твинки)
LOG_ROLES_ID = 1489741698841182260             # 3. Папка Ролі
LOG_NICKNAMES_ID = 1489741658487656529        # 4. Папка Нікнейми
LOG_MESSAGES_ID = 1489741740180242492          # 5. Папка Повідомлення
LOG_VOICE_ID = 1489741808953983036             # 6. Папка Войс переміщення
LOG_SERVER_GENERAL_ID = 1489742637278822531     # 7. Папка Сервер Загальне

ADMIN_LOG_CHANNEL_ID = 1524836308332187699     # ID каналу "керівництво" для анкет
# =========================================================================

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успішно запущений і готовий до роботи!')
    for guild in bot.guilds:
        try:
            invites_cache[guild.id] = await guild.invites()
        except:
            pass
            
    if not update_banner_loop.is_running():
        update_banner_loop.start()

# --- 2. ПАПКА ЗАЙШОВ НА СЕРВЕР ---
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)
    if not channel: return
    embed = discord.Embed(title="📥 УЧАСНИК ЗАЙШОВ НА СЕРВЕР", color=0x00ff00)
    embed.description = f"Користувач {member.mention} (`{member.name}`) приєднався до спільноти KAGE.\nID: `{member.id}`"
    await channel.send(embed=embed)

# --- 2. ПАПКА ВИЙШОВ З СЕРВЕРА ---
@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)
    if not channel: return
    embed = discord.Embed(title="📤 УЧАСНИК ВИЙШОВ З СЕРВЕРА", color=0xffa500)
    embed.description = f"Користувач {member.mention} (`{member.name}`) покинув спільноту KAGE.\nID: `{member.id}`"
    await channel.send(embed=embed)

# --- 1. ПАПКА БАН ---
@bot.event
async def on_member_ban(guild, user):
    channel = bot.get_channel(LOG_BANS_ID)
    if not channel: return
    embed = discord.Embed(title="🔨 ЗАБЛОКОВАНО КОРИСТУВАЧА", color=0x8b0000)
    embed.description = f"Користувач {user.mention} (`{user.name}`) був заблокований на сервері.\nID: `{user.id}`"
    await channel.send(embed=embed)

# --- 5. ПАПКА ПОВІДОМЛЕННЯ (ВИДАЛЕННЯ) ---
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    channel = bot.get_channel(LOG_MESSAGES_ID)
    if not channel: return
    embed = discord.Embed(title="🗑️ ПОВІДОМЛЕННЯ ВИДАЛЕНО", color=0xe74c3c)
    embed.add_field(name="Автор:", value=message.author.mention, inline=True)
    embed.add_field(name="Канал:", value=message.channel.mention, inline=True)
    embed.add_field(name="Текст:", value=f"```\n{message.content if message.content else 'Текст відсутній'}\n```", inline=False)
    await channel.send(embed=embed)

# --- 5. ПАПКА ПОВІДОМЛЕННЯ (РЕДАГУВАННЯ) ---
@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content: return
    channel = bot.get_channel(LOG_MESSAGES_ID)
    if not channel: return
    embed = discord.Embed(title="✏️ ПОВІДОМЛЕННЯ ВІДРЕДАГОВАНО", color=0xf1c40f)
    embed.add_field(name="Автор:", value=before.author.mention, inline=False)
    embed.add_field(name="Було:", value=f"```\n{before.content}\n```", inline=False)
    embed.add_field(name="Стало:", value=f"```\n{after.content}\n```", inline=False)
    await channel.send(embed=embed)

# --- 6. ПАПКА ВОЙС ПЕРЕМІЩЕННЯ ---
@bot.event
async def on_voice_state_update(member, before, after):
    channel = bot.get_channel(LOG_VOICE_ID)
    if not channel: return
    embed = discord.Embed(color=0x9b59b6)
    
    if before.channel is None and after.channel is not None:
        embed.title = "🔊 ВХІД У ГОЛОСОВИЙ КАНАЛ"
        embed.description = f"{member.mention} зайшов у канал {after.channel.mention}"
        await channel.send(embed=embed)
    elif before.channel is not None and after.channel is None:
        embed.title = "🔇 ВИХІД З ГОЛОСОВОГО КАНАЛУ"
        embed.description = f"{member.mention} покинув канал {before.channel.mention}"
        await channel.send(embed=embed)
    elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
        embed.title = "🔀 ПЕРЕМІЩЕННЯ МІЖ ВОЙСАМИ"
        embed.description = f"{member.mention} перейшов з {before.channel.mention} до {after.channel.mention}"
        await channel.send(embed=embed)

# --- 3. РОЛИ И 4. НИКНЕЙМЫ ---
@bot.event
async def on_member_update(before, after):
    # Рекрутинг GTA
    gta_role = discord.utils.get(after.guild.roles, id=GTA_ROLE_ID)
    if gta_role in after.roles and gta_role not in before.roles:
        if after.id not in active_interviews:
            active_interviews.add(after.id)
            guild = after.guild
            category = discord.utils.get(guild.categories, id=TICKET_CATEGORY_ID)
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                after: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            ticket_channel = await guild.create_text_channel(name=f"анкета-{after.name}", category=category, overwrites=overwrites)
            embed_rules = discord.Embed(title="⚔️ ВІТАЄМО У СІМ'Ї KAGE | РЕКРУТИНГ ⚔️", description=f"Привіт, {after.mention}!", color=0x00ffff)
            await ticket_channel.send(embed=embed_rules)
            bot.loop.create_task(run_interview(ticket_channel, after))

    # Зміна ролей
    if before.roles != after.roles:
        ch = bot.get_channel(LOG_ROLES_ID)
        if ch:
            added = [r.mention for r in after.roles if r not in before.roles]
            rem = [r.mention for r in before.roles if r not in after.roles]
            embed = discord.Embed(title="🎭 ЗМІНА РОЛЕЙ", color=0x3498db)
            embed.description = f"Учасник: {after.mention}\n🟢 Додано: {', '.join(added) if added else '—'}\n🔴 Вилучено: {', '.join(rem) if rem else '—'}"
            await ch.send(embed=embed)

    # Зміна нікнеймів
    if before.nick != after.nick or before.name != after.name:
        ch = bot.get_channel(LOG_NICKNAMES_ID)
        if ch:
            old = before.nick if before.nick else before.name
            new = after.nick if after.nick else after.name
            if old != new:
                embed = discord.Embed(title="📝 ЗМІНА НІКНЕЙМУ", color=0xe67e22)
                embed.description = f"Користувач: {after.mention}\n❌ Було: `{old}`\n✅ Стало: `{new}`"
                await ch.send(embed=embed)

# --- СИСТЕМА АНКЕТУВАННЯ ---
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
    await channel.send("🎉 **Анкету успішно заповнено.**")
    result_embed = discord.Embed(title=f"📋 НОВА АНКЕТА ВІД: {member.name}", color=0x00ff00)
    for q, a in zip(QUESTIONS, answers): result_embed.add_field(name=q, value=a, inline=False)
    admin_channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
    if admin_channel: await admin_channel.send(embed=result_embed)
    active_interviews.discard(member.id)
    try: await channel.delete()
    except: pass

# --- БЕЗПЕЧНИЙ БАННЕР ---
@tasks.loop(minutes=3)
async def update_banner_loop():
    try:
        guild = await bot.fetch_guild(GUILD_ID)
        full_guild = bot.get_guild(GUILD_ID)
        total_members = full_guild.member_count if full_guild else guild.member_count
    except: 
        return
    try:
        try: 
            image = Image.open('background.png')
        except:
            try: 
                image = Image.open('фон.png')
            except: 
                return
        draw = ImageDraw.Draw(image)
        voice_members = 0
        if full_guild:
            for channel in full_guild.voice_channels: 
                voice_members += len(channel.members)
        icon_user, icon_voice = "\uf0c0", "\uf130"
        num_user, num_voice = f"{total_members}", f"{voice_members}"
        try: 
            font_icons = ImageFont.truetype('iconfont.ttf', size=95)
        except: 
            font_icons = ImageFont.load_default()
        try: 
            font_nums = ImageFont.truetype('myfont.ttf', size=95)
        except: 
            font_nums = ImageFont.load_default()
        draw.text((220, 380), icon_user, fill=(255, 255, 255), font=font_icons)
        draw.text((350, 380), num_user, fill=(255, 255, 255), font=font_nums)
