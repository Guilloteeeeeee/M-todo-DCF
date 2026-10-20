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

from industry_multiples import MULT_DATE, MULT_MIN_MUESTRA, get_multiples, get_pe_sales

DORSEY_R_MIN = 0.09        # tasa de descuento de Dorsey para una empresa estable y sólida (Clorox); si el costo del capital propio del modelo es mayor, se usa ese
DORSEY_G_TERMINAL = 0.03   # Dorsey: ~ crecimiento del PBI de EE.UU.
DORSEY_G_DEFAULT = 0.05    # Dorsey (Clorox): crecimiento constante prudente
DORSEY_G_RANGE = (0.05, 0.07, 0.09)
DORSEY_YEARS = 10

# --- v2.54 · valor combinado (probado primero como columnas del lote)
MULT_EXTREME = 35.0        # EV/EBITDA de la industria por encima de esto: los métodos 2 y 4 se excluyen solos (la mediana de las 91 industrias de Damodaran es ~13×)
COINCIDE_TOL = 0.25        # "coinciden": ningún método incluido se aleja más de ±25 % del valor combinado
COMB_MIN_METODOS = 2       # con menos de 2 métodos no hay combinado

# --- v2.55 · «dos números grandes»: valor por DCF (promedio de métodos DCF) y valor por múltiplos (2-3 múltiplos con peso según sector / industria)
DCF_KEYS = ("m1", "m2", "m3")
PE_EXTREME = 60.0          # P/E de la industria por encima de esto se excluye solo (hoy solo Auto & Truck, 119,6×)
# Pesos PROPUESTOS (a revisar): (EV/EBITDA, P/E, EV/Ventas). Criterio (Damodaran, tablas 4.3-4.4): EV/EBITDA es el más parejo entre empresas con distinta deuda y
# necesidad de inversión; P/E sirve donde la ganancia es estable y positiva; EV/Ventas es el más flojo (ignora márgenes), por eso pesa poco salvo donde la ganancia aún no madura.
SECTOR_WEIGHTS = {
    "Technology": (0.40, 0.40, 0.20), "Communication Services": (0.50, 0.30, 0.20), "Healthcare": (0.30, 0.50, 0.20),
    "Consumer Defensive": (0.40, 0.50, 0.10), "Consumer Cyclical": (0.50, 0.40, 0.10), "Industrials": (0.50, 0.40, 0.10),
    "Basic Materials": (0.60, 0.30, 0.10), "Energy": (0.60, 0.30, 0.10), "Utilities": (0.40, 0.50, 0.10),
}
WEIGHTS_DEFAULT = (0.50, 0.40, 0.10)
INDUSTRY_WEIGHTS = {     # la industria manda sobre el sector
    "Software (Internet)": (0.30, 0.35, 0.35), "Software (System & Application)": (0.35, 0.35, 0.30), "Software (Entertainment)": (0.35, 0.35, 0.30),
    "Drugs (Biotechnology)": (0.20, 0.30, 0.50),
    "Oil/Gas (Production and Exploration)": (0.70, 0.20, 0.10), "Oil/Gas (Integrated)": (0.70, 0.20, 0.10), "Metals & Mining": (0.70, 0.20, 0.10),
    "Steel": (0.70, 0.20, 0.10), "Chemical (Basic)": (0.70, 0.20, 0.10), "Coal & Related Energy": (0.70, 0.20, 0.10),
}
MULT_LABELS = ("EV/EBITDA", "P/E", "EV/Ventas")
DOS_TOL = 0.25
VENTAS_PESO_AVISO = 0.40   # si, tras repartir los pesos, EV/Ventas pesa 40 % o más en el valor por múltiplos, se avisa
COMB_KEYS = ("m1", "m2", "m3", "m4")   # el 5 (circular) NUNCA entra: lleva el precio adentro

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


