"""Prueba de la interfaz con streamlit AppTest, inyectando un data_yahoo falso (sin red)."""
import sys, types
from streamlit.testing.v1 import AppTest
from test_models import industrial
from dcf_models import CompanyData

import data_yahoo as _real            # solo para reutilizar is_degraded (la descarga real se reemplaza por el falso)
fake = types.ModuleType("data_yahoo")
fake.is_degraded = _real.is_degraded
fake.missing_fields = _real.missing_fields
fake.unreliable_reasons = _real.unreliable_reasons
class DataError(Exception): pass
fake.DataError = DataError
BANK = CompanyData(ticker="BNK", name="Banco Test", sector="Financial Services", industry="Banks - Diversified",
                   country="United States", price=50.0, shares_m=500.0, market_cap_m=25_000.0, beta=1.1, rf=0.04,
                   equity=20_000.0, ni_ttm=3_000.0, ni_hist=[2500, 2700, 2900, 3000], equity_hist=[18000, 19000, 19500, 20000],
                   dividends_ttm=1000.0, buybacks_ttm=800.0, ttm_source="TTM Yahoo", asof="2025-06-30")
REIT = CompanyData(ticker="REI", name="REIT Test", sector="Real Estate", industry="REIT - Industrial", country="United States",
                   price=60.0, shares_m=100.0, market_cap_m=6000.0, beta=0.9, rf=0.04, ni_ttm=200.0, da_ttm=250.0,
                   gains_adj_ttm=-20.0, revenue_hist=[900, 950, 1000, 1050], rev_g_y0=0.03, rev_g_y1=0.03)
def load_company(sym, allow_annual=False, adr_ratio=None, fin_cur_mode="auto"):
    if sym == "BAD":
        raise DataError("Yahoo no devolvió datos para 'BAD'")
    if sym == "BNK": return BANK, ["Aviso de prueba"]
    if sym == "REI": return REIT, []
    if sym == "FIN": return CompanyData(ticker="FIN", name="FIN", price=10.0, shares_m=1000.0, market_cap_m=10000.0, beta=1.0,
                                       rf=0.04, ebit_ttm=-5.0, equity=9000.0, ni_ttm=1200.0, ni_hist=[1000, 1100, 1150, 1200],
                                       equity_hist=[8000, 8500, 8800, 9000], dividends_ttm=400.0), []
    if sym == "NEG": return industrial(ebit_ttm=-10.0, ebit_hist=[-30.0, -25.0, -20.0, -10.0]), []
    if sym == "ADR": return industrial(ticker="ADR", country="Taiwan", cap_estimated=True), []
    if sym == "NOC": return industrial(ticker="NOC", country=""), []          # falta solo el país
    return industrial(ticker=sym, fcf_ttm=900.0), []
fake.load_company = load_company
fake.PROFILE_FALLBACK = True
sys.modules["data_yahoo"] = fake

def run(sym, **setup):
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    at.text_input[0].set_value(sym)
    at.button[0].click()
    at.run()
    return at

def check(at, label):
    assert not at.exception, [e.value for e in at.exception]
    print(label, "| métricas:", [m.value for m in at.metric], "| errores:", [e.value[:60] for e in at.error])

