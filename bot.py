"""
ENCRYPTOS BOT — Telegram Analyzer
Modo: monitoramento contínuo a cada 3 minutos + varreduras agendadas
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

# Intervalo de monitoramento contínuo (segundos)
INTERVALO_MONITOR = 180  # 3 minutos

# Horários de relatório completo (independente de ter setup ou não)
HORARIOS_RELATORIO = [
    (6,  0),
    (10, 0),
    (12, 0),
    (16, 0),
    (20, 0),
]

# Score mínimo para disparar alerta no monitoramento contínuo
SCORE_ALERTA = 4  # 4 ou 5 estrelas
# ─────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Controle de alertas já enviados (evita spam do mesmo ativo)
alertas_enviados: dict[str, int] = {}  # symbol -> score do último alerta
COOLDOWN_MINUTOS = 60  # só re-alerta o mesmo ativo após 60 min


async def coletar_e_analisar() -> list:
    """Coleta dados do Encryptos e retorna ranking analisado."""
    scraper = EncryptosScraper(ENCRYPTOS_EMAIL, ENCRYPTOS_PASS)
    dados   = await scraper.coletar_dados()
    if not dados:
        return []
    return EncryptosAnalyzer().analisar(dados)


async def job_monitor(context: ContextTypes.DEFAULT_TYPE):
    """
    Roda a cada 3 minutos.
    Envia alerta APENAS se encontrar setup >= SCORE_ALERTA que ainda não foi alertado.
    """
    try:
        agora  = datetime.now(ZoneInfo(TIMEZONE))
        agora_str = agora.strftime("%d/%m/%Y %H:%M")
        ranking = await coletar_e_analisar()

        novos_alertas = []
        for ativo in ranking:
            sym   = ativo['symbol']
            score = ativo['score']

            if score < SCORE_ALERTA:
                continue

            # Verificar cooldown
            ultimo_score = alertas_enviados.get(sym, 0)
            if ultimo_score == score:
                continue  # já alertado com mesmo score, pular

            novos_alertas.append(ativo)
            alertas_enviados[sym] = score

        if not novos_alertas:
            log.info(f"Monitor [{agora_str}]: sem novos alertas.")
            return

        # Montar e enviar alerta
        linhas = [
            "🚨 *ALERTA ENCRYPTOS — NOVO SETUP!*",
            f"🕐 _{agora_str} (BRT)_",
            "───────────────────────────",
        ]

        elite  = [a for a in novos_alertas if a['score'] == 5]
        forte  = [a for a in novos_alertas if a['score'] == 4]

        if elite:
            linhas.append("\n🔥 *ELITE — OPERAR AGORA*")
            for a in elite:
                linhas.append(formatar_ativo(a))

        if forte:
            linhas.append("\n⚡ *FORTE — QUASE LÁ*")
            for a in forte:
                linhas.append(formatar_ativo(a))

        linhas += ["───────────────────────────", "_Encryptos by Phoenix_"]
        msg = "\n".join(linhas)

        for parte in dividir_mensagem(msg):
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=parte,
                parse_mode=ParseMode.MARKDOWN
            )

        log.info(f"Alerta enviado: {[a['symbol'] for a in novos_alertas]}")

    except Exception as e:
        log.error(f"Erro no monitor: {e}")


async def job_relatorio(context: ContextTypes.DEFAULT_TYPE):
    """
    Roda nos horários fixos.
    Envia relatório completo independente de ter setup ou não.
    """
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()

        if not ranking:
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text="❌ Erro ao acessar painel no relatório agendado."
            )
            return

        msg = formatar_relatorio(ranking, agora_str)
        for parte in dividir_mensagem(msg):
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=parte,
                parse_mode=ParseMode.MARKDOWN
            )

        # Atualizar controle de alertas com o relatório
        for a in ranking:
            if a['score'] >= SCORE_ALERTA:
                alertas_enviados[a['symbol']] = a['score']

        log.info(f"Relatório agendado enviado [{agora_str}]")

    except Exception as e:
        log.error(f"Erro no relatório: {e}")


# ── COMANDOS ──────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟢 *Encryptos Bot Online!*\n\n"
        f"🔄 Monitoramento contínuo a cada *{INTERVALO_MONITOR//60} minutos*\n"
        f"🚨 Alertas automáticos para setups ⭐⭐⭐⭐ e ⭐⭐⭐⭐⭐\n\n"
        "📋 Relatórios completos:\n"
        "• 06:00 | 10:00 | 12:00 | 16:00 | 20:00\n\n"
        "Comandos:\n"
        "/varredura — análise manual agora\n"
        "/status — ver próximos agendamentos\n"
        "/top15 — top 15 oportunidades agora
"        "/limpar — resetar alertas já enviados",
        parse_mode=ParseMode.MARKDOWN
    )


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
    total_alertados = len(alertas_enviados)
    await update.message.reply_text(
        f"✅ *Bot online!*\n\n"
        f"🔄 Monitorando a cada {INTERVALO_MONITOR//60} min\n"
        f"📊 Ativos em cooldown: {total_alertados}\n"
        f"⭐ Score mínimo para alerta: {SCORE_ALERTA}",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alertas_enviados.clear()
    await update.message.reply_text(
        "🗑️ Histórico de alertas limpo!\n"
        "Próximo ciclo vai re-alertar todos os setups qualificados."
    )


async def cmd_top15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retorna as 15 melhores oportunidades do momento com ranking detalhado."""
    msg_espera = await update.message.reply_text("⏳ Buscando as 15 melhores oportunidades agora...")
    try:
        agora_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        ranking   = await coletar_e_analisar()

        if not ranking:
            await msg_espera.edit_text("❌ Erro ao acessar o painel. Tente novamente.")
            return

        top15 = ranking[:15]

        linhas = [
            "🏆 *TOP 15 — MELHORES OPORTUNIDADES AGORA*",
            f"🕐 _{agora_str} (BRT)_",
            "───────────────────────────",
        ]

        medalhas = ["🥇", "🥈", "🥉"]

        for i, a in enumerate(top15):
            medalha = medalhas[i] if i < 3 else f"*#{i+1}*"
            estrelas = "⭐" * a['score']
            s_rsi = "✅" if a['rsi_ok'] else "⚠️"
            s_exp = "✅" if a['exp_ok'] else "⚠️"
            s_lsr = "✅" if a['lsr_ok'] else "⚠️"
            s_oi  = "✅" if a['oi_ok']  else "⚠️"

            # Diagnóstico resumido
            problemas = []
            if not a['rsi_ok']:  problemas.append("RSI")
            if not a['exp_ok']:  problemas.append("EXP")
            if not a['lsr_ok']:  problemas.append("LSR")
            if not a['oi_ok']:   problemas.append("OI")

            if a['score'] == 5:
                status = "🎯 *ENTRAR*"
            elif a['score'] == 4:
                falta = f"Aguardar: {', '.join(problemas)}" if problemas else "Quase lá"
                status = f"⏳ {falta}"
            elif a['score'] == 3:
                falta = f"Falta: {', '.join(problemas)}" if problemas else "Monitorar"
                status = f"👀 {falta}"
            else:
                status = "❌ Sem setup"

            linhas.append(
                f"\n{medalha} *{a['symbol']}* {estrelas}\n"
                f"  RSI 1D:`{a.get('rsi_1d','--')}` 4H:`{a.get('rsi_4h','--')}` 1H:`{a.get('rsi_1h','--')}` {s_rsi}\n"
                f"  EXP 1D:`{a.get('exp_1d','--')}` 4H:`{a.get('exp_4h','--')}` {s_exp}\n"
                f"  LSR:`{a.get('lsr','--')}` {s_lsr} | OI:{s_oi}\n"
                f"  {status} — `{a['symbol']}.P`"
            )

        linhas += ["\n───────────────────────────", "_Encryptos by Phoenix_"]
        msg_final = "\n".join(linhas)

        await msg_espera.delete()
        for parte in dividir_mensagem(msg_final):
            await update.message.reply_text(parte, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg_espera.edit_text(f"❌ Erro: {str(e)[:200]}")


async def post_init(app: Application):
    tz = ZoneInfo(TIMEZONE)

    # Job de monitoramento contínuo
    app.job_queue.run_repeating(
        job_monitor,
        interval=INTERVALO_MONITOR,
        first=10,  # começa 10 segundos após boot
        name="monitor_continuo"
    )
    log.info(f"Monitor contínuo: a cada {INTERVALO_MONITOR}s")

    # Jobs de relatório nos horários fixos
    for hora, minuto in HORARIOS_RELATORIO:
        t = datetime.now(tz).replace(hour=hora, minute=minuto, second=0, microsecond=0).timetz()
        app.job_queue.run_daily(job_relatorio, time=t, name=f"relatorio_{hora:02d}h{minuto:02d}")
        log.info(f"Relatório agendado: {hora:02d}:{minuto:02d}")

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "🟢 *Encryptos Bot Online!*\n\n"
            f"🔄 Monitoramento contínuo a cada *{INTERVALO_MONITOR//60} minutos*\n"
            "🚨 Alertas automáticos quando score ≥ ⭐⭐⭐⭐\n\n"
            "📋 Relatórios completos:\n"
            "• 06:00 | 10:00 | 12:00 | 16:00 | 20:00\n\n"
            "Comandos:\n"
            "/varredura — análise manual\n"
            "/status — ver status\n"
            "/top15 — top 15 oportunidades agora
"        "/limpar — resetar alertas"
        ),
        parse_mode=ParseMode.MARKDOWN
    )


