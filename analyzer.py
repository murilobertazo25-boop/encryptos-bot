"""
analyzer.py — 5 pilares Encryptos com colunas corretas
Trades = coluna Trades Lv do painel (atividade institucional real)
"""
import logging
log = logging.getLogger(__name__)

RSI_MIN      = 65
RSI_PULLBACK = 50
LSR_MAX      = 1.50


def safe(val):
    try:
        return float(val) if val is not None else None
    except:
        return None


def rsi_status(v):
    if v is None: return "⬜"
    if v >= 70:   return "🟢"
    if v >= 65:   return "🟡"
    if v >= 50:   return "🟠"
    return "🔴"


def exp_status(v):
    if v is None: return "⬜"
    if v >= 50:   return "🟢"
    if v >= 10:   return "🟡"
    if v >= 0:    return "🟠"
    return "🔴"


class EncryptosAnalyzer:

    def analisar(self, dados: list) -> list:
        resultados = [self._analisar_ativo(a) for a in dados if a.get('symbol')]
        resultados.sort(key=lambda x: (x['score'], x.get('exp_1d') or 0), reverse=True)
        return resultados

    def _analisar_ativo(self, a: dict) -> dict:
        score = 0

        # ── PILAR 1: RSI TOP-DOWN ──────────────────────────
        rsi = {
            '1d':  safe(a.get('rsi_1d')),
            '4h':  safe(a.get('rsi_4h')),
            '1h':  safe(a.get('rsi_1h')),
            '30m': safe(a.get('rsi_30m')),
            '15m': safe(a.get('rsi_15m')),
            '5m':  safe(a.get('rsi_5m')),
            '1m':  safe(a.get('rsi_1m')),
        }

        htf_vals   = [rsi['1d'], rsi['4h'], rsi['1h']]
        htf_ok_cnt = sum(1 for v in htf_vals if v is not None and v >= RSI_MIN)
        ltf_vals   = [rsi['15m'], rsi['5m'], rsi['1m']]
        ltf_ok_cnt = sum(1 for v in ltf_vals if v is not None and v >= RSI_MIN)
        total_ok   = sum(1 for v in rsi.values() if v is not None and v >= RSI_MIN)

        rsi_ok = False
        if total_ok >= 5:
            rsi_ok = True; score += 1
        elif htf_ok_cnt >= 2:
            rsi_ok = True; score += 0.5

        # Detectar fase
        htf_forte  = htf_ok_cnt >= 2
        ltf_fraco  = ltf_ok_cnt == 0 and len([v for v in ltf_vals if v is not None]) >= 2
        ltf_caindo = any(v is not None and v < RSI_PULLBACK for v in ltf_vals)

        if htf_forte and ltf_fraco:
            fase = "pullback"
        elif htf_forte and ltf_ok_cnt >= 2:
            fase = "tendencia"
        elif htf_forte and ltf_caindo:
            fase = "correcao_forte"
        elif not htf_forte:
            fase = "fraco"
        else:
            fase = "neutro"

        # ── PILAR 2: LSR ───────────────────────────────────
        lsr       = safe(a.get('lsr_valor'))
        lsr_trend = str(a.get('lsr_trend', ''))   # 'up', 'down', 'neutral'
        lsr_caindo = lsr_trend == 'down'

        lsr_ok = False
        if lsr is not None and lsr < LSR_MAX and lsr_caindo:
            lsr_ok = True; score += 1
        elif lsr is not None and lsr < LSR_MAX:
            lsr_ok = True; score += 0.5

        if lsr is not None:
            if lsr < 0.7:   lsr_label = f"🔥 {lsr:.2f} (shorts extremos)"
            elif lsr < 1.0: lsr_label = f"✅ {lsr:.2f} (shorts dominam)"
            elif lsr < 1.3: lsr_label = f"🟡 {lsr:.2f} (equilibrio)"
            elif lsr < 1.6: lsr_label = f"🟠 {lsr:.2f} (longs elevados)"
            else:            lsr_label = f"🔴 {lsr:.2f} (longs extremos)"
            lsr_label += " ↓" if lsr_caindo else " ↑"
        else:
            lsr_label = "⬜ N/D"

        # ── PILAR 3: OI ────────────────────────────────────
        oi_trend = str(a.get('oi_trend', ''))
        oi_ok    = oi_trend == 'up'
        oi_valor = str(a.get('oi_valor', ''))

        if oi_ok:
            score += 1
            oi_label = f"📈 Subindo ({oi_valor})" if oi_valor else "📈 Subindo"
        else:
            oi_label = f"📉 Neutro/caindo ({oi_valor})" if oi_valor else "📉 Neutro/caindo"

        # ── PILAR 4: EXP BTC ───────────────────────────────
        exp = {
            '1d':  safe(a.get('exp_1d')),
            '4h':  safe(a.get('exp_4h')),
            '1h':  safe(a.get('exp_1h')),
            '30m': safe(a.get('exp_30m')),
            '15m': safe(a.get('exp_15m')),
            '5m':  safe(a.get('exp_5m')),
            '1m':  safe(a.get('exp_1m')),
        }

        exp_ok = False
        e1d = exp['1d']
        if e1d is not None and e1d < 0:
            exp_label = f"🔴 1D:{fmt(e1d)} ELIMINADO"
        elif e1d is not None:
            htf_pos = sum(1 for v in [exp['1d'], exp['4h'], exp['1h']] if v is not None and v > 0)
            if htf_pos >= 3:
                exp_ok = True; score += 1
                exp_label = f"✅ HTFs positivos"
            elif htf_pos >= 2:
                exp_ok = True; score += 0.5
                exp_label = f"🟡 HTFs parciais"
            else:
                exp_label = f"🟠 HTFs fracos"
        else:
            exp_label = "⬜ N/D"

        # ── PILAR 5: TRADES (atividade institucional real) ──
        # Usa a coluna Trades Lv do painel — tlv_5m e tlv_1m
        tlv_15m = safe(a.get('tlv_15m'))
        tlv_5m  = safe(a.get('tlv_5m'))
        tlv_1m  = safe(a.get('tlv_1m'))

        # Volume bruto de trades (confirmacao de liquidez)
        vol_5m  = str(a.get('trades_5m', '')).strip()
        vol_1m  = str(a.get('trades_1m', '')).strip()

        trades_ok = False
        tlv_max = max(v for v in [tlv_15m, tlv_5m, tlv_1m] if v is not None) if any(v is not None for v in [tlv_15m, tlv_5m, tlv_1m]) else 0

        if tlv_max >= 3:
            trades_ok = True; score += 1
            trades_label = f"🔥 Alta atividade inst. (15m:{fmt(tlv_15m)} 5m:{fmt(tlv_5m)} 1m:{fmt(tlv_1m)})"
        elif tlv_max >= 1:
            trades_ok = True; score += 0.5
            trades_label = f"✅ Atividade moderada (15m:{fmt(tlv_15m)} 5m:{fmt(tlv_5m)} 1m:{fmt(tlv_1m)})"
        else:
            trades_label = f"🟡 Baixa atividade (15m:{fmt(tlv_15m)} 5m:{fmt(tlv_5m)} 1m:{fmt(tlv_1m)})"

        # Volume de trades bruto
        vol_label = ""
        if vol_5m or vol_1m:
            vol_label = f" | vol 5m:{vol_5m} 1m:{vol_1m}"
        trades_label += vol_label

        # ── ZONAS OPERACIONAIS ─────────────────────────────
        entrada, tp1, tp2, stop = calcular_zonas(safe(a.get('price')), fase)

        # ── LABELS DE FASE ─────────────────────────────────
        fases = {
            "pullback":       ("🎯", "PULLBACK — aguardar reversão LTFs"),
            "tendencia":      ("🚀", "TENDÊNCIA — momentum ativo"),
            "correcao_forte": ("⚠️", "CORREÇÃO FORTE — aguardar estabilização"),
            "fraco":          ("😴", "FRACO — sem setup"),
            "neutro":         ("🔄", "NEUTRO — em formação"),
        }
        fase_emoji, fase_desc = fases.get(fase, ("🔄", "Em formação"))

        return {
            **a,
            'score':        round(min(score, 5)),
            'rsi_ok':       rsi_ok,
            'lsr_ok':       lsr_ok,
            'oi_ok':        oi_ok,
            'exp_ok':       exp_ok,
            'trades_ok':    trades_ok,
            'fase':         fase,
            'fase_emoji':   fase_emoji,
            'fase_label':   f"{fase_emoji} {fase_desc}",
            'lsr_label':    lsr_label,
            'oi_label':     oi_label,
            'exp_label':    exp_label,
            'trades_label': trades_label,
            'rsi_dict':     rsi,
            'exp_dict':     exp,
            'entrada':      entrada,
            'tp1':          tp1,
            'tp2':          tp2,
            'stop':         stop,
        }


def calcular_zonas(price, fase):
    if not price or price <= 0:
        return None, None, None, None

    if fase == "pullback":
        return (
            round(price * 0.97, 8),
            round(price * 1.05, 8),
            round(price * 1.12, 8),
            round(price * 0.93, 8),
        )
    elif fase == "tendencia":
        return (
            round(price * 0.99, 8),
            round(price * 1.08, 8),
            round(price * 1.18, 8),
            round(price * 0.95, 8),
        )
    elif fase == "correcao_forte":
        return (
            round(price * 0.92, 8),
            round(price * 1.05, 8),
            round(price * 1.10, 8),
            round(price * 0.88, 8),
        )
    return None, None, None, None


def fmt(v):
    if v is None: return "--"
    if isinstance(v, float):
        if v == int(v): return str(int(v))
        return f"{v:.2f}"
    return str(v)
