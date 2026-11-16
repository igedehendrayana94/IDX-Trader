"""Monthly report: what the ML-assisted menus recommended each day vs the real prices afterwards.
Usage: python report.py [YYYY-MM]   (default: current month) -> reports/idx_trader_YYYY-MM.xlsx + CSVs.
The app's "Akurasi" tab calls replay() for any date range and shows the same numbers live.

The app does not log its daily output, so the month is replayed point-in-time: per style one model is trained only
on rows whose outcome was known before the month started, then it scores every trading day of the month.
Signals and features use closed daily bars; BSJP's sell price (next open) may come from today's bar once the market
has opened. Summary sheets use Excel formulas over the detail sheets."""
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import idx
import ml
import risk
import timing

OUT = Path(__file__).parent / "reports"
MIN_VALUE = 5e9  # app default liquidity filter (avg daily value, Rp)
STATUS_DONE, STATUS_OPEN, STATUS_WAIT = "Selesai", "Berjalan", "Menunggu"
EXIT_NAME = {"target": "Target", "stop": "Stop loss", "time": "Batas waktu"}


def week_label(d):
    y, w, _ = d.isocalendar()
    mon = date.fromisocalendar(y, w, 1)
    fri = date.fromisocalendar(y, w, 5)
    return f"{y}-W{w:02d} ({mon:%d/%m}–{fri:%d/%m})"


def month_range(month):
    first = pd.Timestamp(f"{month}-01")
    return first, first + pd.offsets.MonthEnd(0)


