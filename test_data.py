"""Pruebas de la capa de datos con DataFrames sintéticos con la forma de yahooquery."""
import pandas as pd, numpy as np
from data_yahoo import build_company, DataError
from dcf_models import Params, value_company, route_model

MONEY = ["TotalRevenue","OperatingIncome","NetIncome","NetIncomeCommonStockholders","TaxProvision","PretaxIncome",
         "DepreciationAndAmortization","CapitalExpenditure","ChangeInWorkingCapital","InterestExpense","TotalDebt",
         "CashCashEquivalentsAndShortTermInvestments","MinorityInterest","CommonStockEquity","InvestedCapital","CapitalLeaseObligations"]

def mk(sym, rows):
    df = pd.DataFrame(rows)
    for c in MONEY:
        if c in df.columns:
            df[c] = df[c] * 1e6          # yahooquery entrega unidades, no millones
    df["asOfDate"] = pd.to_datetime(df["asOfDate"])
    return df.set_index("symbol") if "symbol" in df.columns else df

def frames(sym="ABC", cur="EUR", ttm=True, quarters=True, annual=True):
    A = []
    for y, rev, ebit in [(2021, 800, 100), (2022, 900, 115), (2023, 950, 125), (2024, 1000, 135)]:
        A.append(dict(symbol=sym, asOfDate=f"{y}-12-31", periodType="12M", currencyCode=cur, TotalRevenue=rev,
                      OperatingIncome=ebit, NetIncome=ebit*0.7, TaxRateForCalcs=0.22, CommonStockEquity=500+(y-2021)*30))
    if ttm:
        A.append(dict(symbol=sym, asOfDate="2025-06-30", periodType="TTM", currencyCode=cur, TotalRevenue=1040,
                      OperatingIncome=140, NetIncome=100, NetIncomeCommonStockholders=100, TaxProvision=30, PretaxIncome=130,
                      DepreciationAndAmortization=40, CapitalExpenditure=-55, ChangeInWorkingCapital=-5,
                      InterestExpense=8))
    Q = []
    if quarters:
        for d, r in [("2024-09-30", 255), ("2024-12-31", 262), ("2025-03-31", 258), ("2025-06-30", 265)]:
            Q.append(dict(symbol=sym, asOfDate=d, periodType="3M", currencyCode=cur, TotalRevenue=r, OperatingIncome=r*0.135,
                          TotalDebt=300, CashCashEquivalentsAndShortTermInvestments=120, MinorityInterest=5,
                          CommonStockEquity=620, InvestedCapital=800, CapitalLeaseObligations=40, OrdinarySharesNumber=200e6))
    return mk(sym, A), mk(sym, Q) if Q else mk(sym, [dict(symbol=sym, asOfDate="2000-01-01", periodType="3M")])

price = {"regularMarketPrice": 40.0, "currency": "USD", "marketCap": 8_000e6, "quoteType": "EQUITY", "longName": "ABC ADR"}
prof = {"sector": "Industrials", "industry": "Specialty Industrial Machinery", "country": "Netherlands"}
trend = {"trend": [{"period": "0y", "revenueEstimate": {"growth": 0.04}}, {"period": "+1y", "revenueEstimate": {"growth": 0.06}}]}
fx = lambda a, b: 1.10 if (a, b) == ("EUR", "USD") else None

def test_adr_currency_and_ttm():
    dfa, dfq = frames()
    co, w = build_company("ABC", price, {"beta": 1.1}, {"sharesOutstanding": 200e6}, prof,
                          {"financialCurrency": "EUR", "targetMeanPrice": 45}, trend, dfa, dfq, fx)
    # TTM Yahoo -> convertido a USD (x1.10), en millones
    assert abs(co.revenue_ttm - 1040*1.10) < 1e-9, co.revenue_ttm
    assert co.fin_currency == "EUR" and co.currency == "USD" and abs(co.fx-1.1) < 1e-12
    assert abs(co.shares_m - 200.0) < 1e-9          # 8000e6 / 40
    assert abs(co.capex_ttm - 55*1.1) < 1e-9 and abs(co.nwc_inv_ttm - 5*1.1) < 1e-9
    assert abs(co.tax_rate_eff - 30/130) < 1e-9
    assert abs(co.cash - 120*1.1) < 1e-9 and abs(co.debt - 300*1.1) < 1e-9
    assert co.rev_g_y0 == 0.04 and co.rev_g_y1 == 0.06
    assert len(co.revenue_hist) == 4 and len(co.ebit_hist) == 4 and co.ebit_hist[-1] is not None
    r = value_company(co, Params(), "FCFF", "Base")
    assert r.ok, r.error
    print("  ADR EUR->USD: valor base", round(r.per_share,2), "| precio", co.price)

def test_quarter_sum_when_no_ttm():
    dfa, dfq = frames(ttm=False)
    co, w = build_company("ABC", {**price}, {}, {}, prof, {"financialCurrency": "EUR"}, {}, dfa, dfq, fx)
    assert abs(co.revenue_ttm - (255+262+258+265)*1.1) < 1e-9
    assert co.ttm_source == "suma 4 trimestres"

def test_no_annual_fallback_by_default():
    dfa, dfq = frames(ttm=False, quarters=False)
    co, w = build_company("ABC", price, {}, {"sharesOutstanding": 200e6}, prof, {"financialCurrency": "EUR"}, {}, dfa, dfq, fx)
    assert co.revenue_ttm == 0.0                     # no cae a anual
    r = value_company(co, Params(), "FCFF", "Base")
    assert not r.ok
    co2, w2 = build_company("ABC", price, {}, {"sharesOutstanding": 200e6}, prof, {"financialCurrency": "EUR"}, {}, dfa, dfq, fx, allow_annual=True)
    assert co2.revenue_ttm > 0 and any("AÑO FISCAL" in x for x in w2)

def test_quarter_gap_rejected():
    dfa, dfq = frames(ttm=False)
    dfq = dfq.reset_index(); dfq.loc[1, "asOfDate"] = pd.Timestamp("2024-10-30")   # hueco raro
    dfq = dfq.set_index("symbol")
    co, _ = build_company("ABC", price, {}, {}, prof, {"financialCurrency": "EUR"}, {}, dfa, dfq, fx)
    assert co.revenue_ttm == 0.0

def test_pence():
    dfa, dfq = frames(cur="GBP")
    p = {"regularMarketPrice": 4000.0, "currency": "GBp", "marketCap": 8_000e6, "quoteType": "EQUITY"}
    co, w = build_company("ABC", p, {}, {"sharesOutstanding": 200e6}, prof, {"financialCurrency": "GBP"}, {}, dfa, dfq, lambda a,b: 1.0)
    assert co.currency == "GBP" and abs(co.price - 40.0) < 1e-9 and abs(co.shares_m - 200.0) < 1e-9

def test_missing_price():
    dfa, dfq = frames()
    try:
        build_company("ABC", {}, {}, {}, prof, {}, {}, dfa, dfq, fx)
        assert False
    except DataError:
        pass

def test_etf_warns():
    dfa, dfq = frames()
    co, w = build_company("ABC", {**price, "quoteType": "ETF"}, {}, {"sharesOutstanding": 200e6}, prof, {"financialCurrency": "EUR"}, {}, dfa, dfq, fx)
    assert any("ETF" in x for x in w)

def test_bank_path():
    dfa, dfq = frames(sym="BNK")
    co, w = build_company("BNK", price, {"beta": 1.0}, {"sharesOutstanding": 200e6},
                          {"sector": "Financial Services", "industry": "Banks - Regional", "country": "United States"},
                          {"financialCurrency": "EUR"}, trend, dfa, dfq, fx)
    m, _ = route_model(co)
    assert m == "ER"
    r = value_company(co, Params(), "ER", "Base")
    assert r.ok, r.error
    print("  Banco sintético ER:", round(r.per_share, 2), "P/B", round(r.extras["pb_implied"], 2))

def test_is_degraded_and_search_parse():
    import data_yahoo as dy
    from dcf_models import CompanyData
    full = CompanyData(ticker="MRK", name="Merck & Co., Inc.", sector="Healthcare", industry="Drug Manufacturers - General",
                       country="United States", quote_type="EQUITY")
    assert not dy.is_degraded(full)
    assert dy.is_degraded(CompanyData(ticker="MRK", name="MRK", quote_type="EQUITY"))                       # sin perfil ni nombre
    assert dy.is_degraded(CompanyData(ticker="MRK", name="Merck", industry="Drug Manufacturers - General", quote_type="EQUITY"))  # sin país
    assert not dy.is_degraded(CompanyData(ticker="SPY", name="SPY", quote_type="ETF"))                      # no aplica a ETF
    assert dy.missing_fields(CompanyData(ticker="MRK", name="Merck & Co., Inc.", sector="Healthcare",
                                         industry="Drug Manufacturers - General", quote_type="EQUITY")) == ["país"]
    assert dy.missing_fields(full) == []


def test_load_company_retry_and_degraded():
    """El perfil que falla en la primera consulta se recupera con el reintento; si nunca llega, la carga queda marcada."""
    import sys, types
    import data_yahoo as dy
    dfa, dfq = frames(cur="USD")
    fin_ok = {"financialCurrency": "USD"}
    def make_ticker(profile_works_on):
        calls = {"n": 0}
        class FakeTicker:
            def __init__(self, sym, timeout=20):
                calls["n"] += 1
                self.n, self.sym = calls["n"], sym.upper()
            price = property(lambda s: {s.sym: {**price, "currency": "USD"}})
            summary_detail = property(lambda s: {s.sym: {"beta": 1.1}})
            key_stats = property(lambda s: {s.sym: {"sharesOutstanding": 200e6}})
            financial_data = property(lambda s: {s.sym: fin_ok})
            earnings_trend = property(lambda s: {s.sym: trend})
            asset_profile = property(lambda s: {s.sym: prof if s.n >= profile_works_on else "Quote not found"})
            def get_financial_data(self, fields, frequency="a", trailing=True):
                return dfa if frequency == "a" else dfq
        return FakeTicker, calls
    saved = {k: getattr(dy, k) for k in ("get_risk_free", "yf_fallback", "search_profile", "estimate_beta", "RETRY_WAITS")}
    try:
        dy.get_risk_free = lambda: (0.04, True)
        dy.yf_fallback = lambda sym: {}
        dy.search_profile = lambda sym: {}
        dy.estimate_beta = lambda sym: 1.0
        dy.RETRY_WAITS = (0.0, 0.0)
        for works_on, expect_degraded in ((2, False), (99, True)):
            T, calls = make_ticker(works_on)
            sys.modules["yahooquery"] = types.SimpleNamespace(Ticker=T)
            co, w = dy.load_company("ABC")
            assert dy.is_degraded(co) == expect_degraded, (works_on, co.industry, co.country)
            assert any("Carga incompleta" in x for x in w) == expect_degraded, w
            assert calls["n"] == (2 if works_on == 2 else 3), calls          # 1 inicial + reintentos
            if expect_degraded:
                assert any("perfil (sector/industria/país)" in x for x in w), w
    finally:
        for k, v in saved.items():
            setattr(dy, k, v)
        sys.modules.pop("yahooquery", None)


def test_dash_normalization_in_industry():
    from industry_data import map_industry
    assert map_industry("Utilities—Regulated Electric") == map_industry("Utilities - Regulated Electric") is not None
    assert map_industry("Drug Manufacturers—General") == "Drugs (Pharmaceutical)"
    assert map_industry("Insurance – Life") == map_industry("Insurance - Life")


def test_yahoo_quote_blocked_fallbacks():
    """Caso real visto en Streamlit Cloud: sin cotización, sin beta, sin sector."""
    dfa, dfq = frames(sym="TSM", cur="TWD")
    co, w = build_company("TSM", {}, {}, {}, {}, {}, {}, dfa, dfq, lambda a, b: 0.031,
                          fallback_price=180.0, fallback_currency="USD", adr_ratio=5.0, fallback_beta=1.2)
    assert abs(co.price - 180.0) < 1e-9 and co.currency == "USD" and co.fin_currency == "TWD"  # sin financialCurrency usa la moneda de la tabla
    assert abs(co.shares_m - 200.0 / 5) < 1e-9 or abs(co.shares_m - 40.0) < 1e-9, co.shares_m
    assert co.beta == 1.2
    assert any("sector" in x.lower() for x in w) and any("historial" in x for x in w)

def test_adr_warning_without_ratio():
    dfa, dfq = frames(sym="TSM", cur="TWD")
    co, w = build_company("TSM", {}, {}, {}, {}, {"financialCurrency": "TWD"}, {}, dfa, dfq, lambda a, b: 0.031,
                          fallback_price=180.0, fallback_currency="USD")
    assert any("ADR" in x for x in w)
    assert abs(co.revenue_ttm - 1040 * 0.031) < 1e-9   # TWD convertido a USD

def test_fred_parse():
    from data_yahoo import parse_fred_csv
    txt = "DATE,DGS10\n2026-10-08,4.05\n2026-10-09,.\n2026-10-12,4.12\n"
    assert parse_fred_csv(txt) == 4.12
    assert parse_fred_csv("DATE,DGS10\n") is None

def test_adr_ratio_ignored_when_same_currency():
    dfa, dfq = frames(sym="JPM", cur="USD")
    co, w = build_company("JPM", {}, {}, {}, {}, {"financialCurrency": "USD"}, {}, dfa, dfq, lambda a, b: 1.0,
                          fallback_price=300.0, fallback_currency="USD", adr_ratio=5.0)
    assert abs(co.shares_m - 200.0) < 1e-9, co.shares_m      # NO dividido por 5
    assert any("IGNORADO" in x for x in w)

def test_analyst_ranges_parse():
    from data_yahoo import analyst_ranges
    trend = {"trend": [
        {"period": "0y", "revenueEstimate": {"yearAgoRevenue": 100.0, "low": 105.0, "high": 112.0, "growth": 0.08},
         "earningsEstimate": {"growth": 0.10}},
        {"period": "+1y", "revenueEstimate": {"yearAgoRevenue": 108.0, "low": 110.0, "high": 125.0, "growth": 0.09},
         "earningsEstimate": {"growth": 0.12}},
        {"period": "+5y", "revenueEstimate": {}}]}
    r = analyst_ranges(trend)
    assert abs(r["gl_y0"] - 0.05) < 1e-9 and abs(r["gh_y1"] - (125 / 108 - 1)) < 1e-9
    assert r["eg_y0"] == 0.10 and r["eg_y1"] == 0.12
    assert analyst_ranges({}) == {}


def test_creditos_a_cobrar_informativos():
    """v2.38: las cuentas por cobrar (corrientes y de largo plazo) se leen aparte; si faltan, todo sigue igual."""
    from data_yahoo import _merge_extra, build_company
    dfa, dfq = frames()
    xq = pd.DataFrame([dict(symbol="ABC", asOfDate="2025-06-30", periodType="3M", AccountsReceivable=60e9, NonCurrentAccountsReceivable=61e9)])
    xq["asOfDate"] = pd.to_datetime(xq["asOfDate"])
    dq2 = _merge_extra(dfq, xq.set_index("symbol"), "ABC")
    co, _ = build_company("ABC", price, {}, {}, prof, {"financialCurrency": "EUR"}, trend, dfa, dq2, fx)
    assert abs(co.receivables - 60e3 * 1.10) < 1e-6 and abs(co.receivables_nc - 61e3 * 1.10) < 1e-6, (co.receivables, co.receivables_nc)
    co0, _ = build_company("ABC", price, {}, {}, prof, {"financialCurrency": "EUR"}, trend, dfa, dfq, fx)
    assert co0.receivables is None and co0.receivables_nc is None
    assert _merge_extra(dfq, "error de yahoo", "ABC") is dfq                 # fallo de Yahoo: no rompe nada


def test_industria_desde_la_planilla_de_damodaran():
    """v2.43: la industria sale de la planilla de Damodaran (por ticker, sufijo o nombre); si no figura, de la regla de Yahoo."""
    import damodaran_map as dm
    import industry_data as idt
    from dcf_models import CompanyData
    assert dm.size() > 48000
    g = lambda *a: (dm.lookup(*a) or (None, ""))[0]
    assert g("AAPL", "Apple Inc.", "United States") == "Computers/Peripherals"
    assert g("GOOGL", "Alphabet Inc.", "United States") == "Software (Entertainment)"
    assert g("V", "Visa Inc.", "United States") == "Financial Svcs. (Non-bank & Insurance)"
    assert g("7203.T", "", "Japan") == "Auto & Truck" and g("0700.HK", "", "") == "Software (Entertainment)"   # ceros a la izquierda
    assert g("005930.KS", "", "") == "Computers/Peripherals"                                                    # prefijo A de Corea
    assert g("SAP.DE", "", "") == "Software (System & Application)" and g("NOVO-B.CO", "", "") == "Drugs (Pharmaceutical)"
    assert g("TM", "Toyota Motor Corporation", "Japan") == "Auto & Truck"                                       # ADR: por nombre
    assert dm.lookup("ZZZZ9", "Empresa Inexistente Total SA", "Chile") is None                                  # no figura
    # attach(): planilla primero; sin planilla vuelve a la regla de Yahoo; el selector manual manda sobre todo
    co = CompanyData(ticker="GOOGL", name="Alphabet Inc.", industry="Internet Content & Information", country="United States",
                     sector="Communication Services", price=100, currency="USD", market_cap_m=1e6, debt=0, cash=1, equity=1, ebit_ttm=1, revenue_ttm=10)
    _, name, how = idt.attach(co, "FCFF", None)
    assert name == "Software (Entertainment)" and "planilla" in how, (name, how)
    idt.USE_DAMODARAN_LIST = False
    try:
        _, name2, how2 = idt.attach(co, "FCFF", None)
    finally:
        idt.USE_DAMODARAN_LIST = True
    assert name2 == "Software (Internet)" and "Yahoo" in how2, (name2, how2)
    _, name3, how3 = idt.attach(co, "FCFF", "Power")
    assert name3 == "Power" and "elegida" in how3


