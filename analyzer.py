"""
analyzer.py — 5 pilares Encryptos + detecção de pullback + zonas de entrada/saída
"""
import logging

log = logging.getLogger(__name__)

RSI_MIN        = 65
RSI_PULLBACK   = 50   # abaixo disso nos LTFs = pullback
LSR_MAX        = 1.50
SCORE_ALERTA   = 4


def safe(val):
    try:
        return float(val) if val is not None else None
    except:
        return None


def rsi_status(v):
    if v is None:   return "⬜"
    if v >= 70:     return "🟢"
    if v >= 65:     return "🟡"
    if v >= 50:     return "🟠"
    return "🔴"


def exp_status(v):
    if v is None:   return "⬜"
    if v >= 50:     return "🟢"
    if v >= 20:     return "🟡"
    if v >= 0:      return "🟠"
    return "🔴"


def trades_status(v):
    """Avalia atividade institucional nos LTFs."""
    if v is None:   return "⬜"
    if v >= 5:      return "🔥"
    if v >= 2:      return "✅"
    if v >= 1:      return "🟡"
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

        htf_vals    = [v for k, v in rsi.items() if k in ('1d','4h','1h') and v is not None]
        ltf_vals    = [v for k, v in rsi.items() if k in ('15m','5m','1m') and v is not None]
        htf_ok_cnt  = sum(1 for v in htf_vals if v >= RSI_MIN)
        ltf_ok_cnt  = sum(1 for v in ltf_vals if v >= RSI_MIN)
        total_ok    = sum(1 for v in rsi.values() if v is not None and v >= RSI_MIN)

        rsi_ok = False
        if total_ok >= 5:
            rsi_ok = True; score += 1
        elif htf_ok_cnt >= 2:
            rsi_ok = True; score += 0.5

        # Detectar fase do ativo
        htf_forte  = htf_ok_cnt >= 2
        ltf_fraco  = all(v < RSI_MIN for v in ltf_vals if v is not None) and len(ltf_vals) >= 2
        ltf_caindo = any(v < RSI_PULLBACK for v in ltf_vals if v is not None)

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
        lsr       = safe(a.get('lsr_valor') or a.get('lsr'))
        lsr_trend = str(a.get('lsr_trend', ''))
        lsr_caindo = 'down' in lsr_trend.lower() or '↓' in lsr_trend

        lsr_ok = False
        if lsr is not None and lsr < LSR_MAX and lsr_caindo:
            lsr_ok = True; score += 1
        elif lsr is not None and lsr < LSR_MAX:
            lsr_ok = True; score += 0.5

        # Interpretar LSR
        if lsr is not None:
            if lsr < 0.7:    lsr_label = f"🔥 {lsr:.2f} (shorts extremos)"
            elif lsr < 1.0:  lsr_label = f"✅ {lsr:.2f} (shorts dominam)"
            elif lsr < 1.3:  lsr_label = f"🟡 {lsr:.2f} (neutro)"
            elif lsr < 1.6:  lsr_label = f"🟠 {lsr:.2f} (longs elevados)"
            else:             lsr_label = f"🔴 {lsr:.2f} (longs extremos)"
            lsr_seta = "↓" if lsr_caindo else "↑"
            lsr_label += f" {lsr_seta}"
        else:
            lsr_label = "N/D"

        # ── PILAR 3: OI ────────────────────────────────────
        oi_trend = str(a.get('oi_trend', ''))
        oi_ok    = 'up' in oi_trend.lower() or '↑' in oi_trend
        oi_valor = safe(a.get('oi_valor'))

        if oi_ok:
            score += 1
            oi_label = f"📈 Subindo"
        else:
            oi_label = f"📉 Caindo/neutro"

        if oi_valor:
            if oi_valor >= 1_000_000:
                oi_label += f" ({oi_valor/1_000_000:.1f}M)"
            elif oi_valor >= 1_000:
                oi_label += f" ({oi_valor/1_000:.0f}k)"

        # ── PILAR 4: EXP BTC ───────────────────────────────
        exp = {
            '1d':  safe(a.get('exp_1d')),
            '4h':  safe(a.get('exp_4h')),
            '1h':  safe(a.get('exp_1h')),
            '30m': safe(a.get('exp_30m')),
            '15m': safe(a.get('exp_15m')),
            '5m':  safe(a.get('exp_5m')),
        }

        exp_ok = False
        if exp['1d'] is not None and exp['1d'] < 0:
            exp_label = f"🔴 1D:{exp['1d']} (ELIMINADO)"
        elif exp['1d'] is not None:
            pos = sum(1 for v in [exp['1d'], exp['4h'], exp['1h']] if v is not None and v > 0)
            if pos >= 3:
                exp_ok = True; score += 1
                exp_label = f"✅ Positivo HTFs"
            elif pos >= 2:
                exp_ok = True; score += 0.5
                exp_label = f"🟡 Parcial HTFs"
            else:
                exp_label = f"🟠 Fraco HTFs"
        else:
            exp_label = "⬜ N/D"

        # ── PILAR 5: TRADES (atividade institucional) ──────
        tv_5m = safe(a.get('trades_lv_5m'))
        tv_1m = safe(a.get('trades_lv_1m'))

        trades_ok = False
        if rsi_ok and exp_ok:
            trades_ok = True; score += 1

        # Interpretar atividade institucional nos LTFs
        if tv_5m is not None and tv_1m is not None:
            if tv_5m >= 3 or tv_1m >= 3:
                trades_label = f"🔥 Alta atividade (5m:{tv_5m} 1m:{tv_1m})"
            elif tv_5m >= 1 or tv_1m >= 1:
                trades_label = f"✅ Atividade moderada (5m:{tv_5m} 1m:{tv_1m})"
            else:
                trades_label = f"🟡 Baixa atividade (5m:{tv_5m} 1m:{tv_1m})"
        elif rsi_ok and exp_ok:
            trades_label = "✅ Confirmado por RSI+EXP"
        else:
            trades_label = "⚠️ Sem confirmação"

        # ── ZONAS DE ENTRADA E SAÍDA ───────────────────────
        entrada, saida_1, saida_2, stop = calcular_zonas(a, fase, rsi, exp)

        # ── DIAGNÓSTICO DA FASE ────────────────────────────
        if fase == "pullback":
            fase_label = "🎯 PULLBACK — aguardar reversão LTFs"
            fase_emoji = "🎯"
        elif fase == "tendencia":
            fase_label = "🚀 TENDÊNCIA — momentum ativo"
            fase_emoji = "🚀"
        elif fase == "correcao_forte":
            fase_label = "⚠️ CORREÇÃO FORTE — aguardar estabilização"
            fase_emoji = "⚠️"
        elif fase == "fraco":
            fase_label = "😴 FRACO — sem setup"
            fase_emoji = "😴"
        else:
            fase_label = "🔄 NEUTRO — em formação"
            fase_emoji = "🔄"

        return {
            **a,
            'score':         round(min(score, 5)),
            'rsi_ok':        rsi_ok,
            'lsr_ok':        lsr_ok,
            'oi_ok':         oi_ok,
            'exp_ok':        exp_ok,
            'trades_ok':     trades_ok,
            'fase':          fase,
            'fase_label':    fase_label,
            'fase_emoji':    fase_emoji,
            'lsr_label':     lsr_label,
            'oi_label':      oi_label,
            'exp_label':     exp_label,
            'trades_label':  trades_label,
            'rsi_dict':      rsi,
            'exp_dict':      exp,
            'entrada':       entrada,
            'saida_1':       saida_1,
            'saida_2':       saida_2,
            'stop':          stop,
        }


