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

# ТЕПЕРЬ ВКЛЮЧАЕМ МАКСИМАЛЬНЫЕ ИНТЕНТЫ БЕЗОПАСНО
intents = discord.Intents.all()
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
# ⚠️ НАЛАШТУВАННЯ ID КАНАЛІВ ТА РОЛЕЙ (УСІ ТВОЇ КАНАЛИ АВТОМАТИЧНО ТУТ):
# =========================================================================
GUILD_ID = 1489687778710130728             # ID твого сервера для баннера
GTA_ROLE_ID = 1516860422613897216          # ID ролі GTA
TICKET_CATEGORY_ID = 1489687779960033381   # ID категорії для анкет рекрутингу
ADMIN_LOG_CHANNEL_ID = 1524836308332187699 # ID каналу "керівництво" для рекрутингу

# Твої 7 папок логування:
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
    print(f'Бот {bot.user.name} успішно запущений і готовий до роботи!')
    for guild in bot.guilds:
        try: invites_cache[guild.id] = await guild.invites()
        except: pass
    if not update_banner_loop.is_running():
        update_banner_loop.start()

# --- 2. ПАПКА СИСТЕМНІ ПОВІДОМЛЕННЯ (ЗАЙШОВ / ВИЙШОВ + АНТИ-ТВІНК) ---
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
                        inviter_text = f"{new_inv.inviter.mention} (`{new_inv.inviter.name}`)"
                        invite_code_text = f"`{new_inv.code}`"
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
    created_at = member.created_at.strftime("%d.%m.%Y %H:%M")
    account_age_days = (datetime.now(timezone.utc) - member.created_at).days
    embed = discord.Embed(title="📤 УЧАСНИК ВИЙШОВ З СЕРВЕРА", color=0xffa500)
    embed.add_field(name="👤 Учасник:", value=f"• Нік: {member.mention}\n• ID: `{member.id}`", inline=False)
    embed.add_field(name="📅 Акаунт:", value=f"• Створено: `{created_at}`\n• Вік: `{account_age_days} днів`", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await security_channel.send(embed=embed)

@bot.event
async def on_invite_create(invite):
    try: invites_cache[invite.guild.id] = await invite.guild.invites()
    except: pass

@bot.event
async def on_invite_delete(invite):
    try: invites_cache[invite.guild.id] = await invite.guild.invites()
    except: pass

# --- ПРОСТЫЕ И ЛЕГКИЕ БАЗОВЫЕ СОБЫТИЯ ЛОГОВ (НИКОГДА НЕ ВЕШАЮТ СЕРВЕР) ---
@bot.event
async def on_member_update(before, after):
    # Рекрутинг GTA
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
        embed_rules = discord.Embed(title="⚔️ ВІТАЄМО... У СІМ'Ї KAGE | РЕКРУТИНГ ⚔️", description=f"Привіт, {after.mention}! Ти обрав роль гравця GTA.", color=0x00ffff)
        await ticket_channel.send(embed=embed_rules)
        bot.loop.create_task(run_interview(ticket_channel, after))

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

# =========================================================================
# ⚡️ СВЕРХБЫСТРАЯ СИСТЕМА ЖУРНАЛА АУДИТА (ЛОВИТ МОДЕРАТОРОВ БЕЗ ПЕРЕГРУЗКИ)
# =========================================================================
@bot.event
async def on_audit_log_entry_create(entry):
    # 1. Лог банов
    if entry.action == discord.AuditLogAction.ban:
        channel = bot.get_channel(LOG_BANS_ID)
        if channel:
            target = bot.get_user(entry.target.id)
            embed = discord.Embed(title="🔨 ЗАБЛОКОВАНО КОРИСТУВАЧА", color=0x8b0000)
            embed.add_field(name="👤 Кого:", value=target.mention if target else f"ID: `{entry.target.id}`", inline=False)
            embed.add_field(name="🛡️ Модератор:", value=entry.user.mention, inline=True)
            embed.add_field(name="📝 Причина:", value=f"`{entry.reason or 'Не вказана'}`", inline=True)
            await channel.send(embed=embed)

    # 3. Лог изменения ролей модераторами
    elif entry.action == discord.AuditLogAction.member_role_update:
        channel = bot.get_channel(LOG_ROLES_ID)
        if channel:
            target = bot.get_user(entry.target.id)
            embed = discord.Embed(title="🎭 ЗМІНА РОЛЕЙ МОДЕРАТОРОМ", color=0x3498db)
            embed.description = f"Учасник: {target.mention if target else f'ID: {entry.target.id}'}\n🛡️ Модератор: {entry.user.mention}"
            await channel.send(embed=embed)

    # 4. Лог изменения никнеймов модераторами
    elif entry.action == discord.AuditLogAction.member_update and entry.before.nick != entry.after.nick:
        channel = bot.get_channel(LOG_NICKNAMES_ID)
        if channel:
            target = bot.get_user(entry.target.id)
            embed = discord.Embed(title="📝 ЗМІНА НІКНЕЙМУ МОДЕРАТОРОМ", color=0xe67e22)
            embed.description = f"Користувач: {target.mention if target else f'ID: {entry.target.id}'}\n❌ Було: `{entry.before.nick}`\n✅ Стало: `{entry.after.nick}`\n🛡️ Змінив: {entry.user.mention}"
            await channel.send(embed=embed)

    # 5. Лог удаления чужих сообщений модераторами
    elif entry.action == discord.AuditLogAction.message_delete:
        channel = bot.get_channel(LOG_MESSAGES_ID)
        if channel:
            target = bot.get_user(entry.target.id)
