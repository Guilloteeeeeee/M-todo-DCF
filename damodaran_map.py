"""Busca la industria de Damodaran de cada empresa en SU planilla "Companies in each industry" (indname.xls, 48.156 empresas,
las mismas 94 industrias de industry_data.py). v2.43.

Orden de búsqueda:
  1) Ticker de EE.UU. sin sufijo (NYSE, Nasdaq, NYSE American; y luego OTC).
  2) Ticker con sufijo de Yahoo (.T, .HK, .L, .DE, .PA ...) contra la bolsa que corresponde.
  3) Nombre de la empresa (para ADR y casos sin ticker propio): solo si hay una única coincidencia, o una sola del mismo país.
Si no la encuentra devuelve None y industry_data usa la regla vieja (industria de Yahoo -> Damodaran)."""
from __future__ import annotations

import gzip
import os
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

DAM_FILE_DATE = "octubre 2026"        # cuándo se bajó la planilla (la app avisa si pasaron más de 12 meses)
DAM_FILE_ISO = "2026-10-19"
_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "damodaran_companies.tsv.gz")

US_EXCH = ("NYSE", "NasdaqGS", "NasdaqGM", "NasdaqCM", "NYSEAM", "NYSEArca", "BATS")
# sufijo de Yahoo -> bolsas de la planilla (en orden de preferencia)
SUFFIX: Dict[str, Tuple[str, ...]] = {
    "T": ("TSE",), "HK": ("SEHK",), "SS": ("SHSE",), "SZ": ("SZSE",), "KS": ("KOSE",), "KQ": ("KOSDAQ",), "TW": ("TWSE",),
    "TWO": ("TPEX",), "NS": ("NSEI",), "BO": ("BSE",), "AX": ("ASX",), "TO": ("TSX",), "V": ("TSXV",), "CN": ("CNSX",),
    "L": ("LSE", "AIM"), "DE": ("XTRA", "DB"), "F": ("DB", "XTRA"), "PA": ("ENXTPA",), "AS": ("ENXTAM",), "MI": ("BIT",),
    "MC": ("BME",), "SW": ("SWX",), "ST": ("OM", "NGM"), "CO": ("CPSE",), "HE": ("HLSE",), "OL": ("OB",), "BR": ("ENXTBR",),
    "LS": ("ENXTLS",), "IR": ("ISE",), "VI": ("WBAG",), "WA": ("WSE",), "SA": ("BOVESPA",), "MX": ("BMV",), "SI": ("SGX",),
    "KL": ("KLSE",), "BK": ("SET",), "JK": ("IDX",), "TA": ("TASE",), "JO": ("JSE",), "SR": ("SASE",), "NZ": ("NZSE",),
    "IS": ("IBSE",), "AT": ("ATSE",), "VN": ("HOSE", "HNX"), "PS": ("PSE",), "CR": ("BVC",), "BA": (), "SN": ("SNSE",),
}

_NAME_STOP = re.compile(r"\b(inc|incorporated|corp|corporation|co|ltd|limited|plc|sa|nv|ag|se|ab|asa|oyj|spa|company|holding|holdings|"
                        r"group|the|adr|sab|de|cv|llc|lp|class|a|b|c)\b")

_STATE: Dict[str, object] = {}


def _key(s: str, exch: str = "") -> str:
    k = re.sub(r"[^A-Z0-9]", "", str(s).upper())
    if exch in ("KOSE", "KOSDAQ") and k.startswith("A") and k[1:].isdigit():
        k = k[1:]
    if k.isdigit():
        k = k.lstrip("0") or "0"
    return k


def _norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii").lower()   # sin tildes
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _NAME_STOP.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _load() -> dict:
    if _STATE:
        return _STATE
    by_ex: Dict[str, Dict[str, Tuple[str, str, str]]] = {}
    by_name: Dict[str, List[Tuple[str, str, str]]] = {}
    n = 0
    try:
        with gzip.open(_PATH, "rt", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                xt, grp, country, nm = parts[0], parts[1], parts[2], parts[3]
                if ":" not in xt:
                    continue
                ex, tk = xt.split(":", 1)
                by_ex.setdefault(ex, {}).setdefault(_key(tk, ex), (grp, xt, country))
                nn = _norm_name(nm)
                if len(nn) >= 3:
                    by_name.setdefault(nn, []).append((grp, xt, country))
                n += 1
    except (OSError, EOFError):
        pass
    _STATE.update(by_ex=by_ex, by_name=by_name, n=n)
    return _STATE


def size() -> int:
    return int(_load().get("n", 0))


def lookup(ticker: str, name: str = "", country: str = "") -> Optional[Tuple[str, str]]:
    """(industria de Damodaran, de dónde salió) o None. El texto de origen dice la bolsa:ticker de la planilla y cómo se halló."""
    st = _load()
    by_ex, by_name = st.get("by_ex") or {}, st.get("by_name") or {}
    if not by_ex:
        return None
    sym = (ticker or "").strip().upper()
    if sym:
        base, suf = (sym.rsplit(".", 1) + [""])[:2] if "." in sym else (sym, "")
        if suf and suf in SUFFIX:                       # cotiza fuera de EE.UU.: bolsa según el sufijo de Yahoo
            for ex in SUFFIX[suf]:
                hit = by_ex.get(ex, {}).get(_key(base, ex))
                if hit:
                    return hit[0], f"{hit[1]}, por ticker"
        elif not suf or suf not in SUFFIX:              # sin sufijo (o sufijo que es parte del ticker, ej. BRK.B): EE.UU.
            for ex in US_EXCH + ("OTCPK",):
                hit = by_ex.get(ex, {}).get(_key(sym, ex))
                if hit:
                    return hit[0], f"{hit[1]}, por ticker"
    nn = _norm_name(name)
    if len(nn) >= 3:                                    # ADR y casos sin ticker propio: por nombre
        c = by_name.get(nn) or []
        if len(c) == 1:
            return c[0][0], f"{c[0][1]}, por nombre"
        if len(c) > 1 and country:
            same = [x for x in c if x[2].strip().lower() == country.strip().lower()]
            if len(same) == 1:
                return same[0][0], f"{same[0][1]}, por nombre"
    return None


def lookup_country(ticker: str, name: str = "") -> Optional[Tuple[str, str]]:
    """(país, de dónde salió) o None. Respaldo para cuando Yahoo no entrega el país: lo toma de la misma planilla de Damodaran,
    buscando igual que lookup() (ticker de EE.UU., ticker con sufijo, o nombre si hay una única coincidencia).
    El país es el de la bolsa principal de la planilla (ej. VALE -> Brazil, TSM -> Taiwan)."""
    st = _load()
    by_ex, by_name = st.get("by_ex") or {}, st.get("by_name") or {}
    if not by_ex:
        return None
    sym = (ticker or "").strip().upper()
    if sym:
        base, suf = (sym.rsplit(".", 1) + [""])[:2] if "." in sym else (sym, "")
        if suf and suf in SUFFIX:
            for ex in SUFFIX[suf]:
                hit = by_ex.get(ex, {}).get(_key(base, ex))
                if hit and hit[2]:
                    return hit[2], f"{hit[1]}, por ticker"
        else:
            for ex in US_EXCH + ("OTCPK",):
                hit = by_ex.get(ex, {}).get(_key(sym, ex))
                if hit and hit[2]:
                    return hit[2], f"{hit[1]}, por ticker"
    nn = _norm_name(name)
    if len(nn) >= 3:
        c = by_name.get(nn) or []
        if len(c) == 1 and c[0][2]:
            return c[0][2], f"{c[0][1]}, por nombre"
    return None
