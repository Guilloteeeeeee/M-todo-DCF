"""v2.48 · Mapa de métodos: otras formas de mirar el valor de una empresa, al lado de nuestro DCF.

NADA de esto cambia el valor del modelo (método 1): usa el resultado Base ya calculado y datos de Yahoo / Damodaran.
Solo se aplica a empresas valuadas por FCFF (no financieras ni REIT).

Métodos (valor por acción, en la moneda de cotización):
  1. Nuestro DCF a 10 años (el de siempre).
  2. Nuestro DCF a 5 años: los flujos de los años 1-5 del modelo + valor al año 5 con el múltiplo EV/EBITDA de la industria (Damodaran).
  3. Estilo Dorsey: flujo de caja libre real × crecimiento constante 10 años + perpetuidad de 3 % (libro de Dorsey, modelo de Clorox).
  4. Múltiplos de la industria hoy: EV/EBITDA de la industria (Damodaran) × EBITDA de la empresa.
  5. Estilo Alpha (aproximación NUESTRA, circular): igual que el 2 pero con el múltiplo EV/EBIT que el mercado paga HOY por la empresa.
Además, el «panel a 5 años»: qué valdría la empresa en 5 años, el retorno anual si comprás hoy, y el múltiplo que hace falta en 5 años
para ganar el costo de capital.
Simplificación: se supone que todo el flujo libre llega al accionista y que la deuda neta y las acciones no cambian."""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from industry_multiples import MULT_DATE, MULT_MIN_MUESTRA, get_multiples

DORSEY_R_MIN = 0.09        # tasa de descuento de Dorsey para una empresa estable y sólida (Clorox); si el costo del capital propio del modelo es mayor, se usa ese
DORSEY_G_TERMINAL = 0.03   # Dorsey: ~ crecimiento del PBI de EE.UU.
DORSEY_G_DEFAULT = 0.05    # Dorsey (Clorox): crecimiento constante prudente
DORSEY_G_RANGE = (0.05, 0.07, 0.09)
DORSEY_YEARS = 10

KEYS = ("m1", "m2", "m3", "m4", "m5")
NAMES = {
    "m1": "1. Nuestro DCF a 10 años",
    "m2": "2. Nuestro DCF a 5 años (salida con múltiplo de la industria)",
    "m3": "3. Estilo Dorsey (flujo de caja libre)",
    "m4": "4. Múltiplos de la industria hoy (Damodaran)",
    "m5": "5. Estilo Alpha: 5 años, salida con el múltiplo de hoy (circular)",
}


def dorsey_value(fcf0: float, shares_m: float, g: float, R: float, g_term: float = DORSEY_G_TERMINAL,
                 years: int = DORSEY_YEARS) -> Optional[float]:
    """Modelo simple de Dorsey (cap. 10): flujo del año 1 = flujo actual × (1+g), crece g durante `years` años, después perpetuidad g_term.
    Valor por acción = (flujos descontados + perpetuidad descontada) / acciones. None si los datos no sirven."""
    if not fcf0 or fcf0 <= 0 or not shares_m or shares_m <= 0 or R <= g_term:
        return None
    f, pv = fcf0, 0.0
    for t in range(1, years + 1):
        f *= (1 + g)
        pv += f / (1 + R) ** t
    tv = f * (1 + g_term) / (R - g_term) / (1 + R) ** years
    return (pv + tv) / shares_m


def _irr(cfs: List[float]) -> Optional[float]:
    f = lambda r: sum(cf / (1 + r) ** i for i, cf in enumerate(cfs))
    lo, hi = -0.9, 1.0
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _item(key, valor, price, nota="", rango=None, circular=False, extra=None):
    d = dict(key=key, nombre=NAMES[key], valor=valor, rango=rango, nota=nota, circular=circular,
             ratio=(valor / price if (valor is not None and price) else None),
             ratio_rango=((rango[0] / price, rango[1] / price) if (rango and price) else None))
    if extra:
        d.update(extra)
    return d


