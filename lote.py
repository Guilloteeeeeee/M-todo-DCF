"""
lote.py — Modo lote: valúa muchas empresas de una vez con los supuestos por defecto de la app y devuelve UN Excel.

Sirve para calibrar el modelo con muchos casos juntos (en vez de una empresa por vez) y para detectar patrones de fallas.
Cada fila trae: valores por escenario, ancho de la banda, foso, tasas, márgenes, estado de los datos y "banderas" de revisión.
Una hoja aparte guarda los datos de entrada de cada empresa (JSON) para poder repetir el cálculo sin volver a Yahoo.

evaluate() es lógica pura (sin Streamlit): se puede probar sin red. render() es la pantalla.
"""
from __future__ import annotations

import io
import json
import time
from dataclasses import asdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import data_yahoo
from country_risk import country_crp
from country_tax import marginal_tax_for
from dcf_models import Params, data_checks, field_checks, implied_wacc, route_model, run_scenarios, terminal_growth_default
from industry_data import attach as attach_industry, ERP_DAMODARAN

SCEN_ORDER = ["Pesimista", "Base", "Optimista"]
NO_APLICA_PCT = 0.02          # base < 2 % del precio -> "No aplica por DCF"

SUGGESTED = (
    "AAPL, MSFT, NVDA, ORCL, INTC, CSCO, AMD, ADBE, "                 # tecnología
    "GOOGL, META, NFLX, DIS, VZ, T, "                                   # comunicaciones
    "AMZN, TSLA, HD, MCD, NKE, F, RIVN, "                               # consumo discrecional
    "KO, PEP, PG, WMT, COST, PM, "                                      # consumo defensivo
    "JNJ, MRK, PFE, UNH, LLY, ABBV, MRNA, "                             # salud
    "CAT, BA, UPS, GE, DAL, AAL, LMT, "                                 # industriales
    "XOM, CVX, COP, FCX, NUE, LIN, "                                    # energía y materiales
    "NEE, DUK, SO, O, PLD, AMT, "                                       # utilities y REITs
    "JPM, BAC, GS, V, MA, MET, "                                        # financieras
    "TSM, NVO, ASML, TM, BABA, MELI, VALE, PBR, SAP, "                  # extranjeras / ADR
    "PLTR, SNAP"                                                        # chicas / con pérdidas
)

