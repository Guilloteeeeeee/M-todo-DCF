"""Pruebas del mapa de métodos (v2.48): Dorsey contra su ejemplo de Clorox, coherencia interna y casos que no aplican (sin red)."""
from dataclasses import replace

import methods_map as mm
from dcf_models import Params, route_model, run_scenarios
from industry_data import attach
from test_models import industrial


def _base(**kw):
    co = industrial(ticker="IND", sector="Consumer Defensive", industry="Beverages - Non-Alcoholic", country="United States", fcf_ttm=900.0, **kw)
    co, ind, _ = attach(co, "FCFF", "Beverage (Soft)")
    p = Params(horizon=10, g_terminal=0.035, erp=0.037, moat="auto", marginal_tax=0.25, use_industry_beta=True)
    res = run_scenarios(co, p, "FCFF")["Base"]
    assert res.ok, res.error
    return co, res


def test_dorsey_reproduce_el_ejemplo_de_clorox():
    """Libro de Dorsey, cap. 10: flujo de 600 M, crece 5 % diez años, perpetuidad 3 %, tasa 9 %, 221 M de acciones -> 12.000 M / 221 = 54,30 por acción."""
    v = mm.dorsey_value(600.0, 221.0, 0.05, 0.09)
    assert abs(v - 54.30) < 0.05, v
    assert mm.dorsey_value(-5.0, 100.0, 0.05, 0.09) is None and mm.dorsey_value(100.0, 100.0, 0.05, 0.02) is None   # flujo negativo / tasa ≤ perpetuidad


def test_los_cinco_metodos_y_el_panel():
    co, res = _base()
    mp = mm.methods_map(co, res, "FCFF")
    assert mp["applicable"] and [it["key"] for it in mp["items"]] == list(mm.KEYS)
    byk = {it["key"]: it for it in mp["items"]}
    assert abs(byk["m1"]["valor"] - res.per_share) < 1e-9
    for k in ("m2", "m3", "m4", "m5"):
        assert byk[k]["valor"] is not None and byk[k]["valor"] > 0, k
    assert byk["m5"]["circular"] and not byk["m1"]["circular"]
    assert byk["m3"]["rango"] and byk["m3"]["rango"][0] <= byk["m3"]["valor"] <= byk["m3"]["rango"][1]
    lo, hi = mp["rango"]
    assert lo <= res.per_share <= hi and all(it["valor"] <= hi + 1e-9 for it in mp["items"] if it["valor"] and not it["circular"])
    assert mp["panel"] and mp["panel"]["mult_requerido"] is not None


def test_panel_es_coherente_consigo_mismo():
    """Si el múltiplo de salida fuera justo el requerido, el retorno anual sería el costo de capital; y con el múltiplo del propio modelo el valor a 5 años coincide."""
    co, res = _base()
    mp = mm.methods_map(co, res, "FCFF")
    pn = mp["panel"]
    sh, price = co.shares_m, co.price
    tb = res.table
    bridge = res.equity_value - res.ev
    fc = [r["FCFF"] / sh for r in tb[:5]]
    v5 = (pn["mult_requerido"] * pn["ebit5"] + bridge) / sh
    irr = mm._irr([-price] + fc[:4] + [fc[4] + v5])
    assert abs(irr - pn["wacc"]) < 1e-6, (irr, pn["wacc"])
    v5_model = (pn["mult5_model"] * pn["ebit5"] + bridge) / sh
    assert abs(v5_model - pn["valor5_modelo"]) < 1e-6
    # el valor de hoy con los flujos 1-5 + valor al año 5 del propio modelo = valor del modelo
    acc, dfs = 1.0, []
    for r in tb:
        acc *= (1 + r["WACC"]); dfs.append(acc)
    hoy = (sum(r["VP"] for r in tb[:5]) + pn["ev5_model"] / dfs[4] + bridge) / sh
    assert abs(hoy - res.per_share) < 1e-6, (hoy, res.per_share)


def test_metodo_2_con_el_multiplo_del_modelo_da_el_valor_del_modelo(monkeypatch=None):
    co, res = _base()
    mp0 = mm.methods_map(co, res, "FCFF")
    pn = mp0["panel"]
    ebit0 = res.extras["margin0"] * co.revenue_ttm
    metric = co.ebit_ttm + co.da_ttm
    fake = pn["ev5_model"] / (metric * pn["ebit5"] / ebit0)
    original = mm.get_multiples
    mm.get_multiples = lambda name: dict(n=50, ev_ebitdard=fake, ev_ebitda=fake)
    try:
        mp = mm.methods_map(co, res, "FCFF")
    finally:
        mm.get_multiples = original
    v2 = next(it for it in mp["items"] if it["key"] == "m2")["valor"]
    assert abs(v2 - res.per_share) < 1e-6, (v2, res.per_share)


