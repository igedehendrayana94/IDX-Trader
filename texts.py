"""UI text, Indonesian and English.
Indonesian follows KBBI forms and the Jutif term rules: standard Indonesian where it exists, English in italics
where no standard term exists (swing, stop loss, backtest, walk-forward, machine learning). Add every string to both."""

T = {
    "en": {
        "subtitle": "Stock ideas for the Indonesia Stock Exchange, explained step by step.",
        "disclaimer": "Public data (yfinance, daily, delayed). The app does not place orders: you buy and sell "
                      "yourself in the Stockbit app. Not investment advice.",
        # sidebar
        "mode": "Trading style", "swing": "Swing", "daily": "Daily",
        "swing_cap": "Hold a few days, up to 10. Calmer, fewer checks per day.",
        "daily_cap": "Buy at the open, sell within the day. Needs you to watch the market.",
        "capital": "Your capital (Rp)", "capital_help": "Money you are ready to use for trading. Use money you can afford to lose.",
        "capital_ph": "Example: 1,000,000", "capital_min": "Minimum capital is Rp 1,000,000. Example: 1,000,000",
        "advanced": "Advanced settings",
        "alloc": "Max share of capital per stock (%)",
        "alloc_help": "Spreading money across several stocks lowers the damage from one bad trade.",
        "min_value": "Min avg daily trading value (Rp billion)",
        "min_value_help": "Skips quiet stocks that are hard to buy and sell quickly.",
        "universe": "Stock list (IDX codes)", "use_ihsg": "Use IHSG features in the ML model",
        "refresh": "Refresh data",
        "rules": "Stop loss is never more than {loss} below the buy price. Fees: buy {buy}, sell {sell}.",
        "downloading": "Downloading prices...", "training": "Training the ML model...",
        "no_data": "No data for: ", "no_liquid": "No stock passes the liquidity filter. Lower it in Advanced settings.",
        # header
        "kpi_buys": "Buy ideas today", "kpi_ihsg": "IHSG (market index)", "kpi_ml": "Use ML model?",
        "kpi_date": "Data as of", "ml_on": "Yes", "ml_off": "No",
        # tabs
        "tab_rec": "Recommendations", "tab_ml": "ML prediction", "tab_all": "All stocks", "tab_guide": "Guide",
        # recommendations
        "rec_intro": "Stocks that meet **all** {n} conditions of the {mode} style today. "
                     "Buy at the next market open, then set the stop loss and target in Stockbit right away.",
        "buy": "Buy", "entry": "Buy price", "stop": "Stop loss", "target": "Target", "lots": "Lots",
        "stop_help": "Sell here to cut the loss if the price falls.",
        "target_help": "Sell here to take the profit.",
        "lots_help": "1 lot = 100 shares.",
        "money": "Uses **Rp {cost}** of your capital. If the price hits the stop loss, you lose at most "
                 "**Rp {maxloss}** ({pct} of your capital).",
        "why": "Why this stock", "ml_line": "ML model: **{prob}** chance this plan ends in profit "
                                            "(average stock: {base}).",
        "ml_skip": "The ML model has no proven edge for this style, so it is not shown here.",
        "history": "Past 5 years with the same rule: {n} trades, {win} won, average {avg} per trade.",
        "history_none": "Past 5 years: this rule never triggered on this stock.",
        "history_bad": "On this stock, this rule lost money on average in the past. Consider a smaller position "
                       "or skip it.",
        "open_stockbit": "Open {code} in Stockbit",
        "tab_pos": "My positions",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "phase": {"pre_open": "Pre-opening: orders can be placed", "session1": "Session 1 open",
                  "break": "Lunch break", "session2": "Session 2 open", "pre_close": "Pre-closing auction",
                  "closed": "Market closed"},
        "until": "until {when}", "opens": "opens {when}",
        "plan_title": "When to act",
        "plan_buy": "Place buy order", "plan_buy_v": "{day}, 08:45–08:59 (pre-opening), limit price {price}",
        "plan_protect": "Right after it is bought", "plan_protect_v": "Auto Order: stop loss {stop}, target {target}",
        "plan_check": "Every trading day", "plan_check_v": "After 16:15: open My positions in this app",
        "plan_exit": "Sell at the latest", "plan_exit_v": "{day}, 15:50–16:00 (pre-closing) if stop loss/target not hit",
        "add_pos": "Add a stock I bought", "pos_code": "Stock code", "pos_mode": "Trading style",
        "pos_date": "Buy date", "pos_price": "Buy price", "pos_lots": "Lots", "pos_save": "Save position",
        "pos_saved": "Position saved.", "pos_bad": "Fill in a buy price above 0, at least 1 lot and a date that is not in the future.",
        "pos_none": "No positions yet. After you buy in Stockbit, add the stock here to get hold or sell advice every day.",
        "pos_delete": "Remove", "pos_err": "{code}: not enough price history before {day}.",
        "pnl": "Profit/loss now", "held": "Days held", "pos_confirm": "Remove {code} from My positions? This does not sell anything in Stockbit.", "day_n": "Day {n} of {m}", "deadline": "Sell at the latest",
        "act": {
            "hold": ("HOLD", "up", "No reason to sell yet. Make sure the Auto Order for stop loss and target is active in Stockbit."),
            "hold_last": ("SELL TODAY", "down", "Today is the last day of this plan. If stop loss/target is still not hit, sell in pre-closing (15:50–16:00)."),
            "wait_data": ("WAIT", "flat", "No closed trading day since the buy date yet. Make sure the Auto Order for stop loss and target is active."),
            "sell_stop": ("SELL", "down", "Price touched the stop loss {stop}. If your Auto Order was active, the stock is probably sold already: check Portfolio in Stockbit. If not, sell in the next session."),
            "sell_target": ("SELL: TAKE PROFIT", "up", "Price reached the target {target}. If your Auto Order was active, check Portfolio in Stockbit. If not, sell in the next session."),
            "sell_time": ("SELL", "down", "The {m}-day time limit has passed. Sell in the next session; the plan's reason to hold is over."),
            "warn_trend": ("CONSIDER SELLING", "down", "Price closed below its 20-day average: the uptrend is weakening. Selling early limits the loss, or raise the stop loss to your buy price."),
        },
        "hours_title": "IDX trading hours (WIB)",
        "hours": ["Pre-opening 08:45–09:00: orders can already be placed",
                  "Session 1: 09:00–12:00 (Friday 09:00–11:30)",
                  "Session 2: 13:30–15:50 (Friday 14:00–15:50)",
                  "Pre-closing 15:50–16:00: closing price auction",
                  "Exchange holidays are not included in this app's dates: check the IDX calendar."],
        "ml_why": "Method: gradient boosting, usually the most accurate choice for table data such as stock "
                  "indicators. It is tested walk-forward so it never peeks at the future.",
        "cta_buy": "BUY {code} IN STOCKBIT", "total": "Total cost", "maxloss": "Max loss",
        "of_capital": "of capital", "conds": "{a}/{b} conditions", "full_table": "Full table (advanced)",
        "ihsg_name": "Jakarta Composite Index", "ml_short": "ML model",
        "none_title": "No stock meets all conditions today.",
        "none_body": "Not buying is a valid decision. Forcing a trade without a signal is the most common "
                     "beginner mistake.",
        "near_title": "Almost there: watch these",
        "near_intro": "These stocks meet all but one condition. They are not buy signals yet.",
        "near_missing": "Still missing: {cond}",
        "zero_lots": "Capital too small to buy 1 lot of: {codes}.",
        # ML tab
        "ml_intro": "The model learned from 5 years of prices to estimate the chance that each stock's "
                    "trade plan (buy price, stop loss, target) ends in profit.",
        "ml_good": "In testing on data it never saw, the model picked winners better than chance. "
                   "Use it as a second opinion next to the conditions, not on its own.",
        "ml_bad": "In testing on data it never saw, the model was no better than a coin flip for this style. "
                  "Ignore its numbers for now.",
        "auc": "Test score (AUC)", "auc_help": "0.5 = coin flip. Above about 0.55 = useful.",
        "top": "Highest chance of profit", "prob": "Chance of profit",
        "details": "Test details (for advanced users)",
        "ml_tech": "Gradient boosting (scikit-learn HistGradientBoosting) on price, trend, momentum, volume and "
                   "market features. Validated walk-forward: each block is predicted by a model trained only on "
                   "earlier data.",
        "foreign_ok": "Foreign flow: {n} trading days loaded from data/foreign{used}.",
        "foreign_used": ", used by the model", "foreign_wait": ", the model uses it from 60 days",
        "foreign_none": "Foreign flow: no files yet. Download 'Ringkasan Saham' (Excel) for each day from "
                        "idx.co.id > Data Pasar > Ringkasan Perdagangan, then save it in data/foreign/ with the "
                        "date in the file name (YYYYMMDD).",
        # all stocks tab
        "all_intro": "Every stock in the list, best match first.",
        "only_signal": "Show only full signals",
        "footer": "Backtest: past 5 years, buy at the next open after each signal, sell at stop loss, target or "
                  "time limit, fees included. Few trades means weak evidence.",
        # guide tab
        "guide_steps_title": "How to use this app",
        "guide_steps": [
            "Pick your **trading style** in the sidebar: Swing if you cannot watch the market all day.",
            "Enter your **capital**. Start small while you learn.",
            "Open **Recommendations**. If there is no buy idea, do nothing today.",
            "If there is one, open the stock in **Stockbit** and buy the shown number of lots at the market open.",
            "Right after buying, set the **stop loss** and **target** with Stockbit's Auto Order.",
            "Do not move the stop loss lower. Accept small losses; they are part of trading.",
        ],
        "guide_terms_title": "Terms",
        "guide_risk_title": "Before you start",
        "guide_risk": [
            "Past results do not guarantee future results. Every trade can lose.",
            "Only use money you will not need in the next year.",
            "Do not put all your capital in one stock.",
        ],
    },
    "id": {
        "subtitle": "Ide saham Bursa Efek Indonesia yang dijelaskan langkah demi langkah.",
        "disclaimer": "Data publik (yfinance, harian, dengan jeda). Aplikasi ini tidak melakukan pemesanan: beli "
                      "dan jual dilakukan sendiri melalui aplikasi Stockbit. Bukan saran investasi.",
        "mode": "Gaya trading", "swing": "*Swing*", "daily": "Harian",
        "swing_cap": "Tahan beberapa hari, paling lama 10 hari. Lebih santai, tidak perlu sering memantau.",
        "daily_cap": "Beli saat pasar buka, jual pada hari yang sama. Perlu memantau pasar.",
        "capital": "Modal (Rp)", "capital_ph": "Contoh: 1.000.000",
        "capital_min": "Modal minimal Rp 1.000.000. Contoh: 1.000.000", "capital_help": "Uang yang siap dipakai untuk trading. Pakai uang yang siap "
                                                 "ditanggung jika rugi.",
        "advanced": "Pengaturan lanjutan",
        "alloc": "Porsi modal maksimum per saham (%)",
        "alloc_help": "Membagi modal ke beberapa saham mengurangi dampak satu transaksi yang rugi.",
        "min_value": "Nilai transaksi rata-rata harian minimum (miliar Rp)",
        "min_value_help": "Melewati saham sepi yang sulit dibeli dan dijual dengan cepat.",
        "universe": "Daftar saham (kode BEI)", "use_ihsg": "Pakai fitur IHSG pada model *machine learning*",
        "refresh": "Perbarui data",
        "rules": "*Stop loss* paling jauh {loss} di bawah harga beli. Biaya: beli {buy}, jual {sell}.",
        "downloading": "Mengunduh data harga...", "training": "Melatih model machine learning...",
        "no_data": "Data tidak tersedia: ",
        "no_liquid": "Tidak ada saham yang lolos filter likuiditas. Turunkan batasnya di Pengaturan lanjutan.",
        "kpi_buys": "Ide beli hari ini", "kpi_ihsg": "IHSG (indeks pasar)", "kpi_ml": "Pakai model ML?",
        "kpi_date": "Data per tanggal", "ml_on": "Ya", "ml_off": "Tidak",
        "tab_rec": "Rekomendasi", "tab_ml": "Prediksi ML", "tab_all": "Semua saham", "tab_guide": "Panduan",
        "rec_intro": "Saham yang memenuhi **semua** ({n}) syarat gaya {mode} hari ini. Beli saat pasar buka "
                     "berikutnya, lalu segera pasang *stop loss* dan target di Stockbit.",
        "buy": "Beli", "entry": "Harga beli", "stop": "Stop loss", "target": "Target", "lots": "Lot",
        "stop_help": "Jual di harga ini untuk membatasi rugi jika harga turun.",
        "target_help": "Jual di harga ini untuk mengambil untung.",
        "lots_help": "1 lot = 100 lembar saham.",
        "money": "Memakai **Rp {cost}** dari modal. Jika harga menyentuh *stop loss*, rugi paling besar "
                 "**Rp {maxloss}** ({pct} dari modal).",
        "why": "Alasan saham ini dipilih",
        "ml_line": "Model ML: peluang rencana ini berakhir untung **{prob}** (rata-rata saham: {base}).",
        "ml_skip": "Model ML belum terbukti unggul untuk gaya ini, jadi tidak ditampilkan di sini.",
        "history": "Lima tahun terakhir dengan aturan yang sama: {n} transaksi, {win} untung, rata-rata {avg} "
                   "per transaksi.",
        "history_none": "Lima tahun terakhir: aturan ini belum pernah muncul pada saham ini.",
        "history_bad": "Pada saham ini, aturan yang sama rata-rata merugi pada masa lalu. Pertimbangkan jumlah lot "
                       "yang lebih kecil atau lewati saham ini.",
        "open_stockbit": "Buka {code} di Stockbit",
        "tab_pos": "Posisi saya",
        "days": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"],
        "phase": {"pre_open": "Pra-pembukaan: order sudah bisa dipasang", "session1": "Sesi 1 berlangsung",
                  "break": "Istirahat siang", "session2": "Sesi 2 berlangsung", "pre_close": "Pra-penutupan",
                  "closed": "Pasar tutup"},
        "until": "sampai {when}", "opens": "buka {when}",
        "plan_title": "Kapan bertindak",
        "plan_buy": "Pasang order beli", "plan_buy_v": "{day}, 08:45–08:59 (pra-pembukaan), harga limit {price}",
        "plan_protect": "Segera setelah terbeli", "plan_protect_v": "Auto Order: stop loss {stop}, target {target}",
        "plan_check": "Setiap hari bursa", "plan_check_v": "Setelah 16:15: buka Posisi saya di aplikasi ini",
        "plan_exit": "Jual paling lambat", "plan_exit_v": "{day}, 15:50–16:00 (pra-penutupan) jika stop loss/target belum tersentuh",
        "add_pos": "Tambah saham yang sudah dibeli", "pos_code": "Kode saham", "pos_mode": "Gaya trading",
        "pos_date": "Tanggal beli", "pos_price": "Harga beli", "pos_lots": "Lot", "pos_save": "Simpan posisi",
        "pos_saved": "Posisi tersimpan.", "pos_bad": "Isi harga beli di atas 0, minimal 1 lot, dan tanggal yang tidak melewati hari ini.",
        "pos_none": "Belum ada posisi. Setelah membeli di Stockbit, tambahkan sahamnya di sini untuk mendapat saran tahan atau jual setiap hari.",
        "pos_delete": "Hapus", "pos_err": "{code}: riwayat harga sebelum {day} tidak cukup.",
        "pnl": "Untung/rugi saat ini", "held": "Lama ditahan", "pos_confirm": "Hapus {code} dari Posisi saya? Ini tidak menjual apa pun di Stockbit.", "day_n": "Hari ke-{n} dari {m}", "deadline": "Jual paling lambat",
        "act": {
            "hold": ("TAHAN", "up", "Belum ada alasan menjual. Pastikan Auto Order stop loss dan target aktif di Stockbit."),
            "hold_last": ("JUAL HARI INI", "down", "Hari ini hari terakhir rencana ini. Jika stop loss/target belum tersentuh, jual pada pra-penutupan (15:50–16:00)."),
            "wait_data": ("TUNGGU", "flat", "Belum ada hari bursa yang selesai sejak tanggal beli. Pastikan Auto Order stop loss dan target sudah aktif."),
            "sell_stop": ("JUAL", "down", "Harga sudah menyentuh stop loss {stop}. Jika Auto Order aktif, saham kemungkinan sudah terjual: cek Portfolio di Stockbit. Jika belum, jual pada sesi berikutnya."),
            "sell_target": ("JUAL: AMBIL UNTUNG", "up", "Harga sudah mencapai target {target}. Jika Auto Order aktif, cek Portfolio di Stockbit. Jika belum, jual pada sesi berikutnya."),
            "sell_time": ("JUAL", "down", "Batas waktu {m} hari sudah lewat. Jual pada sesi berikutnya karena alasan menahan saham sudah selesai."),
            "warn_trend": ("PERTIMBANGKAN JUAL", "down", "Harga ditutup di bawah rata-rata 20 hari: tren naik melemah. Jual lebih awal untuk membatasi rugi, atau naikkan stop loss ke harga beli."),
        },
        "hours_title": "Jam perdagangan BEI (WIB)",
        "hours": ["Pra-pembukaan 08:45–09:00: order sudah bisa dipasang",
                  "Sesi 1: 09:00–12:00 (Jumat 09:00–11:30)",
                  "Sesi 2: 13:30–15:50 (Jumat 14:00–15:50)",
                  "Pra-penutupan 15:50–16:00: lelang harga penutupan",
                  "Hari libur bursa belum diperhitungkan dalam tanggal aplikasi ini: cek kalender BEI."],
        "ml_why": "Metode: *gradient boosting*, umumnya pilihan paling akurat untuk data tabel seperti indikator "
                  "saham. Model diuji dengan metode *walk-forward* sehingga tidak pernah melihat data masa depan.",
        "cta_buy": "BELI {code} DI STOCKBIT", "total": "Total biaya", "maxloss": "Rugi maks.",
        "of_capital": "dari modal", "conds": "{a}/{b} syarat", "full_table": "Tabel lengkap (lanjutan)",
        "ihsg_name": "Indeks Harga Saham Gabungan", "ml_short": "Model ML",
        "none_title": "Hari ini belum ada saham yang memenuhi semua syarat.",
        "none_body": "Tidak membeli juga merupakan keputusan yang sah. Memaksakan transaksi tanpa sinyal adalah "
                     "kesalahan yang paling sering dilakukan pemula.",
        "near_title": "Hampir memenuhi syarat: layak dipantau",
        "near_intro": "Saham berikut memenuhi semua syarat kecuali satu. Saham ini belum menjadi sinyal beli.",
        "near_missing": "Belum terpenuhi: {cond}",
        "zero_lots": "Modal belum cukup untuk membeli 1 lot: {codes}.",
        "ml_intro": "Model ini belajar dari data harga lima tahun untuk memperkirakan peluang rencana transaksi "
                    "setiap saham (harga beli, *stop loss*, target) berakhir untung.",
        "ml_good": "Pada pengujian dengan data yang belum pernah dilihat, model memilih saham untung lebih baik "
                   "daripada menebak acak. Pakai sebagai pendapat kedua di samping syarat, bukan satu-satunya dasar.",
        "ml_bad": "Pada pengujian dengan data yang belum pernah dilihat, model tidak lebih baik daripada menebak "
                  "acak untuk gaya ini. Abaikan angkanya untuk sementara.",
        "auc": "Skor pengujian (AUC)", "auc_help": "0,5 = sama dengan menebak acak. Di atas ±0,55 = berguna.",
        "top": "Peluang untung tertinggi", "prob": "Peluang untung",
        "details": "Detail pengujian (untuk pengguna mahir)",
        "ml_tech": "Model *gradient boosting* (scikit-learn HistGradientBoosting) dengan fitur harga, tren, "
                   "momentum, volume, dan kondisi pasar. Validasi memakai metode *walk-forward*: setiap blok "
                   "diprediksi oleh model yang hanya dilatih dengan data sebelumnya.",
        "foreign_ok": "Aliran dana asing (*foreign flow*): {n} hari perdagangan dimuat dari data/foreign{used}.",
        "foreign_used": ", dipakai oleh model", "foreign_wait": ", model memakainya mulai 60 hari",
        "foreign_none": "Aliran dana asing (*foreign flow*): belum ada berkas. Unduh 'Ringkasan Saham' (Excel) "
                        "untuk setiap hari dari idx.co.id > Data Pasar > Ringkasan Perdagangan, lalu simpan ke "
                        "data/foreign/ dengan tanggal pada nama berkas (YYYYMMDD).",
        "all_intro": "Semua saham dalam daftar, urut dari yang paling cocok.",
        "only_signal": "Tampilkan hanya sinyal penuh",
        "footer": "Uji historis (*backtest*): lima tahun terakhir, beli pada harga pembukaan setelah setiap sinyal, "
                  "jual pada *stop loss*, target, atau batas waktu, sudah termasuk biaya. Jumlah transaksi yang "
                  "sedikit berarti bukti lemah.",
        "guide_steps_title": "Cara memakai aplikasi",
        "guide_steps": [
            "Pilih **gaya trading** di panel samping: *Swing* jika tidak bisa memantau pasar sepanjang hari.",
            "Isi **modal**. Mulai dengan jumlah kecil selama masih belajar.",
            "Buka **Rekomendasi**. Jika tidak ada ide beli, jangan bertransaksi hari ini.",
            "Jika ada, buka saham tersebut di **Stockbit** dan beli sejumlah lot yang tertera saat pasar buka.",
            "Segera setelah membeli, pasang ***stop loss*** dan **target** melalui fitur Auto Order di Stockbit.",
            "Jangan menurunkan *stop loss*. Rugi kecil adalah bagian wajar dari trading.",
        ],
        "guide_terms_title": "Daftar istilah",
        "guide_risk_title": "Sebelum memulai",
        "guide_risk": [
            "Hasil masa lalu tidak menjamin hasil masa depan. Setiap transaksi bisa rugi.",
            "Pakai hanya uang yang tidak dibutuhkan dalam satu tahun ke depan.",
            "Jangan menaruh seluruh modal pada satu saham.",
        ],
    },
}

