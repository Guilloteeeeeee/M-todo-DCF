"""
data_yahoo.py — Capa de datos (Yahoo Finance vía yahooquery) -> CompanyData normalizado.

Separación deliberada:
  * build_company(): lógica pura (recibe módulos y DataFrames ya descargados) -> testeable sin red.
  * load_company():  hace la descarga y llama a build_company().

Reglas de datos:
  * TTM: fila 'TTM' de Yahoo; si no, suma de los últimos 4 trimestres consecutivos (brechas 60-120 días).
    El último año fiscal solo se usa si allow_annual=True (por defecto NO).
  * Todos los montos se convierten a la moneda de COTIZACIÓN (fx spot) y se expresan en millones.
  * Acciones = capitalización / precio (equivale a acciones por ADR/ratio y maneja clases múltiples).
"""
from __future__ import annotations

import math
import re
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from dcf_models import CompanyData

RF_FALLBACK = 0.052   # último recurso (bono 10 años EE.UU. ~5,22 % al 08/10/2026, FRED); se usa solo si fallan todas las fuentes en vivo
PENCE = {"GBp": ("GBP", 100.0), "GBX": ("GBP", 100.0), "ZAc": ("ZAR", 100.0), "ZAC": ("ZAR", 100.0),
         "ILA": ("ILS", 100.0)}


class DataError(Exception):
    pass


FLOW_FIELDS = [
    "TotalRevenue", "OperatingIncome", "EBIT", "NetIncomeCommonStockholders", "NetIncome",
    "InterestExpense", "InterestExpenseNonOperating", "TaxProvision", "PretaxIncome", "TaxRateForCalcs",
    "DepreciationAndAmortization", "ReconciledDepreciation", "CapitalExpenditure", "ChangeInWorkingCapital",
    "CommonStockDividendPaid", "CashDividendsPaid", "RepurchaseOfCapitalStock", "GainLossOnSaleOfPPE",
    "ResearchAndDevelopment",
]
BAL_FIELDS = [
    "TotalDebt", "CapitalLeaseObligations", "CashCashEquivalentsAndShortTermInvestments", "MinorityInterest",
    "StockholdersEquity", "CommonStockEquity", "InvestedCapital", "OrdinarySharesNumber",
    "InvestmentsAndAdvances", "LongTermEquityInvestment",
]
ALL_FIELDS = FLOW_FIELDS + BAL_FIELDS


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def sf(x) -> Optional[float]:
    """float seguro: acepta números, {'raw': x}, strings numéricos; None si no válido."""
    if isinstance(x, dict):
        x = x.get("raw", None)
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(v) or math.isinf(v)) else v


def mod(d, sym: str) -> dict:
    """Extrae el dict de un módulo de yahooquery ({sym: dict | str de error})."""
    if not isinstance(d, dict):
        return {}
    x = d.get(sym)
    return x if isinstance(x, dict) else {}


def _frame(df, sym: str) -> pd.DataFrame:
    """Normaliza la salida de get_financial_data a un DataFrame plano de un solo símbolo."""
    if df is None or isinstance(df, (str, dict)):
        return pd.DataFrame(columns=["asOfDate", "periodType"])
    d = df.reset_index() if "symbol" not in df.columns else df.copy()
    if "symbol" in d.columns:
        d = d[d["symbol"].astype(str).str.upper() == sym.upper()]
    if "asOfDate" not in d.columns:
        return pd.DataFrame(columns=["asOfDate", "periodType"])
    d["asOfDate"] = pd.to_datetime(d["asOfDate"])
    return d.sort_values("asOfDate")


def _series(df: pd.DataFrame, ptype: str, field: str) -> pd.DataFrame:
    if field not in df.columns:
        return pd.DataFrame(columns=["asOfDate", field])
    r = df[(df["periodType"] == ptype)][["asOfDate", field]].dropna()
    return r.sort_values("asOfDate")


