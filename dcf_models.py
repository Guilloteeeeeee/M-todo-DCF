"""
dcf_models.py — Motor de valuación (sin dependencias de red ni de Streamlit).

Tres modelos:
  * FCFF 3 etapas construido desde ingresos  -> empresas industriales / de servicios / tecnología
  * Retorno excedente (residual income)       -> bancos, aseguradoras, mREITs, brokers
  * AFFO (flujo distribuible)                 -> REITs de renta (equity REITs)

Convenciones:
  * Todos los montos de CompanyData están en MILLONES de la moneda de cotización.
  * Tasas en decimales (0.045 = 4,5 %).
  * Los tres escenarios (Pesimista / Base / Optimista) se obtienen cambiando supuestos,
    nunca multiplicando el resultado final.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple
import math
import statistics


class ModelError(Exception):
    """Error 'esperable': el modelo no aplica o faltan datos críticos."""


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _med(xs: List[Optional[float]]) -> Optional[float]:
    v = [x for x in xs if x is not None and not math.isnan(x)]
    return statistics.median(v) if v else None


# ----------------------------------------------------------------------------
# Datos
# ----------------------------------------------------------------------------
@dataclass
class CompanyData:
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    country: str = ""
    website: str = ""
    quote_type: str = "EQUITY"

    price: float = 0.0                 # precio por acción / ADR en moneda de cotización
    currency: str = "USD"              # moneda de cotización
    fin_currency: str = "USD"          # moneda de los estados contables
    fx: float = 1.0                    # fin_currency -> currency (ya aplicado a los montos)
    shares_m: float = 0.0              # acciones implícitas (mkt cap / precio), en millones
    reported_shares_m: Optional[float] = None
    market_cap_m: float = 0.0
    cap_estimated: bool = False        # True: Yahoo no dio la capitalización y se estimó acciones ordinarias × precio (riesgo de ADR mal contado)

    beta: Optional[float] = None
    rf: float = 0.0425

    # --- operativo (FCFF)
    revenue_ttm: float = 0.0
    ebit_ttm: float = 0.0
    da_ttm: float = 0.0
    capex_ttm: float = 0.0             # positivo
    nwc_inv_ttm: float = 0.0           # inversión en capital de trabajo (positivo = consume caja)
    tax_rate_eff: Optional[float] = None
    interest_expense_ttm: Optional[float] = None
    revenue_hist: List[Optional[float]] = field(default_factory=list)   # anual, antiguo -> reciente
    ebit_hist: List[Optional[float]] = field(default_factory=list)
    invested_capital: Optional[float] = None   # según Yahoo (deuda + patrimonio: INCLUYE caja e inversiones)
    non_op_assets: float = 0.0         # inversiones de largo plazo en otras empresas / valores (valor contable)
    cash: float = 0.0
    debt: float = 0.0                  # incluye arrendamientos
    lease_debt: float = 0.0            # parte de 'debt' que son arrendamientos
    minority: float = 0.0
    pension_liab: Optional[float] = None   # pensiones y beneficios post-empleo (M): INFORMATIVO, no se resta del valor
    receivables: Optional[float] = None    # cuentas por cobrar corrientes (M): INFORMATIVO (detectar financieras propias)
    receivables_nc: Optional[float] = None # cuentas por cobrar de largo plazo (M): INFORMATIVO
    rev_g_y0: Optional[float] = None   # crecimiento ingresos estimado año fiscal en curso
    rev_g_y1: Optional[float] = None   # crecimiento ingresos estimado año fiscal siguiente
    rev_gl_y0: Optional[float] = None  # crecimiento de ingresos: estimación MÍNIMA de analistas (año en curso)
    rev_gl_y1: Optional[float] = None
    rev_gh_y0: Optional[float] = None  # ... estimación MÁXIMA
    rev_gh_y1: Optional[float] = None
    eps_g_y0: Optional[float] = None   # crecimiento esperado del BPA (analistas)
    eps_g_y1: Optional[float] = None

    # --- financieras
    equity: Optional[float] = None     # patrimonio común (book value)
    ni_ttm: Optional[float] = None
    ni_hist: List[Optional[float]] = field(default_factory=list)
    equity_hist: List[Optional[float]] = field(default_factory=list)
    dividends_ttm: float = 0.0         # positivo
    buybacks_ttm: float = 0.0          # positivo

    # --- REIT
    gains_adj_ttm: float = 0.0         # ajuste a NI por ganancias/pérdidas en venta de activos (signo CF)

    # --- I+D (se capitaliza como activo, Damodaran cap. 11)
    rd_ttm: float = 0.0                # gasto en I+D de los últimos 12 meses (millones, moneda de cotización)
    rd_hist: List[Optional[float]] = field(default_factory=list)   # I+D anual, antiguo -> reciente (hasta 4 años)

    # --- referencia de industria (Damodaran); lo completa la app
    ind_name: str = ""
    ind_region: str = ""
    ind_ubeta: Optional[float] = None      # beta desapalancada del sector (corregida por caja)
    ind_beta_lev: Optional[float] = None   # beta del sector tal cual (se usa en financieras)
    ind_roc: Optional[float] = None        # retorno sobre capital promedio del sector (Damodaran)
    ind_margin: Optional[float] = None     # margen EBIT promedio del sector (Damodaran)
    ind_de: Optional[float] = None         # deuda / capital propio de mercado promedio del sector

    # --- flujo de caja real de Yahoo (v2.48; para el método estilo Dorsey)
    fcf_ttm: Optional[float] = None    # flujo de caja libre = flujo operativo − inversión, últimos 12 meses (M, moneda de cotización)
    cfo_ttm: Optional[float] = None    # flujo de caja operativo, últimos 12 meses
    country_from: str = ""              # vacío = el país vino de Yahoo; si no, de dónde se tomó (planilla de Damodaran)

    # --- referencia
    target_price: Optional[float] = None
    n_analysts: Optional[int] = None
    ttm_source: str = ""
    asof: str = ""


@dataclass
class Params:
    horizon: int = 10
    g_terminal: float = 0.025
    erp: float = 0.045
    crp: float = 0.0                   # prima de riesgo país (sobre Ke)
    rf: Optional[float] = None
    beta: Optional[float] = None
    wacc_override: Optional[float] = None
    captive_adj: bool = True                # v2.41: restar solo la deuda propia cuando hay financiera propia (Ford, GM, CAT...)
    capitalize_rd: bool = True              # capitalizar el gasto en I+D (Damodaran, cap. 11) con los años que entrega Yahoo
    survival_adj: bool = True               # ajuste por probabilidad de quiebra (Damodaran, cap. 8) para calificación sintética peor que BBB
    ke_override: Optional[float] = None
    marginal_tax: float = 0.25
    margin_mode: str = "median"        # median | ttm | manual
    margin_manual: Optional[float] = None
    margin_years: int = 5
    moat: str = "auto"                 # auto | Ninguno | Estrecho | Amplio
    moat_spread: Optional[float] = None    # si se fija, reemplaza al moat (uso interno / pruebas)
    growth_override: Optional[Tuple[float, float]] = None
    roic_cap: float = 0.40
    include_leases: Optional[bool] = None   # None = automático (EEUU: no; resto: sí)
    include_nonop: bool = True              # sumar inversiones en otras empresas (valor contable)
    use_industry_beta: bool = True          # mezclar beta de la acción con la del sector (Damodaran)
    wacc_shift: float = 0.0                 # desplazamiento de la tasa de descuento (solo la grilla de sensibilidad)
    # financieras
    persistence: float = 0.5
    # REIT
    affo_ratio: float = 0.90
    affo_ps_override: Optional[float] = None
    roi_spread: float = 0.01


@dataclass
class Scen:
    name: str = "Base"
    g_adj: float = 0.0
    m_rule: str = "base"               # base | pess | opt
    spread_delta: float = 0.0
    persistence: Optional[float] = None
    roe_scale: float = 1.0
    roi_spread: Optional[float] = None


SCENARIOS: Dict[str, Scen] = {
    # Los escenarios solo mueven palancas del negocio (crecimiento, margen, foso). Tasas y g terminal: pestaña Sensibilidad.
    "Pesimista": Scen("Pesimista", g_adj=-0.03, m_rule="pess",
                      spread_delta=-0.02, persistence=0.0, roe_scale=0.90, roi_spread=0.0),
    "Base": Scen("Base"),
    "Optimista": Scen("Optimista", g_adj=+0.03, m_rule="opt",
                      spread_delta=+0.02, persistence=0.75, roe_scale=1.05, roi_spread=0.02),
}

MOAT_SPREADS = {"Ninguno": 0.0, "Estrecho": 0.02, "Amplio": 0.05}
MOAT_PARTIAL_LABEL_MIN = 0.50   # desde este premio parcial se muestra Estrecho (solo etiqueta; el cálculo no cambia)


@dataclass
class ValResult:
    model: str
    scenario: str
    ok: bool = True
    error: str = ""
    per_share: float = float("nan")
    equity_value: float = float("nan")
    ev: Optional[float] = None
    discount_rate: float = float("nan")   # WACC (FCFF) o Ke (financieras / REIT)
    ke: float = float("nan")
    g_terminal: float = float("nan")
    tv_share: float = float("nan")
    table: List[dict] = field(default_factory=list)
    extras: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# Enrutado de modelo según sector / industria
# ----------------------------------------------------------------------------
FIN_ER_INDUSTRIES = ("banks", "insurance - ", "mortgage finance", "capital markets", "reit - mortgage")


# Dentro de "Credit Services" de Yahoo conviven redes de pagos (asset-light) y prestamistas (balance pesado).
CREDIT_LENDERS = {"AXP", "COF", "SYF", "DFS", "ALLY", "SOFI", "UPST", "AFRM", "LC", "OMF", "BFH", "SLM", "NAVI",
                  "ENVA", "OPFI", "MFIN", "CACC", "WRLD", "PRAA", "ECPG", "NNI", "LU"}
# Respaldo cuando Yahoo no entrega sector/industria (frecuente desde servidores en la nube): emisores conocidos.
KNOWN_FIN = {
    "JPM", "BAC", "C", "WFC", "GS", "MS", "BK", "STT", "USB", "PNC", "TFC", "SCHW", "COF_", "FITB", "KEY", "RF", "HBAN",
    "MTB", "CFG", "NTRS", "ZION", "CMA", "MET", "PRU", "AIG", "ALL", "TRV", "CB", "PGR", "AFL", "HIG", "LNC", "PFG",
    "CINF", "L", "WRB", "ACGL", "RE", "EG", "UNM", "GL", "AIZ", "BRK-B", "BRK.B",
    "ITUB", "BBD", "BBDO", "BSBR", "SAN", "BBVA", "HSBC", "UBS", "ING", "BCS", "LYG", "NWG", "DB", "CS", "MUFG", "SMFG",
    "MFG", "NMR", "IBN", "HDB", "KB", "SHG", "WF", "CIB", "BAP", "BSAC", "BCH", "CM", "RY", "TD", "BMO", "BNS", "NU",
    "GGAL", "BMA", "BBAR", "SUPV", "BFR", "TFSL", "SIVB", "NYCB", "FHN", "WAL", "PACW", "EWBC", "SNV", "WBS", "OZK",
    "AXS", "SLF", "MFC", "AEG", "PUK", "MCO_", "BLK_",
}
KNOWN_REIT = {
    "O", "SPG", "PLD", "AMT", "CCI", "EQIX", "PSA", "WELL", "VICI", "DLR", "AVB", "EQR", "ESS", "MAA", "UDR", "INVH",
    "ARE", "BXP", "KIM", "REG", "FRT", "HST", "EXR", "CUBE", "VTR", "DOC", "SBAC", "IRM", "WPC", "NNN", "ADC", "STAG",
    "REXR", "FR", "EGP", "CPT", "AMH", "ELS", "SUI", "LAMR", "OUT", "GLPI", "EPR", "LTC", "OHI", "SBRA", "NHI", "MPW",
    "HR", "KRG", "BRX", "SKT", "APLE", "RHP", "PK", "SITC", "ROIC", "CUZ", "DEI", "HIW", "KRC", "VNO", "SLG", "PEAK",
}
_NAME_REIT = ("reit", "realty", "real estate investment", "properties trust", "property trust")
_NAME_FIN = ("bank", "bancorp", "banco", "banque", "banca", "bancshares", "insurance", "assurance",
             "assicurazioni", "reinsurance", "financial group", "financial corp", "financial services group")


def route_model(co: CompanyData) -> Tuple[str, str]:
    """Devuelve (modelo, motivo). modelo in {'FCFF','ER','REIT'}. v2.40: las utilities reguladas van por ER."""
    ind = (co.industry or "").strip().lower()
    sec = (co.sector or "").strip().lower()
    if not ind:
        # Yahoo no dio la industria: primero el sector, después el nombre y la forma de los estados contables.
        name = (co.name or "").lower()
        root = (co.ticker or "").upper().split(".")[0]
        if root in KNOWN_REIT:
            return "REIT", "REIT conocido (Yahoo no informó la industria): AFFO. Confirmalo en el selector."
        if root in KNOWN_FIN:
            return "ER", "Banco/aseguradora conocido (Yahoo no informó la industria): retorno excedente. Confirmalo en el selector."
        if sec == "financial services":
            return "ER", "Sector financiero (industria no informada): retorno excedente."
        if sec == "real estate":
            return "REIT", "Sector inmobiliario (industria no informada): se asume REIT de renta; confirmalo."
        if any(k in name for k in _NAME_REIT):
            return "REIT", "Detectado por el nombre como REIT: confirmalo en el selector."
        if any(k in name for k in _NAME_FIN):
            return "ER", "Detectado por el nombre como banco/aseguradora: confirmalo en el selector."
        if not sec and co.ebit_ttm <= 0 and (co.ni_ttm or 0) > 0 and (co.equity or 0) > 0:
            return "ER", ("Sin sector informado y sin resultado operativo (típico de bancos y aseguradoras): "
                          "retorno excedente. Confirmalo en el selector.")
    if ind.startswith("reit - mortgage"):
        return "ER", "REIT hipotecario: se valúa por patrimonio y ROE (como un financiero)."
    if ind.startswith("reit"):
        return "REIT", "REIT de renta: se valúa por AFFO."
    if ind.startswith("banks"):
        return "ER", "Banco: el pasivo es materia prima, no deuda financiera; se usa retorno excedente."
    if ind.startswith("insurance - ") or ind in ("insurance",):
        return "ER", "Aseguradora: se usa retorno excedente sobre el patrimonio."
    if ind == "mortgage finance":
        return "ER", "Financiera hipotecaria: retorno excedente."
    if ind == "capital markets":
        return "ER", ("Mercado de capitales (bancos de inversión/brokers): retorno excedente. "
                      "Si es una gestora de activos alternativos (BX, KKR, APO), probá FCFF.")
    if ind == "credit services":
        root = (co.ticker or "").upper().split(".")[0]
        if root in CREDIT_LENDERS:
            return "ER", "Prestamista de tarjetas/créditos: el crédito es su negocio, se usa retorno excedente."
        return "FCFF", ("Servicios de crédito: se trata como red de pagos o servicio (V, MA, PYPL), sin cartera de "
                        "préstamos propia. Si es un prestamista, elegí 'Banco / aseguradora / financiera'.")
    if ind.startswith("utilities - regulated"):
        return "ER", ("Utility regulada (electricidad, gas o agua): el regulador fija lo que puede ganar sobre el capital invertido y "
                      "gran parte de lo que invierte es deuda, así que el valor se calcula sobre el patrimonio y el ROE (retorno "
                      "excedente), como en un financiero. Las productoras independientes, renovables y diversificadas siguen por FCFF. "
                      "Confirmalo en el selector si no corresponde.")
    return "FCFF", "Empresa no financiera: FCFF desde ingresos."


# ----------------------------------------------------------------------------
# Costo de capital
# ----------------------------------------------------------------------------
def _bottom_up_beta(co: CompanyData, p: "Params") -> Optional[float]:
    """Beta 'bottom-up' (Damodaran): beta desapalancada del sector re-apalancada con la estructura de la empresa."""
    if co.ind_beta_lev is not None:          # financieras: la deuda es materia prima, se usa la beta del sector
        return co.ind_beta_lev
    if co.ind_ubeta is None:
        return None
    debt = co.debt if _leases_included(co, p) else max(0.0, co.debt - co.lease_debt)
    de = max(debt, 0.0) / max(co.market_cap_m, 1e-9)
    return co.ind_ubeta * (1 + (1 - p.marginal_tax) * de)


BETA_MIN = 0.5     # piso: ninguna empresa se descuenta con una beta menor (decisión v2.34)
BETA_MAX = 2.0     # tope: una beta propia o de industria mayor a 2 no se considera informativa (igual que SWS)


def cost_of_equity(co: CompanyData, p: Params, scen: Scen, warns: List[str]) -> Dict[str, float]:
    """Beta (v2.34): (1) con datos de industria, el promedio simple entre la beta de la industria re-apalancada con la deuda
    de la empresa (Damodaran) y la beta propia de la acción, acotado entre BETA_MIN (0,5) y BETA_MAX (2,0);
    si la beta propia falta o es ≤ 0 (no confiable) se usa solo la de la industria, con los mismos límites;
    (2) sin industria, beta de la acción con ajuste de Blume (0,67·β + 0,33), con los mismos límites;
    (3) sin beta propia ni industria: 1,0 (el promedio del mercado)."""
    rf = p.rf if p.rf is not None else co.rf
    bu = _bottom_up_beta(co, p) if (p.beta is None and p.use_industry_beta) else None
    if p.beta is not None:                          # beta cargada a mano
        beta, beta_adj = p.beta, 0.67 * p.beta + 0.33
    elif bu is not None:
        own = co.beta
        if own is not None and own > 0:
            raw_b = (own + bu) / 2
            txt = (f"Beta = promedio entre la de la industria ({co.ind_name}) re-apalancada con la deuda de la empresa ({bu:.2f}) "
                   f"y la propia de la acción ({own:.2f}) = {raw_b:.2f}")
        else:
            raw_b = bu
            txt = (f"Beta de la industria ({co.ind_name}) re-apalancada con la deuda de la empresa = {bu:.2f}. "
                   "La beta propia de la acción no es confiable o falta, y no se usa")
        beta = clamp(raw_b, BETA_MIN, BETA_MAX)
        if beta != raw_b:
            txt += f"; se llevó a {beta:.2f} ({'piso' if beta > raw_b else 'tope'} de {BETA_MIN:.1f}–{BETA_MAX:.1f})"
        warns.append(txt + ".")
        beta_adj = beta
        if own is not None and own > 0 and abs(own - bu) > 0.5:
            warns.append(f"La beta propia de la acción ({own:.2f}) difiere mucho de la de su industria ({bu:.2f}): "
                         "revisá que la industria detectada sea la correcta (barra lateral → Ajustes avanzados).")
    else:
        raw = co.beta
        if raw is None:
            raw = 1.0
            warns.append("Sin beta en Yahoo ni datos de industria: se usó beta = 1,0.")
        elif raw <= 0:
            warns.append(f"Beta de la acción {raw:.2f} (≤ 0): no es confiable; se usó 1,0 (el promedio del mercado).")
            raw = 1.0
        elif raw > BETA_MAX:
            warns.append(f"Beta {raw:.2f} muy alta: se acotó a {BETA_MAX:.1f}.")
            raw = BETA_MAX
        beta = raw
        beta_adj = clamp(0.67 * raw + 0.33, BETA_MIN, BETA_MAX)   # ajuste de Blume (solo si no hay datos de industria)
        if beta_adj > 0.67 * raw + 0.33:
            warns.append(f"Beta ajustada por debajo de {BETA_MIN:.1f}: se llevó al piso de {BETA_MIN:.1f}.")
    if p.ke_override is not None:
        ke = p.ke_override
    else:
        ke = rf + beta_adj * p.erp + p.crp
    return {"ke": ke, "rf": rf, "beta": beta, "beta_adj": beta_adj}


# Spread por calificación sintética según cobertura de intereses (EBIT / intereses), Damodaran enero 2026.
# Cada fila: (cobertura mínima, spread). Empresas grandes (cap. >= 5.000 M) y chicas/riesgosas.
_SPREAD_LARGE = [(-1e9, .19), (0.2, .16), (0.65, .1261), (0.8, .0885), (1.25, .0509), (1.5, .0321), (1.75, .0275),
                 (2.0, .0184), (2.25, .0138), (2.5, .0111), (3.0, .0089), (4.25, .0078), (5.5, .0070), (6.5, .0055), (8.5, .0040)]
_SPREAD_SMALL = [(-1e9, .19), (0.5, .16), (0.8, .1261), (1.25, .0885), (1.5, .0509), (2.0, .0321), (2.5, .0275),
                 (3.0, .0184), (3.5, .0138), (4.0, .0111), (4.5, .0089), (6.0, .0078), (7.5, .0070), (9.5, .0055), (12.5, .0040)]


_BBB_SPREAD = 0.0111
_STABLE_IND = ("Utility (General)", "Utility (Water)", "Power", "R.E.I.T.", "Retail (REITs)")


def _stable_credit(co: "CompanyData") -> bool:
    """Utilities y REITs: flujos previsibles, consiguen deuda barata aunque la cobertura sea baja."""
    ind = (co.industry or "").lower()
    return co.ind_name in _STABLE_IND or ind.startswith("utilities") or ind.startswith("reit")


def synthetic_spread(coverage: float, large: bool) -> float:
    table = _SPREAD_LARGE if large else _SPREAD_SMALL
    sp = table[0][1]
    for lo, v in table:
        if coverage > lo:
            sp = v
    return sp


def cost_of_capital(co: CompanyData, p: Params, scen: Scen, warns: List[str]) -> Dict[str, float]:
    c = cost_of_equity(co, p, scen, warns)
    rf, ke = c["rf"], c["ke"]
    debt = co.debt if _leases_included(co, p) else max(0.0, co.debt - co.lease_debt)
    if co.ebit_ttm > 0 and co.interest_expense_ttm and co.interest_expense_ttm > 0:
        cov = co.ebit_ttm / co.interest_expense_ttm
        sp = synthetic_spread(cov, co.market_cap_m >= 5000)
        note = f"calificación sintética: cobertura {cov:.1f}x"
        if _stable_credit(co) and sp > _BBB_SPREAD:
            sp, note = _BBB_SPREAD, note + " (tope BBB: utilities/REITs tienen flujos estables)"
        kd = rf + sp + p.crp / 1.5                     # + riesgo país (en deuda ~ CRP/1,5)
        c["kd_note"] = note
    else:
        kd = rf + 0.015
        c["kd_note"] = "sin datos de cobertura: tasa libre de riesgo + 1,5 %"
    E = max(co.market_cap_m, 1e-9)
    D = max(debt, 0.0)
    we, wd = E / (E + D), D / (E + D)
    wacc = we * ke + wd * kd * (1 - p.marginal_tax)
    if p.wacc_override is not None:
        wacc = p.wacc_override
    wacc += p.wacc_shift
    c.update(kd=kd, we=we, wd=wd, wacc=wacc)
    return c


def terminal_beta(co: CompanyData, p: Params) -> Optional[float]:
    """Beta con la que se arma el WACC terminal (v2.35, estructura de deuda de la industria, como Damodaran en crecimiento estable).
    Con datos de industria y sin beta manual: promedio 50/50 entre (a) la beta de los primeros años (promedio empresa/industria, con piso
    y tope), desapalancada con la deuda de la empresa y re-apalancada con el D/E típico de la industria, y (b) 1,0 (el mercado).
    Equivale a 25 % beta propia, 25 % industria y 50 % mercado. Con beta manual, con la opción de industria apagada o sin datos
    de industria: la beta de la industria sola, re-apalancada con su D/E (comportamiento de la v2.33)."""
    if co.ind_ubeta is None or co.ind_de is None:
        return None
    tm = p.marginal_tax
    de_ind = max(co.ind_de, 0.0)
    b_ind = co.ind_ubeta * (1 + (1 - tm) * de_ind)
    if p.beta is not None or not p.use_industry_beta or co.ind_beta_lev is not None:
        return b_ind
    bu = _bottom_up_beta(co, p)
    if bu is None:
        return b_ind
    own = co.beta
    b_expl = clamp((own + bu) / 2 if (own is not None and own > 0) else bu, BETA_MIN, BETA_MAX)
    debt = co.debt if _leases_included(co, p) else max(0.0, co.debt - co.lease_debt)
    de_emp = max(debt, 0.0) / max(co.market_cap_m, 1e-9)
    b_rel = b_expl / (1 + (1 - tm) * de_emp) * (1 + (1 - tm) * de_ind)      # misma beta del negocio, deuda de la industria
    return clamp((b_rel + 1.0) / 2, BETA_MIN, BETA_MAX)


def sector_wacc(co: CompanyData, p: Params) -> Optional[float]:
    """WACC terminal (v2.35): Ke con la beta terminal (ver terminal_beta), deuda a Rf + spread BBB (así lo arma Damodaran) y los
    pesos de capital del D/E típico de la industria; mismas tasas que la empresa (Rf, prima de mercado, prima país).
    La empresa converge hacia este valor en la segunda parte del horizonte."""
    bT = terminal_beta(co, p)
    if bT is None:
        return None
    rf = p.rf if p.rf is not None else co.rf
    tm = p.marginal_tax
    de = max(co.ind_de, 0.0)
    ke = rf + bT * p.erp + p.crp
    kd = rf + _BBB_SPREAD + p.crp / 1.5
    we = 1.0 / (1.0 + de)
    return we * ke + (1 - we) * kd * (1 - tm) + p.wacc_shift


def _leases_included(co: CompanyData, p: Params) -> bool:
    if p.include_leases is not None:
        return p.include_leases
    return (co.country or "").strip().lower() not in ("united states", "usa", "us")


# ----------------------------------------------------------------------------
# Insumos comunes
# ----------------------------------------------------------------------------
def _hist_growth(rev_hist: List[Optional[float]]) -> Optional[float]:
    v = [x for x in rev_hist if x is not None and x > 0]
    if len(v) < 2:
        return None
    yoy = [v[i] / v[i - 1] - 1 for i in range(1, len(v))]
    return statistics.median(yoy)


def _range_weight() -> float:
    return 0.85          # los extremos de analistas son opiniones sueltas: se usa el 85 % de la distancia al promedio


def growth_anchors(co: CompanyData, p: Params, scen: Scen, cap_hi: float = 0.25,
                   use_range: bool = True) -> Tuple[float, float, str]:
    adj = scen.g_adj
    if p.growth_override is not None:
        g1, g2 = p.growth_override
        src = "manual"
    elif co.rev_g_y0 is not None or co.rev_g_y1 is not None:
        a = co.rev_g_y0 if co.rev_g_y0 is not None else co.rev_g_y1
        b = co.rev_g_y1 if co.rev_g_y1 is not None else co.rev_g_y0
        g1, g2 = (a + b) / 2.0, b
        g1, g2 = clamp(g1, -0.05, cap_hi), clamp(g2, -0.05, cap_hi)
        src = "analistas"
        ext = None
        if use_range and scen.m_rule in ("pess", "opt"):
            lo = scen.m_rule == "pess"
            ea = (co.rev_gl_y0 if lo else co.rev_gh_y0)
            eb = (co.rev_gl_y1 if lo else co.rev_gh_y1)
            ea = ea if ea is not None else eb
            eb = eb if eb is not None else ea
            if ea is not None:
                e1, e2 = clamp((ea + eb) / 2.0, -0.10, cap_hi + 0.05), clamp(eb, -0.10, cap_hi + 0.05)
                sgn = -1.0 if lo else 1.0
                # distancia al caso base: entre 1,5 y 6 puntos, en el sentido del escenario
                d1 = clamp(sgn * (e1 - g1) * _range_weight(), 0.015, 0.06)
                d2 = clamp(sgn * (e2 - g2) * _range_weight(), 0.015, 0.06)
                ext = (sgn * d1, sgn * d2)
        if ext is not None:
            g1, g2, adj, src = g1 + ext[0], g2 + ext[1], 0.0, "analistas (rango mín-máx real)"
    else:
        h = _hist_growth(co.revenue_hist)
        if h is None:
            h, src = 0.03, "supuesto (sin datos)"
        else:
            src = "histórico (mediana)"
        g1 = g2 = clamp(h, -0.05, 0.12)
    return g1 + adj, g2 + adj, src


def analyst_margin(co: CompanyData, m0: float) -> Optional[float]:
    """Margen EBIT objetivo según analistas: el margen TTM movido por (crecimiento del BPA / crecimiento de ingresos)
    esperado en los 2 próximos años. Acotado a -15 % / +30 % del margen actual (el BPA también refleja recompras)."""
    if m0 <= 0:
        return None
    eg = [x for x in (co.eps_g_y0, co.eps_g_y1) if x is not None]
    rg = [x for x in (co.rev_g_y0, co.rev_g_y1) if x is not None]
    if len(eg) < 2 or len(rg) < 2:
        return None
    ratio = (1 + eg[0]) * (1 + eg[1]) / ((1 + rg[0]) * (1 + rg[1]))
    return m0 * clamp(ratio, 0.85, 1.30)


def margin_options(co: CompanyData) -> Dict[str, Optional[float]]:
    """Margen EBIT objetivo bajo cada criterio (para mostrar lado a lado)."""
    if co.revenue_ttm <= 0:
        return {}
    m0 = co.ebit_ttm / co.revenue_ttm
    hist = [e / r for r, e in list(zip(co.revenue_hist, co.ebit_hist))[-4:] if r and e is not None and r > 0]
    return {"ttm": m0, "median": _med(hist + [m0]) if hist else m0, "analysts": analyst_margin(co, m0)}


MARGIN_SPREAD = 0.15   # escenarios pesimista/optimista: margen objetivo ∓15 % (relativo; antes ∓2 pp absolutos)


def ttm_distorted(co: CompanyData, m0: float, mt_base: float) -> bool:
    """El margen del TTM está 8 pp o más por debajo del margen objetivo y los ingresos no caen (más de 3 %):
    probablemente un cargo extraordinario de un año y no un deterioro del negocio."""
    if m0 is None or m0 <= 0 or mt_base - m0 < 0.08:
        return False
    prev = next((r for r in reversed(co.revenue_hist) if r), None)
    return prev is None or co.revenue_ttm >= 0.97 * prev


def clean_margin_trend(hist: List[float], m0: float, min_points: int = 4) -> Optional[str]:
    """«sube» / «baja» si el margen operativo se movió en la misma dirección en TODOS los pasos (últimos años + TTM); si no, None.
    Exige al menos `min_points` años de historia: un año raro (cargo único, pico) rompe la serie y la regla no se activa."""
    seq = [h for h in hist if h is not None] + [m0]
    if len(hist) < min_points or len(seq) < min_points + 1:
        return None
    steps = [seq[i] - seq[i - 1] for i in range(1, len(seq))]
    if all(d > 0 for d in steps):
        return "sube"
    if all(d < 0 for d in steps):
        return "baja"
    return None


def _is_price_taker(co: "CompanyData") -> bool:
    """Industrias de precio-aceptante (materias primas, ciclo fuerte): el último margen puede ser un pico o un piso del ciclo."""
    return (co.ind_name or "") in PRICE_TAKER_INDUSTRIES


def margin_target(co: CompanyData, p: Params, scen: Scen) -> Tuple[float, float, str]:
    """(margen inicial TTM, margen objetivo del escenario, descripción)."""
    if co.revenue_ttm <= 0:
        raise ModelError("Ingresos TTM no disponibles o no positivos.")
    m0 = co.ebit_ttm / co.revenue_ttm
    hist = []
    for r, e in list(zip(co.revenue_hist, co.ebit_hist))[-4:]:
        if r and e is not None and r > 0:
            hist.append(e / r)
    if p.margin_mode == "manual" and p.margin_manual is not None:
        mt, desc = p.margin_manual, "manual"
    elif m0 <= 0:
        # Empresa con pérdida operativa. Damodaran (cap. 5 y 8): la empresa joven converge al margen de su industria;
        # la que ya fue rentable se recupera hacia SU propio nivel de años buenos (ej.: Las Vegas Sands vuelve al 17 % de 2006).
        pos = [h for h in hist if h > 0]
        if len(pos) >= 2:
            own = _med(pos)
            if co.ind_margin is not None and co.ind_margin > 0:
                own = min(own, 1.5 * co.ind_margin)          # tope: no volver a un pico irrepetible
            mt, desc = own, (f"mediana de los {len(pos)} años rentables de la propia empresa (recuperación a su nivel histórico, "
                             "con tope de 1,5× el margen de su industria)")
        elif co.ind_margin is not None and co.ind_margin > 0:
            mt, desc = co.ind_margin, f"promedio de la industria {co.ind_name} (la empresa tiene pérdida operativa)"
        else:
            raise ModelError("EBIT TTM ≤ 0 y no hay datos de industria para estimar un margen objetivo. "
                             "Elegí la industria en Ajustes avanzados o cargá un margen objetivo manual.")
    elif p.margin_mode == "ttm":
        mt, desc = m0, "TTM"
    elif p.margin_mode == "analysts" and analyst_margin(co, m0) is not None:
        mt, desc = analyst_margin(co, m0), "TTM ajustado por la expansión de margen que esperan los analistas"
    else:
        mt = _med(hist + [m0]) if hist else m0
        desc = f"mediana {len(hist)} años + TTM" if hist else "TTM (sin historia)"
        trend = clean_margin_trend(hist, m0)
        if trend and not _is_price_taker(co):
            # v2.46 «B suave»: si el margen subió (o bajó) los 4 años seguidos, la mediana queda 2 años atrás de la realidad.
            # Se usa el punto medio entre la mediana y el margen de hoy: corrige a medias y no apuesta a que el último año es el normal.
            mt = (mt + m0) / 2.0
            desc = (f"punto medio entre la mediana y el TTM (el margen {'subió' if trend == 'sube' else 'bajó'} "
                    f"los {len(hist)} años seguidos)")
    if scen.m_rule == "pess":
        if m0 > 0 and ttm_distorted(co, m0, mt):
            # El TTM parece un año extraordinario: el piso pesimista no se ancla a él.
            mt = mt * (1 - MARGIN_SPREAD)
            desc += " · TTM probablemente distorsionado: el pesimista no se ancla a él"
        else:
            mt = min(mt * (1 - MARGIN_SPREAD), m0 if m0 > 0 else mt)
    elif scen.m_rule == "opt":
        mt = max(mt * (1 + MARGIN_SPREAD), m0)
    return m0, mt, desc


# ----------------------------------------------------------------------------
# Foso (moat) automático
# ----------------------------------------------------------------------------
GRAY_ZONE = 0.01   # tolerancia del criterio 1: hasta 1 pp por debajo del umbral, con los otros dos criterios cumplidos, cuenta como Estrecho

PRICE_TAKER_INDUSTRIES = {   # el libro: las de materias primas son precio-aceptantes y hasta las mejores sufren el ciclo bajista
    "Oil/Gas (Integrated)", "Oil/Gas (Production and Exploration)", "Oilfield Svcs/Equip.", "Oil/Gas Distribution",
    "Coal & Related Energy", "Metals & Mining", "Precious Metals", "Steel", "Farming/Agriculture", "Paper/Forest Products",
    "Chemical (Basic)", "Air Transport"}


def _moat_threshold(co: CompanyData, w_ref: float) -> Tuple[float, str]:
    """Umbral del criterio 1 (exceso de retorno): WACC del sector + 5 pp; en sectores de retorno típico bajo, el ROC del sector
    (con piso WACC + 2 pp)."""
    thr, how = w_ref + 0.05, "WACC del sector + 5 pp"
    if co.ind_roc is not None:
        soft = max(co.ind_roc, w_ref + 0.02)
        if soft < thr:
            thr, how = soft, "sector de retorno bajo: el ROC del sector, con piso WACC + 2 pp"
    return thr, how


def moat_partial_premium(co: CompanyData, wacc_ref: float, roic_now: Optional[float]) -> Tuple[float, str]:
    """Premio parcial (v2.36, solo cálculo interno; la clasificación que se muestra sigue siendo Amplio / Estrecho / Ninguno).
    Una empresa «Ninguno» que rinde por encima del WACC del sector pero no llega al umbral del criterio 1 no pasa de golpe de
    ventaja cero a ventaja de foso Estrecho: recibe la fracción (ROIC − WACC) / (umbral − WACC) del retorno extra de un Estrecho.
    Devuelve (fracción entre 0 y 1, texto explicativo); (0, "") si no corresponde."""
    if roic_now is None or roic_now <= wacc_ref:
        return 0.0, ""
    thr, _ = _moat_threshold(co, wacc_ref)
    if roic_now >= thr or thr <= wacc_ref:
        return 0.0, ""
    f = clamp((roic_now - wacc_ref) / (thr - wacc_ref), 0.0, 1.0)
    return f, (f"Premio parcial (cálculo interno): el ROIC {roic_now:.1%} está {100 * (roic_now - wacc_ref):.1f} pp sobre el WACC del sector "
               f"pero {100 * (thr - roic_now):.1f} pp bajo el umbral ({thr:.1%}); en el valor terminal recibe el {f:.0%} del retorno extra de un foso "
               "Estrecho. La clasificación sigue siendo Ninguno.")


def classify_moat(co: CompanyData, wacc: float, roic_now: Optional[float], loss: bool,
                  wacc_ref: Optional[float] = None) -> Tuple[str, List[str]]:
    """Estimación propia del foso. Para Damodaran (cap. 3) una ventaja competitiva es un retorno sobre el capital que se
    mantiene por encima del costo del capital: por eso sin exceso de retorno NO hay foso, y los otros dos criterios
    solo distinguen entre foso Estrecho y Amplio.
      1. Exceso de retorno (obligatorio): ROIC ≥ WACC del sector + 5 pp. En sectores de retorno típico bajo (ej.: utilities) el
         umbral es el menor entre ese y el ROC del sector (con piso WACC + 2 pp), para no exigir lo que el sector nunca da.
      2. Persistencia: los últimos tres márgenes EBIT (2 años + TTM) siguen en al menos 80 % de la mediana propia.
         Un TTM que parece un año extraordinario no cuenta.
      3. Mejor que sus pares: margen mediano ≥ margen del sector, o ROIC ≥ ROC del sector
         (sin datos del sector: ROIC ≥ WACC + 10 pp).
    Amplio = los tres · Estrecho = solo el 1 (o el 1 y uno de los otros) · Ninguno = no cumple el 1.
    Zona gris: ROIC hasta 1 pp bajo el umbral del criterio 1 pero con los criterios 2 y 3 cumplidos = Estrecho."""
    if loss:
        return "Ninguno", ["Pérdida operativa: los números no muestran ventaja competitiva."]
    reasons: List[str] = []
    hits = {1: False, 2: False, 3: False}
    gray = False
    w_ref = wacc_ref if wacc_ref is not None else wacc
    if roic_now is None:
        reasons.append("1) Exceso de retorno: sin capital invertido utilizable, no se evalúa.")
    else:
        thr, how = _moat_threshold(co, w_ref)
        hits[1] = roic_now >= thr
        gray = (not hits[1]) and roic_now >= thr - GRAY_ZONE
        reasons.append(f"1) ROIC {roic_now:.1%} {'≥' if hits[1] else '<'} {thr:.1%} ({how}): {'sí' if hits[1] else ('casi (zona gris, hasta 1 pp por debajo)' if gray else 'no')}.")
    ms = [e / r for r, e in list(zip(co.revenue_hist, co.ebit_hist))[-4:] if r and e is not None and r > 0]
    ttm_ignored = False
    if co.revenue_ttm > 0:
        m_ttm = co.ebit_ttm / co.revenue_ttm
        if ms and ttm_distorted(co, m_ttm, _med(ms + [m_ttm])):
            ttm_ignored = True            # año extraordinario: no cuenta para juzgar el foso
        else:
            ms.append(m_ttm)
    med = _med(ms) if ms else None
    if len(ms) >= 3 and med is not None and med > 0:
        recent = min(ms[-3:])
        hits[2] = recent >= 0.8 * med
        reasons.append(f"2) Persistencia: el menor de los últimos tres márgenes ({recent:.1%}) {'≥' if hits[2] else '<'} 80 % de la "
                       f"mediana propia ({0.8 * med:.1%}): {'sí' if hits[2] else 'no'}.")
        if ttm_ignored:
            reasons.append("(El margen del TTM parece un año extraordinario y no se usa para juzgar el foso.)")
    else:
        reasons.append("2) Persistencia del margen: faltan años de historia o el margen no es positivo, no se evalúa.")
    if co.ind_roc is not None and co.ind_margin is not None and med is not None and roic_now is not None:
        by_margin, by_roic = med >= co.ind_margin, roic_now >= co.ind_roc
        hits[3] = by_margin or by_roic
        reasons.append(f"3) Frente a su sector: margen {med:.1%} vs {co.ind_margin:.1%} ({'mejor' if by_margin else 'peor'}) · "
                       f"ROIC {roic_now:.1%} vs ROC {co.ind_roc:.1%} ({'mejor' if by_roic else 'peor'}): {'sí' if hits[3] else 'no'}.")
    elif roic_now is not None:
        hits[3] = roic_now >= w_ref + 0.10
        reasons.append(f"3) Sin datos del sector: ROIC {roic_now:.1%} {'≥' if hits[3] else '<'} WACC + 10 pp ({w_ref + 0.10:.1%}): "
                       f"{'sí' if hits[3] else 'no'}.")
    else:
        reasons.append("3) Frente a su sector: no se evalúa.")
    label = "Ninguno" if not hits[1] else ("Amplio" if (hits[2] and hits[3]) else "Estrecho")
    if gray and hits[2] and hits[3]:
        label = "Estrecho"
        reasons.append("Zona gris: el ROIC quedó a menos de 1 pp del umbral y cumple persistencia y comparación con sus pares, así que se "
                       "clasifica Estrecho (nunca Amplio) en lugar de dejarlo sin foso por una diferencia mínima.")
    if label == "Amplio" and co.ind_name in PRICE_TAKER_INDUSTRIES:
        label = "Estrecho"
        reasons.append("Tope: productor de materias primas (o aerolínea), precio-aceptante: su retorno depende del ciclo del precio y no de una "
                       "ventaja propia, así que el foso se limita a Estrecho (Damodaran, cap. 10).")
    return label, reasons


def _terminal_roic(co: CompanyData, spread: float, wacc: float, roic0: float, spread_delta: float,
                   roic_cap: float) -> Tuple[float, str]:
    """ROIC al que converge el negocio en el terminal.
    Sin dato de industria: WACC + spread del moat (Ninguno 0 / Estrecho 2 pp / Amplio 5 pp).
    Con dato de industria (criterio Damodaran: una ventaja sostenida mantiene el ROC del sector):
      Ninguno  = WACC
      Estrecho = punto medio entre WACC y el ROC del sector (mínimo WACC + 2 pp)
      Amplio   = ROC del sector (mínimo WACC + 3 pp, para que siga por encima de Estrecho en sectores de retorno bajo)
    Nunca por encima del ROIC actual de la empresa (salvo que el mínimo lo exija) ni del tope.
    Escenarios: -2 pp / +2 pp en el spread."""
    roc = co.ind_roc
    note = ""
    if roc is not None and spread > 0:
        roc = clamp(roc, wacc, roic_cap)
        if spread >= 0.05:
            floor = wacc + 0.03
            tgt = max(floor, roc)
        else:
            floor = wacc + spread
            tgt = max(floor, wacc + 0.5 * (roc - wacc))
        tgt = min(tgt, max(roic0, floor))
        note = f"anclado al ROC del sector ({co.ind_roc:.1%})"
    else:
        tgt = wacc + spread
    roicT = max(wacc, tgt + spread_delta)
    return roicT, note


def _guard_g(g: float, r: float, warns: List[str], label: str = "tasa", gap: float = 0.01) -> float:
    """Mantiene una distancia mínima entre la tasa de descuento y g: con menos de ~2,5 pp el valor terminal
    se vuelve explosivo (EV/NOPAT > 35x) y deja de ser informativo."""
    if r - g < gap:
        warns.append(f"g terminal ({g:.2%}) quedó a menos de {gap * 100:.1f} pp de la {label} ({r:.2%}); se ajustó.")
        return r - gap
    return g


# ----------------------------------------------------------------------------
# Modelo 1: FCFF
# ----------------------------------------------------------------------------
def terminal_growth_default(rf: float) -> float:
    """g terminal automático: tasa libre de riesgo − 1 punto, entre 3,0 % y 3,5 %.
    El techo (3,5 %) queda por debajo del crecimiento nominal de la economía (~3,8–4,1 %: PIB real 1,8 % del CBO más inflación 2,0–2,3 %),
    porque una empresa sola no crece para siempre como toda la economía. El piso (3,0 %) es el valor que usa Dorsey."""
    return clamp(rf - 0.01, 0.03, 0.035)


# ----------------------------------------------------------------------------
# Riesgo de quiebra (Damodaran, cap. 8: valor como negocio en marcha × (1 − probabilidad de quiebra))
# ----------------------------------------------------------------------------
# Spread de la tabla sintética -> calificación; probabilidad acumulada de quiebra a 10 años por calificación (libro, tabla 8.2).
_RATING_BY_SPREAD = [(.0040, "AAA"), (.0055, "AA"), (.0070, "A+"), (.0078, "A"), (.0089, "A-"), (.0111, "BBB"), (.0138, "BB+"),
                     (.0184, "BB"), (.0275, "B+"), (.0321, "B"), (.0509, "B-"), (.0885, "CCC"), (.1261, "CC"), (.16, "C"), (.19, "D")]
_DEFAULT_10Y = {"AAA": .0007, "AA": .0051, "A+": .0057, "A": .0066, "A-": .05, "BBB": .0754, "BB+": .136, "BB": .1963,
                "B+": .2825, "B": .368, "B-": .4212, "CCC": .5902, "CC": .666, "C": .8103, "D": .8716}
_INVESTMENT_GRADE_OR_BBB = ("AAA", "AA", "A+", "A", "A-", "BBB")


def default_risk(co: CompanyData, mt_base: float) -> Optional[Tuple[float, str, float]]:
    """(probabilidad de quiebra a 10 años, calificación sintética, cobertura) o None si no se puede estimar.
    Cobertura = EBIT / intereses; si la empresa pierde plata se usa el EBIT normalizado (ingresos × margen objetivo)."""
    if not co.interest_expense_ttm or co.interest_expense_ttm <= 0:
        return None
    ebit = co.ebit_ttm if co.ebit_ttm > 0 else co.revenue_ttm * mt_base
    cov = ebit / co.interest_expense_ttm
    sp = synthetic_spread(cov, co.market_cap_m >= 5000)
    rating = next((r for v, r in _RATING_BY_SPREAD if sp <= v + 1e-9), "D")
    return _DEFAULT_10Y[rating], rating, cov


# ----------------------------------------------------------------------------
# Etapa del ciclo de vida (Damodaran, tabla 12.1): qué factores mirar primero
# ----------------------------------------------------------------------------
CYCLICAL_INDUSTRIES = {   # cíclicas (ligadas a la economía) y de materias primas, según las industrias de Damodaran
    "Auto & Truck", "Auto Parts", "Homebuilding", "Building Materials", "Construction Supplies", "Engineering/Construction",
    "Air Transport", "Shipbuilding & Marine", "Transportation", "Trucking", "Hotel/Gaming", "Recreation", "Furn/Home Furnishings",
    "Real Estate (Development)", "Rubber& Tires", "Machinery", "Steel", "Chemical (Basic)", "Chemical (Diversified)",
    "Paper/Forest Products", "Semiconductor Equip", "Retail (Automotive)",
    "Oil/Gas (Integrated)", "Oil/Gas (Production and Exploration)", "Oilfield Svcs/Equip.", "Oil/Gas Distribution",
    "Coal & Related Energy", "Metals & Mining", "Precious Metals", "Farming/Agriculture", "Green & Renewable Energy"}
LIFECYCLE_FACTORS = {
    "Con pérdidas y creciendo": "Crecimiento de los ingresos · margen objetivo · probabilidad de supervivencia",
    "En crecimiento": "Crecimiento escalable · sostenibilidad de los márgenes",
    "Madura": "Debilidad operativa y financiera · cambio del equipo gestor",
    "En declive o dificultades": "Valor como negocio en marcha · probabilidad y consecuencias de la quiebra",
    "Cíclica o de materias primas": "Beneficios normalizados · precio normalizado de la materia prima · crecimiento a largo plazo",
    "Servicios financieros": "Riesgo de los fondos propios · calidad del crecimiento (ROE) · colchón de capital regulatorio",
    "Inmobiliaria (REIT)": "Flujo recurrente (AFFO) · deuda · calidad del crecimiento",
}


def lifecycle_info(co: CompanyData, model: str, g1: Optional[float]) -> Tuple[str, str]:
    """Etapa aproximada de la empresa y los factores clave que, según Damodaran, más pesan en su valor."""
    if model == "ER":
        lab = "Servicios financieros"
    elif model == "REIT":
        lab = "Inmobiliaria (REIT)"
    else:
        prev = next((r for r in reversed(co.revenue_hist) if r), None)
        hist = [r for r in co.revenue_hist if r]
        yoy = (co.revenue_ttm / prev - 1) if (prev and co.revenue_ttm > 0) else None
        cagr = ((hist[-1] / hist[-3]) ** 0.5 - 1) if (len(hist) >= 3 and hist[-3] > 0) else None
        shrinking = (yoy is not None and yoy <= -0.03) or (cagr is not None and cagr <= -0.02)
        if co.ebit_ttm <= 0 and (g1 or 0) >= 0.10:
            lab = "Con pérdidas y creciendo"
        elif co.ind_name in CYCLICAL_INDUSTRIES:
            lab = "Cíclica o de materias primas"
        elif co.ebit_ttm <= 0 or shrinking:
            lab = "En declive o dificultades"
        elif (g1 or 0) >= 0.12:
            lab = "En crecimiento"
        else:
            lab = "Madura"
    return lab, LIFECYCLE_FACTORS[lab]


# ----------------------------------------------------------------------------
# Zonas de valuación: dónde está el precio respecto de los tres escenarios (reemplaza al margen de seguridad fijo)
# ----------------------------------------------------------------------------
ZONE_NAMES = ["Muy infravalorada", "Infravalorada", "Bien valuada", "Sobrevalorada", "Muy sobrevalorada"]


def price_zones(pes: Optional[float], base: Optional[float], opt: Optional[float], price: float) -> Optional[dict]:
    """Cinco zonas a partir de los escenarios de la propia empresa (no de un porcentaje fijo):
    muy infravalorada = precio < pesimista; infravalorada = pesimista a punto medio(pesimista, base); bien valuada = entre los dos puntos
    medios alrededor del base; sobrevalorada = punto medio(base, optimista) a optimista; muy sobrevalorada = precio > optimista.
    Devuelve {'cuts': [pes, m1, m2, opt], 'zone': 0..4, 'name': str} o None si falta algún escenario."""
    if pes is None or base is None or opt is None or price is None or price != price:
        return None
    a, b, c = sorted((float(pes), float(base), float(opt)))
    m1, m2 = (a + b) / 2, (b + c) / 2
    if price < a:
        z = 0
    elif price < m1:
        z = 1
    elif price < m2:
        z = 2
    elif price <= c:
        z = 3
    else:
        z = 4
    return {"cuts": [a, m1, m2, c], "base": b, "zone": z, "name": ZONE_NAMES[z]}


# ----------------------------------------------------------------------------
# Capitalización del gasto en I+D (Damodaran, cap. 11)
# ----------------------------------------------------------------------------
RD_LIFE = 4        # años de vida amortizable: los que entrega Yahoo (el libro usa 10 en farmacéuticas, pero no hay tanta historia)


def apply_rd(co: CompanyData, p: Params) -> Tuple[CompanyData, Optional[dict]]:
    """Trata el I+D como inversión: se suma al EBIT del año y se resta su amortización lineal; el I+D no amortizado entra
    como activo en el patrimonio y el capital invertido. Devuelve (empresa ajustada, detalle) o (empresa, None) si no aplica."""
    prior = [x for x in reversed(co.rd_hist or []) if x is not None and x >= 0]      # más reciente primero
    if not p.capitalize_rd or co.rd_ttm is None or co.rd_ttm <= 0 or len(prior) < 3 or co.revenue_ttm <= 0:
        return co, None
    prior = prior[:RD_LIFE]
    while len(prior) < RD_LIFE:
        prior.append(prior[-1])                       # año faltante: se repite el más antiguo (supuesto conservador)
    amort = sum(prior) / RD_LIFE
    asset = co.rd_ttm + sum(prior[k - 1] * (1 - k / RD_LIFE) for k in range(1, RD_LIFE))
    net = co.rd_ttm - amort
    shift = net / co.revenue_ttm                      # el mismo ajuste en puntos de margen se aplica a los años anteriores
    ebit_hist = [(e + shift * r) if (e is not None and r) else e for r, e in zip(co.revenue_hist, co.ebit_hist)]
    co2 = replace(co, ebit_ttm=co.ebit_ttm + net, ebit_hist=ebit_hist,
                  equity=(co.equity + asset) if co.equity is not None else None,
                  invested_capital=(co.invested_capital + asset) if co.invested_capital is not None else None)
    return co2, dict(rd=co.rd_ttm, amort=amort, net=net, asset=asset, shift=shift)



CAPTIVE_NC_MIN = 0.25     # cuentas por cobrar de largo plazo / deuda: señal de que la empresa presta plata a sus clientes
CAPTIVE_INT_MAX = 0.50    # deuda que explica el interés pagado / deuda total: si es menos de la mitad, el resto paga interés dentro del EBIT


def apply_captive_finance(co: CompanyData, p: Params):
    """Financiera propia (Ford Credit, GM Financial, Cat Financial...). Los intereses de su deuda ya están descontados dentro del
    resultado operativo (EBIT); si además se resta toda su deuda en el puente al patrimonio, se la castiga dos veces.
    Se detecta con DOS señales a la vez: (1) cuentas por cobrar de largo plazo >= 25 % de la deuda (la empresa financia a sus
    clientes) y (2) el interés pagado, a una tasa normal, explica menos de la mitad de la deuda (el resto no paga interés "abajo
    del EBIT"). Con las dos juntas no hay falsos positivos en 86 empresas probadas; con una sola sí. La deuda propia se estima
    como interés pagado / costo de la deuda y el resto se excluye (de la deuda y del capital invertido).
    Verificado a mano: Ford (estimó 23.400 M, real 21.900 M), GM (excluyó 115.600 M, real 114.000 M), CAT (8.500 M vs 8.650 M).
    Devuelve (empresa ajustada, info) o (empresa, None). La caja no se toca (falta el dato de cuánta es de la financiera)."""
    if not getattr(p, "captive_adj", True):
        return co, None
    if co.receivables_nc is None or co.interest_expense_ttm is None or co.interest_expense_ttm <= 0:
        return co, None
    debt = co.debt if _leases_included(co, p) else max(0.0, co.debt - co.lease_debt)
    if debt <= 0:
        return co, None
    rf = p.rf if p.rf is not None else co.rf
    kd = rf + _BBB_SPREAD + p.crp / 1.5
    implied = co.interest_expense_ttm / kd
    nc_share = co.receivables_nc / debt
    if nc_share < CAPTIVE_NC_MIN or implied > CAPTIVE_INT_MAX * debt:
        return co, None
    excl = debt - implied
    new = replace(co, debt=co.debt - excl, invested_capital=None if co.invested_capital is None else co.invested_capital - excl)
    return new, dict(excl=excl, implied=implied, debt=debt, nc_share=nc_share, int_share=implied / debt)


def fcff_value(co: CompanyData, p: Params, scen: Scen) -> ValResult:
    warns: List[str] = []
    N = int(clamp(p.horizon, 5, 20))
    co, rd_info = apply_rd(co, p)
    co, cf_info = apply_captive_finance(co, p)
    if cf_info:
        warns.append(f"Financiera propia detectada: las cuentas por cobrar de largo plazo son {cf_info['nc_share']:.0%} de la deuda y el interés pagado "
                     f"explica solo {cf_info['int_share']:.0%} de ella. Los intereses de la financiera ya están dentro del resultado operativo, así que "
                     f"no se restan: de {cf_info['debt']:,.0f} M de deuda se excluyen {cf_info['excl']:,.0f} M (queda la deuda propia estimada, "
                     f"{cf_info['implied']:,.0f} M) y el capital invertido baja lo mismo. La caja no se ajusta (falta el dato de cuánta es de la financiera): "
                     "puede estar sobrando. Es una estimación; verificada a mano con Ford, GM y CAT.")
    if rd_info:
        warns.append(f"I+D capitalizado (Damodaran, cap. 11; vida {RD_LIFE} años porque Yahoo no entrega más historia): EBIT + {rd_info['rd']:,.0f} "
                     f"de I+D − {rd_info['amort']:,.0f} de amortización = {rd_info['net']:+,.0f} M; se suman {rd_info['asset']:,.0f} M de activo "
                     "de I+D al capital invertido. El margen y el ROIC se comparan con promedios de industria que pueden no estar ajustados por I+D.")
    loss = co.ebit_ttm <= 0
    if co.shares_m <= 0 or co.price <= 0:
        raise ModelError("Faltan precio o acciones.")

    m0, mT, m_desc = margin_target(co, p, scen)          # puede levantar ModelError (pérdida sin referencia)
    if loss:
        _, m_ref, _ = margin_target(co, p, replace(scen, m_rule="base"))
        warns.append(f"La empresa tiene pérdida operativa (EBIT TTM ≤ 0): el valor supone que el margen llega a "
                     f"{m_ref:.1%} ({m_desc}). Es un escenario, no una estimación: revisalo con cuidado.")

    m_start, ttm_norm = m0, False                        # margen de partida de la proyección
    if not loss:
        _, m_med, _ = margin_target(co, p, replace(scen, m_rule="base"))
        if ttm_distorted(co, m0, m_med):
            # Damodaran: lo extraordinario se normaliza. Se arranca del margen normal (el del caso base, igual en los tres
            # escenarios) y no del TTM deprimido; el objetivo de cada escenario se alcanza igual en `margin_years`.
            m_start, ttm_norm = m_med, True
            warns.append(f"El margen del TTM ({m0:.1%}) está {(m_med - m0) * 100:.0f} pp bajo el objetivo ({m_med:.1%}) y los ingresos no caen: "
                         f"parece un cargo extraordinario de un año. La proyección arranca del margen normal ({m_med:.1%}) y no del TTM, "
                         "y la tasa de impuestos también arranca de la marginal del país. Revisalo.")

    c = cost_of_capital(co, p, scen, warns)
    wacc, ke = c["wacc"], c["ke"]
    if wacc < 0.055:
        warns.append(f"WACC muy bajo ({wacc:.2%}): el valor es hipersensible. Revisá Rf/beta.")
    # El costo del capital converge al del sector (Damodaran). Con WACC manual o sin datos de industria queda constante.
    wacc_T = sector_wacc(co, p) if p.wacc_override is None else None
    if wacc_T is None:
        wacc_T = wacc
    elif abs(wacc_T - wacc) > 0.015:
        warns.append(f"El WACC converge de {wacc:.2%} (empresa) a {wacc_T:.2%} (sector {co.ind_name}).")
    gT = clamp(p.g_terminal, -0.01, 0.045)
    gT = _guard_g(gT, wacc_T, warns, "WACC", gap=0.025)

    g1, g2, g_src = growth_anchors(co, p, scen)
    my = max(1, min(p.margin_years, N))

    tax0 = clamp(co.tax_rate_eff, 0.0, 0.35) if co.tax_rate_eff is not None else p.marginal_tax
    if loss:
        tax0 = p.marginal_tax
    tax_target = p.marginal_tax                          # la tasa efectiva converge a la marginal del país
    nopat_ttm = co.ebit_ttm * (1 - tax0) if not loss else co.revenue_ttm * m_ref * (1 - tax0)   # el que reportó el TTM
    if ttm_norm:
        tax0 = p.marginal_tax                            # la tasa efectiva del TTM también está distorsionada por el cargo
    nopat0 = co.ebit_ttm * (1 - tax0) if not loss else co.revenue_ttm * m_ref * (1 - tax0)
    if ttm_norm:
        nopat0 = co.revenue_ttm * m_start * (1 - tax0)   # NOPAT normalizado de partida
    nonop = co.non_op_assets if p.include_nonop else 0.0
    # Capital invertido OPERATIVO (criterio Damodaran): deuda + patrimonio - caja - inversiones no operativas
    debt_ic = co.debt if _leases_included(co, p) else max(0.0, co.debt - co.lease_debt)
    if co.equity is not None:
        ic = debt_ic + co.equity + co.minority - co.cash - nonop
        if ic <= 0 and nonop > 0:
            ic_gross = debt_ic + co.equity + co.minority - co.cash
            if ic_gross > 0:
                warns.append(f"Las inversiones no operativas ({nonop:,.0f} M) superan al capital invertido; para el ROIC se usó el capital "
                             f"sin restarlas ({ic_gross:,.0f} M). Esas inversiones se suman igual al valor del patrimonio.")
                ic = ic_gross
    elif co.invested_capital:
        ic = co.invested_capital - co.cash - nonop
    else:
        ic = 0.0
    if ic > 0:
        # ROIC inicial NORMALIZADO: con el margen objetivo del caso base (no con el EBIT del TTM, que puede estar deprimido
        # por cargos extraordinarios y contradice la proyección). Es el mismo en los tres escenarios.
        if loss:
            nopat_norm = nopat0
        else:
            _, mT_base, _ = margin_target(co, p, replace(scen, m_rule="base"))
            nopat_norm = co.revenue_ttm * mT_base * (1 - tax0)
        roic0_ttm = clamp(nopat0 / ic, 0.03, p.roic_cap)
        roic0 = clamp(nopat_norm / ic, 0.03, p.roic_cap)
        if abs(roic0 - roic0_ttm) > 0.03:
            warns.append(f"ROIC inicial normalizado con el margen objetivo ({roic0:.1%}) en lugar del margen del TTM ({roic0_ttm:.1%}): "
                         "así la reinversión es coherente con el margen proyectado.")
    else:
        roic0 = p.roic_cap
        warns.append("Sin capital invertido utilizable: ROIC inicial = tope.")
    if not loss and co.capex_ttm is not None:
        fcf_est = nopat_ttm + co.da_ttm - co.capex_ttm - co.nwc_inv_ttm
        if fcf_est < 0:
            warns.append(f"El flujo libre estimado de los últimos 12 meses es negativo ({fcf_est:,.0f} M): "
                         "el valor depende de que la inversión actual rinda más adelante.")

    # Foso: automático (estimación propia con tres criterios) o elegido a mano.
    if p.moat_spread is not None:
        moat_label = next((k for k, v in MOAT_SPREADS.items() if abs(v - p.moat_spread) < 1e-9), "personalizado")
        spread_base, moat_reasons, moat_src = p.moat_spread, ["Spread fijado por parámetro."], "fijado"
    elif p.moat in MOAT_SPREADS:
        moat_label, spread_base = p.moat, MOAT_SPREADS[p.moat]
        moat_reasons, moat_src = ["Elegido por vos."], "elegido"
    else:
        moat_label, moat_reasons = classify_moat(co, wacc, roic0 if ic > 0 else None, loss, wacc_ref=wacc_T)
        spread_base, moat_src = MOAT_SPREADS[moat_label], "automático"
    spread = max(0.0, spread_base + scen.spread_delta)
    roicT, roic_note = _terminal_roic(co, spread_base, wacc_T, roic0, scen.spread_delta, p.roic_cap)
    moat_partial = 0.0
    if moat_src == "automático" and moat_label == "Ninguno" and ic > 0 and not loss:
        moat_partial, _why = moat_partial_premium(co, wacc_T, roic0)
        if moat_partial > 0:
            r_est, _ = _terminal_roic(co, MOAT_SPREADS["Estrecho"], wacc_T, roic0, 0.0, p.roic_cap)
            roicT = max(wacc_T, wacc_T + moat_partial * (r_est - wacc_T) + scen.spread_delta)
            moat_reasons = list(moat_reasons) + [_why]
            if moat_partial >= MOAT_PARTIAL_LABEL_MIN:
                # Solo la etiqueta que se muestra: el cálculo ya usó el premio parcial exacto (no cambia).
                moat_label = "Estrecho"
                moat_reasons.append(f"Se muestra Estrecho porque recibe {moat_partial:.0%} del beneficio de ese foso "
                                    f"(desde {MOAT_PARTIAL_LABEL_MIN:.0%} se muestra la categoría más cercana). El cálculo usa el porcentaje exacto.")

    hold = min(5, N - 1)                                  # como Damodaran: se sostiene hasta el año 5 y recién ahí baja

    def g_path(t: int) -> float:
        if t == 1:
            return g1
        if t == 2:
            return g2
        if t > N:
            return gT
        if t <= hold:
            return g2
        return g2 + (gT - g2) * (t - hold) / max(1, N - hold)

    def wacc_path(t: int) -> float:
        if t <= hold:
            return wacc
        return wacc + (wacc_T - wacc) * min(1.0, (t - hold) / max(1, N - hold))

    rev = co.revenue_ttm
    rows, pv_sum = [], 0.0
    nopat_N = None
    df = 1.0
    for t in range(1, N + 1):
        g = g_path(t)
        rev *= (1 + g)
        m = m_start + (mT - m_start) * min(1.0, t / my)
        tax = tax0 + (tax_target - tax0) * min(1.0, t / 5)
        roic = roic0 + (roicT - roic0) * t / N
        ebit = rev * m
        tax = tax if ebit > 0 else 0.0           # sin impuesto mientras hay pérdida (no se modelan quebrantos acumulados)
        nopat = ebit * (1 - tax)
        rr = clamp(g_path(t + 1) / roic, -0.3, 1.5)   # la reinversión de hoy financia el crecimiento de mañana
        fcff = nopat * (1 - rr)
        wt = wacc_path(t)
        df *= (1 + wt)
        pv = fcff / df
        pv_sum += pv
        rows.append(dict(Año=t, Crecimiento=g, Ingresos=rev, Margen=m, EBIT=ebit, Impuesto=tax,
                         NOPAT=nopat, Reinversión=rr, ROIC=roic, WACC=wt, FCFF=fcff, VP=pv))
        nopat_N = nopat
        ebit_N = ebit

    nopat_next = nopat_N * (1 + gT)
    tv = nopat_next * (1 - gT / roicT) / (wacc_T - gT)
    pv_tv = tv / df
    ev = pv_sum + pv_tv
    debt_sub = co.debt if _leases_included(co, p) else max(0.0, co.debt - co.lease_debt)
    equity = ev + co.cash + nonop - debt_sub - co.minority
    if nonop > 0.15 * co.market_cap_m:
        warns.append(f"Las inversiones en otras empresas ({nonop:,.0f} M) pesan más del 15 % de la capitalización y se suman a valor contable (puede diferir del de mercado).")
    per_share_raw = equity / co.shares_m
    per_share = max(0.0, per_share_raw)                  # responsabilidad limitada: una acción no vale menos que cero
    per_share_going = per_share
    p_default, rating, cov_def = 0.0, "", None
    if p.survival_adj and not _stable_credit(co):
        _, mt_ref, _ = margin_target(co, p, replace(scen, m_rule="base"))   # misma probabilidad en los tres escenarios
        dr = default_risk(co, mt_ref)
        if dr is not None and dr[1] not in _INVESTMENT_GRADE_OR_BBB:
            p_default, rating, cov_def = dr
            per_share = per_share_going * (1 - p_default)
            warns.append(f"Ajuste por riesgo de quiebra (Damodaran, cap. 8): calificación sintética {rating} (cobertura {cov_def:.1f}×), "
                         f"probabilidad de quiebra a 10 años {p_default:.0%}. Valor como negocio en marcha {per_share_going:,.2f} × (1 − {p_default:.0%}) "
                         f"= {per_share:,.2f}; en una quiebra se supone que el accionista no recibe nada.")
    tv_share = pv_tv / ev if ev > 0 else float("nan")

    exit_mult = tv / ebit_N if ebit_N > 0 else float("nan")
    if tv_share > 0.75:
        warns.append(f"El valor terminal pesa {tv_share:.0%} del EV (>75 %): el resultado depende mucho de g y WACC.")
    if exit_mult > 25:
        warns.append(f"Múltiplo de salida implícito EV/EBIT = {exit_mult:.1f}x (alto).")
    if equity <= 0:
        warns.append(f"Con estos supuestos el valor de la empresa ({ev:,.0f} M) no alcanza a cubrir la deuda y los minoritarios "
                     f"(calculado: {per_share_raw:,.2f} por acción): se muestra 0, porque una acción no puede valer menos que cero.")
    if co.ttm_source and "anual" in co.ttm_source.lower():
        warns.append("Se usó el último año fiscal en lugar de TTM (opción activada).")

    return ValResult(
        model="FCFF", scenario=scen.name, per_share=per_share, equity_value=equity, ev=ev,
        discount_rate=wacc, ke=ke, g_terminal=gT, tv_share=tv_share, table=rows, warnings=warns,
        extras=dict(wacc=wacc, wacc_T=wacc_T, ke=ke, kd=c["kd"], kd_note=c.get("kd_note", ""), we=c["we"], wd=c["wd"],
                    beta=c["beta"], rf=c["rf"], beta_T=terminal_beta(co, p),
                    g1=g1, g2=g2, g_src=g_src, margin0=m0, margin_start=m_start, ttm_normalized=ttm_norm, margin_target=mT, margin_rule=m_desc, roic0=roic0, roicT=roicT,
                    moat_label=moat_label, moat_reasons=moat_reasons, moat_src=moat_src, moat_partial=moat_partial,
                    captive_excl=(cf_info or {}).get('excl', 0.0),
                    exit_ev_ebit=exit_mult, tv_nopat=tv / nopat_N if nopat_N else float('nan'), roic_note=roic_note,
                    nopat0=nopat0, tv=tv, pv_explicit=pv_sum, pv_tv=pv_tv,
                    cash=co.cash, nonop=nonop, ic_op=ic, debt=debt_sub, minority=co.minority, spread=spread,
                    p_default=p_default, rating=rating, per_share_going=per_share_going,
                    rd_net=(rd_info or {}).get('net'), rd_asset=(rd_info or {}).get('asset')),
    )


# ----------------------------------------------------------------------------
# Modelo 2: retorno excedente (bancos, aseguradoras, mREITs, brokers)
# ----------------------------------------------------------------------------
def excess_return_value(co: CompanyData, p: Params, scen: Scen) -> ValResult:
    warns: List[str] = []
    N = int(clamp(p.horizon, 5, 20))
    if co.equity is None or co.equity <= 0:
        raise ModelError("Patrimonio (book value) no disponible o ≤ 0.")
    if co.ni_ttm is None:
        raise ModelError("Resultado neto TTM no disponible.")
    if co.shares_m <= 0 or co.price <= 0:
        raise ModelError("Faltan precio o acciones.")

    c = cost_of_equity(co, p, scen, warns)
    ke = c["ke"]
    gT = clamp(p.g_terminal, -0.01, 0.05)
    gT = _guard_g(gT, ke, warns, "Ke")

    bv0 = co.equity
    roe_ttm = co.ni_ttm / bv0
    roe_h = []
    for ni, eq in list(zip(co.ni_hist, co.equity_hist))[-4:]:
        if ni is not None and eq and eq > 0:
            roe_h.append(ni / eq)
    roe_med = _med(roe_h)
    roe_norm = 0.5 * roe_ttm + 0.5 * roe_med if roe_med is not None else roe_ttm
    roe_norm = clamp(roe_norm, 0.0, 0.30) * scen.roe_scale
    if roe_ttm < 0:
        warns.append("ROE TTM negativo: se usó ROE normalizado ≥ 0.")
    pers = scen.persistence if scen.persistence is not None else p.persistence
    roe_T = ke + pers * (roe_norm - ke)
    roe_T = max(roe_T, gT + 0.005)

    total_payout_hist = None
    if co.ni_ttm and co.ni_ttm > 0:
        total_payout_hist = (co.dividends_ttm + co.buybacks_ttm) / co.ni_ttm
    payout0 = clamp(total_payout_hist if total_payout_hist is not None else 0.5, 0.2, 1.0)
    payoutT = clamp(1 - gT / roe_T, 0.0, 1.0)

    bv = bv0
    rows, pv_sum = [], 0.0
    for t in range(1, N + 1):
        roe_t = roe_norm + (roe_T - roe_norm) * t / N
        payout_t = payout0 + (payoutT - payout0) * t / N
        ni = roe_t * bv
        ri = (roe_t - ke) * bv
        pv = ri / (1 + ke) ** t
        pv_sum += pv
        bv_next = bv + ni * (1 - payout_t)
        rows.append(dict(Año=t, ROE=roe_t, Payout=payout_t, Patrimonio_ini=bv, Resultado=ni,
                         Retorno_excedente=ri, VP=pv, Patrimonio_fin=bv_next))
        bv = bv_next
    ri_next = (roe_T - ke) * bv
    tv = ri_next / (ke - gT)
    pv_tv = tv / (1 + ke) ** N
    equity = bv0 + pv_sum + pv_tv
    per_share_raw = equity / co.shares_m
    per_share = max(0.0, per_share_raw)
    created = pv_sum + pv_tv
    tv_share = pv_tv / equity if equity > 0 else float("nan")

    if equity <= 0:
        warns.append(f"Valor del patrimonio ≤ 0 en este escenario (calculado: {per_share_raw:,.2f} por acción): se muestra 0, "
                     "porque una acción no puede valer menos que cero.")
    if roe_norm < ke:
        warns.append(f"ROE normalizado ({roe_norm:.1%}) < Ke ({ke:.1%}): el mercado debería pagar menos que el book value.")
    if abs(created) > 1.5 * bv0:
        warns.append("El valor creado/destruido supera 1,5x el book value: revisá ROE y Ke.")

    return ValResult(
        model="Retorno excedente", scenario=scen.name, per_share=per_share, equity_value=equity,
        ev=None, discount_rate=ke, ke=ke, g_terminal=gT, tv_share=tv_share, table=rows, warnings=warns,
        extras=dict(ke=ke, beta=c["beta"], rf=c["rf"], bv0=bv0, bv_ps=bv0 / co.shares_m,
                    roe_ttm=roe_ttm, roe_med=roe_med if roe_med is not None else float("nan"),
                    roe_norm=roe_norm, roe_T=roe_T, payout0=payout0, payoutT=payoutT,
                    pb_implied=equity / bv0, pe_implied=equity / co.ni_ttm if co.ni_ttm > 0 else float("nan"),
                    pb_current=co.market_cap_m / bv0, persistence=pers, pv_explicit=pv_sum, pv_tv=pv_tv),
    )


# ----------------------------------------------------------------------------
# Modelo 3: REIT por AFFO
# ----------------------------------------------------------------------------
def reit_value(co: CompanyData, p: Params, scen: Scen) -> ValResult:
    warns: List[str] = []
    N = int(clamp(p.horizon, 5, 20))
    if co.shares_m <= 0 or co.price <= 0:
        raise ModelError("Faltan precio o acciones.")
    c = cost_of_equity(co, p, scen, warns)
    ke = c["ke"]
    gT = clamp(p.g_terminal, -0.01, 0.04)
    gT = _guard_g(gT, ke, warns, "Ke")

    if p.affo_ps_override is not None:
        affo0 = p.affo_ps_override * co.shares_m
        affo_src = "AFFO/acción ingresado a mano"
        ffo = affo0 / p.affo_ratio if p.affo_ratio else affo0
    else:
        if co.ni_ttm is None:
            raise ModelError("Resultado neto TTM no disponible.")
        ffo = co.ni_ttm + co.da_ttm + co.gains_adj_ttm
        affo0 = ffo * p.affo_ratio
        affo_src = f"FFO estimado × {p.affo_ratio:.0%} (supuesto de ajuste a AFFO)"
        warns.append("AFFO estimado (Yahoo no lo informa): para mayor precisión ingresá el AFFO/acción "
                     "que reporta la compañía.")
    if affo0 <= 0:
        raise ModelError("AFFO/FFO ≤ 0: el modelo no aplica.")

    g1, g2, g_src = growth_anchors(co, p, replace(scen, g_adj=0.5 * scen.g_adj), cap_hi=0.06, use_range=False)
    g0 = clamp(g1, -0.02, 0.06 + abs(0.5 * scen.g_adj))
    roi = ke + (scen.roi_spread if scen.roi_spread is not None else p.roi_spread)

    def g_path(t: int) -> float:
        if t > N:
            return gT
        hold = min(5, N - 1)
        return g0 if t <= hold else g0 + (gT - g0) * (t - hold) / max(1, N - hold)

    affo = affo0
    rows, pv_sum = [], 0.0
    for t in range(1, N + 1):
        g = g_path(t)
        affo *= (1 + g)
        payout = clamp(1 - g_path(t + 1) / roi, 0.0, 1.5)   # lo retenido hoy financia el crecimiento de mañana
        dist = affo * payout
        pv = dist / (1 + ke) ** t
        pv_sum += pv
        rows.append(dict(Año=t, Crecimiento=g, AFFO=affo, Payout=payout, Distribución=dist, VP=pv))
    tv = affo * (1 + gT) * (1 - gT / roi) / (ke - gT)
    pv_tv = tv / (1 + ke) ** N
    equity = pv_sum + pv_tv
    per_share_raw = equity / co.shares_m
    per_share = max(0.0, per_share_raw)
    tv_share = pv_tv / equity if equity > 0 else float("nan")
    if equity <= 0:
        warns.append(f"Valor ≤ 0 en este escenario (calculado: {per_share_raw:,.2f} por acción): se muestra 0.")
    if tv_share > 0.80:
        warns.append(f"El valor terminal pesa {tv_share:.0%} del valor.")
    return ValResult(
        model="REIT (AFFO)", scenario=scen.name, per_share=per_share, equity_value=equity, ev=None,
        discount_rate=ke, ke=ke, g_terminal=gT, tv_share=tv_share, table=rows, warnings=warns,
        extras=dict(ke=ke, beta=c["beta"], rf=c["rf"], ffo=ffo, affo0=affo0, affo_ps=affo0 / co.shares_m,
                    affo_src=affo_src, g0=g0, roi=roi,
                    p_affo_implied=equity / affo0, p_affo_current=co.market_cap_m / affo0, pv_explicit=pv_sum, pv_tv=pv_tv),
    )


# ----------------------------------------------------------------------------
# Orquestación
# ----------------------------------------------------------------------------
MODEL_FUNCS = {"FCFF": fcff_value, "ER": excess_return_value, "REIT": reit_value}


def value_company(co: CompanyData, p: Params, model: str, scen_name: str) -> ValResult:
    scen = SCENARIOS[scen_name]
    try:
        res = MODEL_FUNCS[model](co, p, scen)
        if res.ok:
            res.extras["lifecycle"], res.extras["lifecycle_factors"] = lifecycle_info(co, model, res.extras.get("g1"))
        return res
    except ModelError as e:
        return ValResult(model=model, scenario=scen_name, ok=False, error=str(e))


def run_scenarios(co: CompanyData, p: Params, model: str) -> Dict[str, ValResult]:
    return {name: value_company(co, p, model, name) for name in ("Pesimista", "Base", "Optimista")}


def sensitivity(co: CompanyData, p: Params, model: str, d_rate=(-0.01, -0.005, 0, 0.005, 0.01),
                d_g=(-0.01, -0.005, 0, 0.005, 0.01)) -> Dict[str, object]:
    """Grilla valor/acción: tasa de descuento (WACC o Ke) × g terminal. Escenario Base."""
    base = value_company(co, p, model, "Base")
    if not base.ok:
        return {"ok": False}
    r0 = base.discount_rate
    grid = []
    for dr in d_rate:
        row = []
        for dg in d_g:
            pp = replace(p, g_terminal=p.g_terminal + dg)
            if model == "FCFF":
                pp = replace(pp, wacc_shift=p.wacc_shift + dr)
            else:
                pp = replace(pp, ke_override=r0 + dr)
            r = value_company(co, pp, model, "Base")
            row.append(r.per_share if r.ok else float("nan"))
        grid.append(row)
    return dict(ok=True, rates=[r0 + d for d in d_rate], gs=[p.g_terminal + d for d in d_g], grid=grid)


def implied_wacc(co: CompanyData, p: Params, model: str, lo: float = -0.08, hi: float = 0.10, iters: int = 18) -> Optional[dict]:
    """DCF inverso (solo FCFF): desplazamiento de la tasa de descuento con el cual el valor Base iguala el precio.
    Usa el mismo desplazamiento que la grilla de sensibilidad (mueve juntos el WACC de la empresa y el del sector, así
    se conserva la convergencia). Devuelve {'wacc': WACC inicial implícito, 'shift': desplazamiento, 'wacc_model': el del modelo}
    o None si no se puede (otro modelo, valor 0, o el precio no cae dentro del rango de búsqueda)."""
    if model != "FCFF" or not co.price or co.price <= 0:
        return None
    base = value_company(co, p, model, "Base")
    if not base.ok or base.per_share <= 0:
        return None

    def val(sh: float) -> Optional[float]:
        r = value_company(co, replace(p, wacc_shift=p.wacc_shift + sh), model, "Base")
        return r.per_share if r.ok else None

    v_lo, v_hi = val(lo), val(hi)
    if v_lo is None or v_hi is None or not (v_lo >= co.price >= v_hi):
        return None
    a, b = lo, hi
    for _ in range(iters):
        m = (a + b) / 2
        v = val(m)
        if v is None:
            return None
        if v > co.price:
            a = m
        else:
            b = m
    sh = (a + b) / 2
    return {"wacc": base.discount_rate + sh, "shift": sh, "wacc_model": base.discount_rate}


def field_checks(co: CompanyData, model: str, p: Optional[Params] = None) -> List[dict]:
    """Control obligatorio por dato importado: qué se usó, si parece razonable y qué revisar.
    Estado: 'ok' (✅), 'aviso' (⚠️: revisar), 'info' (ℹ️: dato faltante con supuesto conocido)."""
    out: List[dict] = []
    p = p or Params()

    def add(campo, valor, estado, nota):
        out.append(dict(Campo=campo, Valor=valor, Estado=estado, Control=nota))

    rev = co.revenue_ttm or 0.0
    ebit_m = co.ebit_ttm / rev if rev > 0 else None
    leases = _leases_included(co, p)

    add("Precio y moneda", f"{co.price:,.2f} {co.currency}", "ok" if co.price > 0 else "aviso",
        "Moneda y fecha de la cotización: confirmar que el precio es el de la clase de acción correcta.")
    if co.fin_currency != co.currency:
        add("Moneda de los estados contables", f"{co.fin_currency} → {co.currency}", "aviso",
            f"Convertidos a tipo de cambio spot ({co.fx:.4g}): el valor depende de ese tipo de cambio.")
    else:
        add("Moneda de los estados contables", co.fin_currency, "ok", "Igual a la moneda de cotización.")
    if co.reported_shares_m and co.shares_m > 0:
        diff = abs(co.shares_m / co.reported_shares_m - 1)
        add("Acciones (implícitas = capitalización ÷ precio)", f"{co.shares_m:,.0f} M",
            "aviso" if diff > 0.15 else "ok",
            f"Difieren {diff:.0%} de las reportadas ({co.reported_shares_m:,.0f} M): normal en ADRs, sospechoso si no." if diff > 0.15
            else "Coinciden con las reportadas (±15 %).")
    else:
        add("Acciones (implícitas = capitalización ÷ precio)", f"{co.shares_m:,.0f} M", "info",
            "Sin acciones reportadas para contrastar.")
    add("Ingresos TTM", f"{rev:,.0f} M", "ok" if rev > 0 else "aviso",
        f"Fuente: {co.ttm_source or 'n/d'}" + (f" · al {co.asof}" if co.asof else "") + ". Verificar año fiscal.")
    if co.asof:
        try:
            import datetime as _dt
            age = (_dt.date.today() - _dt.date.fromisoformat(co.asof)).days
            add("Antigüedad de los datos contables", f"{age} días", "aviso" if age > 450 else "ok",
                "Más de 15 meses sin actualizar: puede haber un balance más reciente." if age > 450 else "Dentro de lo esperable.")
        except Exception:  # noqa: BLE001
            pass

    if model == "FCFF":
        if ebit_m is None:
            add("EBIT (resultado operativo)", f"{co.ebit_ttm:,.0f} M", "aviso", "Sin ingresos para calcular el margen.")
        else:
            odd = ebit_m > 0.70 or ebit_m < -0.30
            add("EBIT (resultado operativo)", f"{co.ebit_ttm:,.0f} M · margen {ebit_m:.1%}", "aviso" if odd else "ok",
                "Margen fuera de lo habitual: revisá la definición de operating income." if odd
                else "Margen razonable. Validar que no incluya ganancias extraordinarias.")
        da_r = co.da_ttm / rev if rev > 0 else 0
        add("D&A (amortización)", f"{co.da_ttm:,.0f} M", "info" if co.da_ttm == 0 else ("aviso" if da_r > 0.25 else "ok"),
            "Sin dato: se asume 0 (el FCFF queda subestimado)." if co.da_ttm == 0
            else ("D&A mayor al 25 % de los ingresos: revisar." if da_r > 0.25 else "Signo normalizado a positivo."))
        cx_r = co.capex_ttm / rev if rev > 0 else 0
        add("CapEx", f"{co.capex_ttm:,.0f} M", "info" if co.capex_ttm == 0 else ("aviso" if cx_r > 0.35 else "ok"),
            "Sin dato: se asume 0 (el valor queda sobrestimado)." if co.capex_ttm == 0
            else ("CapEx mayor al 35 % de los ingresos: ¿inversión extraordinaria?" if cx_r > 0.35 else "Signo normalizado a positivo."))
        add("Capital de trabajo (variación)", f"{co.nwc_inv_ttm:,.0f} M", "info" if co.nwc_inv_ttm == 0 else "ok",
            "Sin dato o cero: se asume 0." if co.nwc_inv_ttm == 0 else "Incremento positivo = consume caja.")
        if co.tax_rate_eff is None:
            add("Impuesto efectivo", "n/d", "info", "Sin dato: se usa la tasa marginal del país.")
        else:
            odd = not (0.0 <= co.tax_rate_eff <= 0.35)
            add("Impuesto efectivo", f"{co.tax_rate_eff:.1%}", "aviso" if odd else "ok",
                "Fuera de 0–35 %: se acotó. Un año atípico no debería usarse mecánicamente." if odd
                else f"Converge a la marginal del país ({p.marginal_tax:.1%}) en 5 años.")
        if co.pension_liab is not None and co.pension_liab > 0:
            add("Pensiones y beneficios post-empleo", f"{co.pension_liab:,.0f} M", "info",
                "Informativo: NO se resta del valor (Damodaran pide restar los pasivos de pensiones subfinanciados). "
                "Compará con el valor del patrimonio.")
        ebitda = co.ebit_ttm + co.da_ttm
        debt_net = co.debt if leases else max(0.0, co.debt - co.lease_debt)
        lev = debt_net / ebitda if ebitda > 0 else None
        add("Deuda", f"{debt_net:,.0f} M" + (" (con arrendamientos)" if leases else " (sin arrendamientos)"),
            "aviso" if (lev is not None and lev > 6) or (ebitda <= 0 and debt_net > 0) else "ok",
            "Deuda/EBITDA > 6x o EBITDA ≤ 0: riesgo financiero alto." if (lev is not None and lev > 6) or (ebitda <= 0 and debt_net > 0)
            else "Corto + largo plazo. Revisar arrendamientos.")
        liquid = co.cash + (co.non_op_assets if p.include_nonop else 0.0)
        add("Caja e inversiones no operativas", f"{co.cash:,.0f} M + {co.non_op_assets:,.0f} M",
            "aviso" if co.market_cap_m > 0 and liquid > 0.6 * co.market_cap_m else "ok",
            "Superan el 60 % de la capitalización: confirmar que no haya doble conteo." if co.market_cap_m > 0 and liquid > 0.6 * co.market_cap_m
            else "Se suman al valor de la empresa: confirmar que no estén ya dentro del EBIT.")
        if not co.interest_expense_ttm or co.interest_expense_ttm <= 0:
            add("Intereses pagados", "n/d", "info", "Sin dato: costo de la deuda = tasa libre de riesgo + 1,5 %.")
        else:
            add("Intereses pagados", f"{co.interest_expense_ttm:,.0f} M", "ok", "Base de la calificación sintética.")
    if model in ("FCFF", "ER") or co.equity is not None:
        eq_ok = co.equity is not None and co.equity > 0
        add("Patrimonio contable", "n/d" if co.equity is None else f"{co.equity:,.0f} M", "ok" if eq_ok else "aviso",
            "Revisar patrimonio común vs total (los minoritarios van aparte)." if eq_ok
            else "Patrimonio ausente o ≤ 0 (típico con recompras fuertes): el ROIC y el ROE no son confiables.")
    if model == "ER":
        add("Resultado neto TTM", "n/d" if co.ni_ttm is None else f"{co.ni_ttm:,.0f} M",
            "aviso" if co.ni_ttm is None else "ok", "Base del ROE; normalizar partidas extraordinarias.")
    if model == "REIT":
        add("AFFO", "estimado", "info",
            "Yahoo no informa AFFO: se estima desde el FFO. Lo ideal es cargar el reportado por la compañía.")
    nh = len([x for x in co.revenue_hist if x])
    add("Historia de ingresos", f"{nh} años", "aviso" if nh < 3 else "ok",
        "Menos de 3 años: la mediana histórica y el foso automático son poco confiables." if nh < 3 else "Suficiente para la mediana y la estabilidad del margen.")
    if co.beta is None:
        add("Beta de la acción", "n/d", "info", "Sin beta propia: se usa solo la de la industria (o 1,0 si tampoco hay industria).")
    else:
        add("Beta de la acción", f"{co.beta:.2f}", "aviso" if co.beta <= 0 or co.beta > 2.5 else "ok",
            "Beta ≤ 0 (no se usa) o muy alta: no es confiable." if co.beta <= 0 or co.beta > 2.5
            else "Con datos de industria se promedia con la del sector (piso 0,5, tope 2,0).")
    add("Tasa libre de riesgo", f"{co.rf:.2%}", "ok" if 0.01 <= co.rf <= 0.12 else "aviso",
        "Bono del Tesoro de EE.UU. a 10 años." if 0.01 <= co.rf <= 0.12 else "Fuera de rango: revisar.")
    if model in ("FCFF", "REIT"):
        have = co.rev_g_y0 is not None or co.rev_g_y1 is not None
        na = co.n_analysts
        add("Estimaciones de analistas", f"{na} analistas" if na else ("sí" if have else "n/d"),
            "info" if not have else ("aviso" if (na is not None and na < 3) else "ok"),
            "Sin estimaciones: crecimiento = mediana histórica (confianza menor)." if not have
            else ("Pocos analistas (< 3): estimación poco representativa." if (na is not None and na < 3) else "Crecimiento de años 1–2 según analistas."))
    return out


def data_checks(co: CompanyData) -> List[str]:
    """Advertencias sobre la calidad / naturaleza de los datos (independientes del modelo)."""
    w: List[str] = []
    if co.quote_type and co.quote_type.upper() not in ("EQUITY",):
        w.append(f"El instrumento es '{co.quote_type}', no una acción ordinaria: el DCF no aplica.")
    if co.fin_currency != co.currency:
        w.append(f"Estados contables en {co.fin_currency}, cotización en {co.currency}: "
                 f"convertido a tipo de cambio spot ({co.fx:.4g}).")
    if co.currency not in ("USD",):
        w.append(f"Cotiza en {co.currency}: la tasa libre de riesgo por defecto es la del Tesoro de EE.UU.; "
                 "ajustala si querés valuar en moneda local.")
    if co.reported_shares_m and co.shares_m > 0:
        diff = abs(co.shares_m / co.reported_shares_m - 1)
        if diff > 0.15:
            w.append(f"Acciones implícitas ({co.shares_m:,.0f} M) difieren {diff:.0%} de las reportadas "
                     f"({co.reported_shares_m:,.0f} M): puede ser el ratio del ADR (normal) o un dato erróneo.")
    return w