FLAG_HELP = {
    "datos incompletos": "Yahoo no entregó sector, industria, país, nombre o la capitalización de mercado.",
    "no confiable": "Faltan datos clave (o llegaron degradados): el Excel NO muestra valores, solo una referencia. Se reintenta solo; si persiste, probá esa empresa más tarde.",
    "no aplica por DCF": "El valor base es menos de 2 % del precio: con estos supuestos el negocio no genera valor para el accionista (pérdidas, ROIC bajo el costo de capital). El DCF no es la herramienta adecuada.",
    "sin analistas": "No hay estimaciones de analistas de ingresos: el crecimiento sale de la historia.",
    "pérdida operativa": "EBIT del TTM ≤ 0.",
    "TTM bajo vs mediana, ingresos estables": "El margen del TTM está 8 pp o más por debajo del objetivo y los ingresos no caen: parece un cargo extraordinario. La proyección arranca del margen normal, no del TTM.",
    "TTM bajo vs mediana, ingresos caen": "El margen del TTM está 8 pp o más por debajo del objetivo y los ingresos caen: ¿deterioro real?",
    "TTM alto vs mediana": "El margen del TTM está 8 pp o más por encima del objetivo: ¿pico de ciclo?",
    "banda ancha": "Pesimista < 40 % del base u optimista > 2 veces el base.",
    "pesimista en 0": "El valor del pesimista quedó en 0 (patrimonio negativo en ese escenario).",
    "base ≤ 0": "El valor base es 0: el negocio no cubre su deuda con estos supuestos.",
    "base lejos del precio": "El base es menos de 40 % o más de 160 % del precio.",
    "g recortado": "El crecimiento terminal se recortó por la distancia mínima con la tasa de descuento.",
    "ROIC normalizado": "El ROIC inicial normalizado difiere más de 3 pp del ROIC con el TTM.",
    "WACC extremo": "WACC menor a 6 % o mayor a 12 %.",
    "controles ⚠️": "Hay datos con controles en estado REVISAR.",
}


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def evaluate(sym: str, load_fn: Callable, adr_ratio: float = 0.0) -> Tuple[dict, Optional[str]]:
    """Valúa un ticker con los supuestos por defecto. Devuelve (fila, JSON de datos de entrada o None). Nunca levanta excepción."""
    t0 = time.time()
    row: Dict[str, object] = {"Ticker": sym}
    try:
        co, load_warns = load_fn(sym, False, adr_ratio)
    except Exception as e:  # noqa: BLE001
        row.update({"Estado": "ERROR de datos", "Detalle": str(e)[:300], "Segundos": round(time.time() - t0, 1)})
        return row, None
    raw = None
    try:
        raw = json.dumps(asdict(co), default=str)
    except Exception:  # noqa: BLE001
        pass
    try:
        missing = data_yahoo.missing_fields(co)
        tax, _ = marginal_tax_for(co.country)
        crp, _ = country_crp(co.country)
        g_req = terminal_growth_default(co.rf)
        model, _ = route_model(co)
        p = Params(horizon=10, g_terminal=g_req, erp=ERP_DAMODARAN, crp=crp, moat="auto", marginal_tax=tax, margin_mode="median",
                   margin_years=5, persistence=0.5, affo_ratio=0.90, include_nonop=True, use_industry_beta=True)
        co2, ind_name, _ = attach_industry(co, model, None)
        res = run_scenarios(co2, p, model)
        base = res["Base"]
        if (model == "FCFF" and not base.ok and "EBIT" in base.error and (co.ni_ttm or 0) > 0 and (co.equity or 0) > 0):
            model = "ER"
            co2, ind_name, _ = attach_industry(co, model, None)
            res = run_scenarios(co2, p, model)
            base = res["Base"]
        row.update({"Empresa": co.name, "Sector": co.sector, "Industria": co.industry, "País": co.country,
                    "Industria Damodaran": ind_name or "", "Modelo": model, "Precio": co.price, "Moneda": co.currency})
        if not base.ok:
            row.update({"Estado": "No valuable", "Detalle": base.error[:300], "Datos faltantes": ", ".join(missing),
                        "Banderas": "datos incompletos" if missing else "", "Segundos": round(time.time() - t0, 1)})
            return row, raw
        vp, vb, vo = (res[n].per_share if res[n].ok else None for n in SCEN_ORDER)
        ex = base.extras or {}
        flags: List[str] = []
        if missing:
            flags.append("datos incompletos")
        if co.rev_g_y0 is None and co.rev_g_y1 is None:
            flags.append("sin analistas")
        if model == "FCFF" and co.ebit_ttm <= 0:
            flags.append("pérdida operativa")
        m0, mT = _f(ex.get("margin0")), _f(ex.get("margin_target"))
        d_m = (m0 - mT) if (m0 is not None and mT is not None) else None
        if model == "FCFF" and d_m is not None and co.ebit_ttm > 0:
            prev = next((r for r in reversed(co.revenue_hist) if r), None)
            rev_ok = prev is None or co.revenue_ttm >= 0.97 * prev
            if d_m <= -0.08:
                flags.append("TTM bajo vs mediana, ingresos estables" if rev_ok else "TTM bajo vs mediana, ingresos caen")
            elif d_m >= 0.08:
                flags.append("TTM alto vs mediana")
        r_pb = (vp / vb) if (vp is not None and vb) else None
        r_ob = (vo / vb) if (vo is not None and vb) else None
        if (r_pb is not None and r_pb < 0.4) or (r_ob is not None and r_ob > 2.0):
            flags.append("banda ancha")
        if vp is not None and vp <= 0:
            flags.append("pesimista en 0")
        if vb is not None and vb <= 0:
            flags.append("base ≤ 0")
        if vb and co.price and not (0.4 <= vb / co.price <= 1.6):
            flags.append("base lejos del precio")
        if abs(base.g_terminal - g_req) > 5e-5:
            flags.append("g recortado")
        if any("ROIC inicial normalizado" in w for w in base.warnings):
            flags.append("ROIC normalizado")
        wacc = _f(base.discount_rate)
        if wacc is not None and (wacc < 0.06 or wacc > 0.12):
            flags.append("WACC extremo")
        n_check = sum(1 for c in field_checks(co2, model, p) if c["Estado"] == "aviso")
        if n_check:
            flags.append("controles ⚠️")
        all_w = list(dict.fromkeys(list(load_warns) + data_checks(co2) + list(base.warnings)))
        bad = data_yahoo.unreliable_reasons(co)
        no_aplica = vb is not None and co.price > 0 and vb <= NO_APLICA_PCT * co.price
        estado = "No confiable" if bad else ("No aplica por DCF" if no_aplica else ("Datos incompletos" if missing else "OK"))
        if bad:
            flags.insert(0, "no confiable")
        elif no_aplica:
            flags.insert(0, "no aplica por DCF")
        row.update({
            "Estado": estado,
            "Pesimista": vp, "Base": vb, "Optimista": vo,
            "Pes/Base": r_pb, "Opt/Base": r_ob, "Base vs precio": (vb / co.price - 1) if (vb is not None and co.price) else None,
            "WACC": wacc, "WACC terminal": _f(ex.get("wacc_T")), "Ke": _f(base.ke), "g terminal aplicado": _f(base.g_terminal),
            "Crecim. año 1": _f(ex.get("g1")), "Fuente crecim.": ex.get("g_src", ""),
            "Margen TTM": m0, "Margen objetivo": mT, "TTM − objetivo (pp)": (d_m * 100) if d_m is not None else None,
            "ROIC inicial": _f(ex.get("roic0")), "ROIC terminal": _f(ex.get("roicT")),
            "Foso": ex.get("moat_label", ""), "Origen foso": ex.get("moat_src", ""),
            "Etapa": base.extras.get("lifecycle", ""), "P(quiebra 10a)": _f(ex.get("p_default")) if ex.get("p_default") else None,
            "I+D capitalizado (M)": _f(ex.get("rd_asset")),
            "VT / EV": _f(base.tv_share), "EV/EBIT salida": _f(ex.get("exit_ev_ebit")),
            "Pensiones (M)": co2.pension_liab,
            "Pensiones / patrimonio": (co2.pension_liab / base.equity_value) if (co2.pension_liab and base.equity_value and base.equity_value > 0) else None,
            "Avisos (n)": len(all_w), "Controles ⚠️ (n)": n_check, "Datos faltantes": ", ".join(missing),
            "Banderas": " · ".join(flags), "Primer aviso": (all_w[0][:160] if all_w else ""),
        })
        try:
            _imp = implied_wacc(co2, p, model) if estado == "OK" or estado == "Datos incompletos" else None
        except Exception:  # noqa: BLE001
            _imp = None
        row["WACC implícito (precio)"] = _imp["wacc"] if _imp else None
        row["WACC modelo − implícito (pp)"] = (_imp["wacc_model"] - _imp["wacc"]) * 100 if _imp else None
        if estado in ("No confiable", "No aplica por DCF"):
            ref = "/".join("n/d" if v is None else f"{v:.2f}" for v in (vp, vb, vo))
            row.update({"Valor ref. pes/base/opt": ref, "Pesimista": None, "Base": None, "Optimista": None,
                        "Pes/Base": None, "Opt/Base": None, "Base vs precio": None,
                        "Detalle": ("Motivos: " + "; ".join(bad)) if bad else
                                   "Con estos supuestos el negocio no genera valor para el accionista: " + (base.warnings[0][:200] if base.warnings else "")})
    except Exception as e:  # noqa: BLE001
        row.update({"Estado": "ERROR de cálculo", "Detalle": f"{type(e).__name__}: {e}"[:300]})
    row["Segundos"] = round(time.time() - t0, 1)
    return row, raw