class Fundamentals:
    """Acceso TTM / anual / último saldo sobre los DataFrames anual (a) y trimestral (q)."""

    def __init__(self, dfa: pd.DataFrame, dfq: pd.DataFrame, allow_annual: bool = False):
        self.a, self.q, self.allow_annual = dfa, dfq, allow_annual
        self.sources: Dict[str, str] = {}
        self.asof: Dict[str, pd.Timestamp] = {}

    def ttm(self, field: str) -> Optional[float]:
        for df in (self.q, self.a):
            s = _series(df, "TTM", field)
            if len(s):
                self.sources[field] = "TTM Yahoo"
                self.asof[field] = s["asOfDate"].iloc[-1]
                return float(s[field].iloc[-1])
        s = _series(self.q, "3M", field).tail(4)
        if len(s) == 4:
            gaps = s["asOfDate"].diff().dt.days.dropna()
            if all(60 <= g <= 120 for g in gaps):
                self.sources[field] = "suma 4 trimestres"
                self.asof[field] = s["asOfDate"].iloc[-1]
                return float(s[field].sum())
        if self.allow_annual:
            s = _series(self.a, "12M", field)
            if len(s):
                self.sources[field] = "ÚLTIMO AÑO FISCAL (no TTM)"
                self.asof[field] = s["asOfDate"].iloc[-1]
                return float(s[field].iloc[-1])
        return None

    def latest(self, field: str) -> Optional[float]:
        """Último saldo (balance): trimestral más reciente; si no, anual."""
        cands = []
        for df, pt in ((self.q, "3M"), (self.a, "12M")):
            s = _series(df, pt, field)
            if len(s):
                cands.append((s["asOfDate"].iloc[-1], float(s[field].iloc[-1])))
        if not cands:
            return None
        return max(cands, key=lambda x: x[0])[1]

    def annual_hist(self, field: str, n: int = 4) -> List[Optional[float]]:
        s = _series(self.a, "12M", field).tail(n)
        return [float(v) for v in s[field].tolist()]

    def annual_hist_dates(self, field: str, n: int = 4):
        s = _series(self.a, "12M", field).tail(n)
        return list(s["asOfDate"])

    def currency(self) -> Optional[str]:
        for df in (self.q, self.a):
            if "currencyCode" in df.columns and df["currencyCode"].notna().any():
                return str(df["currencyCode"].dropna().iloc[-1])
        return None


def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def analyst_growth(earnings_trend_mod: dict) -> Tuple[Optional[float], Optional[float]]:
    g0 = g1 = None
    trend = earnings_trend_mod.get("trend") if isinstance(earnings_trend_mod, dict) else None
    for item in trend or []:
        if not isinstance(item, dict):
            continue
        per = item.get("period")
        est = item.get("revenueEstimate") or {}
        g = sf(est.get("growth"))
        if per == "0y":
            g0 = g
        elif per == "+1y":
            g1 = g
    return g0, g1


def analyst_ranges(earnings_trend_mod: dict) -> dict:
    """Rango de estimaciones de analistas: crecimiento de ingresos mínimo/máximo y crecimiento esperado del BPA."""
    out: dict = {}
    trend = earnings_trend_mod.get("trend") if isinstance(earnings_trend_mod, dict) else None
    for item in trend or []:
        if not isinstance(item, dict) or item.get("period") not in ("0y", "+1y"):
            continue
        k = "y0" if item["period"] == "0y" else "y1"
        est = item.get("revenueEstimate") or {}
        ago = sf(est.get("yearAgoRevenue"))
        lo, hi = sf(est.get("low")), sf(est.get("high"))
        if ago and ago > 0:
            if lo is not None:
                out["gl_" + k] = lo / ago - 1
            if hi is not None:
                out["gh_" + k] = hi / ago - 1
        eg = sf((item.get("earningsEstimate") or {}).get("growth"))
        if eg is not None:
            out["eg_" + k] = eg
    return out


