"""
ENCRYPTOS BOT — Telegram Analyzer
Versão corrigida: usa JobQueue nativo do PTB (sem conflito de event loop)
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
# CONFIGURAÇÕES
# ─────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ENCRYPTOS_EMAIL  = os.environ["ENCRYPTOS_EMAIL"]
ENCRYPTOS_PASS   = os.environ["ENCRYPTOS_PASS"]
TIMEZONE         = "America/Sao_Paulo"

HORARIOS = [
    (6,  0),
    (8,  0),
    (10, 0),
    (10, 30),
    (11, 0),
    (12, 0),
    (13, 0),
    (16, 0),
    (20, 0),
]
# ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


async def executar_varredura(context: ContextTypes.DEFAULT_TYPE, manual: bool = False):
    bot   = context.bot
    agora = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")

    try:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"🔍 *Iniciando varredura Encryptos...*\n_{agora}_",
            parse_mode=ParseMode.MARKDOWN
        )

        scraper = EncryptosScraper(ENCRYPTOS_EMAIL, ENCRYPTOS_PASS)
        dados   = await scraper.coletar_dados()

        if not dados:
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text="❌ Erro ao acessar o painel Encryptos. Tentando na próxima janela."
            )
            return

        analyzer = EncryptosAnalyzer()
        ranking  = analyzer.analisar(dados)
        msg      = formatar_mensagem(ranking, agora, manual)

        for parte in dividir_mensagem(msg):
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=parte,
                parse_mode=ParseMode.MARKDOWN
            )

        log.info("Varredura enviada com sucesso!")

    except Exception as e:
        log.error(f"Erro na varredura: {e}")
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"❌ Erro: `{str(e)[:200]}`",
            parse_mode=ParseMode.MARKDOWN
        )


async def job_varredura(context: ContextTypes.DEFAULT_TYPE):
    await executar_varredura(context, manual=False)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    horarios_txt = "\n".join(f"• {h:02d}:{m:02d}" for h, m in HORARIOS)
    await update.message.reply_text(
        f"🟢 *Encryptos Bot Online!*\n\nVarreduras automáticas (BRT):\n{horarios_txt}\n\n"
        f"Comandos:\n/varredura — análise manual agora\n/status — confirmar se está online",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_varredura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Iniciando varredura manual...")
    await executar_varredura(context, manual=True)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot online e funcionando!")


async def post_init(app: Application):
    tz = ZoneInfo(TIMEZONE)
    for hora, minuto in HORARIOS:
        t = datetime.now(tz).replace(hour=hora, minute=minuto, second=0, microsecond=0).timetz()
        app.job_queue.run_daily(job_varredura, time=t, name=f"varredura_{hora:02d}h{minuto:02d}")
        log.info(f"Job agendado: {hora:02d}:{minuto:02d}")

    log.info(f"✅ {len(HORARIOS)} horários registrados")

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "🟢 *Encryptos Bot Online!*\n\n"
            "Horários de varredura (BRT):\n"
            "• 06:00 — Abertura Londres\n"
            "• 08:00 — Revisão manhã\n"
            "• 10:00 — 🎯 Abertura NY\n"
            "• 10:30 — Overlap máximo\n"
            "• 11:00 — 🎯 Foco institucional\n"
            "• 12:00 — Revisão 4H\n"
            "• 13:00 — Última janela\n"
            "• 16:00 — Tarde\n"
            "• 20:00 — Preparação noturna\n\n"
            "_Envie /varredura para análise manual_"
        ),
        parse_mode=ParseMode.MARKDOWN
    )


def formatar_mensagem(ranking, agora, manual):
    tipo  = "🖐️ MANUAL" if manual else "⏰ AUTOMÁTICA"
    linhas = [f"📊 *ENCRYPTOS — VARREDURA {tipo}*", f"🕐 _{agora} (BRT)_", "───────────────────────────"]

    elite     = [a for a in ranking if a['score'] == 5]
    forte     = [a for a in ranking if a['score'] == 4]
    watchlist = [a for a in ranking if a['score'] == 3]

    if elite:
        linhas.append("\n🔥 *SETUPS ELITE — OPERAR AGORA*")
        for a in elite[:5]: linhas.append(formatar_ativo(a))
    if forte:
        linhas.append("\n⚡ *SETUPS FORTES — QUASE LÁ*")
        for a in forte[:5]: linhas.append(formatar_ativo(a))
    if watchlist:
        linhas.append("\n👀 *WATCHLIST — MONITORAR*")
        for a in watchlist[:5]: linhas.append(formatar_ativo_curto(a))
    if not elite and not forte and not watchlist:
        linhas.append("\n😴 *Nenhum setup qualificado no momento.*")

    linhas += ["───────────────────────────", "_Encryptos by Phoenix_"]
    return "\n".join(linhas)


def formatar_ativo(a):
    return (
        f"\n*{a['symbol']}* {'⭐'*a['score']}\n"
        f"  RSI 1D:`{a.get('rsi_1d','--')}` 4H:`{a.get('rsi_4h','--')}` 1H:`{a.get('rsi_1h','--')}` {'✅' if a['rsi_ok'] else '⚠️'}\n"
        f"  EXP 1D:`{a.get('exp_1d','--')}` 4H:`{a.get('exp_4h','--')}` {'✅' if a['exp_ok'] else '⚠️'}\n"
        f"  LSR:`{a.get('lsr','--')}` {'✅' if a['lsr_ok'] else '⚠️'} | OI:{'✅' if a['oi_ok'] else '⚠️'}\n"
        f"  {'🎯 *ENTRAR no pullback*' if a['score']==5 else '⏳ Aguardar confirmação'}\n"
        f"  `{a['symbol']}.P`"
    )


def formatar_ativo_curto(a):
    return f"  • *{a['symbol']}* {'⭐'*a['score']} — RSI 1D:`{a.get('rsi_1d','--')}` EXP:`{a.get('exp_1d','--')}` LSR:`{a.get('lsr','--')}`"


def dividir_mensagem(msg, limite=4000):
    if len(msg) <= limite: return [msg]
    partes = []
    while msg:
        if len(msg) <= limite: partes.append(msg); break
        corte = msg.rfind('\n', 0, limite)
        if corte == -1: corte = limite
        partes.append(msg[:corte]); msg = msg[corte:]
    return partes


def main():
    log.info("🚀 Encryptos Bot iniciando...")
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("varredura", cmd_varredura))
    app.add_handler(CommandHandler("status",    cmd_status))
    log.info("🤖 Bot aguardando comandos...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
