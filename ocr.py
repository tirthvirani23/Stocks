"""Reads a portfolio screenshot: finds stock names or symbols, and quantities and average prices where visible."""

from __future__ import annotations

import io
import re

import analysis as a

STOP = {"NSE", "BSE", "LTP", "QTY", "AVG", "DAY", "NET", "TOTAL", "INVESTED", "CURRENT", "HOLDINGS", "EQUITY",
        "BUY", "SELL", "PNL", "VALUE", "RETURNS", "RETURN", "STOCKS", "STOCK", "SHARES", "PRICE", "MARKET", "INDIA",
        "LIMITED", "LTD", "THE", "AND", "ALL", "NEW", "TOP", "MAX", "ONE", "SORT", "FILTER"}
_INDEX = None


def _index():
    """symbol -> ticker, and a list of (normalised company name start, symbol)."""
    global _INDEX
    if _INDEX is None:
        symbols, names = {}, []
        for block in a.static_industries().values():
            for s in block["stocks"]:
                sym = s["ticker"][:-3]
                symbols[sym] = s["ticker"]
                words = re.sub(r"[^a-z0-9 ]", " ", s["name"].lower()).split()
                words = [w for w in words if w not in ("limited", "ltd", "the", "india", "company", "corporation")]
                core = "".join(words[:2])
                if len(core) >= 7:
                    names.append((core, sym, s.get("market_cap") or 0))
        names.sort(key=lambda x: (-len(x[0]), -x[2]))  # longest name first, then the larger company
        _INDEX = (symbols, names)
    return _INDEX


def read_text(image_bytes: bytes) -> str:
    import pytesseract
    from PIL import Image, ImageOps, ImageStat

    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    if ImageStat.Stat(img).mean[0] < 110:  # dark-mode screenshot: flip to dark text on light
        img = ImageOps.invert(img)
    if img.width < 1600:
        scale = 1600 / img.width
        img = img.resize((1600, int(img.height * scale)))
    img = ImageOps.autocontrast(img)
    return pytesseract.image_to_string(img, config="--psm 6")


_NUM = r"(\d[\d,]*\.?\d*)"
_QTY = [re.compile(r"(?:qty|quantity)\.?\s*[:=]?\s*" + _NUM, re.I),
        re.compile(_NUM + r"\s*(?:shares?|qty|nos)\b", re.I)]
_AVG = [re.compile(r"avg\.?\s*(?:price|cost)?\.?\s*[:=]?\s*(?:₹|rs\.?|inr)?\s*" + _NUM, re.I),
        re.compile(r"(?:buy|average)\s*(?:price|cost)\s*[:=]?\s*(?:₹|rs\.?|inr)?\s*" + _NUM, re.I)]


def _num(text):
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _find_stock(line: str):
    symbols, names = _index()
    for token in re.findall(r"[A-Z][A-Z0-9&\-]{1,14}", line):
        if token in symbols and token not in STOP:
            return token
    squashed = re.sub(r"[^a-z0-9]", "", line.lower())
    if len(squashed) >= 7:
        for core, sym, _cap in names:
            if core in squashed:
                return sym
    return None


def _details(line: str):
    qty = avg = None
    for pat in _QTY:
        m = pat.search(line)
        if m:
            qty = _num(m.group(1))
            break
    for pat in _AVG:
        m = pat.search(line)
        if m:
            avg = _num(m.group(1))
            break
    return qty, avg


def parse_holdings(text: str) -> list[dict]:
    """Some apps print quantity and average price above the stock name, others below it.
    Whichever comes first in the image decides how the lines are paired."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    events = []  # ("stock", symbol) or ("details", (qty, avg)) in reading order
    for line in lines:
        sym = _find_stock(line)
        qty, avg = _details(line)
        if qty is not None or avg is not None:
            events.append(("details", (qty, avg)))
        if sym:
            events.append(("stock", sym))
    kinds = [k for k, _ in events]
    details_first = "details" in kinds and "stock" in kinds and kinds.index("details") < kinds.index("stock")

    found, order = {}, []

    def row(sym):
        if sym not in found:
            found[sym] = {"Symbol": sym, "Quantity": None, "Buy price": None}
            order.append(sym)
        return found[sym]

    def apply(target, det):
        if target["Quantity"] is None and det[0] is not None:
            target["Quantity"] = det[0]
        if target["Buy price"] is None and det[1] is not None:
            target["Buy price"] = det[1]

    pending, current = [], None
    for kind, val in events:
        if kind == "stock":
            current = row(val)
            if details_first:
                for det in pending:
                    apply(current, det)
                pending = []
        elif details_first:
            pending.append(val)
        elif current is not None:
            apply(current, val)
    return [found[s] for s in order]