RESCUE_STATES = ("No confiable",)


def rescue(rows: List[dict], raws: Dict[str, str], load_fn: Callable, waits=(10.0,), sleep: Callable = time.sleep,
           on_progress: Optional[Callable[[str], None]] = None) -> int:
    """Vuelve a valuar, esperando entre intentos, las filas "No confiables" (Yahoo suele limitar las consultas por un rato).
    Reemplaza la fila solo si mejora. Devuelve cuántas se recuperaron."""
    fixed = 0
    for wait in waits:
        todo = [i for i, r in enumerate(rows) if r.get("Estado") in RESCUE_STATES]
        if not todo:
            break
        sleep(wait)
        for i in todo:
            sym = str(rows[i]["Ticker"])
            if on_progress:
                on_progress(sym)
            new, raw = evaluate(sym, load_fn)
            if new.get("Estado") not in RESCUE_STATES:
                rows[i] = new
                if raw:
                    raws[sym] = raw
                fixed += 1
            sleep(1.0)
    return fixed


def summarize(rows: List[dict]) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int, str]]]:
    """(conteo por estado, conteo por bandera con su explicación)."""
    states: Dict[str, int] = {}
    flags: Dict[str, int] = {}
    for r in rows:
        states[str(r.get("Estado", ""))] = states.get(str(r.get("Estado", "")), 0) + 1
        for fl in str(r.get("Banderas", "") or "").split(" · "):
            if fl:
                flags[fl] = flags.get(fl, 0) + 1
    return (sorted(states.items(), key=lambda kv: -kv[1]),
            [(k, v, FLAG_HELP.get(k, "")) for k, v in sorted(flags.items(), key=lambda kv: -kv[1])])