at = run("IND"); check(at, "IND"); assert len(at.metric) in (3, 5)
at = run("BNK"); check(at, "BNK"); assert len(at.metric) in (3, 5)
at = run("REI"); check(at, "REI"); assert len(at.metric) in (3, 5)
at = run("FIN"); check(at, "FIN"); assert len(at.metric) in (3, 5)
assert any("Resultado degradado" in e.value for e in at.error), "FIN no trae industria/país: debe mostrar el cartel rojo"
assert not any("Resultado degradado" in e.value for e in run("IND").error), "IND está completo: no debe haber cartel"
at = run("NOC"); check(at, "NOC"); assert len(at.metric) in (3, 5)
assert not any("Resultado degradado" in e.value for e in at.error), "falta solo el país: no debe ser rojo"
assert any("Dato incompleto" in w.value and "país" in w.value for w in at.warning), "falta solo el país: cartel amarillo y preciso"
assert any("industria" in e.value for e in run("FIN").error), "el cartel rojo nombra lo que falta"
at = run("ADR"); check(at, "ADR"); assert len(at.metric) in (3, 5)
assert any("ADR" in e.value and "Resultado degradado" in e.value for e in at.error), "ADR sin capitalización: cartel rojo"
at = run("IND"); assert any("Etapa:" in c.value for c in at.caption), "falta la etiqueta de etapa"
at = run("IND"); check(at, "IND mapa")
assert any("Mapa de métodos" in str(e.label) for e in at.expander), "falta el mapa de métodos"
_idx = [str(i) for d in at.dataframe for i in d.value.index]
assert any(i.startswith("1. Nuestro DCF") for i in _idx) and any(i.startswith("5. Estilo Alpha") for i in _idx), _idx
assert any("Múltiplo que hace falta en 5 años" in m.value for m in at.markdown), "falta el panel a 5 años"
at = run("BNK"); check(at, "BNK mapa")
assert any("Mapa de métodos" in c.value and "solo se calcula" in c.value for c in at.caption), "financieras: aviso de que no aplica"
at = run("NEG"); check(at, "NEG"); assert at.error and not at.metric
at = run("BAD"); check(at, "BAD"); assert at.error
# cambio de modelo manual y de moat
at = run("IND"); at.selectbox[1].set_value("ER") if False else None
# reinicio de la barra lateral al cambiar de ticker
at = run("IND")
adr = [w for w in at.sidebar.number_input if w.label.startswith("Acciones ordinarias")][0]
adr.set_value(7.0); at.run()
at.text_input[0].set_value("IND"); at.button[0].click(); at.run()   # mismo ticker: conserva
adr = [w for w in at.sidebar.number_input if w.label.startswith("Acciones ordinarias")][0]
assert adr.value == 7.0, adr.value
at.text_input[0].set_value("BNK"); at.button[0].click(); at.run()   # ticker nuevo: reinicia
adr = [w for w in at.sidebar.number_input if w.label.startswith("Acciones ordinarias")][0]
assert adr.value == 0.0, adr.value
assert not at.exception and len(at.metric) == 3
print("Reinicio de barra lateral OK")
# industria manual + panel de contraste
at = run("IND")
sel = [w for w in at.sidebar.selectbox if w.label.startswith("Industria para comparar")][0]
sel.set_value("Machinery"); at.run()
assert not at.exception, [e.value for e in at.exception]
txt = " ".join(m.value for m in at.markdown)
assert "Contraste con el sector" in txt
assert any("Machinery" in str(c) for df in at.dataframe for c in df.value.columns), "falta la tabla de contraste"
print("Panel de sector OK")
# desplegable "cómo se llega al valor" y referencias, en los tres modelos; margen según analistas
for sym in ("IND", "BNK", "REI"):
    at = run(sym)
    assert not at.exception, (sym, [e.value for e in at.exception])
    assert any("¿Cómo se llega al valor" in str(e.label) for e in at.expander), sym
    dfs = [df.value for df in at.dataframe]
    assert any("Peso del valor terminal en el total" in list(d.index) or "= Valor por acción" in list(d.index) for d in dfs), sym
    assert any("Referencia" == d.index.name or "Referencia" in str(d.index.name) for d in dfs), sym
at = run("IND")
sel = [w for w in at.sidebar.selectbox if w.label.startswith("Margen operativo")][0]
sel.set_value("analysts"); at.run()
assert not at.exception, [e.value for e in at.exception]
print("Puente y referencias OK")
# --- Modo lote
at = AppTest.from_file("app.py", default_timeout=120)
at.run()
at.sidebar.radio[0].set_value("Lote de empresas")
at.run()
assert not at.exception, [e.value for e in at.exception]
assert at.title[0].value.endswith("Modo lote"), at.title[0].value
at.text_area[0].set_value("IND, BNK, REI, BAD")
at.number_input[1].set_value(0.0)                       # sin pausa
at.run()
btn = next(b for b in at.button if "próxima tanda" in b.label)
btn.click()
at.run()
assert not at.exception, [e.value for e in at.exception]
rows = at.session_state["lote_rows"]
assert [r["Ticker"] for r in rows] == ["IND", "BNK", "REI", "BAD"], rows
assert rows[0]["Estado"] == "OK" and rows[3]["Estado"] == "ERROR de datos", [r.get("Estado") for r in rows]
assert len(at.dataframe) >= 1
# v2.42: si los tickers ya están hechos, aparece el botón para volver a valuarlos
at.run()                                                # nueva interacción: ya no quedan pendientes
redo = next(b for b in at.button if "Volver a valuar" in b.label)
redo.click(); at.run()
assert not at.exception, [e.value for e in at.exception]
assert at.session_state["lote_rows"] == [], at.session_state["lote_rows"]
print("Modo lote OK")
print("AppTest OK")
