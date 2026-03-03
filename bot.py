"""
ENCRYPTOS BOT v4 — Browser persistente (resolve Errno 11)
"""

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import scraper as scraper_module
from analyzer import EncryptosAnalyzer, rsi_status, exp_status

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ENCRYPTOS_EMAIL  = os.environ["ENCRYPTOS_EMAIL"]
ENCRYPTOS_PASS   = os.environ["ENCRYPTOS_PASS"]
TIMEZONE         = "America/Sao_Paulo"

INTERVALO_MONITOR = 180   # 3 minutos
SCORE_ALERTA      = 4

HORARIOS_RELATORIO = [(6,0),(10,0),(12,0),(16,0),(20,0)]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

alertas_enviados: dict = {}


async def coletar_e_analisar() -> list:
    """Coleta dados usando o browser persistente e analisa."""
    dados = await scraper_module.coletar_dados(ENCRYPTOS_EMAIL, ENCRYPTOS_PASS)
    if not dados:
        return []
    return EncryptosAnalyzer().analisar(dados)


# ── JOBS ──────────────────────────────────────────────────

async def job_monitor(context: ContextTypes.DEFAULT_TYPE):
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()

        novos = []
        for a in ranking:
            if a['score'] < SCORE_ALERTA:
                continue
            if alertas_enviados.get(a['symbol']) == a['score']:
                continue
            novos.append(a)
            alertas_enviados[a['symbol']] = a['score']

        if not novos:
            log.info(f"Monitor [{agora_str}]: sem novos alertas.")
            return

        linhas = [
            "🚨 *ALERTA — NOVO SETUP DETECTADO!*",
            f"🕐 _{agora_str} (BRT)_",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        for a in novos:
            linhas.append(formatar_ativo_completo(a))
        linhas += ["━━━━━━━━━━━━━━━━━━━━━━━━━━━", "_Encryptos by Phoenix_"]

        for parte in dividir_mensagem("\n".join(linhas)):
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=parte, parse_mode=ParseMode.MARKDOWN)

        log.info(f"Alerta: {[a['symbol'] for a in novos]}")

    except Exception as e:
        log.error(f"Erro monitor: {e}")


async def job_relatorio(context: ContextTypes.DEFAULT_TYPE):
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()

        if not ranking:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="Erro ao acessar painel.")
            return

        msg = formatar_relatorio(ranking, agora_str)
        for parte in dividir_mensagem(msg):
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=parte, parse_mode=ParseMode.MARKDOWN)

        for a in ranking:
            if a['score'] >= SCORE_ALERTA:
                alertas_enviados[a['symbol']] = a['score']

    except Exception as e:
        log.error(f"Erro relatorio: {e}")


