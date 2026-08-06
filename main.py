import discord
from discord.ext import commands, tasks
import io
import os
import json
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
intents.invites = True
intents.bans = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
# ⚠️ НАЛАШТУВАННЯ ID КАНАЛІВ ТА РОЛЕЙ
# =========================================================================
GUILD_ID = 1489687778710130728             # ID твого сервера для баннера
GTA_ROLE_ID = 1516860422613897216          # ID ролі GTA
TICKET_CATEGORY_ID = 1489687779960033381   # ID категорії для анкет рекрутингу
ADMIN_LOG_CHANNEL_ID = 1524836308332187699 # ID каналу "керівництво" для рекрутингу

# --- КАНАЛИ ЛОГУВАННЯ ("папки") ---
BAN_LOG_CHANNEL_ID = 1489741516971966655        # 1. папка "бан"
JOIN_LEAVE_LOG_CHANNEL_ID = 1524853896822915173 # 2. папка "системні: зайшов/вийшов"
ROLE_LOG_CHANNEL_ID = 1489741698841182260       # 3. папка "ролі"
NICKNAME_LOG_CHANNEL_ID = 1489741658487656529   # 4. папка "нікнейми"
MESSAGE_LOG_CHANNEL_ID = 1489741740180242492    # 5. папка "повідомлення"
VOICE_LOG_CHANNEL_ID = 1489741808953983036      # 6. папка "войс переміщення"
GENERAL_LOG_CHANNEL_ID = 1489742637278822531    # 7. папка "сервер загальне"
# =========================================================================

# --- ПРОСТЕ ЛОКАЛЬНЕ СХОВИЩЕ ДАНИХ УЧАСНИКІВ (для показу інформації при виході) ---
DATA_FILE = "members_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Помилка збереження даних: {e}")

members_data = load_data()


def now_str():
    return datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S")


async def get_audit_executor(guild, action, target_id=None, within_seconds=10):
    try:
        async for entry in guild.audit_logs(action=action, limit=10):
            age = (datetime.now(timezone.utc) - entry.created_at).total_seconds()
            if age > within_seconds:
                break
            if target_id is not None:
                entry_target_id = getattr(entry.target, "id", None)
                if entry_target_id != target_id:
                    continue
            return entry
    except discord.Forbidden:
        return None
    except Exception as e:
        print(f"Помилка audit log: {e}")
        return None
    return None


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


# =========================================================================
# 2. ВХІД / ВИХІД + ПОВНА АНКЕТА УЧАСНИКА
# =========================================================================
@bot.event
async def on_member_join(member):
    guild = member.guild
    channel = bot.get_channel(JOIN_LEAVE_LOG_CHANNEL_ID)

    inviter_text = "Не вдалося визначити (можливо, офіційне посилання Discord або додано адміном)"
    invite_code_text = "Невідомо"
    invite_uses_text = "Невідомо"
    invite_used = None
    inviter_id = None
    inviter_name = None

    try:
        current_invites = await guild.invites()
    except:
        current_invites = []

    if guild.id in invites_cache:
        for old_inv in invites_cache[guild.id]:
            for new_inv in current_invites:
                if old_inv.code == new_inv.code and new_inv.uses > old_inv.uses:
                    invite_used = new_inv
                    inviter_text = f"{new_inv.inviter.mention} (`{new_inv.inviter.name}`)"
                    invite_code_text = f"`{new_inv.code}`"
                    invite_uses_text = f"`{new_inv.uses}` користувачів"
                    inviter_id = new_inv.inviter.id
                    inviter_name = new_inv.inviter.name
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

    members_data[str(member.id)] = {
        "name": member.name,
        "id": member.id,
        "joined_at": now_str(),
        "account_created": created_at,
        "account_age_days": account_age_days,
        "inviter_id": inviter_id,
        "inviter_name": inviter_name,
        "invite_code": invite_code_text,
    }
    save_data(members_data)

    if channel:
        embed = discord.Embed(
            title="🔍 ДЕТАЛЬНИЙ ЗВІТ ПРО НОВОГО УЧАСНИКА (ВХІД)",
            description=f"Користувач {member.mention} приєднався до спільноти KAGE.",
            color=embed_color
        )
        embed.add_field(name="👤 Учасник:", value=f"• Нік: `{member.name}`\n• ID: `{member.id}`", inline=False)
        embed.add_field(name="📅 Дата створення акаунта:", value=f"• Створено: `{created_at}`\n• Статус: {security_status}", inline=False)
        embed.add_field(name="🔗 Хто запросив за посиланнями:", value=f"• Автор: {inviter_text}", inline=False)
        embed.add_field(name="📊 Статистика посилання:", value=f"• Код: {invite_code_text}\n• Всього зайшло за ним: {invite_uses_text}", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"KAGE Security System • {datetime.now().strftime('%H:%M:%S')}")
        await channel.send(embed=embed)