COLUMNS = ["Ticker", "Empresa", "Estado", "Modelo", "Sector", "Industria", "País", "Industria Damodaran", "Precio", "Moneda",
           "Pesimista", "Base", "Optimista", "Valor ref. pes/base/opt", "Pes/Base", "Opt/Base", "Base vs precio",
           "WACC", "WACC terminal", "Ke", "g terminal aplicado", "Crecim. año 1", "Fuente crecim.",
           "Margen TTM", "Margen objetivo", "TTM − objetivo (pp)", "ROIC inicial", "ROIC terminal",
           "Foso", "Origen foso", "Etapa", "P(quiebra 10a)", "I+D capitalizado (M)", "VT / EV", "EV/EBIT salida", "Pensiones (M)", "Pensiones / patrimonio", "WACC implícito (precio)", "WACC modelo − implícito (pp)", "Avisos (n)", "Controles ⚠️ (n)",
           "Datos faltantes", "Banderas", "Primer aviso", "Detalle", "Segundos"]


def build_excel(rows: List[dict], raws: Dict[str, str]) -> bytes:
    import pandas as pd
    buf = io.BytesIO()
    df = pd.DataFrame(rows)
    df = df[[c for c in COLUMNS if c in df.columns]]
    states, flags = summarize(rows)
    resumen = [("Generado", datetime.now().strftime("%Y-%m-%d %H:%M")), ("Empresas", len(rows)), ("", "")]
    resumen += [(f"Estado: {k}", v) for k, v in states] + [("", "")]
    resumen += [(f"Bandera: {k}", f"{v} — {h}") for k, v, h in flags]
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Lote", index=False)
        pd.DataFrame(resumen, columns=["Concepto", "Valor"]).to_excel(xw, sheet_name="Resumen", index=False)
        pd.DataFrame([(k, v) for k, v in FLAG_HELP.items()], columns=["Bandera", "Qué significa"]).to_excel(
            xw, sheet_name="Leyenda_banderas", index=False)
        pd.DataFrame([(k, v) for k, v in raws.items()], columns=["Ticker", "Datos_JSON"]).to_excel(
            xw, sheet_name="Datos_crudos", index=False)
        try:
            ws = xw.book["Lote"]
            ws.freeze_panes = "C2"
            for i, col in enumerate(df.columns, start=1):
                ws.column_dimensions[ws.cell(1, i).column_letter].width = 14 if col not in ("Empresa", "Banderas", "Primer aviso", "Detalle", "Industria") else 34
            pct = {"Pes/Base": "0.00", "Opt/Base": "0.00", "Base vs precio": "0%", "WACC": "0.00%", "WACC terminal": "0.00%", "Ke": "0.00%",
                   "g terminal aplicado": "0.00%", "Crecim. año 1": "0.0%", "Margen TTM": "0.0%", "Margen objetivo": "0.0%",
                   "ROIC inicial": "0.0%", "ROIC terminal": "0.0%", "VT / EV": "0%", "P(quiebra 10a)": "0%", "Pesimista": "0.00", "Base": "0.00", "Optimista": "0.00",
                   "Pensiones / patrimonio": "0%", "WACC implícito (precio)": "0.00%", "WACC modelo − implícito (pp)": "0.00"}
            for i, col in enumerate(df.columns, start=1):
                if col in pct:
                    for r in range(2, ws.max_row + 1):
                        ws.cell(r, i).number_format = pct[col]
        except Exception:  # noqa: BLE001
            pass
    return buf.getvalue()


def parse_tickers(text: str) -> List[str]:
    out: List[str] = []
    for tok in text.replace("\n", ",").replace(";", ",").replace(" ", ",").split(","):
        t = tok.strip().upper()
        if t and t not in out:
            out.append(t)
    return out