def combine(items: List[dict], price: float, mult_ind: Optional[float] = None) -> Dict:
    """Valor combinado: solo métodos que aplican, sin el circular, sin los que usan un múltiplo de industria extremo.
    Mediana si quedan 3 o más, promedio si son 2. Marca 'coinciden' si ningún método se aleja más de ±25 % del combinado.
    Devuelve dict(valor, ratio, regla, keys, excluidos {key: motivo}, lo, hi, lo_ratio, hi_ratio, coinciden, marca, desvio_max)."""
    out = dict(valor=None, ratio=None, regla="", keys=[], excluidos={}, lo=None, hi=None, lo_ratio=None, hi_ratio=None,
               coinciden=None, marca="", desvio_max=None)
    vals = {}
    for it in items:
        k = it["key"]
        if k not in COMB_KEYS:
            if k == "m5":
                out["excluidos"][k] = "circular (lleva el precio adentro)"
            continue
        v = it["valor"]
        if v is None:
            out["excluidos"][k] = "no aplica a esta empresa"
        elif v <= 0:
            out["excluidos"][k] = "valor cero o negativo"
        elif k in ("m2", "m4") and mult_ind and mult_ind > MULT_EXTREME:
            out["excluidos"][k] = f"múltiplo de industria extremo ({mult_ind:.1f}×)"
        else:
            vals[k] = v
    n = len(vals)
    if n < COMB_MIN_METODOS:
        out["marca"] = "un solo método: no alcanza para combinar" if n == 1 else "ningún método aplicable"
        out["keys"] = list(vals)
        return out
    xs = sorted(vals.values())
    if n >= 3:
        comb = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
        out["regla"] = "mediana"
    else:
        comb = sum(xs) / n
        out["regla"] = "promedio"
    dev = max(abs(v / comb - 1) for v in xs)
    out.update(valor=comb, ratio=(comb / price if price else None), keys=sorted(vals), lo=xs[0], hi=xs[-1],
               lo_ratio=(xs[0] / price if price else None), hi_ratio=(xs[-1] / price if price else None),
               desvio_max=dev, coinciden=dev <= COINCIDE_TOL)
    out["marca"] = "coinciden" if out["coinciden"] else "no coinciden: no te fíes del promedio"
    return out


def multiple_weights(sector: str, ind_name: str) -> tuple:
    """(peso EV/EBITDA, peso P/E, peso EV/Ventas) para esa industria (si está) o ese sector."""
    return INDUSTRY_WEIGHTS.get(ind_name or "") or SECTOR_WEIGHTS.get(sector or "") or WEIGHTS_DEFAULT


def _range_fields(vals: List[float], price: float) -> dict:
    lo, hi = min(vals), max(vals)
    return dict(lo=lo, hi=hi, lo_ratio=(lo / price if price else None), hi_ratio=(hi / price if price else None))


