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
    print(f'Бот {bot.user.name} успішно запущений і готовий!')
    if not update_banner_loop.is_running():
        update_banner_loop.start()

@tasks.loop(minutes=3)
async def update_banner_loop():
    GUILD_ID = 1489687778710130728 
    
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

        voice_members = 0
        if full_guild:
            for channel in full_guild.voice_channels:
                voice_members += len(channel.members)

        # Коды иконок и цифры
        icon_user = "\uf0c0"  
        icon_voice = "\uf130" 
        num_user = f"{total_members}"
        num_voice = f"{voice_members}"

        # МАСШТАБ: Делаем шрифт ОГРОМНЫМ (Размер 80), чтобы его было хорошо видно с ПК и телефона
        try:
            font_icons = ImageFont.truetype('iconfont.ttf', size=80)
        except:
            font_icons = ImageFont.load_default(size=80)

        try:
            font_nums = ImageFont.load_default(size=80)
        except:
            font_nums = ImageFont.load_default()

        # ПОЛНОЕ ЦЕНТРИРОВАНИЕ: опустили Y на 390 и 520, сохранив идеальный X
        
        # Строка 1: Участники
        draw.text((160, 390), icon_user, fill=(255, 255, 255), font=font_icons)
        draw.text((280, 390), num_user, fill=(255, 255, 255), font=font_nums)

        # Строка 2: Голосовой онлайн
        draw.text((165, 520), icon_voice, fill=(255, 255, 255), font=font_icons)
        draw.text((280, 520), num_voice, fill=(255, 255, 255), font=font_nums)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        await guild.edit(banner=img_byte_arr.read())
        print("Баннер успешно обновлен со статистикой!")
    except Exception as e:
        print(f"Ошибка при更新 баннера: {e}")

@bot.command()
async def forcebanner(ctx):
    await ctx.send("Запуск масштабного обновления баннера...")
    await update_banner_loop()
    await ctx.send("Готово!")

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
