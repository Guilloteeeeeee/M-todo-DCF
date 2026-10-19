"""Control de la moneda de los estados contables (v2.47): para ADRs compara lo que informa Yahoo con lo que calcula la app.
Uso:  python probar_moneda.py        (guarda resultados_moneda.txt: mandamelo)"""
import traceback
from yahooquery import Ticker
import data_yahoo

TICKERS = ["VALE", "PBR", "ITUB", "BBD", "ABEV", "TSM", "ASML", "SAP", "TM", "BABA"]


def _d(x, sym):
    v = x.get(sym) if isinstance(x, dict) else None
    return v if isinstance(v, dict) else {}


out = []
for sym in TICKERS:
    out.append(f"\n===== {sym} =====")
    try:
        t = Ticker(sym, timeout=20)
        sd, ks, fd = _d(t.summary_detail, sym), _d(t.key_stats, sym), _d(t.financial_data, sym)
        out.append(f"Yahoo: financialCurrency={fd.get('financialCurrency')} | precio/ventas={sd.get('priceToSalesTrailing12Months')} | "
                   f"precio/valor libro={ks.get('priceToBook')} | capitalización={sd.get('marketCap')} | ingresos={fd.get('totalRevenue')}")
        co_conv, _ = data_yahoo.load_company(sym, False, None, "convertir")   # confiando en la etiqueta de Yahoo
        co_auto, w = data_yahoo.load_company(sym)                              # con el control automático
        ps = lambda c: (c.market_cap_m / c.revenue_ttm) if c.revenue_ttm else float("nan")
        out.append(f"App confiando en la etiqueta: ingresos {co_conv.revenue_ttm:,.0f} M {co_conv.currency} | precio/ventas {ps(co_conv):.2f} | "
                   f"fx {co_conv.fx:.4f} ({co_conv.fin_currency} -> {co_conv.currency})")
        out.append(f"App con control automático:    ingresos {co_auto.revenue_ttm:,.0f} M {co_auto.currency} | precio/ventas {ps(co_auto):.2f} | "
                   f"fx {co_auto.fx:.4f} | corregida: {'SI' if any('corregida' in x for x in w) else 'no'}")
        for x in w:
            if "Moneda de los estados" in x:
                out.append("  aviso: " + x)
    except Exception as e:  # noqa: BLE001
        out.append(f"  FALLÓ: {type(e).__name__}: {e}")
        out.append(traceback.format_exc(limit=3))
txt = "\n".join(out)
open("resultados_moneda.txt", "w", encoding="utf-8").write(txt)
print(txt)
print("\nListo. Se guardó resultados_moneda.txt: mandamelo.")
