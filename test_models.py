"""Pruebas de invariantes del motor con datos sintéticos (sin red)."""
from dataclasses import replace
import math

from dcf_models import (CompanyData, Params, SCENARIOS, value_company, run_scenarios, sensitivity,
                        route_model, fcff_value, excess_return_value, reit_value, Scen)


def industrial(**kw):
    d = dict(ticker="IND", name="Industrial SA", sector="Industrials", industry="Specialty Industrial",
             country="United States", price=100.0, currency="USD", fin_currency="USD",
             shares_m=100.0, market_cap_m=10_000.0, beta=1.0, rf=0.04,
             revenue_ttm=10_000.0, ebit_ttm=1_500.0, da_ttm=400.0, capex_ttm=500.0, nwc_inv_ttm=50.0,
             tax_rate_eff=0.21, interest_expense_ttm=100.0,
             revenue_hist=[8_000, 8_800, 9_400, 9_800], ebit_hist=[1_100, 1_250, 1_400, 1_450],
             invested_capital=8_000.0, cash=500.0, debt=2_000.0, lease_debt=0.0, minority=0.0,
             rev_g_y0=0.05, rev_g_y1=0.05)
    d.update(kw)
    return CompanyData(**d)


def test_no_moat_growth_is_worthless():
    """Con ROIC terminal = WACC, el valor terminal NO depende de g (crecimiento sin valor)."""
    co = industrial()
    p = Params(moat_spread=0.0)
    vals = []
    for g in (0.01, 0.025, 0.035):
        r = fcff_value(co, replace(p, g_terminal=g), SCENARIOS["Base"])
        # TV = NOPAT*(1+g)/WACC -> comparable vía NOPAT_N: verificamos TV*WACC/(NOPAT_N*(1+g)) == 1
        nopat_n = r.table[-1]["NOPAT"]
        w = r.extras["wacc"]
        assert abs(r.extras["tv"] * w / (nopat_n * (1 + r.g_terminal)) - 1) < 1e-9
        vals.append(r.per_share)
    print("  FCFF sin moat:", [round(v, 2) for v in vals])


def test_scenarios_ordered():
    for co in (industrial(),):
        res = run_scenarios(co, Params(moat_spread=0.02), "FCFF")
        a, b, c = (res[k].per_share for k in ("Pesimista", "Base", "Optimista"))
        assert a < b < c, (a, b, c)
        print("  FCFF escenarios:", round(a, 1), round(b, 1), round(c, 1))


def test_more_moat_more_value():
    co = industrial()
    v = [fcff_value(co, Params(moat_spread=s), SCENARIOS["Base"]).per_share for s in (0.0, 0.02, 0.05)]
    assert v[0] < v[1] < v[2], v


def test_higher_wacc_lower_value():
    co = industrial()
    lo = fcff_value(co, Params(wacc_override=0.07), SCENARIOS["Base"]).per_share
    hi = fcff_value(co, Params(wacc_override=0.10), SCENARIOS["Base"]).per_share
    assert lo > hi


def test_ebit_negative_stops():
    r = value_company(industrial(ebit_ttm=-50.0, ebit_hist=[-100.0, -80.0, -60.0, -50.0]), Params(), "FCFF", "Base")
    assert not r.ok and "EBIT" in r.error            # sin historia rentable ni industria: no hay margen objetivo
    r = value_company(industrial(ebit_ttm=-50.0), Params(), "FCFF", "Base")
    assert r.ok and "rentables de la propia empresa" in " ".join(r.warnings), r.warnings   # ya fue rentable: se recupera a su nivel


def test_excess_return_invariant_roe_eq_ke():
    """ROE = Ke => valor = book value, para cualquier persistencia/payout."""
    ke = 0.04 + (0.67 * 1.0 + 0.33) * 0.045
    bv = 20_000.0
    co = CompanyData(ticker="BNK", industry="Banks - Regional", sector="Financial Services",
                     country="United States", price=50.0, shares_m=500.0, market_cap_m=25_000.0,
                     beta=1.0, rf=0.04, equity=bv, ni_ttm=ke * bv, ni_hist=[ke * bv] * 4,
                     equity_hist=[bv] * 4, dividends_ttm=1_000.0, buybacks_ttm=500.0)
    for pers in (0.0, 0.5, 1.0):
        r = excess_return_value(co, Params(persistence=pers), SCENARIOS["Base"])
        assert abs(r.equity_value / bv - 1) < 1e-9, (pers, r.equity_value / bv)
    print("  ER ROE=Ke -> P/B =1 OK")


def test_excess_return_roe_above_ke():
    bv = 20_000.0
    co = CompanyData(ticker="BNK", industry="Banks - Diversified", country="United States", price=50.0,
                     shares_m=500.0, market_cap_m=25_000.0, beta=1.0, rf=0.04, equity=bv,
                     ni_ttm=0.15 * bv, ni_hist=[0.14 * bv, 0.15 * bv, 0.16 * bv, 0.15 * bv],
                     equity_hist=[bv] * 4, dividends_ttm=1_500.0, buybacks_ttm=1_000.0)
    res = run_scenarios(co, Params(), "ER")
    a, b, c = (res[k].per_share for k in ("Pesimista", "Base", "Optimista"))
    assert a < b < c
    assert res["Pesimista"].equity_value > 0
    # persistencia 0 => ROE_T = Ke => TV de retorno excedente = 0
    assert abs(res["Pesimista"].extras["roe_T"] - res["Pesimista"].ke) < 1e-12
    print("  ER escenarios:", round(a, 1), round(b, 1), round(c, 1), " P/B base", round(res["Base"].extras["pb_implied"], 2))


def test_reit_no_spread_is_affo_over_ke():
    """ROI = Ke => valor = AFFO0*(1+g)/(Ke-g) ... el crecimiento retenido no crea valor => AFFO/Ke aprox."""
    co = CompanyData(ticker="REI", industry="REIT - Industrial", sector="Real Estate", country="United States",
                     price=60.0, shares_m=100.0, market_cap_m=6_000.0, beta=0.9, rf=0.04,
                     ni_ttm=200.0, da_ttm=250.0, gains_adj_ttm=-20.0, revenue_hist=[900, 950, 1000, 1050],
                     rev_g_y0=0.03, rev_g_y1=0.03)
    r = reit_value(co, Params(roi_spread=0.0), replace(SCENARIOS["Base"], roi_spread=0.0))
    affo1 = r.table[0]["AFFO"]            # AFFO del año 1 (ya incluye el crecimiento del año 1)
    ke = r.ke
    assert abs(r.equity_value / (affo1 / ke) - 1) < 1e-9, (r.equity_value, affo1 / ke)
    print("  REIT ROI=Ke -> V = AFFO1/Ke OK; AFFO/acción", round(r.extras["affo_ps"], 2))
    res = run_scenarios(co, Params(), "REIT")
    a, b, c = (res[k].per_share for k in ("Pesimista", "Base", "Optimista"))
    assert a < b < c, (a, b, c)
    print("  REIT escenarios:", round(a, 1), round(b, 1), round(c, 1))


