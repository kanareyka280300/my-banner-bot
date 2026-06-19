import discord
from discord.ext import commands, tasks
import io
import os
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Код веб-сервера для Render
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
    print(f'Бот {bot.user.name} успішно запущений!')
    update_banner_loop.start()

@tasks.loop(minutes=3)
async def update_banner_loop():
    # НАСТРОЙКА: Вставьте ID вашего сервера вместо цифр ниже
    GUILD_ID = 1489687778710130728  
    
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        print("Сервер не найден! Проверьте GUILD_ID.")
        return

    try:
        # Открываем вашу фоновую картинку
        image = Image.open('фон.png') 
        draw = ImageDraw.Draw(image)

        # Считаем участников
        total_members = guild.member_count

        # Считаем людей в голосовых каналах
        voice_members = 0
        for channel in guild.voice_channels:
            voice_members += len(channel.members)

        # Текст для вывода
        text_line1 = f"Всего: {total_members}"
        text_line2 = f"В голосовых: {voice_members}"

        # НАСТРОЙКА ШРИФТА: используем загруженный шрифт и ставим крупный размер 28
        try:
            font = ImageFont.truetype('myfont.ttf', 28)
        except Exception as e:
            print(f"Не удалось загрузить шрифт, использую стандартный: {e}")
            font = ImageFont.load_default()

        # Точные координаты для крупного шрифта, чтобы он попал в рамку
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

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