@bot.event
async def on_member_remove(member):
    guild = member.guild
    channel = bot.get_channel(JOIN_LEAVE_LOG_CHANNEL_ID)
    if not channel:
        return

    stored = members_data.pop(str(member.id), None)
    save_data(members_data)

    kick_entry = await get_audit_executor(guild, discord.AuditLogAction.kick, target_id=member.id)
    if kick_entry:
        action_text = f"👢 Вигнаний(а) модератором {kick_entry.user.mention} (`{kick_entry.user.name}`)"
        if kick_entry.reason:
            action_text += f"\nПричина: {kick_entry.reason}"
    else:
        action_text = "🚪 Покинув(ла) сервер самостійно"

    embed = discord.Embed(
        title="📤 УЧАСНИК ЗАЛИШИВ СЕРВЕР",
        description=f"{member.mention} (`{member.name}`, ID: `{member.id}`)",
        color=0xffa500
    )
    embed.add_field(name="Дія:", value=action_text, inline=False)
    embed.add_field(name="Час виходу:", value=now_str(), inline=False)

    if stored:
        inviter_line = f"<@{stored.get('inviter_id')}> (`{stored.get('inviter_name')}`)" if stored.get('inviter_id') else "Невідомо"
        embed.add_field(
            name="📅 Дані при вході:",
            value=(f"• Зайшов: `{stored.get('joined_at')}`\n"
                   f"• Акаунт створено: `{stored.get('account_created')}` "
                   f"(вік на момент входу: {stored.get('account_age_days')} дн.)\n"
                   f"• Хто запросив: {inviter_line}\n"
                   f"• Інвайт: {stored.get('invite_code')}"),
            inline=False
        )
    else:
        embed.add_field(name="📅 Дані при вході:", value="Немає збережених даних (бот перезапускався або приєднався до входу).", inline=False)

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="KAGE Security System")
    await channel.send(embed=embed)


@bot.event
async def on_invite_create(invite):
    try: invites_cache[invite.guild.id] = await invite.guild.invites()
    except: pass

@bot.event
async def on_invite_delete(invite):
    try: invites_cache[invite.guild.id] = await invite.guild.invites()
    except: pass