def test_datos_de_referencia_avisan_cuando_vencen():
    """v2.44: lista de datos a renovar (ERP, tablas de industria, planilla de empresas) con su edad y si pasaron el plazo."""
    from datetime import date
    import industry_data as idt
    hoy = idt.reference_status(date(2026, 10, 20))
    assert [r["vencida"] for r in hoy] == [False, False, False], hoy
    tarde = {r["nombre"][:8]: r for r in idt.reference_status(date(2027, 5, 1))}
    assert tarde["Prima de"]["vencida"] and tarde["Tablas p"]["vencida"] and not tarde["Planilla"]["vencida"]   # mayo 2027: ERP y tablas de enero vencidas, la planilla no
    muy = idt.reference_status(date(2027, 12, 1))
    assert all(r["vencida"] for r in muy) and "Companies in each industry" in muy[2]["donde"]


def test_redes_de_pago_y_datos_no_se_comparan_con_prestamistas():
    """v2.45: V/MA/bolsas (FCFF, sin deuda de prestamista) van a Business & Consumer Services; prestamistas (ER) y manual no cambian."""
    import industry_data as idt
    from dcf_models import CompanyData
    mk = lambda tk, nm, ind, debt: CompanyData(ticker=tk, name=nm, industry=ind, country="United States", sector="Financial Services",
                                               price=100, currency="USD", market_cap_m=500_000, debt=debt, cash=1, equity=1, ebit_ttm=1, revenue_ttm=10)
    _, n, how = idt.attach(mk("V", "Visa Inc.", "Credit Services", 20_000), "FCFF", None)
    assert n == "Business & Consumer Services" and "reasignada" in how, (n, how)
    _, n, _ = idt.attach(mk("AXP", "American Express Company", "Credit Services", 60_000), "ER", None)
    assert n == "Financial Svcs. (Non-bank & Insurance)", n                      # prestamista por ER: conserva el grupo
    _, n, _ = idt.attach(mk("V", "Visa Inc.", "Credit Services", 900_000), "FCFF", None)
    assert n == "Financial Svcs. (Non-bank & Insurance)", n                      # deuda de prestamista: no se reasigna
    _, n, how = idt.attach(mk("V", "Visa Inc.", "Credit Services", 20_000), "FCFF", "Power")
    assert n == "Power" and "elegida" in how                                      # lo que elegís vos manda


def test_estados_ya_en_dolares_rotulados_como_reales():
    """Caso Vale/Petrobras: Yahoo dice BRL pero los montos ya están en USD. El control con los múltiplos de Yahoo lo detecta."""
    dfa, dfq = frames(sym="VAL", cur="BRL")
    fxb = lambda a, b: 0.2 if (a, b) == ("BRL", "USD") else None
    # cap 8.000 M; ventas TTM 1.040 M -> precio/ventas real 7,7×; valor libro 620 M -> 12,9×
    summ = {"beta": 1.0, "priceToSalesTrailing12Months": 8000 / 1040}
    ks = {"sharesOutstanding": 200e6, "priceToBook": 8000 / 620}
    co, w = build_company("VAL", price, summ, ks, prof, {"financialCurrency": "BRL"}, trend, dfa, dfq, fxb)
    assert abs(co.revenue_ttm - 1040.0) < 1e-9 and abs(co.fx - 1.0) < 1e-12 and co.fin_currency == "USD"      # sin convertir
    assert abs(co.debt - 300.0) < 1e-9 and abs(co.cash - 120.0) < 1e-9
    assert any("Moneda de los estados contables corregida" in x for x in w)