def replay(first, last, raw=None, data=None, ihsg=None):
    """Point-in-time replay of the dates first..last (Timestamps). raw = bars incl. today's (for BSJP's next open),
    data/ihsg = closed bars; fetched when not given. Returns (bsjp rows, rekomendasi rows, info, all scored rows)."""
    now = datetime.now(timing.WIB)
    raw = raw if raw is not None else idx.fetch(idx.UNIVERSE, period="5y")
    data = data if data is not None else {c: timing.drop_unfinished(d, now) for c, d in raw.items()}
    ihsg = ihsg if ihsg is not None else timing.drop_unfinished(idx.fetch_ihsg(period="5y"), now)
    scored = {}
    if not ((ihsg.index >= first) & (ihsg.index <= last)).any():  # no closed trading day in the range
        return pd.DataFrame(), pd.DataFrame(), {"data_to": ihsg.index[-1].date()}, {}
    light = risk.regime_series(data, ihsg)["light"]
    names = idx.NAMES

    # ---------- BSJP: ML top 3 per day among liquid stocks ----------
    p = ml.dataset(data, "bsjp", ihsg=ihsg)
    dates = np.sort(p["date"].unique())
    cut = dates[max(np.searchsorted(dates, first) - 2, 0)]
    known = p.assign(y=p["y"].where(p["date"] < cut))
    m = ml.fit(known)
    hist = ml.oos(known[known["date"] < first], "bsjp")
    move = ((hist["ret"] + 1) * (1 + idx.BUY_FEE) / (1 - idx.SELL_FEE) - 1)
    rng = {r: move[hist["rank"] == r].quantile([0.25, 0.5, 0.75]).to_numpy() for r in (1, 2, 3)}
    auc = ml.summary(hist)["auc"].mean()
    month_rows = p[(p["date"] >= first) & (p["date"] <= last)].copy()
    value20 = pd.concat([idx.indicators(df)["value20"].rename(c) for c, df in data.items()], axis=1)
    month_rows["value20"] = [value20.at[d, c] for d, c in zip(month_rows["date"], month_rows["code"])]
    liquid = month_rows[month_rows["value20"] >= MIN_VALUE].copy()
    liquid["prob"] = m.predict_proba(liquid[ml.cols(liquid)])[:, 1]
    liquid["rank"] = liquid.groupby("date")["prob"].rank(ascending=False, method="first")
    base_bsjp = liquid["ret"].mean()  # all liquid stock-days, net: the comparison line
    scored["bsjp"] = liquid[["date", "code", "prob", "rank", "ret", "y"]]
    bsjp = []
    for _, r in liquid[liquid["rank"] <= 3].sort_values(["date", "rank"]).iterrows():
        d, c = r["date"], r["code"]
        df = data[c]
        close = float(df.at[d, "Close"])
        after = raw[c][raw[c].index > d]
        sell_px = float(after["Open"].iloc[0]) if len(after) else None
        sig = bool(idx.conditions(idx.indicators(df[df.index <= d]), "daily").iloc[-1].all())
        q = rng[int(r["rank"])]
        bsjp.append({
            "Tanggal": d.date(), "Minggu": week_label(d.date()), "Kode": c, "Nama saham": names.get(c, ""),
            "Peringkat ML": int(r["rank"]), "Peluang untung (ML)": r["prob"],
            "Harga beli (penutupan)": close, "Harga beli maks.": close + idx.tick(close),
            "Prediksi buka besok (median)": idx.round_tick(close * (1 + q[1]), up=q[1] > 0),
            "Prediksi rentang bawah": idx.round_tick(close * (1 + q[0])),
            "Prediksi rentang atas": idx.round_tick(close * (1 + q[2]), up=True),
            "Harga buka sebenarnya": sell_px, "Tanggal jual": after.index[0].date() if len(after) else None,
            "Lampu pasar": {"green": "Hijau", "yellow": "Kuning", "red": "Merah"}.get(light.get(d), ""),
            "4 syarat Harian": "Ya" if sig else "Tidak",
            "Status": STATUS_DONE if sell_px is not None else STATUS_WAIT,
        })

    # ---------- Rekomendasi: Swing/Harian signals plus the ML's top 3 per day (to judge the ML itself) ----------
    rek, edge = [], {}
    for mode in idx.MODES:
        p = ml.dataset(data, mode, ihsg=ihsg)
        gap = idx.MODES[mode]["hold"] + 1
        dates = np.sort(p["date"].unique())
        cut = dates[max(np.searchsorted(dates, first) - gap, 0)]
        known = p.assign(y=p["y"].where(p["date"] < cut))
        m = ml.fit(known)
        edge[mode] = ml.summary(ml.oos(known[known["date"] < first], mode))["auc"].mean()
        rows = p[(p["date"] >= first) & (p["date"] <= last)].copy()
        rows["value20"] = [value20.at[d, c] for d, c in zip(rows["date"], rows["code"])]
        rows = rows[rows["value20"] >= MIN_VALUE].copy()
        rows["prob"] = m.predict_proba(rows[ml.cols(rows)])[:, 1]
        rows["rank"] = rows.groupby("date")["prob"].rank(ascending=False, method="first")
        scored[mode] = rows[["date", "code", "prob", "rank", "ret", "y"]]
        frames = {c: idx.indicators(df) for c, df in data.items()}
        sigs = {c: idx.conditions(d_ind, mode).all(axis=1) for c, d_ind in frames.items()}
        for _, r in rows.iterrows():
            d, c = r["date"], r["code"]
            d_ind = frames[c]
            i = d_ind.index.get_loc(d)
            sig = bool(sigs[c].iloc[i])
            if r["rank"] > 3 and not sig:
                continue
            arr, n = idx.ohlca(d_ind), len(d_ind)
            close = float(d_ind["Close"].iloc[i])
            row = {"Tanggal sinyal": d.date(), "Minggu": week_label(d.date()), "Kode": c,
                   "Nama saham": names.get(c, ""), "Gaya": "Swing" if mode == "swing" else "Harian",
                   "Peringkat ML": int(r["rank"]), "Peluang untung (ML)": r["prob"],
                   "ML terbukti?": "Ya" if edge[mode] >= 0.53 else "Tidak",
                   "4 syarat terpenuhi": "Ya" if sig else "Tidak",
                   "Lampu pasar": {"green": "Hijau", "yellow": "Kuning", "red": "Merah"}.get(light.get(d), ""),
                   "Harga sinyal (penutupan)": close}
            if i + 1 >= n:  # bought at the next open, which has not happened in closed data yet
                stop, target, _ = idx.plan(close, float(d_ind["atr"].iloc[i]), mode, 0, 0)
                row.update({"Stop loss": stop, "Target (prediksi harga)": target, "Harga beli sebenarnya": None,
                            "Tanggal keluar": None, "Harga keluar": None, "Alasan keluar": "", "Status": STATUS_WAIT})
            else:
                entry = float(arr[0][i + 1])
                stop, target, _ = idx.plan(entry, float(arr[4][i]), mode, 0, 0)
                ret, j = idx.outcome(arr, i, mode)
                exit_px = (ret + 1) * entry * (1 + idx.BUY_FEE) / (1 - idx.SELL_FEE)
                hit = "stop" if arr[2][j] <= stop else "target" if arr[1][j] >= target else "time"
                done = hit != "time" or i + idx.MODES[mode]["hold"] <= n - 1
                row.update({"Stop loss": stop, "Target (prediksi harga)": target, "Harga beli sebenarnya": entry,
                            "Tanggal keluar": d_ind.index[j].date(), "Harga keluar": round(exit_px, 2),
                            "Alasan keluar": EXIT_NAME[hit] if done else "Masih dipegang (harga terakhir)",
                            "Status": STATUS_DONE if done else STATUS_OPEN})
            rek.append(row)
    rek = sorted(rek, key=lambda r: (r["Tanggal sinyal"], r["Gaya"], r["Peringkat ML"]))
    info = {"bsjp_auc": auc, "bsjp_base": base_bsjp, **edge,
            "data_to": max(df.index[-1] for df in data.values()).date()}
    return pd.DataFrame(bsjp), pd.DataFrame(rek), info, scored


