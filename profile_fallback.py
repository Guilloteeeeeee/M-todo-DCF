"""Respaldo de perfil cuando Yahoo limita los módulos (v2.49).

Cuando Yahoo no entrega el país (o el ADR), la app prueba, en este orden:
  1) la memoria de cargas anteriores buenas de ese mismo ticker (archivo local que la app va llenando sola),
  2) la tabla propia de ADR / emisores extranjeros (país de la sede y ordinarias por ADR),
  3) la planilla de empresas de Damodaran (damodaran_map.lookup_country),
  4) la moneda de los estados contables, solo cuando esa moneda pertenece a un único país (BRL -> Brazil, TWD -> Taiwan...).
Nunca inventa: si ninguna capa lo sabe, el país queda vacío y la app avisa."""
from __future__ import annotations

import json
import os
import tempfile
import time
from typing import Dict, Optional, Tuple

MEMORY_MAX_DAYS = 365

# --- tabla propia: país de la sede de emisores extranjeros que cotizan en EE.UU. (ticker de Yahoo -> país, nombre como en country_risk.py)
_BY_COUNTRY = {
    "Brazil": "PBR PBR-A ITUB BBD BBDO ABEV SBS ERJ GGB SID CIG CIG-C UGP ELP BRFS VALE",
    "Argentina": "YPF GGAL BMA PAM TEO CEPU LOMA TGS CRESY EDN BBAR SUPV IRS",
    "Mexico": "AMX FMX KOF TV CX ASR PAC OMAB",
    "Chile": "SQM BCH BSAC ENIA ENIC CCU LTM",
    "Colombia": "EC CIB AVAL",
    "Peru": "BVN",
    "Taiwan": "TSM UMC ASX CHT",
    "Korea": "KB SHG PKX KEP SKM KT",
    "Japan": "TM SONY HMC MUFG SMFG MFG NMR IX CAJ",
    "China": "BABA JD BIDU NTES TCOM YUMC BEKE ZTO LI NIO XPEV",
    "India": "INFY WIT HDB IBN RDY TTM",
    "Israel": "TEVA CHKP NICE WIX",
    "Netherlands": "ASML ING PHG STLA",
    "Denmark": "NVO",
    "Germany": "SAP",
    "United Kingdom": "AZN GSK BP SHEL UL DEO BTI RIO VOD HSBC BCS LYG",
    "Switzerland": "NVS UBS",
    "France": "SNY TTE",
    "Italy": "E",
    "Sweden": "ERIC",
    "Finland": "NOK",
    "Spain": "SAN BBVA TEF",
    "Norway": "EQNR",
    "Australia": "BHP",
    "South Africa": "GFI HMY SBSW",
}
ADR_COUNTRY: Dict[str, str] = {t: c for c, ts in _BY_COUNTRY.items() for t in ts.split()}

# ordinarias por ADR (solo las que el ratio no es 1 y que conozco con certeza; el resto se aprende de cargas buenas)
ADR_RATIO: Dict[str, float] = {"TSM": 5.0, "TM": 10.0, "BABA": 8.0, "CHT": 10.0, "UMC": 5.0, "ASX": 2.0}

# moneda de los estados contables -> país, solo monedas de un único país
CURRENCY_COUNTRY: Dict[str, str] = {
    "BRL": "Brazil", "TWD": "Taiwan", "KRW": "Korea", "JPY": "Japan", "INR": "India", "MXN": "Mexico", "CLP": "Chile",
    "COP": "Colombia", "PEN": "Peru", "ARS": "Argentina", "ZAR": "South Africa", "ILS": "Israel", "TRY": "Turkey",
    "PLN": "Poland", "SEK": "Sweden", "NOK": "Norway", "DKK": "Denmark", "CHF": "Switzerland", "AUD": "Australia",
    "CAD": "Canada", "HKD": "Hong Kong", "SGD": "Singapore", "THB": "Thailand", "IDR": "Indonesia", "MYR": "Malaysia",
    "PHP": "Philippines", "NZD": "New Zealand", "CZK": "Czech Republic", "HUF": "Hungary", "RON": "Romania",
    "CNY": "China", "GBP": "United Kingdom",
}


def _path() -> str:
    env = os.environ.get("DCF_PROFILE_MEMORY")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here if os.access(here, os.W_OK) else tempfile.gettempdir(), "profile_memory.json")


def _read() -> dict:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def recall(sym: str) -> dict:
    """Perfil guardado de una carga buena anterior ({} si no hay o es muy viejo)."""
    d = _read().get((sym or "").upper()) or {}
    if not isinstance(d, dict) or time.time() - float(d.get("ts", 0) or 0) > MEMORY_MAX_DAYS * 86400:
        return {}
    return d


def remember(sym: str, info: dict) -> None:
    """Guarda el perfil de una carga buena (solo datos que vinieron de Yahoo). Nunca falla."""
    try:
        clean = {k: v for k, v in info.items() if v not in (None, "", 0)}
        if not clean:
            return
        mem = _read()
        mem[(sym or "").upper()] = {**clean, "ts": time.time()}
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:  # noqa: BLE001
        pass


def learned_ratio(shares_adr_m: Optional[float], reported_shares_m: Optional[float], fin_cur: str, qcur: str) -> Optional[float]:
    """Ordinarias por ADR observadas en una carga buena (solo si la empresa reporta en otra moneda y el cociente es casi entero y > 1)."""
    if not shares_adr_m or not reported_shares_m or fin_cur == qcur:
        return None
    r = reported_shares_m / shares_adr_m
    if 1.5 <= r <= 200 and abs(r - round(r)) / r < 0.03:
        return float(round(r))
    return None


def country_chain(sym: str, name: str = "", fin_cur: str = "") -> Optional[Tuple[str, str]]:
    """(país, de dónde salió) probando las capas 1-4, o None."""
    s = (sym or "").upper()
    c = recall(s).get("country")
    if c:
        return str(c), "memoria de una carga anterior de este ticker"
    if s in ADR_COUNTRY:
        return ADR_COUNTRY[s], "tabla propia de ADR / emisores extranjeros"
    try:
        from damodaran_map import lookup_country
        hit = lookup_country(s, name)
        if hit:
            return hit[0], f"planilla de Damodaran ({hit[1]})"
    except Exception:  # noqa: BLE001
        pass
    if fin_cur in CURRENCY_COUNTRY:
        return CURRENCY_COUNTRY[fin_cur], f"moneda de los estados contables ({fin_cur}; supuesto)"
    return None
