"""
scraper.py — Acessa o painel Encryptos e coleta os dados dos ativos.
Usa Playwright para simular um navegador real.
"""

import asyncio
import logging
from playwright.async_api import async_playwright

log = logging.getLogger(__name__)

class EncryptosScraper:
    URL_LOGIN     = "https://www.encryptos.app/login"
    URL_DASHBOARD = "https://www.encryptos.app/dashboard-beta"

    def __init__(self, email: str, password: str):
        self.email    = email
        self.password = password

    async def coletar_dados(self) -> list[dict]:
        """Faz login, lê o painel e retorna lista de ativos com seus indicadores."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page    = await browser.new_page()

            try:
                # ── LOGIN ──
                log.info("Fazendo login no Encryptos...")
                await page.goto(self.URL_LOGIN, wait_until="networkidle")
                await page.fill('input[type="email"]',    self.email)
                await page.fill('input[type="password"]', self.password)
                await page.click('button[type="submit"]')
                await page.wait_for_url("**/dashboard**", timeout=15000)
                log.info("Login realizado com sucesso!")

                # ── AGUARDAR PAINEL CARREGAR ──
                await page.wait_for_selector("table tbody tr", timeout=20000)
                await asyncio.sleep(3)  # aguardar dados em tempo real

                # ── LER DADOS ──
                log.info("Coletando dados do painel...")
                dados = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('table tbody tr');
                    const ativos = [];
                    
                    rows.forEach((row, idx) => {
                        if (idx >= 20) return; // só os 20 primeiros
                        const cols = row.querySelectorAll('td');
                        if (cols.length < 10) return;
                        
                        const getText = (el) => el ? el.textContent.trim() : '';
                        const getNum  = (el) => {
                            const t = getText(el).replace(',', '.');
                            return isNaN(parseFloat(t)) ? null : parseFloat(t);
                        };

                        // Mapear colunas conforme a view BertasoEXPbtc
                        // Ajuste os índices se necessário conforme o layout do painel
                        const ativo = {
                            symbol:    getText(cols[1]),
                            price:     getNum(cols[2]),
                            
                            // RSI: 1d, 4h, 1h, 30m, 15m, 5m, 1m
                            rsi_1d:  getNum(cols[17]),
                            rsi_4h:  getNum(cols[18]),
                            rsi_1h:  getNum(cols[19]),
                            rsi_30m: getNum(cols[20]),
                            rsi_15m: getNum(cols[21]),
                            rsi_5m:  getNum(cols[22]),
                            rsi_1m:  getNum(cols[23]),
                            
                            // EXP BTC: 1d, 4h, 1h, 30m, 15m, 5m
                            exp_1d:  getNum(cols[24]),
                            exp_4h:  getNum(cols[25]),
                            exp_1h:  getNum(cols[26]),
                            exp_30m: getNum(cols[27]),
                            exp_15m: getNum(cols[28]),
                            exp_5m:  getNum(cols[29]),
                            
                            // LSR e OI
                            lsr:       getNum(cols[13]),
                            lsr_trend: getText(cols[14]),  // ↑ ou ↓
                            oi_trend:  getText(cols[11]),  // ↑ ou ↓
                        };
                        
                        if (ativo.symbol && ativo.symbol !== '') {
                            ativos.push(ativo);
                        }
                    });
                    
                    return ativos;
                }
                """)

                log.info(f"Coletados {len(dados)} ativos do painel.")
                return dados

            except Exception as e:
                log.error(f"Erro no scraper: {e}")
                return []
            finally:
                await browser.close()