def test_conversion_correcta_no_se_toca():
    """Si los estados SÍ están en la moneda rotulada, los múltiplos de Yahoo coinciden con los convertidos: no se corrige."""
    dfa, dfq = frames(sym="VAL", cur="BRL")
    fxb = lambda a, b: 0.2 if (a, b) == ("BRL", "USD") else None
    summ = {"beta": 1.0, "priceToSalesTrailing12Months": 8000 / (1040 * 0.2)}
    ks = {"sharesOutstanding": 200e6, "priceToBook": 8000 / (620 * 0.2)}
    co, w = build_company("VAL", price, summ, ks, prof, {"financialCurrency": "BRL"}, trend, dfa, dfq, fxb)
    assert abs(co.revenue_ttm - 1040 * 0.2) < 1e-9 and abs(co.fx - 0.2) < 1e-12 and co.fin_currency == "BRL"
    assert not any("corregida" in x for x in w)
    # sin múltiplos de Yahoo no hay con qué comprobar: se confía en la etiqueta
    co2, w2 = build_company("VAL", price, {"beta": 1.0}, {"sharesOutstanding": 200e6}, prof, {"financialCurrency": "BRL"}, trend, dfa, dfq, fxb)
    assert abs(co2.fx - 0.2) < 1e-12 and not any("corregida" in x for x in w2)
    # una sola señal que no coincide con ninguna de las dos hipótesis: tampoco se toca
    co3, w3 = build_company("VAL", price, {"beta": 1.0, "priceToSalesTrailing12Months": 1.0}, {"sharesOutstanding": 200e6}, prof,
                            {"financialCurrency": "BRL"}, trend, dfa, dfq, fxb)
    assert abs(co3.fx - 0.2) < 1e-12


def test_moneda_manual_y_euro_no_se_corrigen_solos():
    dfa, dfq = frames(sym="VAL", cur="BRL")
    fxb = lambda a, b: 0.2 if (a, b) == ("BRL", "USD") else None
    summ = {"beta": 1.0, "priceToSalesTrailing12Months": 8000 / 1040}
    ks = {"sharesOutstanding": 200e6, "priceToBook": 8000 / 620}
    # «Convertir siempre»: se respeta la etiqueta aunque los múltiplos digan otra cosa
    co, _ = build_company("VAL", price, summ, ks, prof, {"financialCurrency": "BRL"}, trend, dfa, dfq, fxb, fin_cur_mode="convertir")
    assert abs(co.fx - 0.2) < 1e-12
    # «No convertir»: aunque no haya múltiplos de Yahoo
    co2, w2 = build_company("VAL", price, {"beta": 1.0}, {"sharesOutstanding": 200e6}, prof, {"financialCurrency": "BRL"}, trend, dfa, dfq, fxb,
                            fin_cur_mode="no_convertir")
    assert abs(co2.fx - 1.0) < 1e-12 and abs(co2.revenue_ttm - 1040.0) < 1e-9 and any("elegiste" in x for x in w2)
    # EUR->USD (1,10): la conversión mueve los montos <20 %, no se controla
    dfe, dfqe = frames(sym="ABC", cur="EUR")
    co3, w3 = build_company("ABC", price, {"beta": 1.1, "priceToSalesTrailing12Months": 8000 / 1040}, {"sharesOutstanding": 200e6, "priceToBook": 8000 / 620},
                            prof, {"financialCurrency": "EUR"}, trend, dfe, dfqe, fx)
    assert abs(co3.fx - 1.10) < 1e-12 and not any("corregida" in x for x in w3)


def test_diagnostico_de_moneda_devuelve_campos_de_yahoo():
    import sys, types
    class FakeTicker:
        def __init__(self, sym, timeout=20): self.sym = sym
        summary_detail = {"VAL": {"priceToSalesTrailing12Months": 1.35, "trailingPE": 9.0, "marketCap": 5.5e10}}
        key_stats = {"VAL": {"priceToBook": 1.5, "trailingEps": 1.4}}
        financial_data = {"VAL": {"financialCurrency": "BRL", "totalRevenue": 4.1e10}}
    fake = types.ModuleType("yahooquery"); fake.Ticker = FakeTicker
    old = sys.modules.get("yahooquery"); sys.modules["yahooquery"] = fake
    try:
        import data_yahoo
        d = data_yahoo.currency_diagnostic(" val ")
    finally:
        if old is not None: sys.modules["yahooquery"] = old
        else: sys.modules.pop("yahooquery", None)
    assert d["financialCurrency"] == "BRL" and abs(d["precio/ventas (Yahoo)"] - 1.35) < 1e-9
    assert abs(d["precio/valor libro (Yahoo)"] - 1.5) < 1e-9 and abs(d["BPA trailing (Yahoo)"] - 1.4) < 1e-9
    assert d["EBITDA (Yahoo, crudo)"] is None          # lo que Yahoo no entrega queda en None


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("OK", k)
    print(n, "pruebas OK")