def test_no_aplica_a_financieras_ni_sin_datos():
    co, res = _base()
    assert not mm.methods_map(co, res, "ER")["applicable"]
    assert not mm.methods_map(co, None, "FCFF")["applicable"]
    # sin flujo de caja libre real: Dorsey n/d pero el resto se calcula, con una explicación
    co2 = replace(co, fcf_ttm=None)
    mp = mm.methods_map(co2, res, "FCFF")
    m3 = next(it for it in mp["items"] if it["key"] == "m3")
    assert m3["valor"] is None and "flujo de caja libre" in m3["nota"].lower()
    assert next(it for it in mp["items"] if it["key"] == "m2")["valor"] is not None
    # flujo negativo: el método no aplica
    co3 = replace(co, fcf_ttm=-50.0)
    m3b = next(it for it in mm.methods_map(co3, res, "FCFF")["items"] if it["key"] == "m3")
    assert m3b["valor"] is None and "negativo" in m3b["nota"]


def test_sin_multiplo_de_industria_se_avisa():
    co, res = _base()
    original = mm.get_multiples
    mm.get_multiples = lambda name: None
    try:
        mp = mm.methods_map(co, res, "FCFF")
    finally:
        mm.get_multiples = original
    byk = {it["key"]: it for it in mp["items"]}
    assert byk["m2"]["valor"] is None and byk["m4"]["valor"] is None and byk["m3"]["valor"] is not None
    assert any("No hay múltiplo de industria" in n for n in mp["notas"])


def test_tabla_de_multiplos_cubre_las_industrias_y_dorsey_sube_con_el_crecimiento():
    from industry_data import IND
    from industry_multiples import MULT
    assert set(MULT) <= set(IND) and len(MULT) == 91
    assert all(v[1] > 0 and v[2] > 0 and v[0] > 0 for v in MULT.values())
    vs = [mm.dorsey_value(1000.0, 100.0, g, 0.09) for g in (0.03, 0.05, 0.09)]
    assert vs[0] < vs[1] < vs[2]


def _it(key, ratio, price=100.0):
    return dict(key=key, valor=None if ratio is None else ratio * price, circular=(key == "m5"))


def test_combinado_reglas():
    """v2.54: mediana con 3+, promedio con 2, el circular nunca entra, múltiplo extremo excluye 2 y 4, marca de coincidencia ±25 %."""
    c = mm.combine([_it("m1", 1.0), _it("m2", 1.1), _it("m3", 0.9), _it("m4", 1.05), _it("m5", 5.0)], 100.0, 14.0)
    assert c["regla"] == "mediana" and c["keys"] == ["m1", "m2", "m3", "m4"] and abs(c["ratio"] - 1.025) < 1e-9
    assert c["coinciden"] is True and c["marca"] == "coinciden" and "m5" in c["excluidos"]
    # un método loco no mueve la mediana, pero la marca avisa
    c = mm.combine([_it("m1", 1.0), _it("m2", 1.1), _it("m3", 0.2), _it("m4", 1.05)], 100.0, 14.0)
    assert abs(c["ratio"] - 1.025) < 1e-9 and c["coinciden"] is False and c["marca"].startswith("no coinciden")
    # con 2 métodos, promedio
    c = mm.combine([_it("m1", 1.0), _it("m2", None), _it("m3", 1.2), _it("m4", None)], 100.0, 14.0)
    assert c["regla"] == "promedio" and abs(c["ratio"] - 1.1) < 1e-9 and c["excluidos"]["m2"] == "no aplica a esta empresa"
    # múltiplo extremo: salen 2 y 4; queda 1 solo -> sin combinado
    c = mm.combine([_it("m1", 1.0), _it("m2", 9.0), _it("m3", None), _it("m4", 8.0)], 100.0, 47.8)
    assert c["ratio"] is None and "un solo método" in c["marca"] and "extremo" in c["excluidos"]["m2"] and "extremo" in c["excluidos"]["m4"]
    # valores negativos no entran
    c = mm.combine([_it("m1", 1.0), _it("m2", -0.5), _it("m3", 1.1), _it("m4", 1.2)], 100.0, 14.0)
    assert c["keys"] == ["m1", "m3", "m4"] and "negativo" in c["excluidos"]["m2"]


def test_combinado_en_el_mapa():
    co, res = _base()
    mp = mm.methods_map(co, res, "FCFF")
    cb = mp["combinado"]
    assert cb and cb["ratio"] is not None and "m5" not in cb["keys"] and cb["lo"] <= cb["valor"] <= cb["hi"]
    assert mm.methods_map(co, res, "FFE")["combinado"] is None


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("OK", k)
    print(n, "pruebas OK")