def test_reit_override_affo():
    co = CompanyData(ticker="REI", industry="REIT - Retail", price=60.0, shares_m=100.0, market_cap_m=6000.0,
                     beta=0.9, rf=0.04, ni_ttm=1.0, da_ttm=1.0, revenue_hist=[900, 950, 1000])
    r = value_company(co, Params(affo_ps_override=4.0), "REIT", "Base")
    assert r.ok and abs(r.extras["affo_ps"] - 4.0) < 1e-9


def test_routing():
    assert route_model(CompanyData("A", industry="Banks - Diversified"))[0] == "ER"
    assert route_model(CompanyData("A", industry="Insurance - Life"))[0] == "ER"
    assert route_model(CompanyData("A", industry="Insurance Brokers"))[0] == "FCFF"
    assert route_model(CompanyData("A", industry="REIT - Residential"))[0] == "REIT"
    assert route_model(CompanyData("A", industry="REIT - Mortgage"))[0] == "ER"
    assert route_model(CompanyData("A", industry="Software - Infrastructure"))[0] == "FCFF"


def test_routing_without_industry():
    assert route_model(CompanyData("A", name="First Bancorp", sector=""))[0] == "ER"
    assert route_model(CompanyData("A", name="Realty Income Corporation"))[0] == "REIT"
    assert route_model(CompanyData("A", name="Banco Santander", industry=""))[0] == "ER"
    assert route_model(CompanyData("A", name="Foo", sector="Financial Services"))[0] == "ER"
    assert route_model(CompanyData("A", name="JPMorgan Chase & Co.", ebit_ttm=0, ni_ttm=5.0, equity=50.0))[0] == "ER"
    assert route_model(CompanyData("A", name="Coca-Cola", ebit_ttm=14000, ni_ttm=10000, equity=25000))[0] == "FCFF"


def test_routing_credit_services():
    assert route_model(CompanyData("V", industry="Credit Services"))[0] == "FCFF"
    assert route_model(CompanyData("MA", industry="Credit Services"))[0] == "FCFF"
    assert route_model(CompanyData("AXP", industry="Credit Services"))[0] == "ER"
    assert route_model(CompanyData("COF", industry="Credit Services"))[0] == "ER"


def test_country_crp():
    from country_risk import country_crp
    assert country_crp("United States")[0] == 0.0
    assert abs(country_crp("Brazil")[0] - (0.0324 - 0.0023)) < 1e-9
    assert country_crp("South Korea")[0] > 0 and country_crp("Germany")[0] == 0.0
    assert country_crp("")[0] == 0.0 and "no informado" in country_crp("")[1]
    assert country_crp("Atlantis")[0] == 0.0 and "no figura" in country_crp("Atlantis")[1]


def test_routing_known_tickers_and_ebit_negative():
    assert route_model(CompanyData("JPM", name="JPM"))[0] == "ER"
    assert route_model(CompanyData("ITUB", name="ITUB"))[0] == "ER"
    assert route_model(CompanyData("O", name="O"))[0] == "REIT"
    assert route_model(CompanyData("KO", name="KO", ebit_ttm=100, ni_ttm=50, equity=100))[0] == "FCFF"
    assert route_model(CompanyData("XXX", name="XXX", ebit_ttm=-5, ni_ttm=50, equity=100))[0] == "ER"


def test_sensitivity_monotone():
    co = industrial()
    s = sensitivity(co, Params(), "FCFF")
    assert s["ok"]
    g = s["grid"]
    for row in g:  # a mayor g, mayor valor (ROIC_T > WACC)
        assert row[0] < row[-1]
    for j in range(5):  # a mayor tasa, menor valor
        assert g[0][j] > g[-1][j]


def test_us_leases_excluded():
    co = industrial(debt=3_000.0, lease_debt=1_000.0)
    v_us = fcff_value(co, Params(), SCENARIOS["Base"])
    v_in = fcff_value(replace(co, country="Netherlands"), Params(), SCENARIOS["Base"])
    assert v_us.extras["debt"] == 2_000.0 and v_in.extras["debt"] == 3_000.0


def test_no_analyst_fallback_and_capped():
    co = industrial(rev_g_y0=None, rev_g_y1=None, revenue_hist=[100, 160, 260, 420])
    r = fcff_value(co, Params(), SCENARIOS["Base"])
    assert r.extras["g1"] <= 0.12 + 1e-9


def test_bridge_identity():
    r = fcff_value(industrial(cash=500.0, debt=2000.0, minority=30.0, non_op_assets=700.0), Params(), SCENARIOS["Base"])
    e = r.extras
    assert abs(r.equity_value - (e["pv_explicit"] + e["pv_tv"] - e["debt"] + e["cash"] + e["nonop"] - e["minority"])) < 1e-6
    assert e["nonop"] == 700.0
    r0 = fcff_value(industrial(cash=500.0, debt=2000.0, minority=30.0, non_op_assets=700.0), Params(include_nonop=False),
                    SCENARIOS["Base"])
    assert r.equity_value - r0.equity_value >= 700.0 - 1e-6      # +700 de inversiones y, además, menor capital operativo (ROIC mayor)


def test_operating_invested_capital():
    """El capital invertido para el ROIC excluye caja e inversiones no operativas (criterio Damodaran)."""
    co = industrial(equity=6000.0, debt=3000.0, cash=1000.0, non_op_assets=2000.0, lease_debt=0.0, minority=0.0)
    r = fcff_value(co, Params(), SCENARIOS["Base"])
    assert abs(r.extras["ic_op"] - (3000 + 6000 - 1000 - 2000)) < 1e-9
    from dcf_models import margin_target
    _, mT, _ = margin_target(co, Params(), SCENARIOS["Base"])
    nopat_norm = co.revenue_ttm * mT * (1 - co.tax_rate_eff)          # ROIC inicial normalizado con el margen objetivo
    assert abs(r.extras["roic0"] - min(nopat_norm / 6000, 0.40)) < 1e-9
    r2 = fcff_value(co, Params(include_nonop=False), SCENARIOS["Base"])
    assert abs(r2.extras["ic_op"] - 8000) < 1e-9
    assert abs(r.ev - (r.extras["pv_explicit"] + r.extras["pv_tv"])) < 1e-6


def test_roic0_normalized_with_target_margin():
    """EBIT TTM deprimido por un cargo extraordinario: el ROIC inicial sale del margen objetivo (mediana), igual en los 3 escenarios."""
    hist_ebit = [2_800, 2_900, 3_000, 3_000]                       # margen ~30 % sobre ingresos de 10.000
    co = industrial(revenue_hist=[9_000, 9_500, 9_800, 10_000], ebit_hist=hist_ebit, ebit_ttm=1_000.0, revenue_ttm=10_000.0,
                    equity=8_000.0, debt=2_000.0, cash=500.0)
    rs = {k: fcff_value(co, Params(), s) for k, s in SCENARIOS.items()}
    r0 = {k: v.extras["roic0"] for k, v in rs.items()}
    assert len({round(x, 12) for x in r0.values()}) == 1, r0          # no depende del escenario
    ttm_based = 1_000.0 * (1 - 0.21) / rs["Base"].extras["ic_op"]
    assert r0["Base"] > 2 * ttm_based, (r0["Base"], ttm_based)         # normalizado >> el del TTM deprimido
    # v2.25: con TTM distorsionado el NOPAT de partida ya es el normalizado; el aviso pasa a ser el de la distorsión
    assert any("arranca del margen normal" in w for w in rs["Base"].warnings), rs["Base"].warnings
    # empresa sin distorsión: sin aviso
    clean = fcff_value(industrial(), Params(), SCENARIOS["Base"])
    assert not any("ROIC inicial normalizado" in w for w in clean.warnings)


def test_analyst_range_scenarios_and_margin():
    from dcf_models import analyst_margin, margin_options
    co = industrial(rev_g_y0=.05, rev_g_y1=.05, rev_gl_y0=.02, rev_gl_y1=.02, rev_gh_y0=.09, rev_gh_y1=.10,
                    eps_g_y0=.12, eps_g_y1=.12)
    r = {n: fcff_value(co, Params(), SCENARIOS[n]).extras for n in ("Pesimista", "Base", "Optimista")}
    assert abs(r["Base"]["g1"] - .05) < 1e-9
    assert abs(r["Pesimista"]["g1"] - (.05 - .0255)) < 1e-9 and abs(r["Optimista"]["g2"] - (.05 + .0425)) < 1e-9, r
    # sin rango de analistas: +-3 puntos fijos como antes
    co2 = industrial(rev_g_y0=.05, rev_g_y1=.05)
    assert abs(fcff_value(co2, Params(), SCENARIOS["Pesimista"]).extras["g1"] - .02) < 1e-9
    # margen según analistas
    m0 = co.ebit_ttm / co.revenue_ttm
    assert abs(analyst_margin(co, m0) - m0 * (1.12 ** 2 / 1.05 ** 2)) < 1e-9
    assert analyst_margin(co2, m0) is None
    mo = margin_options(co)
    assert set(mo) == {"ttm", "median", "analysts"} and mo["analysts"] > mo["ttm"]
    ra = fcff_value(co, Params(margin_mode="analysts"), SCENARIOS["Base"]).extras
    assert abs(ra["margin_target"] - mo["analysts"]) < 1e-9
    rb = fcff_value(co2, Params(margin_mode="analysts"), SCENARIOS["Base"]).extras     # sin datos: cae a mediana
    assert abs(rb["margin_target"] - margin_options(co2)["median"]) < 1e-9


def test_synthetic_kd_and_growth_hold():
    from dcf_models import synthetic_spread
    assert synthetic_spread(2.0, True) == 0.0275 and synthetic_spread(2.1, True) == 0.0184
    assert synthetic_spread(9.0, True) == 0.0040 and synthetic_spread(-3, False) == 0.19
    r = fcff_value(industrial(rev_g_y0=0.08, rev_g_y1=0.08), Params(growth_override=(0.06, 0.06), g_terminal=0.025),
                   SCENARIOS["Base"])
    g = [row["Crecimiento"] for row in r.table]
    assert g[:5] == [0.06] * 5 and abs(g[-1] - 0.025) < 1e-9 and all(g[i] > g[i + 1] for i in range(4, 9)), g
    assert "sintética" in r.extras["kd_note"]


def test_blume_only_without_industry_and_bbb_cap():
    from industry_data import attach
    co = industrial(beta=0.7, industry="Beverages - Non-Alcoholic")
    r_no = fcff_value(co, Params(), SCENARIOS["Base"])                       # sin sector: Blume
    assert abs(r_no.extras["ke"] - (0.04 + (0.67 * 0.7 + 0.33) * 0.045)) < 1e-9
    co2, _, _ = attach(co, "FCFF")
    r_si = fcff_value(co2, Params(), SCENARIOS["Base"])                       # con sector: sin Blume
    assert abs(r_si.extras["ke"] - (0.04 + r_si.extras["beta"] * 0.045)) < 1e-9     # con sector: promedio con la propia (v2.34)
    # utility con cobertura 2x: spread tope BBB; empresa común con la misma cobertura: sin tope
    ut = industrial(industry="Utilities - Regulated Electric", ebit_ttm=1500.0, interest_expense_ttm=700.0, debt=10_000.0)
    cm = industrial(industry="Specialty Retail", ebit_ttm=1500.0, interest_expense_ttm=700.0, debt=10_000.0)
    kd_ut = fcff_value(ut, Params(rf=0.04), SCENARIOS["Base"]).extras["kd"]
    kd_cm = fcff_value(cm, Params(rf=0.04), SCENARIOS["Base"]).extras["kd"]
    assert abs(kd_ut - (0.04 + 0.0111)) < 1e-9 and abs(kd_cm - (0.04 + 0.0184)) < 1e-9, (kd_ut, kd_cm)


def test_industry_beta_pure():
    from industry_data import attach, map_industry
    co = industrial(beta=0.28, industry="Beverages - Non-Alcoholic")
    assert map_industry(co.industry) == "Beverage (Soft)"
    co2, name, how = attach(co, "FCFF")
    assert name == "Beverage (Soft)" and co2.ind_ubeta and co2.ind_beta_lev is None
    e0 = fcff_value(co, Params(), SCENARIOS["Base"]).extras                       # sin sector: Blume sin piso
    e1 = fcff_value(co2, Params(), SCENARIOS["Base"]).extras                      # industria pura (re-apalancada)
    e2 = fcff_value(co2, Params(use_industry_beta=False), SCENARIOS["Base"]).extras
    e3 = fcff_value(co2, Params(beta=1.2), SCENARIOS["Base"]).extras
    assert e0["beta"] == 0.28 and abs(e0["ke"] - (0.04 + (0.67 * 0.28 + 0.33) * 0.045)) < 1e-9
    bu = co2.ind_ubeta * (1 + 0.75 * 2000 / 10000)
    assert abs(e1["beta"] - max(0.5, min(2.0, (bu + 0.28) / 2))) < 1e-9           # v2.34: promedio con la propia, piso 0,5, tope 2,0
    assert e2["beta"] == 0.28 and e3["beta"] == 1.2
    # beta propia <= 0 sin industria: no confiable -> 1,0
    r = fcff_value(industrial(beta=-0.1), Params(), SCENARIOS["Base"])
    assert r.extras["beta"] == 1.0 and any("no es confiable" in w for w in r.warnings)
    co3, _, _ = attach(industrial(beta=None, industry="Banks - Regional", country="Brazil"), "ER")
    assert co3.ind_beta_lev and co3.ind_region == "Global"
    print("  beta industria+propia KO-like:", round(e1["beta"], 3))


def test_beta_mezcla_con_piso_y_tope():
    from dataclasses import replace
    from industry_data import attach
    from dcf_models import BETA_MIN, BETA_MAX
    assert (BETA_MIN, BETA_MAX) == (0.5, 2.0)
    base, _, _ = attach(industrial(beta=1.0, industry="Beverages - Non-Alcoholic"), "FCFF")
    bu = base.ind_ubeta * (1 + 0.75 * 2000 / 10000)

    def beta_de(own, **kw):
        co = replace(base, beta=own)
        r = fcff_value(co, Params(**kw), SCENARIOS["Base"])
        return r.extras["beta"], r.extras["ke"], r.warnings
    # promedio simple cuando está dentro de los límites
    b, ke, w = beta_de(1.0)
    assert abs(b - max(0.5, (bu + 1.0) / 2)) < 1e-9 and abs(ke - (0.04 + b * 0.045)) < 1e-9 and any("promedio" in x for x in w)
    # piso: propia muy baja + industria baja -> 0,5
    b, _, w = beta_de(0.05)
    assert abs(b - max(0.5, (bu + 0.05) / 2)) < 1e-9
    if (bu + 0.05) / 2 < 0.5:
        assert b == 0.5 and any("piso" in x for x in w)
    # tope: propia enorme -> el promedio no pasa de 2,0
    b, _, w = beta_de(6.0)
    assert b <= 2.0 + 1e-12
    big, _, _ = attach(industrial(beta=6.0, industry="Semiconductors"), "FCFF")
    bb, _, wb = (lambda r: (r.extras["beta"], r.extras["ke"], r.warnings))(fcff_value(big, Params(), SCENARIOS["Base"]))
    assert bb <= 2.0 + 1e-12
    # propia ausente o <= 0: solo la industria (con límites)
    for own in (None, -0.3, 0.0):
        b, _, w = beta_de(own)
        assert abs(b - max(0.5, min(2.0, bu))) < 1e-9 and any("no es confiable o falta" in x for x in w), (own, b)
    # beta manual no se toca
    assert beta_de(1.0, beta=0.3)[0] == 0.3
    # sin industria: Blume con piso 0,5
    r = fcff_value(industrial(beta=0.1), Params(), SCENARIOS["Base"])
    assert r.extras["beta"] == 0.1 and abs(r.extras["ke"] - (0.04 + 0.5 * 0.045)) < 1e-9
    print("  beta mezcla: industria", round(bu, 3), "→ ok")


def test_loss_negative_fcf_and_reinvestment():
    from dcf_models import ModelError
    from industry_data import attach
    loss_co = industrial(ebit_ttm=-300.0, ebit_hist=[-500, -400, -350, -320], industry="Specialty Retail")
    # 1) sin datos de industria ni margen manual: se rechaza y el mensaje explica cómo seguir
    try:
        fcff_value(loss_co, Params(), SCENARIOS["Base"])
        assert False, "debía rechazar"
    except ModelError as e:
        assert "industria" in str(e).lower()
    # 2) con industria: el margen objetivo es el promedio de la industria
    loss_i, _, _ = attach(loss_co, "FCFF")
    r = fcff_value(loss_i, Params(), SCENARIOS["Base"])
    assert r.ok and math.isfinite(r.per_share) and any("pérdida operativa" in w for w in r.warnings)
    assert abs(r.extras["margin_target"] - loss_i.ind_margin) < 1e-9, (r.extras["margin_target"], loss_i.ind_margin)
    assert r.table[0]["Margen"] < r.table[-1]["Margen"] and r.table[-1]["Margen"] > 0.03
    assert r.extras["moat_label"] == "Ninguno"
    # 3) con margen manual positivo manda el manual
    r_m = fcff_value(loss_co, Params(margin_mode="manual", margin_manual=0.15), SCENARIOS["Base"])
    assert r_m.ok and abs(r_m.extras["margin_target"] - 0.15) < 1e-9
    # 4) FCF negativo con EBIT positivo (capex enorme): valúa y avisa
    heavy = industrial(capex_ttm=3_000.0)
    r2 = fcff_value(heavy, Params(), SCENARIOS["Base"])
    assert r2.ok and any("negativo" in w for w in r2.warnings), r2.warnings
    # 5) la reinversión sale solo del crecimiento: un pago único en capital de trabajo no cambia el valor
    base_v = fcff_value(industrial(), Params(), SCENARIOS["Base"]).per_share
    spike_v = fcff_value(industrial(nwc_inv_ttm=6_000.0), Params(), SCENARIOS["Base"]).per_share
    assert abs(base_v - spike_v) < 1e-9, (base_v, spike_v)


def test_scenarios_only_business_levers():
    """Pesimista/Optimista no mueven ni el WACC ni g terminal (eso va en Sensibilidad)."""
    co = industrial()
    res = run_scenarios(co, Params(), "FCFF")
    assert len({round(res[k].extras["wacc"], 12) for k in res}) == 1
    assert len({round(res[k].g_terminal, 12) for k in res}) == 1
    er = run_scenarios(industrial(equity=5_000.0, ni_ttm=800.0), Params(), "ER")
    assert len({round(er[k].ke, 12) for k in er}) == 1


def test_wacc_converges_to_sector():
    from industry_data import attach
    from dcf_models import sector_wacc
    co2, _, _ = attach(industrial(beta=1.0, industry="Beverages - Non-Alcoholic"), "FCFF")
    p = Params(rf=0.0524, erp=0.0425)
    ws = sector_wacc(co2, p)
    assert ws is not None and 0.06 < ws < 0.09
    co3 = replace(co2, debt=5_000.0)
    ws = sector_wacc(co3, p)                  # v2.35: el WACC terminal usa la beta de la empresa (desapalancada) → depende de su deuda
    r = fcff_value(co3, p, SCENARIOS["Base"])
    w = [row["WACC"] for row in r.table]
    assert abs(w[0] - r.extras["wacc"]) < 1e-12 and abs(w[4] - r.extras["wacc"]) < 1e-12      # constante hasta el año 5
    assert abs(w[-1] - ws) < 1e-12 and abs(r.extras["wacc_T"] - ws) < 1e-12                    # llega al del sector
    # sin datos de industria o con WACC manual: constante
    r_no = fcff_value(industrial(), Params(), SCENARIOS["Base"])
    assert len({round(row["WACC"], 12) for row in r_no.table}) == 1
    r_man = fcff_value(co2, Params(wacc_override=0.09), SCENARIOS["Base"])
    assert len({round(row["WACC"], 12) for row in r_man.table}) == 1
    # el desplazamiento de la sensibilidad mueve ambos extremos
    r_up = fcff_value(co3, replace(p, wacc_shift=0.01), SCENARIOS["Base"])
    assert abs(r_up.extras["wacc_T"] - ws - 0.01) < 1e-12


