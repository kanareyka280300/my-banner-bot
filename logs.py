import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timezone
import os

# ВКЛЮЧАЕМ ИНТЕНТЫ ДЛЯ ЧТЕНИЯ СОБЫТИЙ СЕРВЕРА
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
intents.voice_states = True 

bot = commands.Bot(command_prefix="?", intents=intents)

# =========================================================================
# ⚠️ НАСТРОЙКА ID КАНАЛІВ ДЛЯ ТВОЇХ СЕМИ ПАПОК ЛОГІВ:
# =========================================================================
LOG_BANS_ID = 148974351034404865              # 1. Папка Бан
SECURITY_LOG_CHANNEL_ID = 1524853896822915173 # 2. Зайшов / Вийшов (+ Твинки)
LOG_ROLES_ID = 148974354184112208             # 3. Папка Ролі
LOG_NICKNAMES_ID = 148974355203325453         # 4. Папка Нікнейми
LOG_MESSAGES_ID = 148974170532231433          # 5. Папка Повідомлення
LOG_VOICE_ID = 148974136931238320             # 6. Папка Войс переміщення
LOG_SERVER_GENERAL_ID = 1489743537278212131     # 7. Папка Server General
# =========================================================================

@bot.event
async def on_ready():
    print(f'Бот-логгер {bot.user.name} успішно запущений і стежить за сервером!')

