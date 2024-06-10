from dotenv import load_dotenv
import os
from telegram import Update, Bot
from telegram.ext import CommandHandler, MessageHandler, Application, filters, ContextTypes
import asyncio
from threading import Thread
from requests import get
from pika import BlockingConnection, ConnectionParameters
from functools import wraps

exchange = "telegram"
receive_from = "send"

connection = BlockingConnection(ConnectionParameters('localhost'))
channel = connection.channel()
channel.exchange_declare(exchange=exchange, exchange_type='direct')
result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue
channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=receive_from)

def sync(func: callable):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))
    return wrapper

load_dotenv()
Token = os.getenv('TELEGRAM_TOKEN')
BotName = os.getenv('BOT_NAME')

bot = Bot(token=Token)


IMAGE_DIRECTORY = 'img'
if not os.path.exists(IMAGE_DIRECTORY):
    os.makedirs(IMAGE_DIRECTORY)


# Store chat IDs for broadcasting
def store_chat_id(chat_id):
    try:
        with open("chat_ids.txt", "r+") as file:
            stored_ids = file.read().splitlines()
            if str(chat_id) not in stored_ids:
                file.write(f"{chat_id}\n")
    except FileNotFoundError:
        with open("chat_ids.txt", "w") as file:
            file.write(f"{chat_id}\n")


def remove_chat_id(chat_id):
    try:
        with open("chat_ids.txt", "r") as file:
            stored_ids = file.read().splitlines()
        with open("chat_ids.txt", "w") as file:
            for stored_id in stored_ids:
                if stored_id != str(chat_id):
                    file.write(f"{stored_id}\n")
    except FileNotFoundError:
        pass


# Telegram Bot
# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store_chat_id(update.effective_chat.id)
    await update.message.reply_text('Hello! I am FlameGuard. I will alert you when I detect fire.')


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remove_chat_id(update.effective_chat.id)
    await update.message.reply_text('You will no longer receive alerts from FlameGuard.')


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Help: \n /start - Subscribe to alerts \n /stop - Unsubscribe from alerts \n /help - Show help message')


# Responses
def handle_response(text: str) -> str:
    processed: str = text.lower()
    print('Processed text: ' + processed)

    if 'hello' in processed:
        return 'Hey there!'
    if 'bye' in processed:
        return 'Goodbye!'
    if 'thank' in processed:
        return 'You are welcome!'
    return 'I do not understand'


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type: str = update.message.chat.type
    text: str = update.message.text

    print(f'User {update.message.chat.id} in {message_type} sent: {text}')
    if message_type == 'group': 
        if BotName in text:
            new_text: str = text.replace(BotName, '').strip()
            response: str = handle_response(new_text)
        else:
            return
    else:
        response: str = handle_response(text)
    
    print('Bot responded: ' + response)
    await update.message.reply_text(response)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')


# Broadcast image to all chat IDs when alert
async def broadcast_image(bot, image_path, caption):
    try:
        with open("chat_ids.txt", "r") as file:
            chat_ids = file.read().splitlines()
            for chat_id in chat_ids:
                with open(image_path, 'rb') as photo:
                    try:
                        await bot.send_photo(chat_id=int(chat_id), photo=photo, caption=caption)
                        print(f"Image sent to {chat_id}")
                    except Exception as e:
                        print(f"Failed to send image to {chat_id}: {e}")
    except FileNotFoundError:
        print("No chat IDs found to broadcast.")


async def stop_bot_on_command(app):
    while True:
        user_input = await asyncio.to_thread(input, "Enter 'q' to stop the bot: ")
        if user_input.strip().lower() == 'q':
            print("Stopping the bot...")
            await app.shutdown()
            break


async def callback(ch, method, properties, body):
    print(f"Received: {body.decode()}")
    img_link, message = body.decode().split(' ', 1)
    with open(os.path.join(IMAGE_DIRECTORY, 'fire.png'), 'wb') as image_file:
        image_file.write(get(img_link).content)
    await broadcast_image(bot, os.path.join(IMAGE_DIRECTORY, 'fire.png'), message)


def consume(loop):
    asyncio.set_event_loop(loop)
    channel.basic_consume(on_message_callback=lambda ch, method, properties, body: asyncio.run_coroutine_threadsafe(callback(ch, method, properties, body), loop), queue=queue_name, auto_ack=True)
    channel.start_consuming()


async def main():
    print('Bot started')
    app = Application.builder().token(Token).build()

    # Commands
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('stop', stop))
    app.add_handler(CommandHandler('help', help))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Error
    app.add_error_handler(error)

    return app

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(main())

    consume_thread = Thread(target=consume, args=(loop,), daemon=True)
    consume_thread.start()

    try:
        loop.run_until_complete(asyncio.gather(
            app.run_polling(),
            stop_bot_on_command(app)
        ))
    finally:
        loop.close()