def summarize(bsjp, rek, scored, by_week=False):
    """Accuracy per menu (finished trades only, net of fees). 'Akurasi' = share of finished picks that made a profit;
    AUC = how well the ML ranked all liquid stocks in the period (0.5 = coin flip)."""
    from sklearn.metrics import roc_auc_score
    fb, fs = idx.BUY_FEE, idx.SELL_FEE
    b = bsjp.assign(net=lambda x: x["Harga buka sebenarnya"] * (1 - fs) / (x["Harga beli (penutupan)"] * (1 + fb)) - 1,
                    pl=lambda x: (x["Harga buka sebenarnya"] * (1 - fs) - x["Harga beli (penutupan)"] * (1 + fb)) * idx.LOT,
                    date=lambda x: x["Tanggal"]) if len(bsjp) else bsjp
    r = rek.assign(net=lambda x: x["Harga keluar"] * (1 - fs) / (x["Harga beli sebenarnya"] * (1 + fb)) - 1,
                   pl=lambda x: (x["Harga keluar"] * (1 - fs) - x["Harga beli sebenarnya"] * (1 + fb)) * idx.LOT,
                   date=lambda x: x["Tanggal sinyal"]) if len(rek) else rek
    menus = []
    if len(b):
        menus += [("BSJP – ML #1", b[b["Peringkat ML"] == 1], "bsjp"), ("BSJP – ML top 3", b, "bsjp")]
    if len(r):
        for gaya, key in (("Harian", "daily"), ("Swing", "swing")):
            g = r[r["Gaya"] == gaya]
            menus += [(f"{gaya} – ML top 3", g[g["Peringkat ML"] <= 3], key),
                      (f"{gaya} – sinyal 4 syarat", g[g["4 syarat terpenuhi"] == "Ya"], key)]
    rows = []
    for name, df, key in menus:
        groups = df.groupby("Minggu") if by_week else [("Periode ini", df)]
        for week, g in groups:
            done = g[g["Status"] == STATUS_DONE]
            sc = scored.get(key, pd.DataFrame(columns=["date", "ret", "y", "prob"]))
            if by_week:
                sc = sc[sc["date"].dt.date.map(week_label) == week]
            lab = sc[sc["y"].notna()]
            rows.append({
                "Menu": name, "Minggu": week, "Rekomendasi": len(g), "Selesai": len(done),
                "Untung": int((done["net"] > 0).sum()),
                "Akurasi (untung/selesai)": (done["net"] > 0).mean() if len(done) else np.nan,
                "Prediksi ML rata-rata": done["Peluang untung (ML)"].mean() if len(done) else np.nan,
                "Rata-rata hasil bersih": done["net"].mean() if len(done) else np.nan,
                "Total untung/rugi per lot (Rp)": done["pl"].sum(),
                "Semua saham (pembanding)": sc["ret"].mean() if len(sc) else np.nan,
                "AUC periode": roc_auc_score(lab["y"], lab["prob"]) if lab["y"].nunique() == 2 else np.nan,
            })
    return pd.DataFrame(rows)


