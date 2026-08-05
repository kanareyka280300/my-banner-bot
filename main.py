import discord
from discord.ext import commands, tasks
import io
import os
import json
import urllib.request
import urllib.parse
import asyncio
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone

# ВКЛЮЧАЕМ ВСЕ НЕОБХОДИМЫЕ ИНТЕНТЫ ДЛЯ ЛОГИРОВАНИЯ
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
intents.voice_states = True 
intents.invites = True  
intents.moderation = True # Для відстеження банів

bot = commands.Bot(command_prefix="!", intents=intents)

# Словники для кешування
invites_cache = {}
member_inviters = {} # Пам'ять: хто кого запросив (щоб логувати при виході)

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
LOG_BANS_ID = 111111111111111111              # 1. Папка Бан
SECURITY_LOG_CHANNEL_ID = 1524853896822915173 # 2. Зайшов / Вийшов (+ Твинки)
LOG_ROLES_ID = 333333333333333333             # 3. Папка Ролі
LOG_NICKNAMES_ID = 444444444444444444         # 4. Папка Нікнейми
LOG_MESSAGES_ID = 555555555555555555          # 5. Папка Повідомлення
LOG_VOICE_ID = 666666666666666666             # 6. Папка Войс переміщення
LOG_SERVER_GENERAL_ID = 77777777777777777     # 7. Папка Сервер Загальне

ADMIN_LOG_CHANNEL_ID = 1524836308332187699     # ID каналу "керівництво" для анкет
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

# =========================================================================
# 2. ПАПКА СИСТЕМНІ ПОВІДОМЛЕННЯ (ЗАЙШОВ / ВИЙШОВ + ДАННІ + ХТО ЗАПРОСИВ)
# =========================================================================
@bot.event
async def on_member_join(member):
    guild = member.guild
    security_channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)
    
    inviter_text = "Не вдалося визначити (офіційне посилання або додано адміном)"
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
                    member_inviters[member.id] = {
                        "inviter": f"{new_inv.inviter.name} ({new_inv.inviter.mention})",
                        "code": new_inv.code
                    }
                    break
            if invite_used:
                break

    if not invite_used and guild.vanity_url_code:
        inviter_text = "Офіційне кастомне посилання сервера (Vanity URL)"
        invite_code_text = f"`{guild.vanity_url_code}`"
        member_inviters[member.id] = {"inviter": "Vanity URL", "code": guild.vanity_url_code}

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
            title="📥 УЧАСНИК ЗАЙШОВ НА СЕРВЕР",
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
async def on_member_remove(member):
    security_channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)
    if not security_channel: return

    created_at = member.created_at.strftime("%d.%m.%Y %H:%M")
    now = datetime.now(timezone.utc)
    account_age_days = (now - member.created_at).days
    
    invite_info = member_inviters.get(member.id, {"inviter": "Невідомо / Зник з пам'яті бота", "code": "Невідомо"})
    
    embed = discord.Embed(
        title="📤 УЧАСНИК ВИЙШОВ З СЕРВЕРА",
        description=f"Користувач {member.mention} покинув спільноту KAGE.",
        color=0xffa500 
    )
    embed.add_field(name="👤 Учасник:", value=f"• Нік: `{member.name}`\n• ID: `{member.id}`", inline=False)
    embed.add_field(name="📅 Профіль:", value=f"• Створено: `{created_at}`\n• Вік акаунта: `{account_age_days} днів`", inline=False)
    embed.add_field(name="🔗 Хто його колись запросив:", value=f"• Автор: {invite_info['inviter']}\n• Код посилання: `{invite_info['code']}`", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"KAGE Security System • {datetime.now().strftime('%H:%M:%S')}")
    await security_channel.send(embed=embed)
    
    if member.id in member_inviters:
        try: del member_inviters[member.id]
        except: pass

@bot.event
async def on_invite_create(invite):
    try: invites_cache[invite.guild.id] = await invite.guild.invites()
    except: pass

@bot.event
async def on_invite_delete(invite):
    try: invites_cache[invite.guild.id] = await invite.guild.invites()
    except: pass

# =========================================================================
# 1. ПАПКА БАН (ХТО, КОГО, ПРИЧИНА)
# =========================================================================
@bot.event
async def on_member_ban(guild, user):
    log_channel = bot.get_channel(LOG_BANS_ID)
    if not log_channel: return
    
    await asyncio.sleep(2) 
    moderator = "Невідомо (Адмін / Інший бот)"
    reason = "Не вказана"
    
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                moderator = entry.user.mention
                reason = entry.reason if entry.reason else "Не вказана"
                break
    except: pass

    embed = discord.Embed(title="🔨 ЗАБЛОКОВАНО КОРИСТУВАЧА", color=0x8b0000)
    embed.add_field(name="👤 Кого:", value=f"{user.mention} (`{user.name}`)\nID: `{user.id}`", inline=False)
    embed.add_field(name="🛡️ Хто заблокував:", value=moderator, inline=False)
    embed.add_field(name="📝 Причина:", value=f"`{reason}`", inline=False)
    embed.set_footer(text=f"KAGE Admin Logs • {datetime.now().strftime('%H:%M:%S')}")
    await log_channel.send(embed=embed)

# =========================================================================
# 3. ПАПКА РОЛІ ТА РЕКРУТИНГ GTA
# =========================================================================
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
            embed_rules = discord.Embed(
                title="⚔️ ВІТАЄМО У СІМ'Ї KAGE | РЕКРУТИНГ ⚔️",
                description=f"Привіт, {after.mention}! Ти обрав роль гравця GTA.\nЗараз бот проведе автоматичне опитування. Будь ласка, відповідай на кожне питання одним повідомленням. Починаємо!",
                color=0x00ffff
            )
            await ticket_channel.send(embed=embed_rules)
            bot.loop.create_task(run_interview(ticket_channel, after))

    # Лог змін ролей
    if before.roles != after.roles:

