import discord
from discord.ext import commands, tasks
import io
import os
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Код веб-сервера для стабильной круглосуточной работы на Render
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

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успішно запущений і готовий до роботи!')
    if not update_banner_loop.is_running():
        update_banner_loop.start()

@tasks.loop(minutes=3)
async def update_banner_loop():
    GUILD_ID = 1489687778710130728  # Ваш точный ID сервера KAGE REBORN
    
    try:
        guild = await bot.fetch_guild(GUILD_ID)
        full_guild = bot.get_guild(GUILD_ID)
        if full_guild:
            total_members = full_guild.member_count
        else:
            total_members = guild.member_count
    except Exception as e:
        print(f"Не вдалося знайти сервер: {e}")
        return

    try:
        # Проверяем, под каким именем картинка сохранилась на хостинге
        try:
            image = Image.open('background.png')
        except:
            image = Image.open('фон.png')
            
        draw = ImageDraw.Draw(image)

        # Считаем активный онлайн в голосовых каналах
        voice_members = 0
        if full_guild:
            for channel in full_guild.voice_channels:
                voice_members += len(channel.members)

        # Специальные коды иконок (люди и микрофон) для шрифта Font Awesome
        text_line1 = f"\uf0c0  {total_members}"
        text_line2 = f"\uf130  {voice_members}"

        # Подключаем иконный шрифт и ставим крупный размер 65 для рамки
        try:
            font = ImageFont.truetype('iconfont.ttf', size=65)
        except Exception as e:
            print(f"Ошибка загрузки шрифта, использую стандартный: {e}")
            try:
                font = ImageFont.load_default(size=65)
            except:
                font = ImageFont.load_default()

        # Координаты, чтобы иконки и цифры встали ровно по центру вашей рамки
        draw.text((110, 220), text_line1, fill=(255, 255, 255), font=font)
        draw.text((110, 320), text_line2, fill=(255, 255, 255), font=font)

        # Сохраняем картинку в буфер и отправляем баннер в Discord
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        await guild.edit(banner=img_byte_arr.read())
        print("Баннер успешно обновлен со статистикой!")
    except Exception as e:
        print(f"Ошибка при обновлении баннера: {e}")

# Команда для принудительного обновления через чат
@bot.command()
async def forcebanner(ctx):
    await ctx.send("Запуск масштабного обновления баннера...")
    await update_banner_loop()
    await ctx.send("Готово!")

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
