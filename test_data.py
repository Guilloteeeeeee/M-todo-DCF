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


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("OK", k)
    print(n, "pruebas OK")
