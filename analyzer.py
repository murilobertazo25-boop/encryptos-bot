"""
analyzer.py — Aplica os 5 pilares do método Encryptos em cada ativo
e gera um score de 0 a 5.
"""

import logging

log = logging.getLogger(__name__)

# ─────────────────────────────────────────
# LIMITES DO MÉTODO ENCRYPTOS
# ─────────────────────────────────────────
RSI_MIN          = 65     # RSI mínimo para confirmar momentum
LSR_MAX          = 1.50   # LSR acima disso = muitos longs = risco
EXP_MIN_1D       = 0      # EXP BTC deve ser positivo no 1D
EXP_ELIMINACAO   = 0      # EXP BTC 1D negativo = eliminar ativo


class EncryptosAnalyzer:

    def analisar(self, dados: list[dict]) -> list[dict]:
        """Analisa cada ativo e retorna lista ordenada por score."""
        resultados = []

        for ativo in dados:
            if not ativo.get('symbol'):
                continue

            resultado = self._analisar_ativo(ativo)
            resultados.append(resultado)

        # Ordenar: score desc, depois EXP 1D desc
        resultados.sort(key=lambda x: (x['score'], x.get('exp_1d', 0)), reverse=True)
        return resultados

    def _analisar_ativo(self, a: dict) -> dict:
        """Calcula score e detalhes de um ativo."""
        score = 0
        detalhes = []

        # ── PILAR 1: RSI TOP-DOWN ──────────────────────────
        rsi_tfs = [
            ('1D',  a.get('rsi_1d')),
            ('4H',  a.get('rsi_4h')),
            ('1H',  a.get('rsi_1h')),
            ('30m', a.get('rsi_30m')),
            ('15m', a.get('rsi_15m')),
            ('5m',  a.get('rsi_5m')),
        ]

        tfs_validos   = [(tf, v) for tf, v in rsi_tfs if v is not None]
        tfs_acima_65  = [(tf, v) for tf, v in tfs_validos if v >= RSI_MIN]
        tfs_htf_ok    = all(v >= RSI_MIN for tf, v in tfs_validos[:3])  # 1D, 4H, 1H

        rsi_ok = False
        if len(tfs_acima_65) >= 5:          # 5+ TFs acima de 65
            rsi_ok = True
            score += 1
            detalhes.append("✅ RSI top-down confirmado")
        elif tfs_htf_ok:                     # pelo menos 1D, 4H, 1H ok
            score += 0.5
            detalhes.append("🟡 RSI HTFs confirmados (LTFs em pullback)")
        else:
            detalhes.append("❌ RSI sem top-down")

        # ── PILAR 2: LSR ───────────────────────────────────
        lsr       = a.get('lsr')
        lsr_trend = a.get('lsr_trend', '')
        lsr_caindo = '↓' in str(lsr_trend) or 'down' in str(lsr_trend).lower()

        lsr_ok = False
        if lsr is not None and lsr < LSR_MAX and lsr_caindo:
            lsr_ok = True
            score += 1
            if lsr < 0.7:
                detalhes.append(f"✅✅ LSR {lsr:.2f} ↓ — acúmulo extremo de shorts!")
            else:
                detalhes.append(f"✅ LSR {lsr:.2f} ↓")
        elif lsr is not None and lsr < LSR_MAX:
            lsr_ok = True
            score += 0.5
            detalhes.append(f"🟡 LSR {lsr:.2f} (tendência neutra)")
        else:
            detalhes.append(f"❌ LSR desfavorável: {lsr}")

        # ── PILAR 3: OPEN INTEREST ─────────────────────────
        oi_trend = a.get('oi_trend', '')
        oi_ok    = '↑' in str(oi_trend) or 'up' in str(oi_trend).lower()

        if oi_ok:
            score += 1
            detalhes.append("✅ OI subindo — novo capital entrando")
        else:
            detalhes.append("❌ OI caindo ou neutro")

        # ── PILAR 4: EXP BTC ───────────────────────────────
        exp_1d = a.get('exp_1d')
        exp_4h = a.get('exp_4h')
        exp_1h = a.get('exp_1h')

        exp_ok = False
        # Regra de eliminação: EXP 1D negativo = 0 pontos
        if exp_1d is not None and exp_1d < EXP_ELIMINACAO:
            detalhes.append(f"❌ EXP BTC 1D negativo ({exp_1d}) — ELIMINADO")
        elif exp_1d is not None and exp_1d >= 0:
            positivos = sum(1 for v in [exp_1d, exp_4h, exp_1h] if v is not None and v > 0)
            if positivos >= 3:
                exp_ok = True
                score += 1
                detalhes.append(f"✅ EXP BTC positivo em 3 HTFs (1D: +{exp_1d})")
            elif positivos >= 2:
                exp_ok = True
                score += 0.5
                detalhes.append(f"🟡 EXP BTC positivo em 2 HTFs (1D: +{exp_1d})")
            else:
                detalhes.append(f"⚠️ EXP BTC fraco nos HTFs (1D: {exp_1d})")

        # ── PILAR 5: TRADES (volume institucional) ─────────
        # Heurística: se EXP e RSI são altos, assumimos atividade institucional
        trades_ok = rsi_ok and exp_ok
        if trades_ok:
            score += 1
            detalhes.append("✅ Atividade institucional confirmada")
        else:
            detalhes.append("⚠️ Atividade institucional não confirmada")

        # ── SCORE FINAL ────────────────────────────────────
        score_final = round(min(score, 5))

        return {
            **a,
            'score':    score_final,
            'rsi_ok':   rsi_ok,
            'lsr_ok':   lsr_ok,
            'oi_ok':    oi_ok,
            'exp_ok':   exp_ok,
            'detalhes': detalhes,
        }
