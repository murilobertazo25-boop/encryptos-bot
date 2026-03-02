"""
analyzer.py — Aplica os 5 pilares do método Encryptos em cada ativo.
"""
import logging
log = logging.getLogger(__name__)

RSI_MIN = 65
LSR_MAX = 1.50

def safe(val):
    """Retorna float ou None com segurança."""
    try:
        return float(val) if val is not None else None
    except:
        return None

class EncryptosAnalyzer:

    def analisar(self, dados: list) -> list:
        resultados = [self._analisar_ativo(a) for a in dados if a.get('symbol')]
        resultados.sort(key=lambda x: (x['score'], x.get('exp_1d') or 0), reverse=True)
        return resultados

    def _analisar_ativo(self, a: dict) -> dict:
        score = 0

        # ── PILAR 1: RSI TOP-DOWN ──
        rsi_tfs = [
            safe(a.get('rsi_1d')),
            safe(a.get('rsi_4h')),
            safe(a.get('rsi_1h')),
            safe(a.get('rsi_30m')),
            safe(a.get('rsi_15m')),
            safe(a.get('rsi_5m')),
        ]
        validos      = [v for v in rsi_tfs if v is not None]
        acima_65     = [v for v in validos if v >= RSI_MIN]
        htf_ok       = all((v or 0) >= RSI_MIN for v in rsi_tfs[:3] if v is not None) and len([v for v in rsi_tfs[:3] if v is not None]) >= 2

        rsi_ok = False
        if len(acima_65) >= 5:
            rsi_ok = True; score += 1
        elif htf_ok:
            rsi_ok = True; score += 0.5

        # ── PILAR 2: LSR ──
        lsr       = safe(a.get('lsr'))
        lsr_trend = str(a.get('lsr_trend', ''))
        lsr_caindo = '↓' in lsr_trend or 'down' in lsr_trend.lower()

        lsr_ok = False
        if lsr is not None and lsr < LSR_MAX and lsr_caindo:
            lsr_ok = True; score += 1
        elif lsr is not None and lsr < LSR_MAX:
            lsr_ok = True; score += 0.5

        # ── PILAR 3: OI ──
        oi_trend = str(a.get('oi_trend', ''))
        oi_ok    = '↑' in oi_trend or 'up' in oi_trend.lower()
        if oi_ok:
            score += 1

        # ── PILAR 4: EXP BTC ──
        exp_1d = safe(a.get('exp_1d'))
        exp_4h = safe(a.get('exp_4h'))
        exp_1h = safe(a.get('exp_1h'))

        exp_ok = False
        if exp_1d is not None and exp_1d < 0:
            pass  # eliminado
        elif exp_1d is not None and exp_1d >= 0:
            positivos = sum(1 for v in [exp_1d, exp_4h, exp_1h] if v is not None and v > 0)
            if positivos >= 3:
                exp_ok = True; score += 1
            elif positivos >= 2:
                exp_ok = True; score += 0.5

        # ── PILAR 5: TRADES ──
        trades_ok = rsi_ok and exp_ok
        if trades_ok:
            score += 1

        return {
            **a,
            'score':  round(min(score, 5)),
            'rsi_ok': rsi_ok,
            'lsr_ok': lsr_ok,
            'oi_ok':  oi_ok,
            'exp_ok': exp_ok,
        }
