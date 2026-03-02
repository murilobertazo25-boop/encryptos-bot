"""
╔═══════════════════════════════════════════╗
║     ENCRYPTOS BOT - Telegram Analyzer     ║
║           by Phoenix Method               ║
╚═══════════════════════════════════════════╝

Analisa os 5 pilares do método Encryptos:
1. RSI Momentum (top-down)
2. LSR - Long/Short Ratio
3. Open Interest
4. EXP BTC (força relativa)
5. Trades (atividade institucional)
"""

import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.constants import ParseMode

from scraper import EncryptosScraper
from analyzer import EncryptosAnalyzer

# ─────────────────────────────────────────
# CONFIGURAÇÕES — edite aqui
# ─────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")
ENCRYPTOS_EMAIL  = os.getenv("ENCRYPTOS_EMAIL", "murilo.bertazo25@gmail.com")
ENCRYPTOS_PASS   = os.getenv("ENCRYPTOS_PASS",  "SUA_SENHA_AQUI")
TIMEZONE         = "America/Sao_Paulo"

# Horários de varredura (hora:minuto no fuso de SP)
HORARIOS = [
    (6,  0),   # Abertura Londres
    (8,  0),   # Revisão manhã
    (10, 0),   # 🎯 Abertura NY — mais importante
    (10, 30),  # Overlap máximo
    (11, 0),   # 🎯 Foco institucional
    (12, 0),   # Revisão 4H
    (13, 0),   # Última janela
    (16, 0),   # Tarde
    (20, 0),   # Preparação noturna
]
# ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


async def executar_varredura(manual: bool = False):
    """Executa varredura completa e envia para Telegram."""
    bot = Bot(token=TELEGRAM_TOKEN)
    agora = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")

    try:
        # Aviso de início
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"🔍 *Iniciando varredura Encryptos...*\n_{agora}_",
            parse_mode=ParseMode.MARKDOWN
        )

        # 1. Scraping do painel
        log.info("Iniciando scraping do Encryptos...")
        scraper = EncryptosScraper(ENCRYPTOS_EMAIL, ENCRYPTOS_PASS)
        dados = await scraper.coletar_dados()

        if not dados:
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text="❌ Erro ao acessar o painel Encryptos. Tentando novamente na próxima janela.",
            )
            return

        # 2. Análise dos 5 pilares
        log.info(f"Analisando {len(dados)} ativos...")
        analyzer = EncryptosAnalyzer()
        ranking = analyzer.analisar(dados)

        # 3. Montar mensagem
        msg = formatar_mensagem(ranking, agora, manual)

        # 4. Enviar (dividir se muito longo)
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
            text=f"❌ Erro na varredura: `{str(e)[:200]}`",
            parse_mode=ParseMode.MARKDOWN
        )


def formatar_mensagem(ranking: list, agora: str, manual: bool) -> str:
    """Formata o ranking para envio no Telegram."""
    tipo = "🖐️ MANUAL" if manual else "⏰ AUTOMÁTICA"
    
    linhas = [
        f"📊 *ENCRYPTOS — VARREDURA {tipo}*",
        f"🕐 _{agora} (BRT)_",
        "─" * 30,
    ]

    # Separar por score
    elite    = [a for a in ranking if a['score'] == 5]
    forte    = [a for a in ranking if a['score'] == 4]
    watchlist = [a for a in ranking if a['score'] == 3]

    # ── ELITE ──
    if elite:
        linhas.append("\n🔥 *SETUPS ELITE — OPERAR AGORA*")
        for a in elite[:5]:
            linhas.append(formatar_ativo(a))

    # ── FORTE ──
    if forte:
        linhas.append("\n⚡ *SETUPS FORTES — QUASE LÁ*")
        for a in forte[:5]:
            linhas.append(formatar_ativo(a))

    # ── WATCHLIST ──
    if watchlist:
        linhas.append("\n👀 *WATCHLIST — MONITORAR*")
        for a in watchlist[:5]:
            linhas.append(formatar_ativo_curto(a))

    # ── NENHUM ──
    if not elite and not forte and not watchlist:
        linhas.append("\n😴 *Nenhum setup qualificado no momento.*")
        linhas.append("_Mercado sem confluência. Aguardar próxima janela._")

    linhas.append("\n─" * 30)
    linhas.append("_Encryptos by Phoenix • Uso exclusivo do membro_")

    return "\n".join(linhas)