def calcular_zonas(a, fase, rsi, exp):
    """Estima zonas de entrada, alvos e stop baseado na fase."""
    price = safe(a.get('price'))
    if not price or price <= 0:
        return None, None, None, None

    # Heurísticas baseadas na metodologia Encryptos
    # Valores aproximados — refinados com a estrutura do ativo
    if fase == "pullback":
        # Pullback saudável: entrada no suporte, alvos conservadores
        entrada = round(price * 0.97, 6)   # 3% abaixo (zona de suporte esperada)
        saida_1 = round(price * 1.05, 6)   # +5% (TP1)
        saida_2 = round(price * 1.12, 6)   # +12% (TP2)
        stop    = round(price * 0.93, 6)   # -7% (SL)

    elif fase == "tendencia":
        # Tendência ativa: entrada agora ou no próximo recuo
        entrada = round(price * 0.99, 6)   # entrada próxima
        saida_1 = round(price * 1.08, 6)   # +8%
        saida_2 = round(price * 1.18, 6)   # +18%
        stop    = round(price * 0.95, 6)   # -5%

    elif fase == "correcao_forte":
        # Correção: aguardar mais fundo, alvos menores
        entrada = round(price * 0.92, 6)   # -8% (ainda pode cair)
        saida_1 = round(price * 1.05, 6)   # +5%
        saida_2 = round(price * 1.10, 6)   # +10%
        stop    = round(price * 0.88, 6)   # -12%

    else:
        return None, None, None, None

    return entrada, saida_1, saida_2, stop
