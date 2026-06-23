import discord
from discord.ext import commands, tasks
import io
import os
import aiohttp
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

# --- НАЛАШТУВАННЯ АНКЕТИ РЕКРУТИНГУ GTA ---
QUESTIONS = [
    "1. Як Ваше ім'я?",
    "2. Який Ваш статичний ID у грі?",
    "3. Який саме нікнейм Ви будете ставити при заході в гру (пам'ятайте про прізвище Kage)?",
    "4. Вкажіть Ваш нікнейм у Telegram (наприклад, @ua_vasilivna):"
]
active_interviews = set()

# НАСТРОЙКА ID ДЛЯ РЕКРУТИНГУ (Вставьте свои три ID сервера)
GTA_ROLE_ID = 1516860422613897216        
TICKET_CATEGORY_ID = 1516860343874359367 
ADMIN_LOG_CHANNEL_ID = 1516871322729447464 

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успішно запущений і готовий до всього!')
    if not update_banner_loop.is_running():
        update_banner_loop.start()

# --- БЛОК СТАТИСТИКИ PUBG ---
@bot.command(name="stats")
async def pubg_stats(ctx, *, player_name: str):
    pubg_key = os.environ.get('PUBG_TOKEN')
    if not pubg_key:
        await ctx.send("❌ Помилка: Ключ PUBG_TOKEN не налаштований на хостингу Render!")
        return

    await ctx.send(f"🔍 Шукаю статистику гравця **{player_name}** в базі PUBG Steam...")

    headers = {
        "Authorization": f"Bearer {pubg_key}",
        "Accept": "application/vnd.api+json"
    }

    async with aiohttp.ClientSession() as session:
        # 1. Шукаємо гравця за його нікнеймом у системі Steam
        player_url = f"https://pubg.com[playerNames]={player_name}"
        async with session.get(player_url, headers=headers) as resp:
            if resp.status != 200:
                await ctx.send(f"❌ Гравця з нікнеймом **{player_name}** не знайдено в Steam. Перевірте регістр букв!")
                return
            player_data = await resp.json()
            
        try:
            player_id = player_data['data'][0]['id']
            actual_name = player_data['data'][0]['attributes']['name']
        except:
            await ctx.send("❌ Сталася помилка при зчитуванні даних гравця.")
            return

        # 2. Запитуємо статистику
        stats_url = f"https://pubg.com{player_id}/seasons/lifetime"
        async with session.get(stats_url, headers=headers) as resp:
            if resp.status != 200:
                await ctx.send("❌ Не вдалося завантажити статистику для цього гравця.")
                return
            stats_data = await resp.json()

        try:
            # Беремо дані для режиму Squad FPP
            squad_stats = stats_data['data']['attributes']['gameModeStats']['squad-fpp']
            
            wins = squad_stats.get('wins', 0)
            kills = squad_stats.get('kills', 0)
            rounds = squad_stats.get('roundsPlayed', 0)
            top10s = squad_stats.get('top10s', 0)
            damage = int(squad_stats.get('damageDealt', 0))
            
            kd = round(kills / max(rounds - wins, 1), 2)
            avg_dmg = round(damage / max(rounds, 1), 1)
            win_rate = round((wins / max(rounds, 1)) * 100, 1)
        except Exception as e:
            await ctx.send("📊 У цього гравця немає зіграних матчів у режимі Squad за поточний період.")
            return

        # 3. Будуємо картку виводу статистики українською мовою
        embed = discord.Embed(
            title=f"🔥 СТАТИСТИКА ГРАВЦЯ PUBG: {actual_name} 🔥",
            description=f"Платформа: **Steam** | Режим: **Squad FPP**",
            color=0x00ffff
        )
        embed.add_field(name="Зіграно каток 🎮", value=f"{rounds}", inline=True)
        embed.add_field(name="Перемоги (Топ-1) 🏆", value=f"{wins} ({win_rate}%)", inline=True)
        embed.add_field(name="Попадання в Топ-10 🎯", value=f"{top10s}", inline=True)
        
        embed.add_field(name="Всього фрагів 💀", value=f"{kills}", inline=True)
        embed.add_field(name="Рейтинг K/D 📈", value=f"**{kd}**", inline=True)
        embed.add_field(name="Сер. урон за матч ⚔️", value=f"{avg_dmg}", inline=True)
        
        embed.set_footer(text=f"PUBG ID: {player_id}")
        await ctx.send(embed=embed)

# --- Альтернативний виклик фразою KAGE ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return
        
    text = message.content.lower()
    if text.startswith("kage посмотри"):
        name_to_search = message.content[13:].strip()
        if name_to_search:
            ctx = await bot.get_context(message)
            await pubg_stats(ctx, player_name=name_to_search)
            return
            
    await bot.process_commands(message)

# --- АВТОМАТИЧНИЙ РЕКРУТИНГ ---
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
            description=f"Привіт, {after.mention}! Ти обрав роль гравця GTA.\nЗараз бот проведе автоматичне опитування. Будь ласка, відповідай на кожне питання одним повідомленням. Починаємо!",
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
    await channel.send("🎉 **Дякуємо! Анкету успішно заповнено.**\nКанал автоматично закриється через 10 секунд.")
    result_embed = discord.Embed(title=f"📋 НОВА АНКЕТА ВІД: {member.name}", color=0x00ff00)
    for q, a in zip(QUESTIONS, answers): result_embed.add_field(name=q, value=a, inline=False)
    admin_channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
    if admin_channel: await admin_channel.send(content="🔔 **Надійшла нова анкетна заявка GTA!**", embed=result_embed)
    active_interviews.discard(member.id)
    await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.Duration(seconds=10))
    try: await channel.delete()
    except: pass

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
        try: font_icons = ImageFont.truetype('iconfont.ttf', size=80)
        except: font_icons = ImageFont.load_default()
        try: font_nums = ImageFont.truetype('myfont.ttf', size=80)
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
bot.run(token)