# --- 2. ПАПКА ЗАЙШОВ / ВИЙШОВ ---
@bot.event
async def on_member_remove(member):
    security_channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)
    if not security_channel: return
    created_at = member.created_at.strftime("%d.%m.%Y %H:%M")
    account_age_days = (datetime.now(timezone.utc) - member.created_at).days
    embed = discord.Embed(title="📤 УЧАСНИК ВИЙШОВ З СЕРВЕРА", color=0xffa500)
    embed.add_field(name="👤 Учасник:", value=f"• Нік: {member.mention}\n• ID: `{member.id}`", inline=False)
    embed.add_field(name="📅 Акаунт:", value=f"• Створено: `{created_at}`\n• Вік: `{account_age_days} днів`", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await security_channel.send(embed=embed)

# --- СВЕРХБЫСТРЫЙ И ЛЕГКИЙ ЖУРНАЛ АУДИТА (ЛОВИТ КТО ЧТО СДЕЛАЛ) ---
@bot.event
async def on_audit_log_entry_create(entry):
    # 1. Папка Бан
    if entry.action == discord.AuditLogAction.ban:
        channel = bot.get_channel(LOG_BANS_ID)
        if channel:
            target = bot.get_user(entry.target.id)
            embed = discord.Embed(title="🔨 ЗАБЛОКОВАНО КОРИСТУВАЧА", color=0x8b0000)
            embed.add_field(name="👤 Кого:", value=target.mention if target else f"ID: `{entry.target.id}`", inline=False)
            embed.add_field(name="🛡️ Модератор:", value=entry.user.mention, inline=True)
            embed.add_field(name="📝 Причина:", value=f"`{entry.reason or 'Не вказана'}`", inline=True)
            await channel.send(embed=embed)

    # 3. Папка Зміна ролей модератором
    elif entry.action == discord.AuditLogAction.member_role_update:
        channel = bot.get_channel(LOG_ROLES_ID)
        if channel:
            target = bot.get_user(entry.target.id)
            embed = discord.Embed(title="🎭 ЗМІНА РОЛЕЙ МОДЕРАТОРОМ", color=0x3498db)
            embed.description = f"Учасник: {target.mention if target else f'ID: {entry.target.id}'}\n🛡️ Модератор: {entry.user.mention}"
            await channel.send(embed=embed)

    # 4. Папка Нікнейми
    elif entry.action == discord.AuditLogAction.member_update and entry.before.nick != entry.after.nick:
        channel = bot.get_channel(LOG_NICKNAMES_ID)
        if channel:
            target = bot.get_user(entry.target.id)
            embed = discord.Embed(title="📝 ЗМІНА НІКНЕЙМУ МОДЕРАТОРОМ", color=0xe67e22)
            embed.description = f"Користувач: {target.mention if target else f'ID: {entry.target.id}'}\n❌ Було: `{entry.before.nick}`\n✅ Стало: `{entry.after.nick}`\n🛡️ Змінив: {entry.user.mention}"
            await channel.send(embed=embed)

    # 5. Папка Повідомлення (Удаление чужих сообщений модератором)
    elif entry.action == discord.AuditLogAction.message_delete:
        channel = bot.get_channel(LOG_MESSAGES_ID)
        if channel:
            target = bot.get_user(entry.target.id)
            embed = discord.Embed(title="🗑️ ПОВІДОМЛЕННЯ ВИДАЛЕНО МОДЕРАТОРОМ", color=0xe74c3c)
            embed.add_field(name="🛡️ Видалив модератор:", value=entry.user.mention, inline=True)
            embed.add_field(name="👤 Creator повідомлення:", value=target.mention if target else "Невідомо", inline=True)
            await channel.send(embed=embed)

    # 6. Папка Войс переміщення (Перетягивание людей)
    elif entry.action == discord.AuditLogAction.member_move:
        channel = bot.get_channel(LOG_VOICE_ID)
        if channel:
            embed = discord.Embed(title="🔀 ПЕРЕМІЩЕННЯ У ВОЙСІ МОДЕРАТОРОМ", color=0x9b59b6)
            embed.description = f"🛡️ Перетягнув модератор: {entry.user.mention}\n📊 Кількість переміщених: `{entry.extra.count}` користувачів."
            await channel.send(embed=embed)

    # 7. Папка Сервер Загальне (Выдача Мутов / Тайм-аутов)
    elif entry.action == discord.AuditLogAction.member_update and hasattr(entry.after, 'timed_out_until'):
        if entry.after.timed_out_until is not None:
            channel = bot.get_channel(LOG_SERVER_GENERAL_ID)
            if channel:
                target = bot.get_user(entry.target.id)
                embed = discord.Embed(title="🛡️ ВИДАНО МУТ (ТАЙМ-АУТ)", color=0xe74c3c)
                embed.add_field(name="👤 Кому:", value=target.mention if target else f"ID: `{entry.target.id}`", inline=True)
                embed.add_field(name="🛡️ Хто видав:", value=entry.user.mention, inline=True)
                embed.add_field(name="📝 Причина:", value=f"`{entry.reason or 'Не вказана'}`", inline=False)
                await channel.send(embed=embed)

    # 7. Папка Сервер Загальне (Создание каналов)
    elif entry.action == discord.AuditLogAction.channel_create:
        channel = bot.get_channel(LOG_SERVER_GENERAL_ID)
        if channel:
            embed = discord.Embed(title="🏗️ СТВОРЕНО НОВИЙ КАНАЛ", color=0x2ecc71)
            embed.description = f"🛠️ Створив модератор: {entry.user.mention}\nID каналу: `{entry.target.id}`"
            await channel.send(embed=embed)

# --- 5. ПАПКА ПОВІДОМЛЕННЯ (РЕДАКТИРОВАНИЕ И ОБЫЧНОЕ УДАЛЕНИЕ СВОЕГО) ---
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    channel = bot.get_channel(LOG_MESSAGES_ID)
    if not channel: return
    embed = discord.Embed(title="🗑️ ПОВІДОМЛЕННЯ ВИДАЛЕНО АВТОРОМ", color=0xe74c3c)
    embed.add_field(name="Автор:", value=message.author.mention, inline=True)
    embed.add_field(name="Канал:", value=message.channel.mention, inline=True)
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

# --- 6. ПАПКА ВОЙС ПЕРЕМІЩЕННЯ (ОБЫЧНЫЕ ВХОДЫ И ВЫХОДЫ) ---
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

token = os.environ.get('LOGS_TOKEN')
bot.run(token)
