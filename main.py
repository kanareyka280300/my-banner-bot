import discord
from discord.ext import commands
import io
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Код веб-сервера для обхода ограничений бесплатного хостинга
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
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успішно запущений і готовий до роботи!')

@bot.command()
async def setbanner(ctx):
    if not ctx.message.attachments:
        await ctx.send("Будь ласка, прикріпіть картинку до повідомлення з командою!")
        return
    attachment = ctx.message.attachments
    if not attachment.filename.lower().endswith(('png', 'jpg', 'jpeg')):
        await ctx.send("Файл має бути картинкою у форматі PNG або JPG!")
        return
    await ctx.send("Завантажую та встановлюю баннер...")
    try:
        image_bytes = await attachment.read()
        await ctx.guild.edit(banner=image_bytes)
        await ctx.send("Ура! Баннер сервера успішно оновлено!")
    except discord.Forbidden:
        await ctx.send("У мене немає прав на зміну баннера, або у сервера немає 2-го рівня бусту (Boost Level 2).")
    except Exception as e:
        await ctx.send(f"Сталася помилка: {e}")

# Бот автоматически возьмет токен из настроек хостинга Render
token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