def methods_map(co, res, model: str = "FCFF", dorsey_g: float = DORSEY_G_DEFAULT, dorsey_R: Optional[float] = None) -> Dict:
    """co: empresa YA con la industria cargada (idt.attach); res: resultado Base del modelo (ValResult); model: modelo usado.
    Devuelve {'applicable', 'reason', 'items': [...5 métodos...], 'panel': {...} o None, 'notas': [...], 'rango': (min, max) o None}."""
    out = dict(applicable=False, reason="", items=[], panel=None, notas=[], rango=None)
    if model != "FCFF":
        out["reason"] = "Solo se calcula para empresas valuadas por flujo libre (FCFF); este modelo es " + str(model) + "."
        return out
    if res is None or not getattr(res, "ok", False) or not res.table or not co.price or co.price <= 0 or not co.shares_m:
        out["reason"] = "El modelo no pudo calcular el valor base: no hay con qué armar el mapa."
        return out
    out["applicable"] = True
    ex, tb, price, sh = res.extras or {}, res.table, co.price, co.shares_m
    bridge = res.equity_value - res.ev                      # caja + inversiones − deuda − minoritarios (no cambia entre métodos)
    items: List[dict] = []
    notas: List[str] = []
    if (ex.get("p_default") or 0) > 0:
        notas.append("El ajuste por riesgo de quiebra solo está en el método 1; los otros métodos muestran el valor como negocio en marcha.")

    # --- 1. nuestro DCF
    items.append(_item("m1", res.per_share, price, "Valor del modelo (con el ajuste por riesgo de quiebra, si corresponde)."))

    # --- datos para los métodos a 5 años
    ebit0 = (ex.get("margin0") or 0.0) * (co.revenue_ttm or 0.0)       # EBIT TTM tal como lo usa el modelo (con I+D capitalizado si corresponde)
    five_ok = len(tb) >= 5 and ebit0 > 0 and all(r["FCFF"] is not None for r in tb[:5])
    df = []                                                           # factor de descuento acumulado de cada año (1/(1+WACC)... acumulado)
    acc = 1.0
    for r in tb:
        acc *= (1 + r["WACC"])
        df.append(acc)                                                # df[t-1] = Π(1+WACC_i): se DIVIDE
    ebit5 = tb[4]["EBIT"] if five_ok else None
    pv15 = sum(r["VP"] for r in tb[:5]) if five_ok else None
    ev5_model = (res.ev - pv15) * df[4] if five_ok else None
    ev_now = price * sh - bridge
    mult_now = ev_now / ebit0 if ebit0 > 0 else None

    # --- múltiplo de la industria
    mm = get_multiples(co.ind_name)
    rdcap = bool(ex.get("rd_asset"))
    metric_ttm = mult_ind = None
    if mm:
        mult_ind = mm["ev_ebitdard"] if rdcap else mm["ev_ebitda"]
        metric_ttm = (co.ebit_ttm or 0.0) + (co.da_ttm or 0.0) + ((co.rd_ttm or 0.0) if rdcap else 0.0)
        if metric_ttm <= 0:
            metric_ttm = None
        if mm["n"] < MULT_MIN_MUESTRA:
            notas.append(f"Los múltiplos de «{co.ind_name}» salen de una muestra chica ({mm['n']} empresas en EE.UU.): tomalos con pinzas.")
        if (co.country or "").strip().lower() not in ("", "united states", "usa", "us"):
            notas.append("Los múltiplos de la industria son de empresas de EE.UU. (Damodaran no trae la tabla global): para una empresa de otro país son solo una referencia.")
        notas.append(f"Múltiplo de la industria «{co.ind_name}»: {mult_ind:.1f}× {'EV/EBITDAR&D (el modelo capitaliza I+D)' if rdcap else 'EV/EBITDA'} (Damodaran, {MULT_DATE}).")
    else:
        notas.append(f"No hay múltiplo de industria para «{co.ind_name or 'sin industria'}»: los métodos 2 y 4 no se calculan.")

    # --- 2. 5 años con salida sector
    v2 = None
    if five_ok and metric_ttm and mult_ind:
        ev5 = mult_ind * metric_ttm * (ebit5 / ebit0)
        v2 = (pv15 + ev5 / df[4] + bridge) / sh
    items.append(_item("m2", v2, price, "Flujos del modelo años 1-5 + valor al año 5 con el múltiplo de la industria."))

    # --- 3. Dorsey
    fcf0 = co.fcf_ttm
    R = dorsey_R if dorsey_R else max(DORSEY_R_MIN, ex.get("ke") or 0.0)
    v3 = rng3 = None
    nota3 = ""
    if fcf0 is None:
        nota3 = "Sin flujo de caja libre de Yahoo para esta empresa."
    elif fcf0 <= 0:
        nota3 = f"El flujo de caja libre de los últimos 12 meses es negativo ({fcf0:,.0f} M): el método no aplica."
    else:
        v3 = dorsey_value(fcf0, sh, dorsey_g, R)
        vs = [dorsey_value(fcf0, sh, g, R) for g in DORSEY_G_RANGE]
        if all(v is not None for v in vs):
            rng3 = (min(vs), max(vs))
        nota3 = (f"Flujo de caja libre real {fcf0:,.0f} M, crece {dorsey_g:.0%} anual 10 años, perpetuidad {DORSEY_G_TERMINAL:.0%}, "
                 f"tasa {R:.1%}. Rango con crecimiento {DORSEY_G_RANGE[0]:.0%}-{DORSEY_G_RANGE[-1]:.0%}.")
        if co.ni_ttm and co.ni_ttm > 0 and fcf0 < 0.5 * co.ni_ttm:
            notas.append("El flujo de caja libre de los últimos 12 meses es menos de la mitad de la ganancia neta: el método Dorsey puede salir muy bajo si ese flujo es transitorio.")
    items.append(_item("m3", v3, price, nota3, rango=rng3))

    # --- 4. múltiplos hoy
    v4 = None
    if metric_ttm and mult_ind:
        v4 = (mult_ind * metric_ttm + bridge) / sh
    items.append(_item("m4", v4, price, "Múltiplo de la industria × EBITDA actual. No distingue a una empresa de calidad del promedio de su industria."))

    # --- 5. estilo Alpha (circular)
    v5 = None
    if five_ok and mult_now and mult_now > 0:
        v5 = (pv15 + mult_now * ebit5 / df[4] + bridge) / sh
    items.append(_item("m5", v5, price, "Circular: el múltiplo de salida es el que el mercado paga hoy, así que el valor sale cerca del precio por construcción. Aproximación nuestra, NO es el número de Alpha Spread.",
                       circular=True))
    out["items"] = items
    out["notas"] = notas

    vals = [it["valor"] for it in items if it["valor"] is not None and not it["circular"]]
    lows = [it["rango"][0] if it["rango"] else it["valor"] for it in items if it["valor"] is not None and not it["circular"]]
    highs = [it["rango"][1] if it["rango"] else it["valor"] for it in items if it["valor"] is not None and not it["circular"]]
    if vals:
        out["rango"] = (min(lows), max(highs))

    # --- panel a 5 años
    if five_ok:
        W = tb[0]["WACC"]
        fc = [r["FCFF"] / sh for r in tb[:5]]
        v5_model = (ev5_model + bridge) / sh
        irr_model = _irr([-price] + fc[:4] + [fc[4] + v5_model])
        v5_now = (mult_now * ebit5 + bridge) / sh if mult_now else None
        irr_now = _irr([-price] + fc[:4] + [fc[4] + v5_now]) if v5_now is not None else None
        pv_fc = sum(r["FCFF"] / d for r, d in zip(tb[:5], df[:5])) / sh      # flujos 1-5 por acción, descontados
        v5_req = (price - pv_fc) * df[4]
        mult_req = (v5_req * sh - bridge) / ebit5 if ebit5 > 0 else None
        out["panel"] = dict(
            wacc=W, ebit5=ebit5, ev5_model=ev5_model, mult5_model=ev5_model / ebit5 if ebit5 > 0 else None,
            valor5_modelo=v5_model, retorno_modelo=irr_model, mult_hoy=mult_now,
            valor5_mult_hoy=v5_now, retorno_mult_hoy=irr_now, valor5_requerido=v5_req, mult_requerido=mult_req,
            sector_mult_ebit=None)
    return out