# ── FORMATAÇÃO ────────────────────────────────

def formatar_relatorio(ranking, agora_str, manual=False):
    tipo   = "🖐️ MANUAL" if manual else "⏰ RELATÓRIO"
    linhas = [f"📊 *ENCRYPTOS — {tipo}*", f"🕐 _{agora_str} (BRT)_", "───────────────────────────"]

    elite     = [a for a in ranking if a['score'] == 5]
    forte     = [a for a in ranking if a['score'] == 4]
    watchlist = [a for a in ranking if a['score'] == 3]

    if elite:
        linhas.append("\n🔥 *ELITE — OPERAR AGORA*")
        for a in elite[:5]: linhas.append(formatar_ativo(a))
    if forte:
        linhas.append("\n⚡ *FORTE — QUASE LÁ*")
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
        f"\n*{a['symbol']}* {'⭐'*a['score']}\n"
        f"  RSI 1D:`{a.get('rsi_1d','--')}` 4H:`{a.get('rsi_4h','--')}` 1H:`{a.get('rsi_1h','--')}` {'✅' if a['rsi_ok'] else '⚠️'}\n"
        f"  EXP 1D:`{a.get('exp_1d','--')}` 4H:`{a.get('exp_4h','--')}` {'✅' if a['exp_ok'] else '⚠️'}\n"
        f"  LSR:`{a.get('lsr','--')}` {'✅' if a['lsr_ok'] else '⚠️'} | OI:{'✅' if a['oi_ok'] else '⚠️'}\n"
        f"  {'🎯 *ENTRAR no pullback*' if a['score']==5 else '⏳ Aguardar confirmação'}\n"
        f"  `{a['symbol']}.P`"
    )


def formatar_curto(a):
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
    app.add_handler(CommandHandler("limpar",    cmd_limpar))
    app.add_handler(CommandHandler("top15",     cmd_top15))
    log.info("🤖 Bot aguardando comandos...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