# ── COMANDOS ──────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *ENCRYPTOS BOT v4 Online!*\n\n"
        "🔄 Monitor continuo a cada *3 minutos*\n"
        "🚨 Alertas automaticos para setups 4-5 estrelas\n\n"
        "📋 Relatorios: 06h | 10h | 12h | 16h | 20h\n\n"
        "Comandos:\n"
        "/top15 — top 15 oportunidades agora\n"
        "/varredura — analise manual completa\n"
        "/status — status do bot\n"
        "/limpar — resetar alertas",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_top15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_espera = await update.message.reply_text("⏳ Analisando painel Encryptos...")
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()

        if not ranking:
            await msg_espera.edit_text("Erro ao acessar o painel. Tente novamente em 1 minuto.")
            return

        top15    = ranking[:15]
        medalhas = ["🥇","🥈","🥉"]

        linhas = [
            "🏆 *TOP 15 — MELHORES OPORTUNIDADES AGORA*",
            f"🕐 _{agora_str} (BRT)_",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        for i, a in enumerate(top15):
            medal = medalhas[i] if i < 3 else f"*#{i+1}*"
            linhas.append(f"\n{medal} *{a['symbol']}* {'⭐'*a['score']} {a.get('fase_emoji','')}")
            linhas.append(formatar_corpo_ativo(a))

        linhas += ["━━━━━━━━━━━━━━━━━━━━━━━━━━━", "_Encryptos by Phoenix_"]

        await msg_espera.delete()
        for parte in dividir_mensagem("\n".join(linhas)):
            await update.message.reply_text(parte, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg_espera.edit_text(f"Erro: {str(e)[:200]}")


async def cmd_varredura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Iniciando varredura manual...")
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()
        if not ranking:
            await msg.edit_text("Erro ao acessar o painel. Tente novamente em 1 minuto.")
            return
        await msg.delete()
        for parte in dividir_mensagem(formatar_relatorio(ranking, agora_str, manual=True)):
            await update.message.reply_text(parte, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"Erro: {str(e)[:200]}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    browser_ok = scraper_module._browser is not None and scraper_module._browser.is_connected()
    await update.message.reply_text(
        f"✅ *Bot online!*\n"
        f"🌐 Browser: {'✅ ativo' if browser_ok else '🔄 aguardando'}\n"
        f"🔒 Login: {'✅ logado' if scraper_module._logged_in else '🔄 aguardando'}\n"
        f"🔄 Monitor: a cada {INTERVALO_MONITOR//60} min\n"
        f"📊 Ativos em cooldown: {len(alertas_enviados)}\n"
        f"⭐ Score minimo alerta: {SCORE_ALERTA}",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alertas_enviados.clear()
    await update.message.reply_text("🗑️ Historico limpo! Proximo ciclo re-alerta tudo.")


# ── FORMATACAO ────────────────────────────────────────────

def fmt(v):
    if v is None: return "--"
    if isinstance(v, float):
        if v == int(v): return str(int(v))
        return f"{v:.1f}"
    return str(v)


def formatar_corpo_ativo(a):
    rsi = a.get('rsi_dict', {})
    exp = a.get('exp_dict', {})
    linhas = []

    linhas.append(
        f"📊 *RSI:*\n"
        f"  HTF: 1D{rsi_status(rsi.get('1d'))}`{fmt(rsi.get('1d'))}` "
        f"4H{rsi_status(rsi.get('4h'))}`{fmt(rsi.get('4h'))}` "
        f"1H{rsi_status(rsi.get('1h'))}`{fmt(rsi.get('1h'))}`\n"
        f"  LTF: 30m{rsi_status(rsi.get('30m'))}`{fmt(rsi.get('30m'))}` "
        f"15m{rsi_status(rsi.get('15m'))}`{fmt(rsi.get('15m'))}` "
        f"5m{rsi_status(rsi.get('5m'))}`{fmt(rsi.get('5m'))}` "
        f"1m{rsi_status(rsi.get('1m'))}`{fmt(rsi.get('1m'))}`"
    )

    linhas.append(
        f"📈 *EXP BTC:*\n"
        f"  HTF: 1D{exp_status(exp.get('1d'))}`{fmt(exp.get('1d'))}` "
        f"4H{exp_status(exp.get('4h'))}`{fmt(exp.get('4h'))}` "
        f"1H{exp_status(exp.get('1h'))}`{fmt(exp.get('1h'))}`\n"
        f"  LTF: 30m{exp_status(exp.get('30m'))}`{fmt(exp.get('30m'))}` "
        f"15m{exp_status(exp.get('15m'))}`{fmt(exp.get('15m'))}` "
        f"5m{exp_status(exp.get('5m'))}`{fmt(exp.get('5m'))}`"
    )

    linhas.append(
        f"⚖️ *LSR:* {a.get('lsr_label','N/D')}\n"
        f"📦 *OI:* {a.get('oi_label','N/D')}\n"
        f"🏦 *Trades:* {a.get('trades_label','N/D')}\n"
        f"🔍 *Fase:* {a.get('fase_label','N/D')}"
    )

    entrada = a.get('entrada')
    if entrada:
        linhas.append(
            f"\n💰 *ZONAS:*\n"
            f"  🟢 Entrada: `{a['entrada']}`\n"
            f"  🎯 TP1: `{a['tp1']}`\n"
            f"  🚀 TP2: `{a['tp2']}`\n"
            f"  🛑 Stop: `{a['stop']}`"
        )

    linhas.append(f"  📌 `{a['symbol']}.P`")
    return "\n".join(linhas)


def formatar_ativo_completo(a):
    return f"\n{'⭐'*a['score']} *{a['symbol']}* — {a.get('fase_label','')}\n" + formatar_corpo_ativo(a)


def formatar_relatorio(ranking, agora_str, manual=False):
    tipo = "🖐️ MANUAL" if manual else "⏰ RELATORIO"
    linhas = [
        f"📊 *ENCRYPTOS — {tipo}*",
        f"🕐 _{agora_str} (BRT)_",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    elite     = [a for a in ranking if a['score'] == 5]
    forte     = [a for a in ranking if a['score'] == 4]
    watchlist = [a for a in ranking if a['score'] == 3]

    if elite:
        linhas.append("\n🔥 *ELITE — OPERAR AGORA*")
        for a in elite[:5]: linhas.append(formatar_ativo_completo(a))
    if forte:
        linhas.append("\n⚡ *FORTE — QUASE LA*")
        for a in forte[:5]: linhas.append(formatar_ativo_completo(a))
    if watchlist:
        linhas.append("\n👀 *WATCHLIST*")
        for a in watchlist[:5]:
            rsi = a.get('rsi_dict', {})
            linhas.append(
                f"  • *{a['symbol']}* {'⭐'*a['score']} {a.get('fase_emoji','')} "
                f"RSI 1D:`{fmt(rsi.get('1d'))}` 4H:`{fmt(rsi.get('4h'))}` "
                f"EXP:`{fmt(a.get('exp_1d'))}` LSR:{a.get('lsr_label','--')}"
            )
    if not elite and not forte and not watchlist:
        linhas.append("\n😴 *Nenhum setup qualificado no momento.*")

    linhas += ["━━━━━━━━━━━━━━━━━━━━━━━━━━━", "_Encryptos by Phoenix_"]
    return "\n".join(linhas)


def dividir_mensagem(msg, limite=4000):
    if len(msg) <= limite: return [msg]
    partes = []
    while msg:
        if len(msg) <= limite: partes.append(msg); break
        corte = msg.rfind('\n', 0, limite)
        if corte == -1: corte = limite
        partes.append(msg[:corte]); msg = msg[corte:]
    return partes


# ── INIT / SHUTDOWN ───────────────────────────────────────

async def post_init(app: Application):
    tz = ZoneInfo(TIMEZONE)

    app.job_queue.run_repeating(job_monitor, interval=INTERVALO_MONITOR, first=15, name="monitor")
    log.info(f"Monitor: a cada {INTERVALO_MONITOR}s")

    for hora, minuto in HORARIOS_RELATORIO:
        t = datetime.now(tz).replace(hour=hora, minute=minuto, second=0, microsecond=0).timetz()
        app.job_queue.run_daily(job_relatorio, time=t, name=f"rel_{hora:02d}h{minuto:02d}")

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "🤖 *ENCRYPTOS BOT v4 Online!*\n\n"
            "🔄 Monitor continuo a cada *3 minutos*\n"
            "🚨 Alertas automaticos score >= 4 estrelas\n\n"
            "📋 Relatorios: 06h | 10h | 12h | 16h | 20h\n\n"
            "/top15 | /varredura | /status | /limpar"
        ),
        parse_mode=ParseMode.MARKDOWN
    )


async def post_shutdown(app: Application):
    log.info("Fechando browser...")
    await scraper_module.fechar_browser()


def main():
    log.info("🚀 Encryptos Bot v4 iniciando...")
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("top15",     cmd_top15))
    app.add_handler(CommandHandler("varredura", cmd_varredura))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("limpar",    cmd_limpar))
    log.info("🤖 Bot aguardando...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