def dos_valores(items: List[dict], comps: List[dict], weights: tuple, price: float, mult_ind: Optional[float], n_ind: Optional[int] = None) -> Dict:
    """Los «dos números grandes».
    DCF = promedio simple de los métodos DCF que aplican (1, 2 y 3). El 2 sale si el múltiplo de industria es extremo.
    Múltiplos = promedio ponderado de EV/EBITDA, P/E y EV/Ventas; si un múltiplo no se puede calcular (ganancia o EBITDA ≤ 0, dato que falta, múltiplo extremo),
    su peso se reparte entre los que quedan, en proporción a sus pesos. comps: [{'label','valor','mult','metric','motivo'}] en el orden (EV/EBITDA, P/E, EV/Ventas)."""
    dcf = dict(valor=None, ratio=None, keys=[], excluidos={}, lo=None, hi=None, lo_ratio=None, hi_ratio=None)
    vals = {}
    for it in items:
        if it["key"] not in DCF_KEYS:
            continue
        v, k = it["valor"], it["key"]
        if v is None:
            dcf["excluidos"][k] = "no aplica a esta empresa"
        elif v <= 0:
            dcf["excluidos"][k] = "valor cero o negativo"
        elif k == "m2" and mult_ind and mult_ind > MULT_EXTREME:
            dcf["excluidos"][k] = f"múltiplo de salida extremo ({mult_ind:.1f}×)"
        else:
            vals[k] = v
    if vals:
        avg = sum(vals.values()) / len(vals)
        dcf.update(valor=avg, ratio=(avg / price if price else None), keys=sorted(vals), **_range_fields(list(vals.values()), price))
    mu = dict(valor=None, ratio=None, comps=[], pesos="", lo=None, hi=None, lo_ratio=None, hi_ratio=None)
    ok = [c for c in comps if c["valor"] is not None and c["valor"] > 0]
    wsum = sum(weights[i] for i, c in enumerate(comps) if c["valor"] is not None and c["valor"] > 0)
    for i, c in enumerate(comps):
        used = (weights[i] / wsum) if (c["valor"] is not None and c["valor"] > 0 and wsum > 0) else 0.0
        mu["comps"].append(dict(c, peso_base=weights[i], peso=used, ratio=(c["valor"] / price if (c["valor"] and price) else None)))
    if ok and wsum > 0:
        val = sum(c["peso"] * c["valor"] for c in mu["comps"] if c["peso"] > 0)
        mu.update(valor=val, ratio=(val / price if price else None), **_range_fields([c["valor"] for c in ok], price))
        mu["pesos"] = " · ".join(f"{c['label']} {c['peso']:.0%}" for c in mu["comps"] if c["peso"] > 0)
    avisos = []
    es_peso = next((c["peso"] for c in mu["comps"] if c["label"] == "EV/Ventas"), 0.0)
    if mu["valor"] and es_peso >= VENTAS_PESO_AVISO:
        avisos.append(f"se apoya {es_peso:.0%} en EV/Ventas (ignora márgenes): poco confiable")
    if n_ind is not None and n_ind < MULT_MIN_MUESTRA:
        avisos.append(f"muestra chica de la industria ({n_ind} empresas)")
    mu["aviso"] = "; ".join(avisos)
    out = dict(dcf=dcf, mult=mu, brecha=None, coinciden=None, marca="")
    if dcf["valor"] and mu["valor"]:
        out["brecha"] = dcf["valor"] / mu["valor"] - 1
        d = abs(dcf["valor"] - mu["valor"]) / ((dcf["valor"] + mu["valor"]) / 2)
        out["coinciden"] = d <= DOS_TOL
        out["marca"] = "coinciden" if out["coinciden"] else "no coinciden: el DCF y los múltiplos cuentan historias distintas"
    else:
        out["marca"] = "falta uno de los dos valores"
    return out


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
    out = dict(applicable=False, reason="", items=[], panel=None, notas=[], rango=None, combinado=None, dos=None)
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
    out["combinado"] = combine(items, price, mult_ind)

    # --- v2.55 · valor por múltiplos: EV/EBITDA (el método 4), P/E y EV/Ventas de la industria
    ps = get_pe_sales(co.ind_name)
    v4_ok = items[3]["valor"] if (items[3]["valor"] and not (mult_ind and mult_ind > MULT_EXTREME)) else None
    c_eb = dict(label="EV/EBITDA", valor=v4_ok, mult=mult_ind, metric=metric_ttm,
                motivo=("" if v4_ok else ("múltiplo extremo" if (mult_ind and mult_ind > MULT_EXTREME) else "sin múltiplo o EBITDA ≤ 0")))
    pe_v = pe_m = None
    pe_why = ""
    if not ps or not ps["pe"]:
        pe_why = "sin P/E de la industria"
    elif ps["pe"] > PE_EXTREME:
        pe_why = f"múltiplo extremo ({ps['pe']:.0f}×)"
    elif not co.ni_ttm or co.ni_ttm <= 0:
        pe_why = "ganancia neta ≤ 0"
    else:
        pe_m = ps["pe"]
        pe_v = pe_m * co.ni_ttm / sh
    c_pe = dict(label="P/E", valor=pe_v, mult=(ps["pe"] if ps else None), metric=co.ni_ttm, motivo=pe_why)
    es_v = None
    es_why = ""
    if not ps or not ps["ev_sales"]:
        es_why = "sin EV/Ventas de la industria"
    elif not co.revenue_ttm or co.revenue_ttm <= 0:
        es_why = "sin ventas"
    else:
        es_v = (ps["ev_sales"] * co.revenue_ttm + bridge) / sh
    c_es = dict(label="EV/Ventas", valor=es_v, mult=(ps["ev_sales"] if ps else None), metric=co.revenue_ttm, motivo=es_why)
    out["dos"] = dos_valores(items, [c_eb, c_pe, c_es], multiple_weights(co.sector, co.ind_name), price, mult_ind, (ps or {}).get("n"))

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