# plain-language name of each signal condition
COND = {
    "en": {
        "uptrend": "Uptrend: price above its 20- and 50-day averages",
        "rsi_ok": "RSI 45–70: rising but not overheated",
        "macd_up": "MACD momentum getting stronger",
        "volume": "Trading volume above normal (1.2×)",
        "breakout": "Broke above its 20-day high",
        "strong_close": "Closed near the day's high",
        "vol_spike": "Volume spike (2× normal or more)",
        "green": "Price rose today",
    },
    "id": {
        "uptrend": "Tren naik: harga di atas rata-rata 20 dan 50 hari",
        "rsi_ok": "RSI 45–70: naik, tetapi belum jenuh beli",
        "macd_up": "Momentum MACD menguat",
        "volume": "Volume transaksi di atas normal (1,2×)",
        "breakout": "Menembus harga tertinggi 20 hari",
        "strong_close": "Ditutup dekat harga tertinggi hari ini",
        "vol_spike": "Lonjakan volume (2× normal atau lebih)",
        "green": "Harga naik hari ini",
    },
}

# column: (label, help) per language
COLS = {
    "en": {
        "code": ("Code", "IDX stock code"), "signal": ("Signal", "Meets every condition"),
        "score": ("Score", "Number of conditions met"), "ml_prob": ("Chance of profit", "ML model estimate"),
        "close": ("Close", "Last closing price"), "chg%": ("Change %", "Price change today"),
        "entry": ("Buy price", "Suggested buy price"), "stop": ("Stop loss", "Sell here to cut the loss"),
        "target": ("Target", "Sell here to take profit"), "loss%": ("Max loss %", "Distance to stop loss"),
        "lots": ("Lots", "1 lot = 100 shares"), "cost_rp": ("Cost (Rp)", "Buy cost including fee"),
        "max_loss_rp": ("Max loss (Rp)", "Loss if the stop loss is hit, fees included"),
        "value20_bn": ("Daily value (Rp bn)", "Average daily trading value, 20 days"),
        "rsi": ("RSI", "Relative Strength Index, 14 days"),
        "bt_trades": ("Past trades", "Backtest trades in 5 years"),
        "bt_win%": ("Past win %", "Share of backtest trades that made money"),
        "bt_avg%": ("Past avg %", "Average backtest return per trade, fees included"),
    },
    "id": {
        "code": ("Kode", "Kode saham BEI"), "signal": ("Sinyal", "Memenuhi semua syarat"),
        "score": ("Skor", "Jumlah syarat yang terpenuhi"), "ml_prob": ("Peluang untung", "Perkiraan model ML"),
        "close": ("Penutupan", "Harga penutupan terakhir"), "chg%": ("Perubahan %", "Perubahan harga hari ini"),
        "entry": ("Harga beli", "Saran harga beli"), "stop": ("Stop loss", "Jual di sini untuk membatasi rugi"),
        "target": ("Target", "Jual di sini untuk mengambil untung"),
        "loss%": ("Rugi maks. %", "Jarak ke stop loss"),
        "lots": ("Lot", "1 lot = 100 lembar saham"), "cost_rp": ("Biaya (Rp)", "Biaya beli termasuk komisi"),
        "max_loss_rp": ("Rugi maks. (Rp)", "Rugi jika stop loss tersentuh, termasuk biaya"),
        "value20_bn": ("Nilai harian (miliar Rp)", "Rata-rata nilai transaksi harian, 20 hari"),
        "rsi": ("RSI", "Relative Strength Index, 14 hari"),
        "bt_trades": ("Transaksi lalu", "Jumlah transaksi uji historis dalam 5 tahun"),
        "bt_win%": ("Untung lalu %", "Persentase transaksi uji historis yang untung"),
        "bt_avg%": ("Rata-rata lalu %", "Rata-rata hasil uji historis per transaksi, termasuk biaya"),
    },
}