# =========================================================================
# 1. БАНИ
# =========================================================================
@bot.event
async def on_member_ban(guild, user):
    channel = bot.get_channel(BAN_LOG_CHANNEL_ID)
    if not channel:
        return

    entry = await get_audit_executor(guild, discord.AuditLogAction.ban, target_id=user.id)
    moderator_text = f"{entry.user.mention} (`{entry.user.name}`)" if entry else "Невідомо"
    reason_text = (entry.reason if entry and entry.reason else "Причина не вказана")

    embed = discord.Embed(title="🔨 НОВИЙ БАН", color=0xff0000)
    embed.add_field(name="Кого:", value=f"{user.mention} (`{user.name}`, ID: `{user.id}`)", inline=False)
    embed.add_field(name="Хто заблокував:", value=moderator_text, inline=False)
    embed.add_field(name="Причина:", value=reason_text, inline=False)
    embed.add_field(name="Час:", value=now_str(), inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await channel.send(embed=embed)


@bot.event
async def on_member_unban(guild, user):
    channel = bot.get_channel(BAN_LOG_CHANNEL_ID)
    if not channel:
        return
    entry = await get_audit_executor(guild, discord.AuditLogAction.unban, target_id=user.id)
    moderator_text = f"{entry.user.mention} (`{entry.user.name}`)" if entry else "Невідомо"

    embed = discord.Embed(title="🔓 РОЗБАН", color=0x00ff00)
    embed.add_field(name="Кого:", value=f"{user.mention} (`{user.name}`)", inline=False)
    embed.add_field(name="Хто розблокував:", value=moderator_text, inline=False)
    embed.add_field(name="Час:", value=now_str(), inline=False)
    await channel.send(embed=embed)


# =========================================================================
# 3 і 4. РОЛІ ТА НІКНЕЙМИ (+ GTA рекрутинг) + МУТ
# =========================================================================
@bot.event
async def on_member_update(before, after):
    guild = after.guild

    # --- GTA рекрутинг ---
    gta_role = discord.utils.get(guild.roles, id=GTA_ROLE_ID)
    if gta_role in after.roles and gta_role not in before.roles:
        if after.id not in active_interviews:
            active_interviews.add(after.id)
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

    # --- ЛОГ РОЛЕЙ ---
    role_channel = bot.get_channel(ROLE_LOG_CHANNEL_ID)
    if role_channel:
        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]

        if added_roles or removed_roles:
            entry = await get_audit_executor(guild, discord.AuditLogAction.member_role_update, target_id=after.id)
            moderator_text = f"{entry.user.mention} (`{entry.user.name}`)" if entry else "Невідомо / автовидача"

            if added_roles:
                embed = discord.Embed(title="➕ ВИДАНО РОЛЬ", color=0x00b0ff)
                embed.add_field(name="Учасник:", value=f"{after.mention} (`{after.name}`)", inline=False)
                embed.add_field(name="Роль(і):", value=", ".join(r.mention for r in added_roles), inline=False)
                embed.add_field(name="Хто видав:", value=moderator_text, inline=False)
                embed.add_field(name="Дата/час:", value=now_str(), inline=False)
                await role_channel.send(embed=embed)

            if removed_roles:
                embed = discord.Embed(title="➖ ЗАБРАНО РОЛЬ", color=0xb00000)
                embed.add_field(name="Учасник:", value=f"{after.mention} (`{after.name}`)", inline=False)
                embed.add_field(name="Роль(і):", value=", ".join(r.mention for r in removed_roles), inline=False)
                embed.add_field(name="Хто забрав:", value=moderator_text, inline=False)
                embed.add_field(name="Дата/час:", value=now_str(), inline=False)
                await role_channel.send(embed=embed)

    # --- ЛОГ НІКНЕЙМІВ ---
    nick_channel = bot.get_channel(NICKNAME_LOG_CHANNEL_ID)
    if nick_channel and before.nick != after.nick:
        entry = await get_audit_executor(guild, discord.AuditLogAction.member_update, target_id=after.id)
        if entry and entry.user.id != after.id:
            changer_text = f"{entry.user.mention} (`{entry.user.name}`)"
        else:
            changer_text = f"{after.mention} (сам(а) собі)"

        embed = discord.Embed(title="✏️ ЗМІНА НІКНЕЙМУ", color=0xffff00)
        embed.add_field(name="Учасник:", value=f"{after.mention} (`{after.name}`, ID: `{after.id}`)", inline=False)
        embed.add_field(name="Старий нік:", value=f"`{before.nick or before.name}`", inline=True)
        embed.add_field(name="Новий нік:", value=f"`{after.nick or after.name}`", inline=True)
        embed.add_field(name="Хто змінив:", value=changer_text, inline=False)
        embed.add_field(name="Дата/час:", value=now_str(), inline=False)
        await nick_channel.send(embed=embed)

    # --- ЛОГ МУТУ (timeout) ---
    general_channel = bot.get_channel(GENERAL_LOG_CHANNEL_ID)
    if general_channel and before.timed_out_until != after.timed_out_until:
        entry = await get_audit_executor(guild, discord.AuditLogAction.member_update, target_id=after.id)
        moderator_text = f"{entry.user.mention} (`{entry.user.name}`)" if entry else "Невідомо"

        if after.timed_out_until and (not before.timed_out_until or after.timed_out_until > datetime.now(timezone.utc)):
            embed = discord.Embed(title="🔇 ВИДАНО МУТ (TIMEOUT)", color=0x808080)
            embed.add_field(name="Кому:", value=f"{after.mention} (`{after.name}`)", inline=False)
            embed.add_field(name="До:", value=after.timed_out_until.strftime("%d.%m.%Y %H:%M"), inline=True)
            embed.add_field(name="Хто видав:", value=moderator_text, inline=True)
            embed.add_field(name="Дата/час:", value=now_str(), inline=False)
            await general_channel.send(embed=embed)
        elif before.timed_out_until and not after.timed_out_until:
            embed = discord.Embed(title="🔊 МУТ ЗНЯТО", color=0x808080)
            embed.add_field(name="Кому:", value=f"{after.mention} (`{after.name}`)", inline=False)
            embed.add_field(name="Хто зняв:", value=moderator_text, inline=False)
            embed.add_field(name="Дата/час:", value=now_str(), inline=False)
            await general_channel.send(embed=embed)


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