# ----------------------------------------------------------------------------
def render(load_fn: Callable, stretch: dict, version: str) -> None:
    import pandas as pd
    import streamlit as st

    st.title("📊 Modo lote")
    st.caption("Valúa muchas empresas de una vez con los supuestos por defecto y descarga **un solo Excel** para calibrar el modelo. "
               "Herramienta de calibración: no es una recomendación.")
    if "lote_rows" not in st.session_state:
        st.session_state["lote_rows"], st.session_state["lote_raw"] = [], {}
    rows: List[dict] = st.session_state["lote_rows"]
    raws: Dict[str, str] = st.session_state["lote_raw"]

    txt = st.text_area("Tickers (separados por coma, espacio o renglón)", value=SUGGESTED, height=150, key="lote_txt",
                       help="La lista sugerida cubre todos los sectores, empresas grandes y chicas, bancos, REITs, utilities, "
                            "cíclicas, extranjeras y algunas con pérdidas.")
    c1, c2, c3 = st.columns(3)
    tanda = c1.number_input("Empresas por tanda", 5, 60, 10, 5,
                            help="Cada vez que apretás el botón se valúan las próximas empresas pendientes. "
                                 "Tandas chicas evitan que Yahoo limite las consultas.")
    pausa = c2.number_input("Pausa entre empresas (seg)", 0.0, 10.0, 3.0, 0.5)
    go = c3.button("Valuar la próxima tanda", type="primary")

    tickers = parse_tickers(txt)
    done = {str(r["Ticker"]) for r in rows}
    pending = [t for t in tickers if t not in done]
    st.write(f"**{len(tickers)}** tickers · **{len(done & set(tickers))}** hechos · **{len(pending)}** pendientes")

    table_slot = st.empty()
    if go and pending:
        batch = pending[: int(tanda)]
        bar = st.progress(0.0, text="Empezando…")
        for i, sym in enumerate(batch, start=1):
            bar.progress((i - 1) / len(batch), text=f"Valuando {sym} ({i}/{len(batch)})…")
            row, raw = evaluate(sym, load_fn)
            rows.append(row)
            if raw:
                raws[sym] = raw
            if rows:
                table_slot.dataframe(pd.DataFrame(rows)[[c for c in COLUMNS if c in pd.DataFrame(rows).columns][:16]], **stretch)
            if pausa and i < len(batch):
                time.sleep(float(pausa))
        n_bad = sum(1 for r in rows if r.get("Estado") in RESCUE_STATES)
        if n_bad:
            bar.progress(1.0, text=f"Reintentando {n_bad} empresa(s) con datos incompletos…")
            rescue(rows, raws, load_fn, waits=(10.0, 25.0), on_progress=lambda s_: bar.progress(1.0, text=f"Reintentando {s_}…"))
        bar.progress(1.0, text="Tanda terminada")
        pending = [t for t in tickers if t not in {str(r["Ticker"]) for r in rows}]
        st.success(f"Tanda terminada. Pendientes: {len(pending)}."
                   + (" Apretá de nuevo para seguir." if pending else " ¡Lista completa! Descargá el Excel."))
    elif go and not pending:
        st.info("No hay tickers pendientes.")

    if rows:
        df = pd.DataFrame(rows)
        table_slot.dataframe(df[[c for c in COLUMNS if c in df.columns]], **stretch)
        states, flags = summarize(rows)
        st.markdown("**Resumen**")
        st.write(" · ".join(f"{k}: **{v}**" for k, v in states))
        if flags:
            st.dataframe(pd.DataFrame(flags, columns=["Bandera", "Empresas", "Qué significa"]).set_index("Bandera"), **stretch)
        st.download_button("⬇️ Descargar el Excel del lote", build_excel(rows, raws),
                           file_name=f"Lote_DCF_{datetime.now():%Y%m%d_%H%M}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if any(r.get("Estado") in RESCUE_STATES for r in rows) and st.button("Reintentar las 'No confiables'"):
            with st.spinner("Esperando y reintentando…"):
                n = rescue(rows, raws, load_fn, waits=(15.0, 30.0))
            st.success(f"Recuperadas: {n}.")
            st.rerun()
        if st.button("Borrar resultados y empezar de cero"):
            st.session_state["lote_rows"], st.session_state["lote_raw"] = [], {}
            st.rerun()
    st.sidebar.caption(f"Versión de la app: {version}")
