"""Stockbit-style HTML parts: watchlist row with sparkline, order-ticket rows. Pure functions returning HTML."""
from html import escape

# tokens: brand green/red for graphics, darker variants for text (WCAG 4.5:1 on white)
CSS = """<style>
:root{--sb-green:#00AB6B;--sb-red:#EE4A49;--sb-up:#007A4D;--sb-down:#C62F2E;--sb-text:#333333;
--sb-muted:#6B6B6B;--sb-line:#EDEDED;--sb-green-bg:#E1F6E5;--sb-red-bg:#FDECEC;}
.sb-row{display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--sb-line);}
.sb-left{flex:1;min-width:0;}
.sb-code{font-weight:800;font-size:16px;color:var(--sb-text);line-height:1.25;}
.sb-name{font-size:12px;color:var(--sb-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.5;}
.sb-spark{flex:none;width:72px;height:24px;}
.sb-right{flex:none;text-align:right;min-width:104px;}
.sb-price{font-weight:700;font-size:16px;color:var(--sb-text);line-height:1.25;}
.sb-chg{font-size:12px;font-weight:600;line-height:1.5;}
.up{color:var(--sb-up);} .down{color:var(--sb-down);} .flat{color:var(--sb-muted);}
.sb-chip{display:inline-block;font-size:12px;font-weight:700;padding:0 8px;border-radius:4px;line-height:24px;margin-top:4px;}
.sb-chip.up{background:var(--sb-green-bg);} .sb-chip.down{background:var(--sb-red-bg);}
.sb-chip.flat{background:#F2F2F2;}
.sb-ticket{border-top:1px solid var(--sb-line);margin-top:8px;}
.sb-trow{display:flex;justify-content:space-between;gap:16px;padding:8px 0;border-bottom:1px solid var(--sb-line);font-size:14px;}
.sb-trow span:first-child{color:var(--sb-muted);}
.sb-trow span:last-child{font-weight:700;color:var(--sb-text);text-align:right;}
.sb-trow span.up{color:var(--sb-up);} .sb-trow span.down{color:var(--sb-down);}
.sb-stats{display:flex;gap:24px;flex-wrap:wrap;padding:8px 0 16px;}
.sb-stat{font-size:12px;color:var(--sb-muted);} .sb-stat b{display:block;font-size:24px;color:var(--sb-text);line-height:1.25;}
</style>"""


def spark(closes):
    """Inline SVG line of recent closes; green when up over the window, red when down."""
    c = [float(x) for x in closes]
    if len(c) < 2:
        return ""
    lo, hi = min(c), max(c)
    span = (hi - lo) or 1
    pts = " ".join(f"{i * 72 / (len(c) - 1):.1f},{22 - (v - lo) / span * 20:.1f}" for i, v in enumerate(c))
    color = "var(--sb-green)" if c[-1] >= c[0] else "var(--sb-red)"
    return (f'<svg class="sb-spark" viewBox="0 0 72 24" aria-hidden="true">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>')


def direction(x):
    return "up" if x > 0 else "down" if x < 0 else "flat"


def change(abs_chg, pct_chg, num):
    """Stockbit style: +275 (+2,13%). Sign always shown so meaning never depends on colour."""
    sign = "+" if abs_chg > 0 else "-" if abs_chg < 0 else ""
    return f"{sign}{num(abs(abs_chg))} ({sign}{num(abs(pct_chg), 2)}%)"


def row(code, name, closes, price, abs_chg, pct_chg, num, chip=None):
    """Watchlist row. chip = (text, css class) shown under the change."""
    d = direction(abs_chg)
    chip_html = f'<div><span class="sb-chip {chip[1]}">{escape(chip[0])}</span></div>' if chip else ""
    return (f'<div class="sb-row"><div class="sb-left"><div class="sb-code">{escape(code)}</div>'
            f'<div class="sb-name">{escape(name)}</div></div>{spark(closes)}'
            f'<div class="sb-right"><div class="sb-price">{num(price)}</div>'
            f'<div class="sb-chg {d}">{change(abs_chg, pct_chg, num)}</div>{chip_html}</div></div>')


def ticket(rows):
    """Order-ticket list: rows of (label, value, optional css class for the value)."""
    body = "".join(f'<div class="sb-trow"><span>{escape(label)}</span>'
                   f'<span class="{cls or ""}">{escape(value)}</span></div>' for label, value, *cls_ in rows
                   for cls in [cls_[0] if cls_ else ""])
    return f'<div class="sb-ticket">{body}</div>'


def stats(items):
    """Summary strip: list of (label, value)."""
    return '<div class="sb-stats">' + "".join(
        f'<div class="sb-stat"><b>{escape(v)}</b>{escape(k)}</div>' for k, v in items) + "</div>"


if __name__ == "__main__":
    n = lambda x, d=0: f"{x:,.{d}f}"  # noqa: E731
    assert change(275, 2.13, n) == "+275 (+2.13%)" and change(-30, -0.83, n) == "-30 (-0.83%)"
    assert change(0, 0, n) == "0 (0.00%)"
    assert "var(--sb-red)" in spark([3, 2, 1]) and spark([1]) == ""
    assert "&lt;b&gt;" in row("<b>", "", [1, 2], 1, 0, 0, n)  # user codes are escaped
    t = ticket([("A", "1"), ("B", "2", "up")])
    assert t.count("sb-trow") == 2 and 'class="up"' in t
    print("ok")