GLOSSARY = {
    "en": [
        ("Lot", "The buying unit on IDX. 1 lot = 100 shares."),
        ("Stop loss", "A price where you sell to cut a loss. Set it right after buying."),
        ("Target", "A price where you sell to take profit (also called take profit)."),
        ("Swing", "Holding a stock for a few days to catch a short price move."),
        ("Uptrend", "Price keeps making higher highs; here: price above its 20- and 50-day averages."),
        ("RSI", "Measures how fast price rose. Above 70 is often overheated."),
        ("MACD", "Measures momentum: whether the rise is speeding up or slowing down."),
        ("Volume", "Number of shares traded. A rise with high volume is more convincing."),
        ("IHSG", "Jakarta Composite Index: the average movement of the whole market."),
        ("Foreign flow", "Net buying or selling by foreign investors."),
        ("Backtest", "Testing a rule on past prices to see how it would have done."),
        ("AUC", "Test score of the ML model. 0.5 = coin flip, higher is better."),
    ],
    "id": [
        ("Lot", "Satuan pembelian di BEI. 1 lot = 100 lembar saham."),
        ("*Stop loss*", "Harga untuk menjual saham agar rugi tidak membesar. Pasang segera setelah membeli."),
        ("Target", "Harga untuk menjual saham dan mengambil untung (*take profit*)."),
        ("*Swing*", "Menahan saham beberapa hari untuk menangkap pergerakan harga jangka pendek."),
        ("Tren naik", "Harga terus mencetak puncak baru; di sini: harga di atas rata-rata 20 dan 50 hari."),
        ("RSI", "Mengukur seberapa cepat harga naik. Di atas 70 sering berarti jenuh beli."),
        ("MACD", "Mengukur momentum: apakah kenaikan makin cepat atau melambat."),
        ("Volume", "Jumlah saham yang diperdagangkan. Kenaikan dengan volume tinggi lebih meyakinkan."),
        ("IHSG", "Indeks Harga Saham Gabungan: rata-rata pergerakan seluruh pasar."),
        ("Aliran dana asing", "Selisih pembelian dan penjualan oleh investor asing (*foreign flow*)."),
        ("Uji historis", "Menguji aturan pada harga masa lalu untuk melihat hasilnya (*backtest*)."),
        ("AUC", "Skor pengujian model ML. 0,5 = sama dengan menebak acak, makin tinggi makin baik."),
    ],
}
