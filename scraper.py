"""
scraper.py — Acessa o painel Encryptos e coleta os dados dos ativos.
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
                # ── LOGIN ──
                log.info("Acessando login Encryptos...")
                await page.goto(self.URL_LOGIN, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                # Preencher email
                await page.wait_for_selector('input[type="email"]', timeout=15000)
                await page.fill('input[type="email"]', self.email)
                await asyncio.sleep(0.5)

                # Preencher senha
                await page.fill('input[type="password"]', self.password)
                await asyncio.sleep(0.5)

                # Clicar no botão de login
                await page.click('button[type="submit"]')
                log.info("Login submetido, aguardando redirecionamento...")

                # Aguardar dashboard carregar
                await page.wait_for_url("**/dashboard**", timeout=20000)
                await asyncio.sleep(4)  # aguardar dados em tempo real carregarem

                log.info("Dashboard carregado, coletando dados...")

                # Aguardar tabela aparecer
                try:
                    await page.wait_for_selector("table tbody tr", timeout=20000)
                except PlaywrightTimeout:
                    log.warning("Tabela nao encontrada, tentando coletar mesmo assim...")

                await asyncio.sleep(2)

                # ── COLETAR DADOS ──
                dados = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('table tbody tr');
                    if (!rows || rows.length === 0) return [];

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

                        const ativo = {
                            symbol:    txt(cols[1]),
                            rsi_1d:    num(cols[17]),
                            rsi_4h:    num(cols[18]),
                            rsi_1h:    num(cols[19]),
                            rsi_30m:   num(cols[20]),
                            rsi_15m:   num(cols[21]),
                            rsi_5m:    num(cols[22]),
                            rsi_1m:    num(cols[23]),
                            exp_1d:    num(cols[24]),
                            exp_4h:    num(cols[25]),
                            exp_1h:    num(cols[26]),
                            exp_30m:   num(cols[27]),
                            exp_15m:   num(cols[28]),
                            exp_5m:    num(cols[29]),
                            lsr:       num(cols[13]),
                            lsr_trend: txt(cols[14]),
                            oi_trend:  txt(cols[11]),
                        };

                        if (ativo.symbol && ativo.symbol.length > 2) {
                            ativos.push(ativo);
                        }
                    });

                    return ativos;
                }
                """)

                log.info(f"Coletados {len(dados)} ativos.")

                # Se nao coletou nada, logar HTML para debug
                if not dados:
                    url_atual = page.url
                    log.warning(f"Nenhum dado coletado. URL atual: {url_atual}")

                return dados

            except PlaywrightTimeout as e:
                log.error(f"Timeout no scraper: {e}")
                return []
            except Exception as e:
                log.error(f"Erro no scraper: {e}")
                return []
            finally:
                await context.close()
                await browser.close()