# ----------------------------------------------------------------------------
# Construcción pura
# ----------------------------------------------------------------------------
def build_company(sym: str, price_m: dict, summary: dict, keystats: dict, profile: dict, fin: dict,
                  trend: dict, dfa, dfq, fx_fetcher: Callable[[str, str], Optional[float]],
                  rf: float = RF_FALLBACK, allow_annual: bool = False,
                  fallback_price: Optional[float] = None, fallback_currency: Optional[str] = None,
                  adr_ratio: Optional[float] = None, fallback_beta: Optional[float] = None
                  ) -> Tuple[CompanyData, List[str]]:
    warns: List[str] = []
    qt = str(price_m.get("quoteType") or "EQUITY").upper()
    px = sf(price_m.get("regularMarketPrice"))
    if (px is None or px <= 0) and fallback_price:
        px = fallback_price
        warns.append("Yahoo no entregó la cotización completa: el precio salió del último cierre del historial.")
    if px is None or px <= 0:
        raise DataError(f"No encontré precio para '{sym}'. Verificá el ticker (ej.: BRK-B, SAP.DE, 7203.T, TSM).")

    qcur = str(price_m.get("currency") or summary.get("currency") or fallback_currency or "USD")
    if not (price_m.get("currency") or summary.get("currency")) and fallback_currency:
        warns.append(f"Moneda de cotización supuesta por el sufijo del ticker: {qcur}.")
    pence_div = 1.0
    if qcur in PENCE:
        qcur, pence_div = PENCE[qcur]
        px = px / pence_div
        warns.append(f"Precio cotizado en subunidad ({pence_div:.0f}:1): convertido a {qcur}.")

    dfa_, dfq_ = _frame(dfa, sym), _frame(dfq, sym)
    F = Fundamentals(dfa_, dfq_, allow_annual)

    fin_cur = str(fin.get("financialCurrency") or F.currency() or qcur)
    fxr = 1.0
    if fin_cur != qcur:
        fxr = fx_fetcher(fin_cur, qcur)
        if fxr is None or fxr <= 0:
            raise DataError(f"No pude obtener el tipo de cambio {fin_cur}->{qcur}.")

    def M(x):  # a millones de moneda de cotización
        return None if x is None else x * fxr / 1e6

    mc = sf(price_m.get("marketCap")) or sf(summary.get("marketCap"))
    cap_estimated = False
    if mc is not None and pence_div != 1.0:
        pass  # se verifica abajo contra las acciones reportadas
    rep_sh = _first(sf(keystats.get("sharesOutstanding")), F.latest("OrdinarySharesNumber"))
    if mc and mc > 0:
        shares = mc / px
    else:
        shares = _first(sf(keystats.get("impliedSharesOutstanding")), rep_sh)
        if not shares:
            raise DataError("No encontré capitalización ni acciones en circulación.")
        if adr_ratio and adr_ratio > 0 and fin_cur != qcur:
            shares = shares / adr_ratio
            warns.append(f"Acciones ajustadas por ratio de ADR ingresado: {adr_ratio:g} ordinarias por ADR.")
        elif adr_ratio and adr_ratio > 0:
            warns.append(f"Ratio de ADR ({adr_ratio:g}) IGNORADO: la empresa reporta en {fin_cur}, la misma moneda en "
                         "que cotiza (no parece un ADR). Ponelo en 0 salvo que sea un ADR.")
        elif fin_cur != qcur:
            warns.append("⚠️ Parece un ADR o una cotización en otra moneda y Yahoo no dio la capitalización: "
                         "las acciones son las ORDINARIAS. Si cotiza como ADR, cargá 'ordinarias por ADR' "
                         "en la barra lateral (ej.: TSM = 5) o el valor por acción saldrá mal.")
        mc = shares * px
        cap_estimated = (fin_cur != qcur) and not (adr_ratio and adr_ratio > 0)   # posible ADR con acciones ordinarias sin ajustar
        warns.append("Capitalización estimada como acciones × precio.")
    if pence_div != 1.0 and rep_sh and rep_sh > 0:
        ratio = shares / rep_sh
        if 50 <= ratio <= 200:
            shares, mc = shares / pence_div, mc / pence_div
            warns.append("Capitalización de Yahoo venía en subunidad: corregida.")
    shares_m, mc_m = shares / 1e6, mc / 1e6
    rep_sh_m = rep_sh / 1e6 if rep_sh else None

    # --- flujos TTM
    rev = F.ttm("TotalRevenue")
    ebit = _first(F.ttm("OperatingIncome"), F.ttm("EBIT"))
    ni = _first(F.ttm("NetIncomeCommonStockholders"), F.ttm("NetIncome"))
    da = _first(F.ttm("DepreciationAndAmortization"), F.ttm("ReconciledDepreciation"))
    capex = F.ttm("CapitalExpenditure")
    dwc = F.ttm("ChangeInWorkingCapital")
    intexp = _first(F.ttm("InterestExpense"), F.ttm("InterestExpenseNonOperating"))
    tax = F.ttm("TaxProvision")
    pretax = F.ttm("PretaxIncome")
    div = _first(F.ttm("CommonStockDividendPaid"), F.ttm("CashDividendsPaid"))
    bb = F.ttm("RepurchaseOfCapitalStock")
    gains = F.ttm("GainLossOnSaleOfPPE")
    rd_ttm = F.ttm("ResearchAndDevelopment")

    tax_eff = None
    if tax is not None and pretax is not None and pretax > 0:
        r = tax / pretax
        if 0.0 <= r <= 0.5:
            tax_eff = r
    if tax_eff is None:
        t_ann = _series(dfa_, "12M", "TaxRateForCalcs")
        if len(t_ann):
            v = float(t_ann["TaxRateForCalcs"].iloc[-1])
            tax_eff = v if 0 <= v <= 0.5 else None

    src = F.sources.get("TotalRevenue", "sin datos")
    asof = F.asof.get("TotalRevenue")
    if "ÚLTIMO AÑO" in src:
        warns.append("Se usó el ÚLTIMO AÑO FISCAL porque no hay TTM disponible (opción activada).")
    if asof is not None:
        age = (pd.Timestamp.today().normalize() - asof).days
        if age > 200:
            warns.append(f"Los últimos datos contables son de hace {age} días ({asof.date()}).")

    # --- balance
    cash = F.latest("CashCashEquivalentsAndShortTermInvestments")
    debt = F.latest("TotalDebt")
    lease = F.latest("CapitalLeaseObligations")
    minority = F.latest("MinorityInterest")
    equity = _first(F.latest("CommonStockEquity"), F.latest("StockholdersEquity"))
    ic = F.latest("InvestedCapital")
    nonop = _first(F.latest("InvestmentsAndAdvances"), F.latest("LongTermEquityInvestment"))
    if cash is None:
        warns.append("Sin dato de caja: se asumió 0.")
    if debt is None:
        warns.append("Sin dato de deuda: se asumió 0.")

    # --- historia anual
    rev_h = F.annual_hist("TotalRevenue")
    ebit_h_raw = F.annual_hist("OperatingIncome") or F.annual_hist("EBIT")
    ni_h = F.annual_hist("NetIncomeCommonStockholders") or F.annual_hist("NetIncome")
    eq_h = F.annual_hist("CommonStockEquity") or F.annual_hist("StockholdersEquity")
    rd_h = F.annual_hist("ResearchAndDevelopment", 4)
    # alinear EBIT con ingresos por fecha
    rd = F.annual_hist_dates("TotalRevenue")
    ed = F.annual_hist_dates("OperatingIncome") or F.annual_hist_dates("EBIT")
    emap = dict(zip(ed, ebit_h_raw))
    ebit_h = [emap.get(d) for d in rd]

    g0, g1 = analyst_growth(trend)
    rng = analyst_ranges(trend)

    co = CompanyData(
        ticker=sym.upper(),
        name=str(price_m.get("longName") or price_m.get("shortName") or sym.upper()),
        sector=str(profile.get("sector") or ""), industry=str(profile.get("industry") or ""),
        country=str(profile.get("country") or ""), website=str(profile.get("website") or ""), quote_type=qt,
        price=px, currency=qcur, fin_currency=fin_cur, fx=fxr,
        shares_m=shares_m, reported_shares_m=rep_sh_m, market_cap_m=mc_m, cap_estimated=cap_estimated,
        beta=_first(sf(summary.get("beta")), sf(keystats.get("beta")), fallback_beta), rf=rf,
        revenue_ttm=M(rev) or 0.0, ebit_ttm=M(ebit) or 0.0, da_ttm=abs(M(da) or 0.0),
        capex_ttm=abs(M(capex) or 0.0), nwc_inv_ttm=-(M(dwc) or 0.0), tax_rate_eff=tax_eff,
        interest_expense_ttm=abs(M(intexp)) if intexp is not None else None,
        revenue_hist=[M(x) for x in rev_h], ebit_hist=[M(x) for x in ebit_h],
        invested_capital=M(ic), non_op_assets=max(M(nonop) or 0.0, 0.0), cash=M(cash) or 0.0, debt=M(debt) or 0.0,
        lease_debt=min(M(lease) or 0.0, M(debt) or 0.0), minority=M(minority) or 0.0,
        rev_g_y0=g0, rev_g_y1=g1,
        rev_gl_y0=rng.get("gl_y0"), rev_gl_y1=rng.get("gl_y1"), rev_gh_y0=rng.get("gh_y0"), rev_gh_y1=rng.get("gh_y1"),
        eps_g_y0=rng.get("eg_y0"), eps_g_y1=rng.get("eg_y1"),
        equity=M(equity), ni_ttm=M(ni), ni_hist=[M(x) for x in ni_h], equity_hist=[M(x) for x in eq_h],
        dividends_ttm=abs(M(div) or 0.0), buybacks_ttm=abs(M(bb) or 0.0),
        gains_adj_ttm=M(gains) or 0.0,
        rd_ttm=abs(M(rd_ttm) or 0.0), rd_hist=[abs(M(x)) for x in rd_h if x is not None],
        target_price=sf(fin.get("targetMeanPrice")),
        n_analysts=int(sf(fin.get("numberOfAnalystOpinions")) or 0) or None,
        ttm_source=src, asof=str(asof.date()) if asof is not None else "",
    )
    if co.beta is None:
        warns.append("Yahoo no informa beta.")
    elif sf(summary.get("beta")) is None and sf(keystats.get("beta")) is None:
        warns.append("Beta calculada con 5 años de rendimientos mensuales contra el S&P 500 (Yahoo no la informó).")
    if not co.sector and not co.industry:
        warns.append("⚠️ Yahoo no entregó sector ni industria: el modelo se eligió como empresa NO financiera. "
                     "Si es banco, aseguradora o REIT, elegí el modelo a mano en el selector.")
    if g0 is None and g1 is None:
        warns.append("Sin estimaciones de analistas de ingresos: el crecimiento inicial sale de la historia.")
    if qt != "EQUITY":
        warns.append(f"Instrumento tipo {qt}: el DCF no aplica a fondos/ETF.")
    return co, warns