# =========================================================================
# 5. ПОВІДОМЛЕННЯ
# =========================================================================
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    channel = bot.get_channel(MESSAGE_LOG_CHANNEL_ID)
    if not channel:
        return

    entry = await get_audit_executor(message.guild, discord.AuditLogAction.message_delete, target_id=message.author.id)
    deleter_text = f"{entry.user.mention} (`{entry.user.name}`)" if entry and entry.user.id != message.author.id else f"{message.author.mention} (сам(а))"

    embed = discord.Embed(title="🗑️ ПОВІДОМЛЕННЯ ВИДАЛЕНО", color=0xff4500)
    embed.add_field(name="Автор:", value=f"{message.author.mention} (`{message.author.name}`)", inline=False)
    embed.add_field(name="Канал:", value=message.channel.mention, inline=False)
    embed.add_field(name="Текст:", value=(message.content or "*(без тексту / вкладення)*")[:1000], inline=False)
    embed.add_field(name="Хто видалив:", value=deleter_text, inline=False)
    embed.add_field(name="Дата/час:", value=now_str(), inline=False)
    await channel.send(embed=embed)


@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    channel = bot.get_channel(MESSAGE_LOG_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(title="✏️ ПОВІДОМЛЕННЯ ВІДРЕДАГОВАНО", color=0x1e90ff)
    embed.add_field(name="Автор:", value=f"{before.author.mention} (`{before.author.name}`)", inline=False)
    embed.add_field(name="Канал:", value=before.channel.mention, inline=False)
    embed.add_field(name="Було:", value=(before.content or "*(порожньо)*")[:1000], inline=False)
    embed.add_field(name="Стало:", value=(after.content or "*(порожньо)*")[:1000], inline=False)
    embed.add_field(name="Дата/час:", value=now_str(), inline=False)
    await channel.send(embed=embed)


# =========================================================================
# 6. ВОЙС ПЕРЕМІЩЕННЯ
# =========================================================================
@bot.event
async def on_voice_state_update(member, before, after):
    channel = bot.get_channel(VOICE_LOG_CHANNEL_ID)
    if not channel:
        return

    if before.channel is None and after.channel is not None:
        embed = discord.Embed(title="🎙️ ЗАЙШОВ У ВОЙС", color=0x00ff7f)
        embed.description = f"{member.mention} (`{member.name}`) → {after.channel.mention}"
        embed.add_field(name="Дата/час:", value=now_str(), inline=False)
        await channel.send(embed=embed)
        return

    if before.channel is not None and after.channel is None:
        entry = await get_audit_executor(member.guild, discord.AuditLogAction.member_disconnect, target_id=member.id)
        by_text = f"Відключений(а) модератором {entry.user.mention}" if entry else "Вийшов(ла) самостійно"
        embed = discord.Embed(title="🔇 ВИЙШОВ З ВОЙСУ", color=0xff6347)
        embed.description = f"{member.mention} (`{member.name}`) ← {before.channel.mention}"
        embed.add_field(name="Як:", value=by_text, inline=False)
        embed.add_field(name="Дата/час:", value=now_str(), inline=False)
        await channel.send(embed=embed)
        return

    if before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
        entry = await get_audit_executor(member.guild, discord.AuditLogAction.member_move, target_id=member.id)
        by_text = f"Переміщений(а) модератором {entry.user.mention}" if entry else "Перейшов(ла) самостійно"
        embed = discord.Embed(title="🔀 ПЕРЕМІЩЕННЯ У ВОЙСІ", color=0xffa500)
        embed.description = f"{member.mention} (`{member.name}`)\n{before.channel.mention} ➜ {after.channel.mention}"
        embed.add_field(name="Як:", value=by_text, inline=False)
        embed.add_field(name="Дата/час:", value=now_str(), inline=False)
        await channel.send(embed=embed)


# =========================================================================
# 7. СЕРВЕР ЗАГАЛЬНЕ
# =========================================================================
@bot.event
async def on_guild_channel_create(gc):
    channel = bot.get_channel(GENERAL_LOG_CHANNEL_ID)
    if not channel:
        return
    entry = await get_audit_executor(gc.guild, discord.AuditLogAction.channel_create, target_id=gc.id)
    creator_text = f"{entry.user.mention} (`{entry.user.name}`)" if entry else "Невідомо"

    type_text = {
        discord.ChannelType.voice: "🔊 Войс-канал",
        discord.ChannelType.text: "💬 Текстовий канал",
        discord.ChannelType.category: "📁 Категорія",
        discord.ChannelType.stage_voice: "🎤 Stage-канал",
    }.get(gc.type, str(gc.type))

    embed = discord.Embed(
        title="🆕 СТВОРЕНО НОВИЙ КАНАЛ",
        description=f"{type_text}: {gc.mention if hasattr(gc, 'mention') else gc.name}",
        color=0x9370db
    )
    embed.add_field(name="Хто створив:", value=creator_text, inline=False)
    embed.add_field(name="Дата/час:", value=now_str(), inline=False)
    await channel.send(embed=embed)


@bot.event
async def on_guild_channel_delete(gc):
    channel = bot.get_channel(GENERAL_LOG_CHANNEL_ID)
    if not channel:
        return
    entry = await get_audit_executor(gc.guild, discord.AuditLogAction.channel_delete, target_id=gc.id)
    deleter_text = f"{entry.user.mention} (`{entry.user.name}`)" if entry else "Невідомо"

    embed = discord.Embed(title="🗑️ КАНАЛ ВИДАЛЕНО", color=0x9370db)
    embed.add_field(name="Канал:", value=f"`{gc.name}`", inline=False)
    embed.add_field(name="Хто видалив:", value=deleter_text, inline=False)
    embed.add_field(name="Дата/час:", value=now_str(), inline=False)
    await channel.send(embed=embed)


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
            for vc in full_guild.voice_channels: voice_members += len(vc.members)

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
