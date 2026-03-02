"""
scraper.py — Coleta dados completos do painel Encryptos
Captura: RSI todos TFs, EXP BTC todos TFs, LSR valor+trend, OI valor+trend, Trades 5m/1m
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
                log.info("Acessando login Encryptos...")
                await page.goto(self.URL_LOGIN, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                await page.wait_for_selector('input[type="email"]', timeout=15000)
                await page.fill('input[type="email"]', self.email)
                await asyncio.sleep(0.5)
                await page.fill('input[type="password"]', self.password)
                await asyncio.sleep(0.5)
                await page.click('button[type="submit"]')

                log.info("Aguardando dashboard...")
                await page.wait_for_url("**/dashboard**", timeout=20000)
                await asyncio.sleep(5)

                try:
                    await page.wait_for_selector("table tbody tr", timeout=20000)
                except PlaywrightTimeout:
                    log.warning("Tabela demorou, tentando mesmo assim...")

                await asyncio.sleep(2)

                # Capturar headers para mapear colunas dinamicamente
                dados = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('table tbody tr');
                    if (!rows || rows.length === 0) return [];

                    // Capturar headers
                    const headerEls = document.querySelectorAll('table thead th');
                    const headers = Array.from(headerEls).map(h => h.textContent.trim().toLowerCase());

                    const ativos = [];

                    rows.forEach((row, idx) => {
                        if (idx >= 20) return;
                        const cols = row.querySelectorAll('td');
                        if (cols.length < 10) return;

                        const txt = (el) => el ? el.textContent.trim() : '';
                        const num = (el) => {
                            if (!el) return null;
                            const t = el.textContent.trim().replace(',', '.');
                            const n = parseFloat(t);
                            return isNaN(n) ? null : n;
                        };
                        // Pegar seta/trend de um elemento (up/down arrow unicode)
                        const trend = (el) => {
                            if (!el) return '';
                            const t = el.textContent.trim();
                            if (t.includes('↑') || t.includes('▲') || t.includes('up')) return 'up';
                            if (t.includes('↓') || t.includes('▼') || t.includes('down')) return 'down';
                            // Verificar cor (verde=up, vermelho=down)
                            const style = el.style.color || '';
                            const cls = el.className || '';
                            if (style.includes('green') || cls.includes('green') || cls.includes('up')) return 'up';
                            if (style.includes('red') || cls.includes('red') || cls.includes('down')) return 'down';
                            return '';
                        };

                        // Tentar pegar o valor numérico de OI e LSR
                        const getOIValue = (el) => {
                            if (!el) return null;
                            const t = el.textContent.trim().replace(',', '.');
                            // Converter M/k para numero
                            if (t.includes('M')) return parseFloat(t) * 1000000;
                            if (t.includes('k')) return parseFloat(t) * 1000;
                            return parseFloat(t) || null;
                        };

                        const ativo = {
                            symbol:      txt(cols[1]),
                            price:       num(cols[2]),

                            // Trades volume
                            trades_1d:   txt(cols[5]),   // volume 1d
                            trades_1h:   txt(cols[6]),
                            trades_30m:  txt(cols[7]),
                            trades_15m:  txt(cols[8]),
                            trades_5m:   txt(cols[9]),
                            trades_1m:   txt(cols[10]),  // ajustar se necessario

                            // OI
                            oi_valor:    getOIValue(cols[10]),
                            oi_trend:    trend(cols[11]),

                            // LSR
                            lsr_valor:   num(cols[13]),
                            lsr_trend:   trend(cols[14]),

                            // RSI (1d, 4h, 1h, 30m, 15m, 5m, 1m)
                            rsi_1d:      num(cols[17]),
                            rsi_4h:      num(cols[18]),
                            rsi_1h:      num(cols[19]),
                            rsi_30m:     num(cols[20]),
                            rsi_15m:     num(cols[21]),
                            rsi_5m:      num(cols[22]),
                            rsi_1m:      num(cols[23]),

                            // EXP BTC (1d, 4h, 1h, 30m, 15m, 5m, 1m)
                            exp_1d:      num(cols[24]),
                            exp_4h:      num(cols[25]),
                            exp_1h:      num(cols[26]),
                            exp_30m:     num(cols[27]),
                            exp_15m:     num(cols[28]),
                            exp_5m:      num(cols[29]),
                            exp_1m:      num(cols[30]),

                            // Trades Lv (atividade institucional)
                            trades_lv_1d:  num(cols[31]),
                            trades_lv_1h:  num(cols[32]),
                            trades_lv_30m: num(cols[33]),
                            trades_lv_15m: num(cols[34]),
                            trades_lv_5m:  num(cols[35]),
                            trades_lv_1m:  num(cols[36]),
                        };

                        if (ativo.symbol && ativo.symbol.length > 2) {
                            ativos.push(ativo);
                        }
                    });

                    return ativos;
                }
                """)

                log.info(f"Coletados {len(dados)} ativos.")
                if not dados:
                    log.warning(f"URL atual: {page.url}")
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
