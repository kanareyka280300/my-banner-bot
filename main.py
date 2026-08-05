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
# ⚠️ ВСЕ ТВОИ РЕАЛЬНЫЕ ID КАНАЛОВ УЖЕ ВСТАВЛЕНЫ СЮДА АВТОМАТИЧЕСКИ:
# =========================================================================
GUILD_ID = 1489687778710130728             # ID твого сервера KAGE
GTA_ROLE_ID = 1516860422613897216          # ID ролі GTA
TICKET_CATEGORY_ID = 1489687779960033381   # ID категорії для анкет

LOG_BANS_ID = 148974351034404865              # 1. Папка Бан
SECURITY_LOG_CHANNEL_ID = 1524853896822915173 # 2. Зайшов / Вийшов (+ Твинки)
LOG_ROLES_ID = 148974354184112208             # 3. Папка Ролі
LOG_NICKNAMES_ID = 148974355203325453         # 4. Папка Нікнейми
LOG_MESSAGES_ID = 148974170532231433          # 5. Папка Повідомлення
LOG_VOICE_ID = 148974136931238320             # 6. Папка Войс переміщення
LOG_SERVER_GENERAL_ID = 1489743537278212131     # 7. Папка Server General

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

# --- 2. СИСТЕМНІ ПОВІДОМЛЕННЯ (ЗАЙШОВ / ВИЙШОВ) ---
@bot.event
async def on_member_join(member):
    guild = member.guild
    security_channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)
    if not security_channel: return
    
    inviter_text, invite_code_text = "Невідомо", "Невідомо"
    try:
        current_invites = await guild.invites()
        if guild.id in invites_cache:
            for old_inv in invites_cache[guild.id]:
                for new_inv in current_invites:
                    if old_inv.code == new_inv.code and new_inv.uses > old_inv.uses:
                        inviter_text = f"{new_inv.inviter.mention}"
                        invite_code_text = f"`{new_inv.code}`"
                        member_inviters[member.id] = {"inviter": inviter_text, "code": invite_code_text}
                        break
        invites_cache[guild.id] = current_invites
    except: pass

    created_at = member.created_at.strftime("%d.%m.%Y %H:%M")
    account_age_days = (datetime.now(timezone.utc) - member.created_at).days
    status = f"🚨 **ПІДОЗРА НА ТВІНК!** ({account_age_days} днів)" if account_age_days <= 14 else f"✅ Надійний акаунт ({account_age_days} днів)"

    embed = discord.Embed(title="📥 УЧАСНИК ЗАЙШОВ НА СЕРВЕР", color=0x00ff00)
    embed.add_field(name="👤 Учасник:", value=f"• Нік: {member.mention}\n• ID: `{member.id}`", inline=False)
    embed.add_field(name="📅 Акаунт:", value=f"• Створено: `{created_at}`\n• Статус: {status}", inline=False)
    embed.add_field(name="🔗 Інвайт:", value=f"• Запросив: {inviter_text}\n• Код посилання: {invite_code_text}", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await security_channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    security_channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)
    if not security_channel: return

    invite_info = member_inviters.get(member.id, {"inviter": "Невідомо", "code": "Невідомо"})
    created_at = member.created_at.strftime("%d.%m.%Y %H:%M")
    account_age_days = (datetime.now(timezone.utc) - member.created_at).days

    embed = discord.Embed(title="📤 УЧАСНИК ВИЙШОВ З СЕРВЕРА", color=0xffa500)
    embed.add_field(name="👤 Учасник:", value=f"• Нік: {member.mention}\n• ID: `{member.id}`", inline=False)
    embed.add_field(name="📅 Акаунт:", value=f"• Створено: `{created_at}`\n• Вік: `{account_age_days} днів`", inline=False)
    embed.add_field(name="🔗 Колишній інвайт:", value=f"• Запросив: {invite_info['inviter']}\n• Код посилання: {invite_info['code']}", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await security_channel.send(embed=embed)

# --- 1. ПАПКА БАН ---
@bot.event
async def on_member_ban(guild, user):
    channel = bot.get_channel(LOG_BANS_ID)
    if not channel: return
    await asyncio.sleep(1)
    moderator, reason = "Невідомо", "Не вказана"
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                moderator, reason = entry.user.mention, entry.reason or "Не вказана"
                break
    except: pass
    embed = discord.Embed(title="🔨 ЗАБЛОКОВАНО КОРИСТУВАЧА", color=0x8b0000)
    embed.add_field(name="👤 Кого:", value=f"{user.mention} (ID: `{user.id}`)", inline=False)
    embed.add_field(name="🛡️ Модератор:", value=moderator, inline=True)
    embed.add_field(name="📝 Причина:", value=f"`{reason}`", inline=True)
    await channel.send(embed=embed)

# --- 3. ПАПКА РОЛІ ТА РЕКРУТИНГ ---
@bot.event
async def on_member_update(before, after):
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

    if before.roles != after.roles:
        ch = bot.get_channel(LOG_ROLES_ID)
        if not ch: return
        await asyncio.sleep(1)
        mod = "Невідомо"
        try:
            async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                if entry.target.id == after.id: mod = entry.user.mention; break
        except: pass
        added = [r.mention for r in after.roles if r not in before.roles]
        rem = [r.mention for r in before.roles if r not in after.roles]
        embed = discord.Embed(title="🎭 ЗМІНА РОЛЕЙ", color=0x3498db)
        embed.description = f"Учасник: {after.mention}\n🛡️ Модератор: {mod}\n🟢 Додано: {', '.join(added) if added else '—'}\n🔴 Вилучено: {', '.join(rem) if rem else '—'}"
        await ch.send(embed=embed)

    if before.nick != after.nick or before.name != after.name:
        ch = bot.get_channel(LOG_NICKNAMES_ID)
        if not ch: return
        old = before.nick or before.name
        new = after.nick or after.name
        if old != new:
            await asyncio.sleep(1)
            mod = after.mention
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                    if entry.target.id == after.id and entry.before.nick != entry.after.nick: mod = entry.user.mention; break
            except: pass
            embed = discord.Embed(title="📝 ЗМІНА НІКНЕЙМУ", color=0xe67e22)
            embed.description = f"Користувач: {after.mention}\n❌ Було: `{old}`\n✅ Стало: `{new}`\n⚙️ Змінив: {mod}"
            await ch.send(embed=embed)

# --- 5. ПАПКА ПОВІДОМЛЕННЯ ---
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    channel = bot.get_channel(LOG_MESSAGES_ID)
    if not channel: return
    await asyncio.sleep(1)
    mod = message.author.mention
    try:
        async for entry in message.guild.audit_logs(limit=1, action=discord.AuditLogAction.message_delete):
            if entry.target.id == message.author.id: mod = entry.user.mention; break
    except: pass
    embed = discord.Embed(title="🗑️ ПОВІДОМЛЕННЯ ВИДАЛЕНО", color=0xe74c3c)
    embed.add_field(name="Автор:", value=message.author.mention, inline=True)
    embed.add_field(name="🛡️ Видалив:", value=mod, inline=True)
    embed.add_field(name="Текст:", value=f"```\n{message.content if message.content else 'Текст відсутній'}\n```", inline=False)
    await channel.send(embed=embed)

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