# ---------- Excel ----------
FONT, BOLD = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
HEAD = PatternFill("solid", start_color="E6F4EE")
INPUT = Font(name="Arial", size=10, color="0000FF")
FMT = {"price": "#,##0", "pct": "0.00%;-0.00%;0.00%", "prob": "0%", "rp": "#,##0;(#,##0);-"}


def sheet_table(ws, df, formats, formulas):
    """Write df at A1 with header style; formulas = {header: template with {r} for the row}."""
    cols = list(df.columns) + list(formulas)
    for j, h in enumerate(cols, 1):
        c = ws.cell(1, j, h)
        c.font, c.fill, c.alignment = BOLD, HEAD, Alignment(wrap_text=True, vertical="top")
    for i, rec in enumerate(df.itertuples(index=False), 2):
        for j, v in enumerate(rec, 1):
            ws.cell(i, j, None if (isinstance(v, float) and np.isnan(v)) else v).font = FONT
        for j, h in enumerate(formulas, len(df.columns) + 1):
            ws.cell(i, j, formulas[h].format(r=i)).font = FONT
    for j, h in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(j)].width = max(11, min(28, len(h) + 2))
        for i in range(2, len(df) + 2):
            if h in formats:
                ws.cell(i, j).number_format = FMT[formats[h]]
    ws.freeze_panes = "D2"
    ws.row_dimensions[1].height = 42
    return {h: get_column_letter(j) for j, h in enumerate(cols, 1)}