# ----------------------------------------------------------------------------
# Descarga
# ----------------------------------------------------------------------------
SUFFIX_CCY = {".DE": "EUR", ".F": "EUR", ".PA": "EUR", ".AS": "EUR", ".MC": "EUR", ".MI": "EUR", ".BR": "EUR",
              ".HE": "EUR", ".LS": "EUR", ".VI": "EUR", ".SW": "CHF", ".L": "GBp", ".T": "JPY", ".TO": "CAD",
              ".V": "CAD", ".HK": "HKD", ".AX": "AUD", ".SA": "BRL", ".MX": "MXN", ".KS": "KRW", ".TW": "TWD",
              ".SS": "CNY", ".SZ": "CNY", ".NS": "INR", ".BO": "INR", ".ST": "SEK", ".CO": "DKK", ".OL": "NOK",
              ".SI": "SGD", ".JO": "ZAc", ".TA": "ILA"}


def _last_close(sym: str) -> Optional[float]:
    """Último cierre vía historial (endpoint distinto al de cotizaciones; suele seguir funcionando)."""
    try:
        from yahooquery import Ticker
        h = Ticker(sym).history(period="5d", interval="1d")
        if isinstance(h, pd.DataFrame) and len(h) and "close" in h.columns:
            v = sf(h["close"].dropna().iloc[-1])
            return v if v and v > 0 else None
    except Exception:
        pass
    return None