def test_moat_auto_classification():
    from dcf_models import classify_moat
    stable = [1_500, 1_520, 1_480, 1_500]
    co = industrial(ind_roc=0.20, ind_margin=0.10, ebit_hist=stable, ebit_ttm=1_500.0)
    lab, why = classify_moat(co, 0.08, 0.30, False)             # exceso de retorno + estable + mejor que el sector
    assert lab == "Amplio" and len(why) == 3, (lab, why)
    # sin exceso de retorno NO hay foso, aunque el margen sea alto y estable
    assert classify_moat(co, 0.08, 0.12, False)[0] == "Ninguno"
    # exceso de retorno pero margen en caída: Estrecho
    falling = replace(co, ebit_hist=[2_000, 1_900, 1_000, 800], ebit_ttm=700.0)
    assert classify_moat(falling, 0.08, 0.30, False)[0] == "Estrecho"
    # exceso de retorno estable pero peor que sus pares (sector de retorno y margen altos): Estrecho
    tough = replace(co, ind_roc=0.60, ind_margin=0.40)
    assert classify_moat(tough, 0.08, 0.30, False)[0] == "Estrecho"
    assert classify_moat(co, 0.08, 0.30, True)[0] == "Ninguno"  # pérdida
    # integración: automático por defecto, y el selector manual manda
    r_auto = fcff_value(co, Params(), SCENARIOS["Base"])
    assert r_auto.extras["moat_src"] == "automático"
    r_man = fcff_value(co, Params(moat="Ninguno"), SCENARIOS["Base"])
    assert r_man.extras["moat_label"] == "Ninguno" and r_man.extras["moat_src"] == "elegido"
    assert r_man.per_share < r_auto.per_share or r_auto.extras["moat_label"] == "Ninguno"


def test_moat_threshold_absolute_with_soft_floor_for_low_return_sectors():
    """Umbral de ROIC = WACC del sector + 5 pp; en sectores de retorno bajo, el ROC del sector (piso WACC + 2 pp)."""
    from dcf_models import classify_moat
    stable = [1_500, 1_520, 1_480, 1_500]
    # sector de retorno alto (ROC 29 %): manda el umbral absoluto, NO el ROC del sector (PEP / PM)
    hi = industrial(ind_roc=0.29, ind_margin=0.20, ebit_hist=stable, ebit_ttm=1_500.0)
    lab, why = classify_moat(hi, 0.07, 0.18, False, wacc_ref=0.07)
    assert "12.0%" in why[0] and why[0].endswith("sí.") and lab == "Estrecho", (lab, why)
    # sector de retorno bajo (utility): ROC 6 %, WACC sector 5,4 % → umbral 7,4 %
    lo = industrial(ind_roc=0.06, ind_margin=0.10, ebit_hist=stable, ebit_ttm=1_500.0)
    lab, why = classify_moat(lo, 0.06, 0.08, False, wacc_ref=0.054)
    assert "7.4%" in why[0] and why[0].endswith("sí."), why[0]
    lab, why = classify_moat(lo, 0.06, 0.06, False, wacc_ref=0.054)      # 6 % < 7,4 % (a más de 1 pp: sin zona gris)
    assert why[0].endswith("no.") and lab == "Ninguno"
    # WACC propio inflado por deuda cara no contamina el umbral cuando se pasa el del sector
    lab, why = classify_moat(lo, 0.159, 0.08, False, wacc_ref=0.054)
    assert "7.4%" in why[0] and lab != "Ninguno"
    # ROIC terminal: Amplio nunca por debajo de WACC + 3 pp ni de Estrecho
    from dcf_models import _terminal_roic
    ra, _ = _terminal_roic(lo, 0.05, 0.054, 0.12, 0.0, 0.40)
    re_, _ = _terminal_roic(lo, 0.02, 0.054, 0.12, 0.0, 0.40)
    assert abs(ra - 0.084) < 1e-9 and ra > re_ >= 0.074 - 1e-9


def test_negative_equity_floor_zero():
    co = industrial(debt=900_000.0, ebit_ttm=500.0)          # deuda enorme frente al valor operativo
    for scen in SCENARIOS.values():
        r = fcff_value(co, Params(), scen)
        assert r.per_share >= 0.0
    r = fcff_value(co, Params(), SCENARIOS["Base"])
    assert r.per_share == 0.0 and r.equity_value < 0
    assert any("no puede valer menos que cero" in w for w in r.warnings), r.warnings


def test_country_tax_and_terminal_default():
    from country_tax import marginal_tax_for
    from dcf_models import terminal_growth_default
    assert abs(marginal_tax_for("United States")[0] - 0.2563) < 1e-9
    assert marginal_tax_for("Argentina")[0] == 0.35 and marginal_tax_for("South Korea")[0] == 0.264
    assert marginal_tax_for("Hong Kong")[0] == 0.165
    t, note = marginal_tax_for("Narnia")
    assert t == 0.25 and "supuesto" in note and marginal_tax_for("")[0] == 0.25
    assert terminal_growth_default(0.0524) == 0.035 and abs(terminal_growth_default(0.044) - 0.034) < 1e-12
    assert terminal_growth_default(0.035) == 0.03 and abs(terminal_growth_default(0.0425) - 0.0325) < 1e-12


def test_field_checks():
    from dcf_models import field_checks
    co = industrial(da_ttm=0.0, capex_ttm=0.0, nwc_inv_ttm=0.0, ebit_ttm=9_000.0, beta=-0.2, asof="2020-01-01")
    fc = {c["Campo"]: c for c in field_checks(co, "FCFF", Params())}
    assert fc["D&A (amortización)"]["Estado"] == "info" and fc["CapEx"]["Estado"] == "info"
    assert fc["EBIT (resultado operativo)"]["Estado"] == "aviso"          # margen 90 %
    assert fc["Beta de la acción"]["Estado"] == "aviso" and fc["Antigüedad de los datos contables"]["Estado"] == "aviso"
    good = {c["Campo"]: c["Estado"] for c in field_checks(industrial(), "FCFF", Params())}
    assert good["EBIT (resultado operativo)"] == "ok" and good["Precio y moneda"] == "ok"
    assert all(c["Estado"] in ("ok", "aviso", "info") for c in field_checks(industrial(equity=5_000.0, ni_ttm=800.0), "ER", Params()))
    assert any(c["Campo"] == "AFFO" for c in field_checks(industrial(), "REIT", Params()))


