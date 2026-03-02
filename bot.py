"""
ENCRYPTOS BOT — Telegram Analyzer
Monitoramento continuo a cada 3 minutos + alertas automaticos + /top15
"""

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from scraper import EncryptosScraper
from analyzer import EncryptosAnalyzer

# ─────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ENCRYPTOS_EMAIL  = os.environ["ENCRYPTOS_EMAIL"]
ENCRYPTOS_PASS   = os.environ["ENCRYPTOS_PASS"]
TIMEZONE         = "America/Sao_Paulo"

INTERVALO_MONITOR = 180  # segundos (3 minutos)
SCORE_ALERTA      = 4    # minimo para alertar automaticamente
COOLDOWN_MINUTOS  = 60   # nao re-alerta o mesmo ativo antes desse tempo

HORARIOS_RELATORIO = [
    (6,  0),
    (10, 0),
    (12, 0),
    (16, 0),
    (20, 0),
]
# ─────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

alertas_enviados: dict = {}  # symbol -> score do ultimo alerta


async def coletar_e_analisar() -> list:
    scraper = EncryptosScraper(ENCRYPTOS_EMAIL, ENCRYPTOS_PASS)
    dados   = await scraper.coletar_dados()
    if not dados:
        return []
    return EncryptosAnalyzer().analisar(dados)


async def job_monitor(context: ContextTypes.DEFAULT_TYPE):
    """Roda a cada 3 minutos — alerta so se tiver setup novo qualificado."""
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
            "🚨 *ALERTA ENCRYPTOS — NOVO SETUP!*",
            f"🕐 _{agora_str} (BRT)_",
            "───────────────────────────",
        ]
        for a in [x for x in novos if x['score'] == 5]:
            linhas.append("\n🔥 *ELITE — OPERAR AGORA*")
            linhas.append(formatar_ativo(a))
        for a in [x for x in novos if x['score'] == 4]:
            linhas.append("\n⚡ *FORTE — QUASE LA*")
            linhas.append(formatar_ativo(a))

        linhas += ["───────────────────────────", "_Encryptos by Phoenix_"]

        for parte in dividir_mensagem("\n".join(linhas)):
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=parte, parse_mode=ParseMode.MARKDOWN)

        log.info(f"Alerta enviado: {[a['symbol'] for a in novos]}")

    except Exception as e:
        log.error(f"Erro no monitor: {e}")


async def job_relatorio(context: ContextTypes.DEFAULT_TYPE):
    """Roda nos horarios fixos — relatorio completo."""
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()

        if not ranking:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="Erro ao acessar painel no relatorio agendado.")
            return

        msg = formatar_relatorio(ranking, agora_str)
        for parte in dividir_mensagem(msg):
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=parte, parse_mode=ParseMode.MARKDOWN)

        for a in ranking:
            if a['score'] >= SCORE_ALERTA:
                alertas_enviados[a['symbol']] = a['score']

        log.info(f"Relatorio enviado [{agora_str}]")

    except Exception as e:
        log.error(f"Erro no relatorio: {e}")