def _guess_currency(sym: str) -> str:
    for suf, cur in SUFFIX_CCY.items():
        if sym.upper().endswith(suf):
            return cur
    return "USD"


def estimate_beta(sym: str, bench: str = "^GSPC") -> Optional[float]:
    """Beta de 5 años mensual contra el S&P 500, solo si Yahoo no la informa."""
    try:
        from yahooquery import Ticker
        h = Ticker([sym, bench]).history(period="5y", interval="1mo")
        if not isinstance(h, pd.DataFrame) or "adjclose" not in h.columns:
            return None
        col = "adjclose"
        a = h.xs(sym, level=0)[col].dropna()
        b = h.xs(bench, level=0)[col].dropna()
        df = pd.concat([a.pct_change(), b.pct_change()], axis=1, join="inner").dropna()
        if len(df) < 24:
            return None
        cov = df.iloc[:, 0].cov(df.iloc[:, 1])
        var = df.iloc[:, 1].var()
        beta = cov / var if var else None
        return float(beta) if beta is not None and -1 < beta < 4 else None
    except Exception:
        return None


def get_fx(fin: str, quote: str) -> Optional[float]:
    """Cuántas unidades de 'quote' vale 1 unidad de 'fin' (spot de Yahoo; si falla, último cierre)."""
    from yahooquery import Ticker
    for pair, inv in ((f"{fin}{quote}=X", False), (f"{quote}{fin}=X", True)):
        v = None
        try:
            d = Ticker(pair).price
            v = sf(d.get(pair, {}).get("regularMarketPrice")) if isinstance(d, dict) else None
        except Exception:
            v = None
        if not v:
            v = _last_close(pair)
        if v and v > 0:
            return 1.0 / v if inv else v
    return None


