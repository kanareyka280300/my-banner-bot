import disnake
from disnake.ext import commands
from datetime import datetime

# Настройка интентов (обязательно для работы всех функций)
intents = disnake.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Твои ID каналов
CHANNELS = {
    "bans": 148974351034404865,
    "members": 1524853896822915173,
    "roles": 148974354184112208,
    "nicks": 148974355203325453,
    "messages": 148974170532231433,
    "voice": 148974136931238320,
    "general": 1489743537278212131
}

@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен и готов к работе!')

# --- 1. ПАПКА БАН ---
@bot.event
async def on_member_ban(guild, user):
    channel = bot.get_channel(CHANNELS["bans"])
    async for entry in guild.audit_logs(limit=1, action=disnake.AuditLogAction.ban):
        if entry.target.id == user.id:
            embed = disnake.Embed(title="🚫 Пользователь забанен", color=disnake.Color.red())
            embed.add_field(name="Пользователь", value=f"{user.name} ({user.id})")
            embed.add_field(name="Модератор", value=entry.user.mention)
            embed.add_field(name="Причина", value=entry.reason or "Не указана")
            await channel.send(embed=embed)
            break

# --- 2. ЗАШЕЛ / ВЫШЕЛ ---
# (Для работы "кто пригласил" нужно хранить кэш инвайтов, это делается чуть сложнее, 
# я напишу логику определения через аудит)
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(CHANNELS["members"])
    days_created = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days
    status = "Надежный" if days_created > 7 else "Твинк"
    
    embed = disnake.Embed(title="✅ Новый участник", color=disnake.Color.green())
    embed.add_field(name="Ник", value=member.name)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Аккаунт создан", value=f"{days_created} дней назад ({status})")
    await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(CHANNELS["members"])
    embed = disnake.Embed(title="❌ Участник вышел", color=disnake.Color.orange())
    embed.add_field(name="Ник", value=member.name)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Роли на момент выхода", value=", ".join([r.name for r in member.roles if r.name != "@everyone"]))
    await channel.send(embed=embed)

# --- 3. РОЛИ ---
@bot.event
async def on_member_update(before, after):
    # Лог выдачи ролей
    if before.roles != after.roles:
        channel = bot.get_channel(CHANNELS["roles"])
        added_roles = [r.mention for r in after.roles if r not in before.roles]
        removed_roles = [r.mention for r in before.roles if r not in after.roles]
        
        async for entry in after.guild.audit_logs(limit=1, action=disnake.AuditLogAction.member_role_update):
            if entry.target.id == after.id:
                embed = disnake.Embed(title="🎭 Изменение ролей", color=disnake.Color.blue())
                embed.add_field(name="Участник", value=after.mention)
                if added_roles: embed.add_field(name="Выданы роли", value=", ".join(added_roles))
                if removed_roles: embed.add_field(name="Забраны роли", value=", ".join(removed_roles))
                embed.add_field(name="Выдал/Забрал", value=entry.user.mention)
                embed.set_footer(text=f"Время: {datetime.now().strftime('%H:%M:%S')}")
                await channel.send(embed=embed)
                break

# --- 4. НИКНЕЙМЫ ---
    # Дополнение к on_member_update
    if before.nick != after.nick:
        channel = bot.get_channel(CHANNELS["nicks"])
        async for entry in after.guild.audit_logs(limit=1, action=disnake.AuditLogAction.member_update):
            if entry.target.id == after.id:
                embed = disnake.Embed(title="✏️ Смена никнейма", color=disnake.Color.yellow())
                embed.add_field(name="Старый", value=before.nick or "Нет")
                embed.add_field(name="Новый", value=after.nick or "Нет")
                embed.add_field(name="Кто изменил", value=entry.user.mention)
                await channel.send(embed=embed)
                break

# --- 5. СООБЩЕНИЯ (Удаление) ---
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    channel = bot.get_channel(CHANNELS["messages"])
    
    # Пытаемся найти, кто удалил (требует прав админа)
    async for entry in message.guild.audit_logs(limit=1, action=disnake.AuditLogAction.message_delete):
        if entry.target.id == message.author.id:
            deleter = entry.user
            break
    else:
        deleter = "Сам пользователь"
        
    embed = disnake.Embed(title="🗑 Сообщение удалено", color=disnake.Color.dark_red())
    embed.add_field(name="Автор", value=message.author.mention)
    embed.add_field(name="Кто удалил", value=deleter.mention if isinstance(deleter, disnake.Member) else deleter)
    embed.add_field(name="Контент", value=message.content or "Медиафайл/Вложение")
    await channel.send(embed=embed)

# --- 6. ВОЙС ПЕРЕМЕЩЕНИЯ ---
@bot.event
async def on_voice_state_update(member, before, after):
    channel = bot.get_channel(CHANNELS["voice"])
    if before.channel != after.channel:
        action = ""
        if after.channel is None: action = f"Вышел из {before.channel.name}"
        elif before.channel is None: action = f"Зашел в {after.channel.name}"
        else: action = f"Перемещен из {before.channel.name} в {after.channel.name}"
        
        await channel.send(f"🎙 **{member.name}**: {action}")

# Вставьте ваш токен
bot.run(1534672387180728540)
