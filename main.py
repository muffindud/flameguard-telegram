from dotenv import load_dotenv
import os
from telegram import Update, Bot
from telegram.ext import CommandHandler, MessageHandler, Application, filters, ContextTypes
import asyncio


load_dotenv()
Token = os.getenv('TELEGRAM_TOKEN')
BotName = os.getenv('BOT_NAME')

bot = Bot(token=Token)


IMAGE_DIRECTORY = 'img'
if not os.path.exists(IMAGE_DIRECTORY):
    os.makedirs(IMAGE_DIRECTORY)


# Telegram Bot
# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! I am FlameGuard. I will alert you then I detect fire.')

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('If you need help, please contact @' + BotName)

async def custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Custom message')

async def fire_detected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open(os.path.join(IMAGE_DIRECTORY, 'fire.png'), 'rb') as image_file:
        await update.message.reply_photo(photo=image_file, caption="I'm hot! 🔥")


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
    chat_id = update.effective_chat.id
    store_chat_id(chat_id)

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


# Store chat IDs for broadcasting
def store_chat_id(chat_id):
    """Store a new chat ID in a file if it's not already stored."""
    try:
        with open("chat_ids.txt", "r+") as file:
            stored_ids = file.read().splitlines()
            if str(chat_id) not in stored_ids:
                file.write(f"{chat_id}\n")
    except FileNotFoundError:
        with open("chat_ids.txt", "w") as file:
            file.write(f"{chat_id}\n")


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


async def main():
    fire = True
    if fire == True:
        IMAGE_FILENAME = 'fire.png'
        image_path = os.path.join(IMAGE_DIRECTORY, IMAGE_FILENAME)
        await broadcast_image(bot, image_path, "URGENT: Fire detected!")
        fire = False

    print('Bot started')
    app = Application.builder().token(Token).build()

    # Commands
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help))
    app.add_handler(CommandHandler('custom', custom))
    app.add_handler(CommandHandler('fire_detected', fire_detected))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Error
    app.add_error_handler(error)

    return app


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(main())

    try:
        loop.run_until_complete(asyncio.gather(
            app.run_polling(),
            stop_bot_on_command(app)
        ))
    finally:
        loop.close()
