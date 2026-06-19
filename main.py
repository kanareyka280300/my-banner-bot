import discord
from discord.ext import commands, tasks
import io
import os
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

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успішно запущений!')
    if not update_banner_loop.is_running():
        update_banner_loop.start()

@tasks.loop(minutes=3)
async def update_banner_loop():
    GUILD_ID = 1489687778710130728 
    
    # Запрашиваем сервер с полной информацией
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
        try:
            image = Image.open('background.png')
        except:
            image = Image.open('фон.png')
            
        draw = ImageDraw.Draw(image)

        # Считаем людей в голосовых каналах
        voice_members = 0
        if full_guild:
            for channel in full_guild.voice_channels:
                voice_members += len(channel.members)

        # Красивый формат: Текстовый значок + пробелы + Число
        text_line1 = f"USER: {total_members}"
        text_line2 = f"VOX: {voice_members}"

        # НАСТРОЙКА ШРИФТА: ставим огромный размер 70 для масштаба на большом баннере
        try:
            font = ImageFont.truetype('myfont.ttf', size=70)
        except Exception as e:
            print(f"Ошибка загрузки шрифта, использую стандартный: {e}")
            try:
                font = ImageFont.load_default(size=70)
            except:
                font = ImageFont.load_default()

        # Новые сильно смещенные координаты (X=180, Y=220 и Y=320)
        # Они сдвинут огромный текст вправо и вниз, чтобы он встал ровно по центру вашей рамки
        draw.text((180, 220), text_line1, fill=(255, 255, 255), font=font)
        draw.text((180, 320), text_line2, fill=(255, 255, 255), font=font)

        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        await guild.edit(banner=img_byte_arr.read())
        print("Баннер успешно обновлен со статистикой!")
    except Exception as e:
        print(f"Ошибка при обновлении баннера: {e}")

@bot.command()
async def forcebanner(ctx):
    await ctx.send("Запуск масштабного обновления баннера...")
    await update_banner_loop()
    await ctx.send("Готово!")

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