def formatar_ativo(a: dict) -> str:
    """Formata ativo com detalhes completos."""
    estrelas = "⭐" * a['score']
    status_rsi  = "✅" if a['rsi_ok']  else "⚠️"
    status_exp  = "✅" if a['exp_ok']  else "⚠️"
    status_lsr  = "✅" if a['lsr_ok']  else "⚠️"
    status_oi   = "✅" if a['oi_ok']   else "⚠️"
    
    acao = {
        5: "🎯 *ENTRAR no pullback*",
        4: "⏳ Aguardar confirmação",
        3: "👀 Monitorar",
    }.get(a['score'], "")

    return (
        f"\n*{a['symbol']}* {estrelas}\n"
        f"  RSI 1D: `{a.get('rsi_1d', '--')}` | 4H: `{a.get('rsi_4h', '--')}` | 1H: `{a.get('rsi_1h', '--')}` {status_rsi}\n"
        f"  EXP BTC 1D: `{a.get('exp_1d', '--')}` | 4H: `{a.get('exp_4h', '--')}` {status_exp}\n"
        f"  LSR: `{a.get('lsr', '--')}` {status_lsr} | OI: {status_oi}\n"
        f"  {acao}\n"
        f"  `{a['symbol']}.P`"
    )


def formatar_ativo_curto(a: dict) -> str:
    """Formata ativo resumido para watchlist."""
    estrelas = "⭐" * a['score']
    return (
        f"  • *{a['symbol']}* {estrelas} — "
        f"RSI 1D:`{a.get('rsi_1d','--')}` "
        f"EXP:`{a.get('exp_1d','--')}` "
        f"LSR:`{a.get('lsr','--')}`"
    )


def dividir_mensagem(msg: str, limite: int = 4000) -> list:
    """Divide mensagem longa em partes."""
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


async def main():
    """Inicia o scheduler e mantém o bot rodando."""
    log.info("🚀 Encryptos Bot iniciando...")
    
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "🟢 *Encryptos Bot Online!*\n\n"
            "Horários de varredura automática (BRT):\n"
            "• 06:00 — Abertura Londres\n"
            "• 08:00 — Revisão manhã\n"
            "• 10:00 — 🎯 Abertura NY\n"
            "• 10:30 — Overlap máximo\n"
            "• 11:00 — 🎯 Foco institucional\n"
            "• 12:00 — Revisão 4H\n"
            "• 13:00 — Última janela\n"
            "• 16:00 — Tarde\n"
            "• 20:00 — Preparação noturna\n\n"
            "_Envie /varredura para análise manual a qualquer hora_"
        ),
        parse_mode=ParseMode.MARKDOWN
    )

    # Scheduler
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    for hora, minuto in HORARIOS:
        scheduler.add_job(
            executar_varredura,
            trigger='cron',
            hour=hora,
            minute=minuto,
            name=f"varredura_{hora:02d}h{minuto:02d}"
        )
    scheduler.start()
    log.info(f"✅ Scheduler iniciado com {len(HORARIOS)} horários")

    # Loop principal — responde /varredura manual
    import telegram.ext as ext
    app = ext.Application.builder().token(TELEGRAM_TOKEN).build()

    async def cmd_varredura(update, context):
        await update.message.reply_text("🔍 Iniciando varredura manual...")
        await executar_varredura(manual=True)

    async def cmd_start(update, context):
        await update.message.reply_text(
            "🤖 *Encryptos Bot ativo!*\n\n"
            "Comandos disponíveis:\n"
            "/varredura — análise manual agora\n"
            "/status — verificar se bot está online",
            parse_mode=ParseMode.MARKDOWN
        )

    async def cmd_status(update, context):
        jobs = scheduler.get_jobs()
        proximos = [f"• {j.next_run_time.strftime('%H:%M')}" for j in jobs[:3]]
        await update.message.reply_text(
            f"✅ Bot online!\n"
            f"Próximas varreduras:\n" + "\n".join(proximos),
        )

    app.add_handler(ext.CommandHandler("start",    cmd_start))
    app.add_handler(ext.CommandHandler("varredura", cmd_varredura))
    app.add_handler(ext.CommandHandler("status",   cmd_status))

    log.info("🤖 Bot aguardando comandos...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
