import os
import time
import telebot
from flask import Flask, request
from openai import OpenAI

# 1. Get Tokens from Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")

if not BOT_TOKEN or not HF_TOKEN:
    raise ValueError("BOT_TOKEN and HF_TOKEN must be set in your environment variables.")

# 2. Initialize Telegram Bot and Flask App
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# 3. Initialize OpenAI Client (Pointed at Hugging Face Router)
# Defer initialization to avoid import-time errors
client = None

def get_client():
    global client
    if client is None:
        client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=HF_TOKEN,
        )
    return client

# 4. Handle /start and /help commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    print(f"[DEBUG] /start command from {message.chat.id}")
    bot.reply_to(message, "Hello! I am an AI chatbot powered by DeepSeek. Send me a message and I'll reply!")

# 5. Handle all other text messages
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        print(f"[DEBUG] Message received from {message.chat.id}: {message.text}")
        # Show "typing..." status in Telegram while waiting for the API
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Call the Hugging Face API with timeout
        print(f"[DEBUG] Calling OpenAI API with model: deepseek-ai/DeepSeek-V4-Pro:novita")
        try:
            response = get_client().chat.completions.create(
                model="deepseek-ai/DeepSeek-V4-Pro:novita",
                messages=[
                    {
                        "role": "user",
                        "content": message.text,
                    }
                ],
                timeout=30
            )
            
            # Get the AI's reply and send it back to the user
            reply = response.choices[0].message.content
            print(f"[DEBUG] Got reply: {reply[:100]}...")
            bot.reply_to(message, reply)
        except Exception as api_error:
            print(f"[ERROR] API Error: {str(api_error)}")
            error_msg = f"API Error: {str(api_error)[:100]}"
            bot.reply_to(message, error_msg)
        
    except Exception as e:
        print(f"[ERROR] Handler Error: {str(e)}")
        bot.reply_to(message, f"Error: {str(e)[:100]}")

# 6. Flask Route to receive Webhooks from Telegram
@app.route('/' + BOT_TOKEN, methods=['POST'])
def receive_update():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        print(f"[DEBUG] Received webhook: {json_string[:100]}...")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    else:
        print(f"[DEBUG] Invalid content-type: {request.headers.get('content-type')}")
        return "Invalid request", 403

# 8. Webhook Setup on Startup
# Render automatically provides 'RENDER_EXTERNAL_URL' (e.g., https://your-app.onrender.com)
def setup_webhook():
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        try:
            bot.remove_webhook()
            time.sleep(0.5)
            bot.set_webhook(url=f"{render_url}/{BOT_TOKEN}")
            print(f"✓ Webhook set to: {render_url}/{BOT_TOKEN}")
        except Exception as e:
            print(f"✗ Failed to set webhook: {e}")
    else:
        print("⚠ RENDER_EXTERNAL_URL not found. Webhook not set.")

# 7. Default route for Render health checks
_webhook_setup = False

@app.route('/')
def index():
    global _webhook_setup
    if not _webhook_setup:
        setup_webhook()
        _webhook_setup = True
    return "Telegram Bot is running smoothly!", 200

# 9. Start the Flask app (Fallback for local testing)
if __name__ == "__main__":
    setup_webhook()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