def test_relative_margin_spread_and_ttm_distortion():
    from dcf_models import margin_target, ttm_distorted, MARGIN_SPREAD, Scen
    co = industrial(revenue_hist=[900.0, 950.0, 980.0, 1000.0], ebit_hist=[270.0, 285.0, 294.0, 300.0],
                    revenue_ttm=1000.0, ebit_ttm=290.0)
    p = Params()
    m0, mb, _ = margin_target(co, p, SCENARIOS["Base"])
    _, mp, _ = margin_target(co, p, SCENARIOS["Pesimista"])
    _, mo, _ = margin_target(co, p, SCENARIOS["Optimista"])
    assert abs(mp - min(mb * (1 - MARGIN_SPREAD), m0)) < 1e-12 and abs(mo - max(mb * (1 + MARGIN_SPREAD), m0)) < 1e-12
    # margen bajo: el spread relativo no se come la mitad del margen (antes -2 pp sobre 4 % = -50 %)
    low = industrial(revenue_hist=[900.0, 950.0, 980.0, 1000.0], ebit_hist=[36.0, 38.0, 39.0, 40.0], revenue_ttm=1000.0, ebit_ttm=40.0)
    _, mpl, _ = margin_target(low, p, SCENARIOS["Pesimista"])
    assert mpl > 0.8 * 0.04, mpl
    # TTM distorsionado: 10 % de margen contra 30 % histórico, ingresos estables -> el pesimista no se ancla al TTM
    dis = industrial(revenue_hist=[900.0, 950.0, 980.0, 1000.0], ebit_hist=[270.0, 285.0, 294.0, 300.0],
                     revenue_ttm=1010.0, ebit_ttm=101.0)
    m0d, mbd, _ = margin_target(dis, p, SCENARIOS["Base"])
    _, mpd, d = margin_target(dis, p, SCENARIOS["Pesimista"])
    assert ttm_distorted(dis, m0d, mbd) and mpd > m0d + 0.05 and "distorsionado" in d, (m0d, mbd, mpd)
    fall = replace(dis, revenue_ttm=700.0)       # ingresos caen: es deterioro real, se mantiene el ancla al TTM
    m0f, mbf, _ = margin_target(fall, p, SCENARIOS["Base"])
    assert not ttm_distorted(fall, m0f, mbf)
    r = fcff_value(dis, replace(p, g_terminal=0.035), SCENARIOS["Base"])
    assert any("cargo extraordinario" in w for w in r.warnings)
    # v2.25: con TTM distorsionado la proyección ARRANCA del margen normal (no tarda 5 años en recuperarlo)
    assert r.extras["ttm_normalized"] and abs(r.extras["margin_start"] - mbd) < 1e-12, r.extras["margin_start"]
    assert abs(r.table[0]["Margen"] - mbd) < 1e-9 or r.table[0]["Margen"] > 0.25, r.table[0]
    # y vale más que arrancar del TTM deprimido (mismo caso, sin distorsión detectada: ingresos que caen)
    fall2 = replace(dis, revenue_ttm=700.0, ebit_ttm=70.0)
    r_fall = fcff_value(fall2, replace(p, g_terminal=0.035), SCENARIOS["Base"])
    assert not r_fall.extras["ttm_normalized"] and r_fall.extras["margin_start"] == r_fall.extras["margin0"]
    # pesimista y optimista parten del mismo margen normal que el base
    rp = fcff_value(dis, replace(p, g_terminal=0.035), SCENARIOS["Pesimista"])
    ro = fcff_value(dis, replace(p, g_terminal=0.035), SCENARIOS["Optimista"])
    assert abs(rp.extras["margin_start"] - mbd) < 1e-12 and abs(ro.extras["margin_start"] - mbd) < 1e-12
    assert rp.per_share < r.per_share < ro.per_share
    # sin distorsión nada cambia
    ok = industrial()
    assert not fcff_value(ok, p, SCENARIOS["Base"]).extras["ttm_normalized"]


def test_moat_gray_zone():
    from dcf_models import classify_moat
    stable = [1_500, 1_520, 1_480, 1_500]
    co = industrial(ind_roc=0.06, ind_margin=0.10, ebit_hist=stable, ebit_ttm=1_500.0)       # umbral 7,4 % (sector de retorno bajo)
    assert classify_moat(co, 0.06, 0.0745, False, wacc_ref=0.054)[0] == "Amplio"
    lab, why = classify_moat(co, 0.06, 0.0735, False, wacc_ref=0.054)                          # 0,05 pp abajo: zona gris
    assert lab == "Estrecho" and any("Zona gris" in w for w in why), (lab, why)
    assert classify_moat(co, 0.06, 0.0630, False, wacc_ref=0.054)[0] == "Ninguno"              # más de 1 pp abajo: Ninguno
    weak_peers = replace(co, ind_roc=0.60, ind_margin=0.40)                                    # zona gris pero no mejor que los pares
    assert classify_moat(weak_peers, 0.06, 0.1195, False, wacc_ref=0.07)[0] == "Ninguno"


def test_moat_price_takers_capped_at_narrow():
    from dcf_models import classify_moat
    co = industrial(ind_roc=0.20, ind_margin=0.10, ebit_hist=[1_500, 1_520, 1_480, 1_500], ebit_ttm=1_500.0)
    assert classify_moat(co, 0.08, 0.30, False)[0] == "Amplio"
    oil = replace(co, ind_name="Oil/Gas (Integrated)")
    lab, why = classify_moat(oil, 0.08, 0.30, False)
    assert lab == "Estrecho" and any("precio-aceptante" in w for w in why), (lab, why)
    assert classify_moat(oil, 0.08, 0.05, False)[0] == "Ninguno"


def test_moat_persistence_and_ttm_distortion():
    from dcf_models import classify_moat
    base = dict(ind_roc=0.12, ind_margin=0.10, revenue_hist=[1000.0] * 4, revenue_ttm=1000.0)
    ok = industrial(**base, ebit_hist=[130.0, 120.0, 140.0, 125.0], ebit_ttm=130.0)
    _, why = classify_moat(ok, 0.08, 0.20, False, wacc_ref=0.08)
    assert any(x.startswith("2) Persistencia") and x.endswith("sí.") for x in why), why
    # un año malo viejo no cuenta (solo los últimos tres márgenes), uno reciente sí
    old_dip = industrial(**base, ebit_hist=[60.0, 130.0, 140.0, 125.0], ebit_ttm=130.0)
    assert classify_moat(old_dip, 0.08, 0.20, False, wacc_ref=0.08)[0] == "Amplio"
    recent_dip = industrial(**base, ebit_hist=[130.0, 140.0, 60.0, 125.0], ebit_ttm=130.0)
    assert classify_moat(recent_dip, 0.08, 0.20, False, wacc_ref=0.08)[0] == "Estrecho"
    # TTM distorsionado (margen 10 % vs 13 %+, ingresos estables): no se usa
    dist = industrial(**base, ebit_hist=[300.0, 310.0, 305.0, 300.0], ebit_ttm=100.0)
    _, why = classify_moat(dist, 0.08, 0.20, False, wacc_ref=0.08)
    assert any("extraordinario" in x for x in why), why