def build(title, bsjp, rek, info):
    wb = Workbook()
    summ = wb.active
    summ.title = "Ringkasan"
    a = wb.create_sheet("Asumsi")
    for r, (k, v, note) in enumerate([("Biaya beli", idx.BUY_FEE, "Fee beli broker + pajak (dipakai aplikasi)"),
                                      ("Biaya jual", idx.SELL_FEE, "Fee jual broker + pajak (dipakai aplikasi)"),
                                      ("Lembar per lot", idx.LOT, "Aturan BEI")], 2):
        a.cell(r, 1, k).font = FONT
        a.cell(r, 2, v).font = INPUT
        a.cell(r, 2).number_format = "0.00%" if r < 4 else "0"
        a.cell(r, 3, note).font = FONT
    a.cell(1, 1, "Asumsi").font = BOLD
    a.column_dimensions["A"].width, a.column_dimensions["C"].width = 18, 45
    fb, fs, lot = "Asumsi!$B$2", "Asumsi!$B$3", "Asumsi!$B$4"

    ws = wb.create_sheet("BSJP (ML)")
    L = {h: get_column_letter(j) for j, h in enumerate(list(bsjp.columns), 1)}
    buy, sell = L["Harga beli (penutupan)"], L["Harga buka sebenarnya"]
    lo, hi = L["Prediksi rentang bawah"], L["Prediksi rentang atas"]
    bcol = sheet_table(ws, bsjp, {
        "Peluang untung (ML)": "prob", "Harga beli (penutupan)": "price", "Harga beli maks.": "price",
        "Prediksi buka besok (median)": "price", "Prediksi rentang bawah": "price", "Prediksi rentang atas": "price",
        "Harga buka sebenarnya": "price", "Perubahan sebenarnya %": "pct", "Hasil bersih % (setelah biaya)": "pct",
        "Untung/rugi per lot (Rp)": "rp"}, {
        "Perubahan sebenarnya %": f'=IF({sell}{{r}}="","",{sell}{{r}}/{buy}{{r}}-1)',
        "Hasil bersih % (setelah biaya)": f'=IF({sell}{{r}}="","",{sell}{{r}}*(1-{fs})/({buy}{{r}}*(1+{fb}))-1)',
        "Untung/rugi per lot (Rp)": f'=IF({sell}{{r}}="","",({sell}{{r}}*(1-{fs})-{buy}{{r}}*(1+{fb}))*{lot})',
        "Hasil": f'=IF({sell}{{r}}="","",IF({sell}{{r}}*(1-{fs})>{buy}{{r}}*(1+{fb}),"Untung","Rugi"))',
        "Dalam rentang prediksi?": f'=IF({sell}{{r}}="","",IF(AND({sell}{{r}}>={lo}{{r}},{sell}{{r}}<={hi}{{r}}),"Ya","Tidak"))',
    })

    ws = wb.create_sheet("Rekomendasi")
    L = {h: get_column_letter(j) for j, h in enumerate(list(rek.columns), 1)}
    ent, ex = L["Harga beli sebenarnya"], L["Harga keluar"]
    rcol = sheet_table(ws, rek, {
        "Peluang untung (ML)": "prob", "Harga sinyal (penutupan)": "price", "Stop loss": "price",
        "Target (prediksi harga)": "price", "Harga beli sebenarnya": "price", "Harga keluar": "price",
        "Hasil bersih % (setelah biaya)": "pct", "Untung/rugi per lot (Rp)": "rp"}, {
        "Hasil bersih % (setelah biaya)": f'=IF({ex}{{r}}="","",{ex}{{r}}*(1-{fs})/({ent}{{r}}*(1+{fb}))-1)',
        "Untung/rugi per lot (Rp)": f'=IF({ex}{{r}}="","",({ex}{{r}}*(1-{fs})-{ent}{{r}}*(1+{fb}))*{lot})',
        "Hasil": f'=IF({ex}{{r}}="","",IF({ex}{{r}}*(1-{fs})>{ent}{{r}}*(1+{fb}),"Untung","Rugi"))',
    })

    # ---------- summary: formulas over the detail sheets ----------
    nb, nr = max(len(bsjp) + 1, 2), max(len(rek) + 1, 2)
    B = lambda h: f"'BSJP (ML)'!${bcol[h]}$2:${bcol[h]}${nb}"  # noqa: E731
    R = lambda h: f"Rekomendasi!${rcol[h]}$2:${rcol[h]}${nr}"  # noqa: E731
    menus = [  # label, detail range getter, criteria pairs
        ("BSJP – ML #1", B, [(B("Peringkat ML"), "1")]),
        ("BSJP – ML top 3", B, []),
        ("Harian – ML #1", R, [(R("Gaya"), '"Harian"'), (R("Peringkat ML"), "1")]),
        ("Harian – ML top 3", R, [(R("Gaya"), '"Harian"'), (R("Peringkat ML"), '"<=3"')]),
        ("Harian – sinyal 4 syarat", R, [(R("Gaya"), '"Harian"'), (R("4 syarat terpenuhi"), '"Ya"')]),
        ("Swing – ML #1", R, [(R("Gaya"), '"Swing"'), (R("Peringkat ML"), "1")]),
        ("Swing – ML top 3", R, [(R("Gaya"), '"Swing"'), (R("Peringkat ML"), '"<=3"')]),
        ("Swing – sinyal 4 syarat", R, [(R("Gaya"), '"Swing"'), (R("4 syarat terpenuhi"), '"Ya"')]),
    ]

    def stats_row(ws, row, label, rng, crit, extra_label=None):
        sheet_status = rng("Status")
        crit_txt = "".join(f",{c},{v}" for c, v in crit)
        done = f'{sheet_status},"{STATUS_DONE}"'
        ws.cell(row, 1, label).font = FONT
        if extra_label:
            ws.cell(row, 2, extra_label).font = FONT
        f = {
            3: f"=COUNTIFS({sheet_status},\"<>\"{crit_txt}{extra_crit(rng, extra_label)})",
            4: f"=COUNTIFS({done}{crit_txt}{extra_crit(rng, extra_label)})",
            5: f'=COUNTIFS({rng("Hasil")},"Untung",{done}{crit_txt}{extra_crit(rng, extra_label)})',
            6: f'=IFERROR(E{row}/D{row},"-")',
            7: f'=IFERROR(AVERAGEIFS({rng("Hasil bersih % (setelah biaya)")},{done}{crit_txt}'
               f'{extra_crit(rng, extra_label)}),"-")',
            8: f'=SUMIFS({rng("Untung/rugi per lot (Rp)")},{done}{crit_txt}{extra_crit(rng, extra_label)})',
        }
        for col, v in f.items():
            c = ws.cell(row, col, v)
            c.font = FONT
            c.number_format = {6: "0%", 7: "0.00%;-0.00%;0.00%", 8: FMT["rp"]}.get(col, "0")

    def extra_crit(rng, week):
        return f',{rng("Minggu")},"{week}"' if week else ""

    summ["A1"] = f"IDX Trader – ringkasan rekomendasi ML {title}"
    summ["A1"].font = Font(name="Arial", size=14, bold=True)
    summ["A2"] = (f"Data sampai {info['data_to']:%d/%m/%Y}. Replay point-in-time: model dilatih hanya dengan hasil yang "
                  f"sudah diketahui sebelum awal bulan. Hasil per transaksi setelah biaya (lihat sheet Asumsi).")
    summ["A2"].font = FONT
    head = ["Menu", "Minggu", "Jumlah rekomendasi", "Selesai", "Untung", "Tingkat menang",
            "Rata-rata hasil bersih", "Total untung/rugi per 1 lot (Rp)"]
    row = 4
    summ.cell(row, 1, "Ringkasan bulanan").font = BOLD
    row += 1
    for j, h in enumerate(head, 1):
        c = summ.cell(row, j, h)
        c.font, c.fill, c.alignment = BOLD, HEAD, Alignment(wrap_text=True)
    for label, rng, crit in menus:
        row += 1
        stats_row(summ, row, label, rng, crit)
        summ.cell(row, 2, "Sebulan").font = FONT
    row += 2
    summ.cell(row, 1, "Pembanding").font = BOLD
    notes = [("BSJP – semua saham likuid (rata-rata hasil bersih)", info["bsjp_base"], "0.00%;-0.00%;0.00%"),
             ("Skor uji model BSJP sebelum bulan ini (AUC)", info["bsjp_auc"], "0.000"),
             ("Skor uji model Harian (AUC)", info["daily"], "0.000"),
             ("Skor uji model Swing (AUC)", info["swing"], "0.000")]
    for label, v, fmt in notes:
        row += 1
        summ.cell(row, 1, label).font = FONT
        c = summ.cell(row, 7, None if pd.isna(v) else float(v))
        c.font, c.number_format = FONT, fmt
    summ.cell(row + 1, 1, "AUC 0,5 = sama dengan menebak acak; aplikasi menganggap model terbukti jika AUC ≥ 0,53. "
                          "Nilai pembanding dihitung oleh report.py.").font = Font(name="Arial", size=9, italic=True)
    row += 3
    summ.cell(row, 1, "Ringkasan mingguan").font = BOLD
    row += 1
    for j, h in enumerate(head, 1):
        c = summ.cell(row, j, h)
        c.font, c.fill, c.alignment = BOLD, HEAD, Alignment(wrap_text=True)
    weeks = sorted(set(bsjp.get("Minggu", pd.Series(dtype=str))) | set(rek.get("Minggu", pd.Series(dtype=str))))
    for w in weeks:
        for label, rng, crit in menus:
            row += 1
            stats_row(summ, row, label, rng, crit, w)
    for j, wd in enumerate([26, 24, 13, 10, 10, 12, 14, 18], 1):
        summ.column_dimensions[get_column_letter(j)].width = wd
    summ.row_dimensions[5].height = 30
    summ.freeze_panes = "A4"
    return wb


if __name__ == "__main__":
    month = sys.argv[1] if len(sys.argv) > 1 else f"{datetime.now(timing.WIB):%Y-%m}"
    bsjp, rek, info, _ = replay(*month_range(month))
    OUT.mkdir(exist_ok=True)
    path = OUT / f"idx_trader_{month}.xlsx"
    build(f"bulan {month}", bsjp, rek, info).save(path)
    bsjp.to_csv(OUT / f"idx_trader_{month}_bsjp.csv", index=False)
    rek.to_csv(OUT / f"idx_trader_{month}_rekomendasi.csv", index=False)
    print(path, len(bsjp), "BSJP rows,", len(rek), "rekomendasi rows")