def parse_fred_csv(text: str) -> Optional[float]:
    """Último valor numérico de un CSV de FRED ('DATE,DGS10'), en % (ej. 4.12)."""
    last = None
    for line in text.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            try:
                last = float(parts[1])
            except ValueError:
                continue
    return last


def _fred_10y() -> Optional[float]:
    """Rendimiento del Tesoro a 10 años desde FRED (Reserva Federal de St. Louis), sin clave."""
    try:
        import urllib.request
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
        with urllib.request.urlopen(url, timeout=10) as r:
            return parse_fred_csv(r.read().decode("utf-8", "ignore"))
    except Exception:
        return None


def yf_fallback(sym: str) -> dict:
    """Fuente alternativa (yfinance) para sector, industria, país, beta y crecimiento esperado de ingresos."""
    out: dict = {}
    try:
        import yfinance as yf
        tk = yf.Ticker(sym)
    except Exception:
        return out
    try:
        info = tk.info or {}
        for k_out, k_in in (("sector", "sector"), ("industry", "industry"), ("country", "country"), ("website", "website")):
            if info.get(k_in):
                out[k_out] = str(info[k_in])
        b = sf(info.get("beta"))
        if b is not None:
            out["beta"] = b
        nm = info.get("longName") or info.get("shortName")
        if nm:
            out["name"] = str(nm)
    except Exception:
        pass
    try:
        re_ = tk.revenue_estimate
        if re_ is not None and "growth" in getattr(re_, "columns", []):
            for per, key in (("0y", "g0"), ("+1y", "g1")):
                if per in re_.index:
                    v = sf(re_.loc[per, "growth"])
                    if v is not None:
                        out[key] = v
    except Exception:
        pass
    return out


RETRY_WAITS = (1.5, 3.0)     # segundos entre reintentos cuando Yahoo no entrega el perfil (los tests lo ponen en ())