# ── COMANDOS ──────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟢 *Encryptos Bot Online!*\n\n"
        "🔄 Monitoramento continuo a cada 3 minutos\n"
        "🚨 Alertas automaticos para setups 4 e 5 estrelas\n\n"
        "📋 Relatorios completos:\n"
        "06:00 | 10:00 | 12:00 | 16:00 | 20:00\n\n"
        "Comandos:\n"
        "/top15 - top 15 oportunidades agora\n"
        "/varredura - analise manual completa\n"
        "/status - ver status do bot\n"
        "/limpar - resetar alertas ja enviados",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_top15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retorna as 15 melhores oportunidades do momento."""
    msg_espera = await update.message.reply_text("⏳ Buscando as 15 melhores oportunidades...")
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()

        if not ranking:
            await msg_espera.edit_text("❌ Erro ao acessar o painel. Tente novamente.")
            return

        top15  = ranking[:15]
        medalhas = ["🥇", "🥈", "🥉"]

        linhas = [
            "🏆 *TOP 15 - MELHORES OPORTUNIDADES AGORA*",
            f"🕐 _{agora_str} (BRT)_",
            "───────────────────────────",
        ]

        for i, a in enumerate(top15):
            medalha  = medalhas[i] if i < 3 else f"*#{i+1}*"
            estrelas = "⭐" * a['score']

            problemas = []
            if not a['rsi_ok']: problemas.append("RSI")
            if not a['exp_ok']: problemas.append("EXP")
            if not a['lsr_ok']: problemas.append("LSR")
            if not a['oi_ok']:  problemas.append("OI")

            if a['score'] == 5:
                status = "🎯 *ENTRAR no pullback*"
            elif a['score'] == 4:
                falta  = ", ".join(problemas) if problemas else "quase la"
                status = f"⏳ Aguardar: {falta}"
            elif a['score'] == 3:
                falta  = ", ".join(problemas) if problemas else "monitorar"
                status = f"👀 Falta: {falta}"
            else:
                status = "❌ Sem setup"

            linhas.append(
                f"\n{medalha} *{a['symbol']}* {estrelas}\n"
                f"  RSI 1D:`{a.get('rsi_1d','--')}` 4H:`{a.get('rsi_4h','--')}` 1H:`{a.get('rsi_1h','--')}` {'✅' if a['rsi_ok'] else '⚠️'}\n"
                f"  EXP 1D:`{a.get('exp_1d','--')}` 4H:`{a.get('exp_4h','--')}` {'✅' if a['exp_ok'] else '⚠️'}\n"
                f"  LSR:`{a.get('lsr','--')}` {'✅' if a['lsr_ok'] else '⚠️'} | OI:{'✅' if a['oi_ok'] else '⚠️'}\n"
                f"  {status}\n"
                f"  `{a['symbol']}.P`"
            )

        linhas += ["\n───────────────────────────", "_Encryptos by Phoenix_"]

        await msg_espera.delete()
        for parte in dividir_mensagem("\n".join(linhas)):
            await update.message.reply_text(parte, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg_espera.edit_text(f"❌ Erro: {str(e)[:200]}")


async def cmd_varredura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Iniciando varredura manual...")
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()
        if not ranking:
            await update.message.reply_text("❌ Erro ao acessar o painel.")
            return
        msg = formatar_relatorio(ranking, agora_str, manual=True)
        for parte in dividir_mensagem(msg):
            await update.message.reply_text(parte, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)[:200]}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"✅ *Bot online!*\n\n"
        f"🔄 Monitorando a cada {INTERVALO_MONITOR // 60} min\n"
        f"📊 Ativos em cooldown: {len(alertas_enviados)}\n"
        f"⭐ Score minimo para alerta: {SCORE_ALERTA}",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alertas_enviados.clear()
    await update.message.reply_text(
        "🗑️ Historico de alertas limpo!\n"
        "Proximo ciclo vai re-alertar todos os setups qualificados."
    )


# ── FORMATACAO ────────────────────────────────────────────

def formatar_relatorio(ranking, agora_str, manual=False):
    tipo   = "🖐️ MANUAL" if manual else "⏰ RELATORIO"
    linhas = [
        f"📊 *ENCRYPTOS - {tipo}*",
        f"🕐 _{agora_str} (BRT)_",
        "───────────────────────────",
    ]
    elite     = [a for a in ranking if a['score'] == 5]
    forte     = [a for a in ranking if a['score'] == 4]
    watchlist = [a for a in ranking if a['score'] == 3]

    if elite:
        linhas.append("\n🔥 *ELITE - OPERAR AGORA*")
        for a in elite[:5]: linhas.append(formatar_ativo(a))
    if forte:
        linhas.append("\n⚡ *FORTE - QUASE LA*")
        for a in forte[:5]: linhas.append(formatar_ativo(a))
    if watchlist:
        linhas.append("\n👀 *WATCHLIST*")
        for a in watchlist[:5]: linhas.append(formatar_curto(a))
    if not elite and not forte and not watchlist:
        linhas.append("\n😴 *Nenhum setup qualificado no momento.*")

    linhas += ["───────────────────────────", "_Encryptos by Phoenix_"]
    return "\n".join(linhas)


def formatar_ativo(a):
    return (
        f"\n*{a['symbol']}* {'⭐' * a['score']}\n"
        f"  RSI 1D:`{a.get('rsi_1d','--')}` 4H:`{a.get('rsi_4h','--')}` 1H:`{a.get('rsi_1h','--')}` {'✅' if a['rsi_ok'] else '⚠️'}\n"
        f"  EXP 1D:`{a.get('exp_1d','--')}` 4H:`{a.get('exp_4h','--')}` {'✅' if a['exp_ok'] else '⚠️'}\n"
        f"  LSR:`{a.get('lsr','--')}` {'✅' if a['lsr_ok'] else '⚠️'} | OI:{'✅' if a['oi_ok'] else '⚠️'}\n"
        f"  {'🎯 *ENTRAR no pullback*' if a['score'] == 5 else '⏳ Aguardar confirmacao'}\n"
        f"  `{a['symbol']}.P`"
    )


def formatar_curto(a):
    return (
        f"  • *{a['symbol']}* {'⭐' * a['score']} "
        f"RSI:`{a.get('rsi_1d','--')}` "
        f"EXP:`{a.get('exp_1d','--')}` "
        f"LSR:`{a.get('lsr','--')}`"
    )


def dividir_mensagem(msg, limite=4000):
    if len(msg) <= limite:
        return [msg]
    partes = []
    while msg:
        if len(msg) <= limite:
            partes.append(msg)
            break
        corte = msg.rfind('\n', 0, limite)
        if corte == -1:
            corte = limite
        partes.append(msg[:corte])
        msg = msg[corte:]
    return partes


# ── INIT ──────────────────────────────────────────────────

async def post_init(app: Application):
    tz = ZoneInfo(TIMEZONE)

    app.job_queue.run_repeating(
        job_monitor,
        interval=INTERVALO_MONITOR,
        first=10,
        name="monitor_continuo"
    )
    log.info(f"Monitor continuo: a cada {INTERVALO_MONITOR}s")

    for hora, minuto in HORARIOS_RELATORIO:
        t = datetime.now(tz).replace(hour=hora, minute=minuto, second=0, microsecond=0).timetz()
        app.job_queue.run_daily(job_relatorio, time=t, name=f"relatorio_{hora:02d}h{minuto:02d}")
        log.info(f"Relatorio agendado: {hora:02d}:{minuto:02d}")

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "🟢 *Encryptos Bot Online!*\n\n"
            "🔄 Monitoramento continuo a cada 3 minutos\n"
            "🚨 Alertas automaticos para setups 4 e 5 estrelas\n\n"
            "📋 Relatorios completos:\n"
            "06:00 | 10:00 | 12:00 | 16:00 | 20:00\n\n"
            "Comandos:\n"
            "/top15 - top 15 oportunidades agora\n"
            "/varredura - analise manual completa\n"
            "/status - ver status do bot\n"
            "/limpar - resetar alertas ja enviados"
        ),
        parse_mode=ParseMode.MARKDOWN
    )


def main():
    log.info("🚀 Encryptos Bot iniciando...")
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("top15",     cmd_top15))
    app.add_handler(CommandHandler("varredura", cmd_varredura))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("limpar",    cmd_limpar))
    log.info("🤖 Bot aguardando comandos...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
