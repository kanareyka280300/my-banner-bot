import discord
from discord.ext import commands, tasks
import io
import os
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Код веб-сервера для хостинга Render
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
    GUILD_ID = 1489687778710130728  # Ваш точный ID сервера
    
    try:
        guild = await bot.fetch_guild(GUILD_ID)
    except Exception as e:
        print(f"Не вдалося знайти сервер по ID: {e}")
        return

    try:
        # Пытаемся открыть файл картинки по его системному имени на Render
        # Если в прошлый раз загрузился как "фон.png", бот проверит оба варианта
        try:
            image = Image.open('background.png')
        except:
            image = Image.open('фон.png')
            
        draw = ImageDraw.Draw(image)

        # Считаем участников
        total_members = guild.member_count

        # Считаем людей в голосовых каналах
        full_guild = bot.get_guild(GUILD_ID)
        voice_members = 0
        if full_guild:
            for channel in full_guild.voice_channels:
                voice_members += len(channel.members)

        # Текст для вывода
        text_line1 = f"Всего: {total_members}"
        text_line2 = f"В голосовых: {voice_members}"

        # Используем загруженный шрифт
        try:
            font = ImageFont.truetype('myfont.ttf', 28)
        except:
            font = ImageFont.load_default()

        # Отрисовка текста внутри рамки
        draw.text((65, 230), text_line1, fill=(255, 255, 255), font=font)
        draw.text((65, 280), text_line2, fill=(255, 255, 255), font=font)

        # Сохраняем и отправляем в Discord
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
    await ctx.send("Запуск принудительного обновления баннера...")
    await update_banner_loop()
    await ctx.send("Готово!")

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