def search_profile(sym: str) -> dict:
    """Fuente alternativa liviana: el buscador de Yahoo (no usa 'crumb') suele devolver nombre, sector e industria
    aun cuando el endpoint de perfil está limitado. No trae país. Nunca falla: devuelve {} si no hay respuesta."""
    try:
        import json
        import urllib.parse
        import urllib.request
        url = ("https://query2.finance.yahoo.com/v1/finance/search?q=" + urllib.parse.quote(sym)
               + "&quotesCount=6&newsCount=0")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        for q in data.get("quotes") or []:
            if str(q.get("symbol", "")).upper() == sym.upper():
                out = {}
                sec = q.get("sectorDisp") or q.get("sector")
                ind = q.get("industryDisp") or q.get("industry")
                if ind:   # el buscador usa raya larga ("Utilities—Regulated Electric"); el resto del código espera "Utilities - Regulated Electric"
                    ind = re.sub(r"\s*[—–]\s*", " - ", str(ind))
                nm = q.get("longname") or q.get("shortname")
                if sec:
                    out["sector"] = str(sec)
                if ind:
                    out["industry"] = str(ind)
                if nm:
                    out["name"] = str(nm)
                return out
    except Exception:
        pass
    return {}


def missing_fields(co: CompanyData) -> List[str]:
    """Qué datos de perfil no llegaron (lista vacía = completo). No aplica a fondos/ETF."""
    if co.quote_type and co.quote_type != "EQUITY":
        return []
    out = []
    if not co.sector:
        out.append("sector")
    if not co.industry:
        out.append("industria")
    if not co.country:
        out.append("país")
    if not co.name or co.name.upper() == (co.ticker or "").upper():
        out.append("nombre")
    if co.cap_estimated:
        out.append("capitalización de mercado (posible ADR sin ajustar)")
    return out


def unreliable_reasons(co: CompanyData) -> List[str]:
    """Motivos por los que el valor NO es confiable (lista vacía = confiable). Falta solo el país: se acepta con aviso,
    salvo que además no hayan llegado los estimados de analistas (señal de que Yahoo bloqueó varios módulos a la vez)."""
    if co.quote_type and co.quote_type != "EQUITY":
        return []
    miss = missing_fields(co)
    out = [f"falta {m}" for m in miss if m != "país"]
    if "país" in miss and co.rev_g_y0 is None and co.rev_g_y1 is None:
        out.append("faltan país y estimaciones de analistas (Yahoo bloqueó módulos)")
    return out


def is_degraded(co: CompanyData) -> bool:
    """Carga incompleta (falta algún dato de perfil). Una carga así no se guarda en la caché, para que reintentar consulte de nuevo."""
    return bool(missing_fields(co))


def get_risk_free() -> Tuple[float, bool]:
    """Rendimiento del bono a 10 años de EE.UU. (^TNX). (valor, vino_de_yahoo).
    Orden: cotización de Yahoo -> FRED (Reserva Federal) -> historial de Yahoo -> valor fijo."""
    cands = []
    try:
        from yahooquery import Ticker
        d = Ticker("^TNX").price
        cands.append(sf(d.get("^TNX", {}).get("regularMarketPrice")))
    except Exception:
        pass
    cands.append(_fred_10y())
    cands.append(_last_close("^TNX"))
    for v in cands:
        if v:
            if v > 20:
                v /= 10.0
            r = v / 100.0
            if 0.005 <= r <= 0.12:
                return r, True
    return RF_FALLBACK, False


