"""
scraper.py — Coleta dados completos do painel Encryptos
Mapeamento de colunas verificado diretamente no DOM do painel.

MAPA DE COLUNAS CONFIRMADO:
 0: #
 1: Symbol
 2: Price
 3: Price % 1d
 4: Price % 5m
 5: Trades 1d        ← volume de trades
 6: Trades 15m
 7: Trades 5m
 8: Trades 1m
 9: FR
10: OI valor (5m)
11: OI Trend         ← div com class text-green-primary = UP
12: LSR valor (5m)
13: LSR Trend        ← SVG path: 8.25=DOWN, 15.75=UP
14: RSI 1d
15: RSI 4h
16: RSI 1h
17: RSI 30m
18: RSI 15m
19: RSI 5m
20: RSI 1m
21: EXP BTC 1d
22: EXP BTC 4h
23: EXP BTC 1h
24: EXP BTC 30m
25: EXP BTC 15m
26: EXP BTC 5m
27: EXP BTC 1m
28: Trades Lv 1d     ← nível institucional
29: Trades Lv 4h
30: Trades Lv 1h
31: Trades Lv 30m
32: Trades Lv 15m
33: Trades Lv 5m
34: Trades Lv 1m
"""

import asyncio
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger(__name__)


class EncryptosScraper:
    URL_LOGIN     = "https://www.encryptos.app/login"
    URL_DASHBOARD = "https://www.encryptos.app/dashboard-beta"

    def __init__(self, email: str, password: str):
        self.email    = email
        self.password = password

    async def coletar_dados(self) -> list:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                log.info("Fazendo login Encryptos...")
                await page.goto(self.URL_LOGIN, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                await page.wait_for_selector('input[type="email"]', timeout=15000)
                await page.fill('input[type="email"]', self.email)
                await asyncio.sleep(0.5)
                await page.fill('input[type="password"]', self.password)
                await asyncio.sleep(0.5)
                await page.click('button[type="submit"]')

                await page.wait_for_url("**/dashboard**", timeout=20000)
                await asyncio.sleep(5)

                try:
                    await page.wait_for_selector("table tbody tr", timeout=20000)
                except PlaywrightTimeout:
                    log.warning("Tabela demorou, tentando mesmo assim...")

                await asyncio.sleep(2)

                dados = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('table tbody tr');
                    if (!rows || rows.length === 0) return [];

                    const ativos = [];

                    const num = (el) => {
                        if (!el) return null;
                        const t = el.textContent.trim().replace(',', '.');
                        // Converter M/k/b para numero
                        if (t.includes('b')) return parseFloat(t) * 1e9;
                        if (t.includes('m')) return parseFloat(t) * 1e6;
                        if (t.includes('k')) return parseFloat(t) * 1e3;
                        const n = parseFloat(t);
                        return isNaN(n) ? null : n;
                    };

                    const txt = (el) => el ? el.textContent.trim() : '';

                    // OI Trend: div com class text-green-primary = UP
                    const oiTrend = (el) => {
                        if (!el) return 'neutral';
                        const div = el.querySelector('div');
                        if (!div) return 'neutral';
                        return div.className.includes('green') ? 'up' : 'down';
                    };

                    // LSR Trend: SVG path d="M19.5 8.25..." = DOWN, "M4.5 15.75..." = UP
                    const lsrTrend = (el) => {
                        if (!el) return 'neutral';
                        const path = el.querySelector('path');
                        if (!path) return 'neutral';
                        const d = path.getAttribute('d') || '';
                        if (d.includes('8.25')) return 'down';
                        if (d.includes('15.75')) return 'up';
                        return 'neutral';
                    };

                    rows.forEach((row, idx) => {
                        if (idx >= 20) return;
                        const c = row.querySelectorAll('td');
                        if (c.length < 14) return;

                        const symbol = txt(c[1]);
                        if (!symbol || symbol.length < 3) return;

                        ativos.push({
                            symbol: symbol,
                            price:  num(c[2]),

                            // Trades volume (quantidade de operacoes)
                            trades_1d:   txt(c[5]),
                            trades_15m:  txt(c[6]),
                            trades_5m:   txt(c[7]),
                            trades_1m:   txt(c[8]),

                            // Open Interest
                            oi_valor:   txt(c[10]),
                            oi_trend:   oiTrend(c[11]),

                            // Long/Short Ratio
                            lsr_valor:  num(c[12]),
                            lsr_trend:  lsrTrend(c[13]),

                            // RSI por timeframe
                            rsi_1d:   num(c[14]),
                            rsi_4h:   num(c[15]),
                            rsi_1h:   num(c[16]),
                            rsi_30m:  num(c[17]),
                            rsi_15m:  num(c[18]),
                            rsi_5m:   num(c[19]),
                            rsi_1m:   num(c[20]),

                            // EXP BTC por timeframe
                            exp_1d:   num(c[21]),
                            exp_4h:   num(c[22]),
                            exp_1h:   num(c[23]),
                            exp_30m:  num(c[24]),
                            exp_15m:  num(c[25]),
                            exp_5m:   num(c[26]),
                            exp_1m:   num(c[27]),

                            // Trades Level (atividade institucional)
                            tlv_1d:   num(c[28]),
                            tlv_4h:   num(c[29]),
                            tlv_1h:   num(c[30]),
                            tlv_30m:  num(c[31]),
                            tlv_15m:  num(c[32]),
                            tlv_5m:   num(c[33]),
                            tlv_1m:   num(c[34]),
                        });
                    });

                    return ativos;
                }
                """)

                log.info(f"Coletados {len(dados)} ativos.")
                if not dados:
                    log.warning(f"Nenhum dado. URL: {page.url}")
                return dados

            except PlaywrightTimeout as e:
                log.error(f"Timeout: {e}")
                return []
            except Exception as e:
                log.error(f"Erro scraper: {e}")
                return []
            finally:
                await context.close()
                await browser.close()