def test_survival_adjustment_and_lifecycle():
    from dcf_models import default_risk, lifecycle_info
    healthy = industrial()
    r = fcff_value(healthy, Params(), SCENARIOS["Base"])
    assert r.extras["p_default"] == 0.0 and not any("quiebra" in w for w in r.warnings)       # cobertura 15x: AAA, sin ajuste
    weak = industrial(interest_expense_ttm=700.0)                                              # cobertura ~2,1x: BB
    rw = fcff_value(weak, Params(), SCENARIOS["Base"])
    assert 0.1 < rw.extras["p_default"] < 0.3 and rw.extras["rating"] == "BB", rw.extras["rating"]
    assert abs(rw.per_share - rw.extras["per_share_going"] * (1 - rw.extras["p_default"])) < 1e-9
    assert any("riesgo de quiebra" in w for w in rw.warnings)
    off = fcff_value(weak, Params(survival_adj=False), SCENARIOS["Base"])
    assert off.extras["p_default"] == 0.0 and abs(off.per_share - rw.extras["per_share_going"]) < 1e-9
    # misma probabilidad en los tres escenarios
    ps = {n: fcff_value(weak, Params(), SCENARIOS[n]).extras["p_default"] for n in SCENARIOS}
    assert len(set(ps.values())) == 1, ps
    assert default_risk(industrial(interest_expense_ttm=None), 0.1) is None
    # etapas
    lab = lambda co, model="FCFF", g1=0.05: lifecycle_info(co, model, g1)[0]
    assert lab(industrial()) == "Madura"
    assert lab(industrial(), g1=0.20) == "En crecimiento"
    assert lab(industrial(ebit_ttm=-5.0), g1=0.30) == "Con pérdidas y creciendo"
    assert lab(industrial(ebit_ttm=-5.0), g1=0.02) == "En declive o dificultades"
    assert lab(industrial(revenue_ttm=8_000.0)) == "En declive o dificultades"                 # ingresos -18 % anual
    assert lab(industrial(ind_name="Steel")) == "Cíclica o de materias primas"
    assert lab(industrial(), model="ER") == "Servicios financieros"
    assert value_company(industrial(), Params(), "FCFF", "Base").extras["lifecycle"] == "Madura"


def test_rd_capitalization():
    from dcf_models import apply_rd, RD_LIFE
    base = industrial(rd_ttm=400.0, rd_hist=[200.0, 250.0, 300.0, 350.0], equity=4000.0)        # I+D creciente: el ajuste sube el EBIT
    co2, info = apply_rd(base, Params())
    amort = (350 + 300 + 250 + 200) / RD_LIFE
    assert abs(info["amort"] - amort) < 1e-9 and abs(info["net"] - (400 - amort)) < 1e-9
    assert abs(info["asset"] - (400 + 350 * 0.75 + 300 * 0.5 + 250 * 0.25)) < 1e-9
    assert co2.ebit_ttm == base.ebit_ttm + info["net"] and co2.equity == base.equity + info["asset"]
    assert apply_rd(industrial(), Params())[1] is None                                       # sin dato de I+D: no hace nada
    assert apply_rd(base, Params(capitalize_rd=False))[1] is None
    assert apply_rd(industrial(rd_ttm=400.0, rd_hist=[300.0]), Params())[1] is None          # poca historia: no se capitaliza
    r_on = fcff_value(base, Params(), SCENARIOS["Base"])
    r_off = fcff_value(base, Params(capitalize_rd=False), SCENARIOS["Base"])
    assert r_on.extras["rd_asset"] and r_off.extras["rd_asset"] is None
    assert any("I+D capitalizado" in w for w in r_on.warnings)
    assert r_on.extras["margin0"] > r_off.extras["margin0"]


def test_erp_damodaran_constante_y_aviso_de_antiguedad():
    from datetime import date
    import industry_data as idt
    assert abs(idt.ERP_DAMODARAN - 0.0370) < 1e-12 and idt.ERP_DATE_ISO == "2026-10-01"
    assert not idt.erp_is_stale(date(2026, 10, 17))          # recién cargada
    assert not idt.erp_is_stale(date(2027, 3, 30))           # menos de 6 meses
    assert idt.erp_is_stale(date(2027, 4, 15))               # más de 6 meses
    assert idt.erp_age_days(date(2026, 10, 1)) == 0


def test_zonas_de_valuacion():
    from dcf_models import price_zones
    # escenarios 70 / 100 / 140 -> cortes 70, 85, 120, 140
    z = price_zones(70, 100, 140, 60);   assert z["zone"] == 0 and z["name"] == "Muy infravalorada"
    assert price_zones(70, 100, 140, 80)["zone"] == 1
    assert price_zones(70, 100, 140, 100)["zone"] == 2
    assert price_zones(70, 100, 140, 130)["zone"] == 3
    assert price_zones(70, 100, 140, 140)["zone"] == 3                         # justo en el optimista
    assert price_zones(70, 100, 140, 141)["zone"] == 4
    assert price_zones(70, 100, 140, 100)["cuts"] == [70.0, 85.0, 120.0, 140.0]
    assert price_zones(None, 100, 140, 100) is None and price_zones(70, 100, 140, float("nan")) is None
    assert price_zones(0, 0, 0, 10)["zone"] == 4                                # valor 0 (patrimonio negativo): muy sobrevalorada
    assert price_zones(140, 100, 70, 80)["zone"] == 1                           # ordena si vienen desordenados


def test_dcf_inverso_y_pensiones_informativas():
    from dcf_models import implied_wacc
    co = industrial(price=80.0)
    p = Params()
    imp = implied_wacc(co, p, "FCFF")
    assert imp is not None
    # con ese desplazamiento el valor Base iguala el precio
    r = value_company(co, replace(p, wacc_shift=imp["shift"]), "FCFF", "Base")
    assert abs(r.per_share - 80.0) < 0.05
    # precio más alto -> el mercado descuenta menos -> WACC implícito menor
    imp2 = implied_wacc(industrial(price=160.0), p, "FCFF")
    assert imp2 is not None and imp2["wacc"] < imp["wacc"]
    # otro modelo o precio imposible -> None
    assert implied_wacc(co, p, "ER") is None
    assert implied_wacc(industrial(price=1e9), p, "FCFF") is None
    # las pensiones son informativas: no cambian el valor
    v0 = value_company(industrial(), p, "FCFF", "Base").per_share
    v1 = value_company(industrial(pension_liab=5_000.0), p, "FCFF", "Base").per_share
    assert abs(v0 - v1) < 1e-12


def test_regla_beta_global_con_muestra_chica():
    import industry_data as idt
    # petróleo integrado: 4 empresas en EE.UU. -> usa la global (34); la regla no aplica a empresas de otros países
    r, reg = idt.get_ref("Oil/Gas (Integrated)", "United States")
    assert reg.startswith("Global") and r["n"] > 20
    r2, reg2 = idt.get_ref("Oil/Gas (Integrated)", "Brazil")
    assert reg2 == "Global" and r2["n"] == r["n"]
    # industria con muestra grande en EE.UU.: se conserva
    big = next(n for n, v in idt.IND.items() if (v.get("us") or {}).get("n", 0) >= idt.MIN_MUESTRA_US and v.get("gl"))
    r3, reg3 = idt.get_ref(big, "United States")
    assert reg3 == "EE.UU." and r3["n"] >= idt.MIN_MUESTRA_US
    # sin país conocido se trata como EE.UU.
    assert idt.get_ref("Oil/Gas (Integrated)", "")[1].startswith("Global")


