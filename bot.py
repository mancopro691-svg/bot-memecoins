
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime

TOKEN = "9021409963:AAGc-1WcCYdfczcZS5jqo-z0wub8-C7aqBE"
GROUP_CHAT_ID = -1004302458555

monedas_vistas = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot activo (modo estricto).")

def calcular_potencial(marketcap, liquidez, volumen, edad_horas, compras, ventas, price_change):
    puntuacion = 0
    detalles = []

    # Market Cap
    if 20000 <= marketcap <= 80000:
        puntuacion += 3
        detalles.append("MC ideal")
    elif marketcap < 150000:
        puntuacion += 1
        detalles.append("MC aceptable")
    else:
        puntuacion -= 1

    # Liquidez
    if liquidez >= 25000:
        puntuacion += 3
        detalles.append("Liquidez buena")
    elif liquidez >= 15000:
        puntuacion += 1
        detalles.append("Liquidez justa")
    else:
        puntuacion -= 2

    # Volumen
    if volumen >= 20000:
        puntuacion += 3
        detalles.append("Volumen fuerte")
    elif volumen >= 10000:
        puntuacion += 1
        detalles.append("Volumen decente")
    else:
        puntuacion -= 1

    # Edad
    if edad_horas <= 2:
        puntuacion += 2
        detalles.append("Muy temprana")
    elif edad_horas <= 8:
        puntuacion += 1
        detalles.append("Edad buena")

    # Ratio compras/ventas
    if compras > 0 and ventas > 0:
        ratio = compras / ventas
        if 1.3 <= ratio <= 3.0:
            puntuacion += 2
            detalles.append("Compras sanas")
        elif ratio > 4:
            puntuacion -= 1
            detalles.append("Posible manipulación")

    # Momentum de precio
    if price_change > 15:
        puntuacion += 2
        detalles.append("Momentum positivo")
    elif price_change < -10:
        puntuacion -= 1

    if puntuacion >= 10:
        return "Estimación estricta: x6 - x15 (500% - 1400% profit)", " | ".join(detalles)
    elif puntuacion >= 8:
        return "Estimación estricta: x3 - x8 (200% - 700% profit)", " | ".join(detalles)
    else:
        return None, None

def detectar_status(datos):
    pairs = datos.get("pairs", [])
    if not pairs:
        return "Desconocido"
    
    par_principal = pairs[0]
    dex_id = str(par_principal.get("dexId", "")).lower()
    
    if dex_id in ["pumpfun", "pump", "pump.fun"]:
        return "No migrado"
    if any(palabra in dex_id for palabra in ["raydium", "meteora", "orca"]):
        return "Migrado"
    return "Migrado"

async def revisar_nuevas(context: ContextTypes.DEFAULT_TYPE):
    try:
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        respuesta = requests.get(url, timeout=10)
        perfiles = respuesta.json()
        
        for perfil in perfiles:
            if perfil.get("chainId") != "solana":
                continue
            
            contrato = perfil.get("tokenAddress")
            if not contrato or contrato in monedas_vistas:
                continue
            
            monedas_vistas.add(contrato)
            
            url_token = f"https://api.dexscreener.com/latest/dex/tokens/{contrato}"
            resp = requests.get(url_token, timeout=10)
            datos = resp.json()
            
            if not datos.get("pairs"):
                continue
            
            par = datos["pairs"][0]
            
            nombre = par["baseToken"]["name"]
            simbolo = par["baseToken"]["symbol"]
            precio = par.get("priceUsd", "N/A")
            liquidez = par.get("liquidity", {}).get("usd", 0) or 0
            marketcap = par.get("marketCap", 0) or 0
            volumen = par.get("volume", {}).get("h24", 0) or 0
            imagen = par.get("info", {}).get("imageUrl")
            pair_address = par.get("pairAddress", "")
            
            status = detectar_status(datos)
            
            # Holders
            holders = "N/A"
            if pair_address:
                try:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "application/json"
                    }
                    url_holders = f"https://io.dexscreener.com/dex/pair-details/v4/solana/{pair_address.lower()}"
                    resp_h = requests.get(url_holders, headers=headers, timeout=8)
                    if resp_h.status_code == 200:
                        datos_h = resp_h.json()
                        holders_count = datos_h.get("holders", {}).get("count")
                        if holders_count is not None:
                            holders = f"{holders_count:,}"
                except:
                    holders = "N/A"
            
            # Edad
            creado = par.get("pairCreatedAt", 0)
            edad_texto = "N/A"
            edad_horas = 0
            if creado:
                segundos = (datetime.now().timestamp() * 1000 - creado) / 1000
                edad_horas = segundos / 3600
                horas = int(segundos // 3600)
                minutos = int((segundos % 3600) // 60)
                if horas > 0:
                    edad_texto = f"{horas}h {minutos}m"
                else:
                    edad_texto = f"{minutos}m"
            
            # Transacciones
            txns = par.get("txns", {}).get("h24", {})
            compras = txns.get("buys", 0) or 0
            ventas = txns.get("sells", 0) or 0
            
            # Cambio de precio
            price_change = par.get("priceChange", {}).get("h24", 0) or 0
            price_change_texto = f"{price_change:+.1f}%"
            
            # Filtros más estrictos (estilo VIP)
            if liquidez < 15000:
                continue
            if marketcap < 25000 or marketcap > 250000:
                continue
            if volumen < 10000:
                continue
            if edad_horas > 12:  # Solo monedas relativamente nuevas
                continue
            
            potencial, detalles = calcular_potencial(marketcap, liquidez, volumen, edad_horas, compras, ventas, price_change)
            
            texto = (
                f"<b>{nombre}</b> | #{simbolo} | ${simbolo}\n"
                f"CA:\n<code>{contrato}</code>\n"
                f"├ 📊 MC: ${marketcap:,.0f}\n"
                f"├ ⏱ Age: {edad_texto}\n"
                f"├ 📈 Volume 24h: ${volumen:,.0f}\n"
                f"├ 🟢 Buys/Sells: {compras}/{ventas}\n"
                f"├ 📉 Price 24h: {price_change_texto}\n"
                f"├ 💧 Liquidity: ${liquidez:,.0f}\n"
                f"├ 👥 Holders: {holders}\n"
                f"├ 🚀 Status: {status}\n"
            )
            
            if potencial:
                texto += f"└ 📈 Potencial: {potencial}\n"
                if detalles:
                    texto += f"   Detalles: {detalles}\n\n"
                else:
                    texto += "\n"
            else:
                texto += f"└ 📈 Potencial: No cumple criterios estrictos\n\n"
            
            texto += "⚠️ No es consejo financiero. Alto riesgo de pérdida total."
            
            if imagen:
                await context.bot.send_photo(
                    chat_id=GROUP_CHAT_ID,
                    photo=imagen,
                    caption=texto,
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=texto,
                    parse_mode="HTML"
                )
    
    except Exception as e:
        print("Error general:", e)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.job_queue.run_repeating(revisar_nuevas, interval=60, first=10)
    print("Bot iniciado (modo estricto).")
    app.run_polling()

if __name__ == "__main__":
    main()