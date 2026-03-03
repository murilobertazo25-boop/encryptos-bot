"""
scraper.py — Encryptos Scraper com browser persistente
Mantém UMA instância do Chromium aberta e reutiliza entre varreduras.
Isso resolve o Errno 11 (falta de memória no Railway free tier).
"""

import asyncio
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)

# ── Instância global do browser (reutilizada entre chamadas) ──
_playwright = None
_browser: Browser = None
_page: Page = None
_logged_in: bool = False


async def get_page() -> Page:
    """Retorna a página existente ou cria uma nova."""
    global _playwright, _browser, _page, _logged_in

    # Iniciar playwright se necessário
    if _playwright is None:
        _playwright = await async_playwright().start()

    # Iniciar browser se necessário ou se crashou
    if _browser is None or not _browser.is_connected():
        log.info("Iniciando browser Chromium...")
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--single-process",           # economiza memória no Railway
                "--memory-pressure-off",
            ]
        )
        _page = None
        _logged_in = False

    # Criar página se necessário
    if _page is None or _page.is_closed():
        context = await _browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        _page = await context.new_page()
        _logged_in = False

    return _page


async def fazer_login(page: Page, email: str, password: str) -> bool:
    """Faz login e retorna True se bem sucedido."""
    global _logged_in
    try:
        log.info("Fazendo login...")
        await page.goto("https://www.encryptos.app/login", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        await page.wait_for_selector('input[type="email"]', timeout=15000)
        await page.fill('input[type="email"]', email)
        await asyncio.sleep(0.5)
        await page.fill('input[type="password"]', password)
        await asyncio.sleep(0.5)
        await page.click('button[type="submit"]')
        await page.wait_for_url("**/dashboard**", timeout=20000)
        await asyncio.sleep(4)

        _logged_in = True
        log.info("Login OK.")
        return True
    except Exception as e:
        log.error(f"Erro no login: {e}")
        _logged_in = False
        return False


async def coletar_dados(email: str, password: str) -> list:
    """Coleta dados do painel. Reutiliza browser e sessão já logada."""
    global _logged_in, _page

    for tentativa in range(2):
        try:
            page = await get_page()

            # Fazer login se necessário
            if not _logged_in:
                ok = await fazer_login(page, email, password)
                if not ok:
                    return []

            # Navegar para o dashboard se não estiver lá
            if "dashboard" not in page.url:
                await page.goto("https://www.encryptos.app/dashboard-beta",
                               wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
            else:
                # Apenas recarregar os dados sem navegar
                await page.reload(wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)

            # Aguardar tabela
            try:
                await page.wait_for_selector("table tbody tr", timeout=15000)
            except PlaywrightTimeout:
                log.warning("Tabela demorou, tentando coletar...")

            await asyncio.sleep(1)

            dados = await page.evaluate("""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                if (!rows || rows.length === 0) return [];

                const num = (el) => {
                    if (!el) return null;
                    const t = el.textContent.trim().replace(',', '.');
                    if (t.includes('b')) return parseFloat(t) * 1e9;
                    if (t.includes('m')) return parseFloat(t) * 1e6;
                    if (t.includes('k')) return parseFloat(t) * 1e3;
                    const n = parseFloat(t);
                    return isNaN(n) ? null : n;
                };
                const txt = (el) => el ? el.textContent.trim() : '';

                const oiTrend = (el) => {
                    if (!el) return 'neutral';
                    const div = el.querySelector('div');
                    return div && div.className.includes('green') ? 'up' : 'down';
                };

                const lsrTrend = (el) => {
                    if (!el) return 'neutral';
                    const path = el.querySelector('path');
                    if (!path) return 'neutral';
                    const d = path.getAttribute('d') || '';
                    if (d.includes('8.25'))  return 'down';
                    if (d.includes('15.75')) return 'up';
                    return 'neutral';
                };

                const ativos = [];
                rows.forEach((row, idx) => {
                    if (idx >= 20) return;
                    const c = row.querySelectorAll('td');
                    if (c.length < 14) return;
                    const symbol = txt(c[1]);
                    if (!symbol || symbol.length < 3) return;

                    ativos.push({
                        symbol:      symbol,
                        price:       num(c[2]),
                        trades_1d:   txt(c[5]),
                        trades_15m:  txt(c[6]),
                        trades_5m:   txt(c[7]),
                        trades_1m:   txt(c[8]),
                        oi_valor:    txt(c[10]),
                        oi_trend:    oiTrend(c[11]),
                        lsr_valor:   num(c[12]),
                        lsr_trend:   lsrTrend(c[13]),
                        rsi_1d:      num(c[14]),
                        rsi_4h:      num(c[15]),
                        rsi_1h:      num(c[16]),
                        rsi_30m:     num(c[17]),
                        rsi_15m:     num(c[18]),
                        rsi_5m:      num(c[19]),
                        rsi_1m:      num(c[20]),
                        exp_1d:      num(c[21]),
                        exp_4h:      num(c[22]),
                        exp_1h:      num(c[23]),
                        exp_30m:     num(c[24]),
                        exp_15m:     num(c[25]),
                        exp_5m:      num(c[26]),
                        exp_1m:      num(c[27]),
                        tlv_1d:      num(c[28]),
                        tlv_4h:      num(c[29]),
                        tlv_1h:      num(c[30]),
                        tlv_30m:     num(c[31]),
                        tlv_15m:     num(c[32]),
                        tlv_5m:      num(c[33]),
                        tlv_1m:      num(c[34]),
                    });
                });
                return ativos;
            }
            """)

            if dados:
                log.info(f"Coletados {len(dados)} ativos.")
                return dados

            # Se não coletou nada, pode ser que a sessão expirou
            log.warning("Nenhum dado coletado, tentando re-login...")
            _logged_in = False

        except Exception as e:
            log.error(f"Erro tentativa {tentativa+1}: {e}")
            # Resetar página para próxima tentativa
            _page = None
            _logged_in = False
            if tentativa == 0:
                await asyncio.sleep(3)

    return []


async def fechar_browser():
    """Fecha o browser (usar apenas no shutdown)."""
    global _playwright, _browser, _page, _logged_in
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()
    _browser = None
    _playwright = None
    _page = None
    _logged_in = False