def test_beta_terminal_mercado_y_deuda_industria():
    """v2.35: beta terminal = (beta de los primeros años, desapalancada con la deuda de la empresa y re-apalancada con la de la
    industria + 1) / 2. Ejemplo del usuario: industria 0,8, empresa 0,3 → 0,55 → 0,775."""
    from dataclasses import replace
    from dcf_models import terminal_beta, sector_wacc
    p = Params(rf=0.04, erp=0.037, marginal_tax=0.25)
    # sin deuda en la empresa ni en la industria: el ejemplo directo
    c = industrial(beta=0.3, debt=0.0, lease_debt=0.0, ind_ubeta=0.8, ind_de=0.0, ind_name="X")
    assert abs(terminal_beta(c, p) - 0.775) < 1e-12
    r = fcff_value(c, p, SCENARIOS["Base"])
    assert abs(r.extras["beta"] - 0.55) < 1e-12 and abs(r.extras["beta_T"] - 0.775) < 1e-12
    # deuda de la empresa igual a la de la industria: no hay efecto de reapalancar
    c2 = industrial(beta=0.3, debt=2_000.0, lease_debt=0.0, ind_ubeta=0.8 / (1 + 0.75 * 0.2), ind_de=0.2, ind_name="X")
    assert abs(terminal_beta(c2, p) - 0.775) < 1e-9
    # empresa sin deuda y sector muy endeudado: la beta del negocio se re-apalanca con la deuda del sector (y se acota en 2,0)
    c3 = industrial(beta=2.0, debt=0.0, lease_debt=0.0, ind_ubeta=1.5, ind_de=2.7, ind_name="X")
    assert terminal_beta(c3, p) == 2.0
    # piso: beta propia 0,1 e industria 0,6 → 0,35 → piso 0,5 → (0,5 + 1) / 2 = 0,75
    c4 = industrial(beta=0.1, debt=0.0, lease_debt=0.0, ind_ubeta=0.6, ind_de=0.0, ind_name="X")
    assert abs(terminal_beta(c4, p) - 0.75) < 1e-12
    # beta propia no confiable (≤ 0) o ausente: solo industria → (0,8 + 1) / 2 = 0,9
    for b in (None, 0.0, -0.3):
        c5 = industrial(beta=b, debt=0.0, lease_debt=0.0, ind_ubeta=0.8, ind_de=0.0, ind_name="X")
        assert abs(terminal_beta(c5, p) - 0.9) < 1e-12
    # beta manual u opción de industria apagada: se conserva la beta de la industria sola (comportamiento anterior)
    assert abs(terminal_beta(c, replace(p, beta=1.3)) - 0.8) < 1e-12
    assert abs(terminal_beta(c, replace(p, use_industry_beta=False)) - 0.8) < 1e-12
    # el WACC terminal usa esa beta, los pesos de la industria y el desplazamiento
    de = 0.2
    exp = (1 / (1 + de)) * (0.04 + terminal_beta(c2, p) * 0.037) + (1 - 1 / (1 + de)) * (0.04 + 0.0111) * 0.75
    assert abs(sector_wacc(c2, p) - exp) < 1e-12
    assert abs(sector_wacc(c2, replace(p, wacc_shift=0.01)) - exp - 0.01) < 1e-12
    # sin datos de industria: no hay beta terminal
    assert terminal_beta(industrial(), p) is None


def test_premio_parcial_de_foso_y_capital_con_no_operativos():
    """v2.36: (1) el premio parcial es 0 fuera del tramo entre WACC y umbral y proporcional dentro; (2) el ROIC terminal es continuo al cruzar el
    umbral (sin escalón); (3) si las inversiones no operativas superan al capital invertido, el ROIC se calcula sin restarlas."""
    from dcf_models import moat_partial_premium, MOAT_SPREADS
    co = industrial(ind_roc=0.20, ind_margin=0.10)
    # umbral = WACC sector + 5 pp = 13 %; con ROIC 10,5 % y WACC 8 %: mitad del camino
    f, why = moat_partial_premium(co, 0.08, 0.105)
    assert abs(f - 0.5) < 1e-9 and "Premio parcial" in why and "Ninguno" in why
    assert moat_partial_premium(co, 0.08, 0.08)[0] == 0 and moat_partial_premium(co, 0.08, 0.05)[0] == 0
    assert moat_partial_premium(co, 0.08, 0.13)[0] == 0 and moat_partial_premium(co, 0.08, 0.30)[0] == 0
    assert moat_partial_premium(co, 0.08, None)[0] == 0
    # continuidad: se barre el capital invertido (ROIC inicial de ~16 % a ~7 %) y el ROIC terminal no da saltos
    from industry_data import attach
    base, _, _ = attach(industrial(industry="Beverages - Non-Alcoholic"), "FCFF")
    prev = None
    steps = []
    for ic in range(7_000, 22_000, 250):
        c = replace(base, invested_capital=float(ic), equity=None)
        r = fcff_value(c, Params(rf=0.04, erp=0.037), SCENARIOS["Base"])
        steps.append((r.extras["roic0"], r.extras["roicT"], r.extras["moat_label"], r.extras["moat_partial"], r.per_share))
    steps.sort()
    jumps = [abs(b[1] - a[1]) for a, b in zip(steps, steps[1:])]
    assert max(jumps) < 0.012, (max(jumps), steps)                      # antes del cambio había un escalón de 2 pp o más al cruzar el umbral
    assert any(s[3] > 0 for s in steps) and all(s[2] in ("Amplio", "Estrecho", "Ninguno") for s in steps)
    # v2.37: con premio parcial >= 50 % la etiqueta muestra Estrecho; el valor es el mismo que con la etiqueta vieja
    lab = [(s[3], s[2]) for s in steps if s[3] > 0]
    assert all((lab_ == "Estrecho") == (f >= 0.5) for f, lab_ in lab if lab_ != "Amplio"), lab
    assert any(f >= 0.5 and lab_ == "Estrecho" for f, lab_ in lab) and any(f < 0.5 and lab_ == "Ninguno" for f, lab_ in lab), lab
    # el premio parcial solo corre con clasificación automática: con foso elegido no hay premio
    c = replace(base, invested_capital=15_000.0, equity=None)
    r_man = fcff_value(c, Params(rf=0.04, erp=0.037, moat="Ninguno"), SCENARIOS["Base"])
    assert r_man.extras["moat_partial"] == 0 and abs(r_man.extras["roicT"] - r_man.extras["wacc_T"]) < 1e-12
    # capital operativo ≤ 0 por inversiones no operativas: ROIC con el capital sin restarlas, y se avisa
    ge = industrial(equity=5_000.0, debt=2_000.0, cash=500.0, non_op_assets=9_000.0, invested_capital=None)
    r = fcff_value(ge, Params(), SCENARIOS["Base"])
    assert any("inversiones no operativas" in w for w in r.warnings)
    assert 0.03 < r.extras["roic0"] < 0.40 and r.extras["ic_op"] > 0, r.extras["roic0"]
    # si aun así el capital sigue siendo ≤ 0: tope, como antes
    ge2 = industrial(equity=100.0, debt=0.0, cash=500.0, non_op_assets=0.0)
    r2 = fcff_value(ge2, Params(), SCENARIOS["Base"])
    assert r2.extras["roic0"] == Params().roic_cap


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("OK", name)
    print(f"{n} pruebas OK")

