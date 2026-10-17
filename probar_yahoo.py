"""Prueba automática con datos reales: valúa varios tickers y guarda un informe en resultados.txt."""
import traceback
from dcf_models import Params, route_model, run_scenarios, data_checks
import data_yahoo

TICKERS = ["KO", "AAPL", "AMZN", "JPM", "MET", "O", "TSM", "SAP.DE", "NESN.SW", "ITUB", "V", "XOM"]
out = []
for sym in TICKERS:
    out.append(f"\n===== {sym} =====")
    try:
        co, w = data_yahoo.load_company(sym)
        model, why = route_model(co)
        res = run_scenarios(co, Params(), model)
        out.append(f"{co.name} | {co.industry} | {co.country} | precio {co.price:.2f} {co.currency} | modelo {model}")
        out.append(f"datos: {co.ttm_source} al {co.asof} | ingresos TTM {co.revenue_ttm:,.0f} M | EBIT {co.ebit_ttm:,.0f} M | "
                   f"patrimonio {co.equity} | acciones {co.shares_m:,.0f} M | beta {co.beta}")
        for n in ("Pesimista", "Base", "Optimista"):
            r = res[n]
            out.append(f"  {n}: " + (f"{r.per_share:.2f}  ({r.per_share / co.price - 1:+.0%})" if r.ok else f"NO VALUADO - {r.error}"))
        for x in w + data_checks(co):
            out.append("  aviso: " + x)
    except Exception as e:
        out.append(f"  FALLÓ: {type(e).__name__}: {e}")
        out.append(traceback.format_exc(limit=3))
txt = "\n".join(out)
open("resultados.txt", "w", encoding="utf-8").write(txt)
print(txt)
print("\nListo. Se guardó el archivo resultados.txt: mandamelo.")