def load_company(sym: str, allow_annual: bool = False, adr_ratio: Optional[float] = None
                 ) -> Tuple[CompanyData, List[str]]:
    from yahooquery import Ticker
    sym = sym.strip().upper()
    if not sym:
        raise DataError("Ingresá un ticker.")
    t = Ticker(sym, timeout=20)

    failed: List[str] = []

    def safe(fn, label: str = ""):
        try:
            r = mod(fn(), sym)
        except Exception:
            r = {}
        if not r and label:
            failed.append(label)
        return r

    price_m = safe(lambda: t.price, "precio/cotización")
    summary, keystats = safe(lambda: t.summary_detail, "resumen"), safe(lambda: t.key_stats, "estadísticas")
    profile, fin = safe(lambda: t.asset_profile, "perfil (sector/industria/país)"), safe(lambda: t.financial_data, "datos financieros")
    trend = safe(lambda: t.earnings_trend, "estimaciones de analistas")
    try:
        dfa = t.get_financial_data(ALL_FIELDS, frequency="a", trailing=True)
        dfq = t.get_financial_data(ALL_FIELDS, frequency="q", trailing=True)
    except Exception as e:  # noqa: BLE001
        raise DataError(f"Yahoo rechazó la descarga de estados contables de '{sym}': {e}")
    if isinstance(dfa, (str, dict)) and isinstance(dfq, (str, dict)):
        raise DataError(f"Yahoo no tiene estados contables para '{sym}' (o bloqueó la consulta).")

    fb_price = fb_cur = None
    if not sf(price_m.get("regularMarketPrice")):
        fb_price, fb_cur = _last_close(sym), _guess_currency(sym)

    # Reintentos: Yahoo a veces limita los módulos de perfil/cotización por unos segundos.
    if not profile.get("industry") or not (price_m.get("longName") or price_m.get("shortName")):
        import time
        for wait in RETRY_WAITS:
            time.sleep(wait)
            try:
                t2 = Ticker(sym, timeout=20)
                if not profile.get("industry"):
                    profile = mod(t2.asset_profile, sym) or profile
                if not (price_m.get("longName") or price_m.get("shortName")):
                    price_m = mod(t2.price, sym) or price_m
            except Exception:
                pass
            if profile.get("industry") and (price_m.get("longName") or price_m.get("shortName")):
                if "perfil (sector/industria/país)" in failed:
                    failed.remove("perfil (sector/industria/país)")
                break

    alt: dict = {}
    need_alt = (not profile.get("industry") or not (price_m.get("longName") or price_m.get("shortName")) or not any(
        i.get("revenueEstimate") for i in (trend.get("trend") or []) if isinstance(i, dict))
        or (sf(summary.get("beta")) is None and sf(keystats.get("beta")) is None))
    if need_alt:
        alt = yf_fallback(sym)
    if alt.get("name") and not (price_m.get("longName") or price_m.get("shortName")):
        price_m = {**price_m, "longName": alt["name"]}
    if alt.get("industry") and not profile.get("industry"):
        profile = {**profile, **{k: alt[k] for k in ("sector", "industry", "country", "website") if alt.get(k)}}
    if alt.get("website") and not profile.get("website"):
        profile = {**profile, "website": alt["website"]}
    if not profile.get("industry") or not (price_m.get("longName") or price_m.get("shortName")):
        sp = search_profile(sym)                     # tercera vía: buscador de Yahoo (sin país)
        if sp.get("industry") and not profile.get("industry"):
            profile = {**profile, **{k: sp[k] for k in ("sector", "industry") if sp.get(k)}}
            alt = {**alt, "search": True}
        if sp.get("name") and not (price_m.get("longName") or price_m.get("shortName")):
            price_m = {**price_m, "longName": sp["name"]}
    if ("g0" in alt or "g1" in alt) and not any(
            i.get("revenueEstimate") for i in (trend.get("trend") or []) if isinstance(i, dict)):
        trend = {"trend": [{"period": "0y", "revenueEstimate": {"growth": alt.get("g0")}},
                           {"period": "+1y", "revenueEstimate": {"growth": alt.get("g1")}}]}
    has_beta = sf(summary.get("beta")) is not None or sf(keystats.get("beta")) is not None
    fb_beta = None if has_beta else (alt.get("beta") if alt.get("beta") is not None else estimate_beta(sym))

    rf, ok = get_risk_free()
    co, warns = build_company(sym, price_m, summary, keystats, profile, fin, trend, dfa, dfq, get_fx,
                              rf=rf, allow_annual=allow_annual, fallback_price=fb_price,
                              fallback_currency=fb_cur, adr_ratio=adr_ratio, fallback_beta=fb_beta)
    if not ok:
        warns.append(f"No pude leer la tasa del Tesoro a 10 años: se usó Rf = {RF_FALLBACK:.2%}.")
    if alt:
        warns.append("Sector/industria/estimaciones/beta completados con una fuente alternativa (yfinance / buscador de Yahoo).")
    miss = missing_fields(co)
    if miss:
        warns.append("🔴 Carga incompleta: no pude leer " + ", ".join(miss) + " de Yahoo (ni con reintentos ni con fuentes alternativas)"
                     + (f". Módulos que no respondieron: {', '.join(failed)}" if failed else "") + ".")
    return co, warns
