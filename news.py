"""News per stock from Google News RSS (Indonesian), scored with a keyword list.
History is only a few weeks, so the score is NOT used in signals or ML; it is shown on cards, and hard red flags
(suspension, PKPU, bankruptcy, default, UMA) block a buy in the risk gate. Headlines are saved daily under
data/news/ so the score can be tested once enough history exists."""
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

URL = "https://news.google.com/rss/search?q={q}&hl=id&gl=ID&ceid=ID:id"

# shortcut: keyword list, crude on nuance (negation, sarcasm); upgrade to a model once data/news/ has months of history
POS = ["laba naik", "laba tumbuh", "laba melonjak", "laba bersih naik", "pendapatan naik", "kinerja positif",
       "menguat", "melonjak", "meroket", "melesat", "rekor", "dividen", "buyback", "akuisisi", "ekspansi",
       "kontrak baru", "rekomendasi beli", "target harga naik", "upgrade", "asing borong", "net buy", "bullish",
       "naik", "untung", "cuan"]
NEG = ["laba turun", "laba anjlok", "rugi", "pendapatan turun", "kinerja negatif", "melemah", "anjlok", "ambruk",
       "merosot", "longsor", "terjun", "downgrade", "asing lepas", "net sell", "bearish", "gugatan", "sanksi", "denda",
       "phk", "turun", "tekanan", "boncos"]
RED = ["suspen", "penghentian sementara", "pkpu", "pailit", "gagal bayar", "delisting", "fraud"]  # substrings
RED_CASE = [r"\bUMA\b", r"\bFCA\b", r"\bdefault\b"]  # matched case-sensitive: "uma"/"fca" are also plain words


def _hits(text, words):
    t = text.lower()
    return [w for w in words if re.search(rf"\b{re.escape(w)}\b", t)]


def score(title):
    """+1 positive, -1 negative, 0 neutral/mixed. Longer phrases win over the single words inside them."""
    pos, neg = _hits(title, POS), _hits(title, NEG)
    pos = [w for w in pos if not any(w != n and w in n for n in neg)]  # "laba turun" beats "laba"
    neg = [w for w in neg if not any(w != p and w in p for p in pos)]  # "laba naik" beats "naik"
    return (len(pos) > len(neg)) - (len(neg) > len(pos))


def red_flag(title):
    return any(w in title.lower() for w in RED) or any(re.search(p, title) for p in RED_CASE)


def parse(xml_text, code, days=7, now=None):
    """Items mentioning the code in the title, newest first, from the last `days` days."""
    now = now or datetime.now(timezone.utc)
    out = []
    for it in ET.fromstring(xml_text).iter("item"):
        title = it.findtext("title") or ""
        if not re.search(rf"\b{code}\b", title.upper()):
            continue  # Google matches loosely; keep only headlines about this stock
        try:
            when = parsedate_to_datetime(it.findtext("pubDate"))
        except (TypeError, ValueError):
            continue
        if now - when > timedelta(days=days):
            continue
        out.append({"code": code, "title": title, "link": it.findtext("link") or "",
                    "source": it.findtext("source") or "", "time": when.isoformat(),
                    "score": score(title), "red": red_flag(title)})
    return sorted(out, key=lambda x: x["time"], reverse=True)


def fetch(code, days=7):
    """Headlines for one stock; [] when Google News is unreachable."""
    req = urllib.request.Request(URL.format(q=urllib.parse.quote(f"saham {code}")),
                                 headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return parse(r.read().decode("utf-8", "replace"), code, days)
    except (OSError, ET.ParseError):
        return []


def summary(items):
    return {"n": len(items), "pos": sum(i["score"] > 0 for i in items), "neg": sum(i["score"] < 0 for i in items),
            "red": [i for i in items if i["red"]]}


def save(items, folder, day):
    """Append headlines to data/news/YYYYMMDD.json, one entry per link."""
    if not items:
        return
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / f"{day:%Y%m%d}.json"
    old = json.loads(f.read_text()) if f.exists() else []
    seen = {i["link"] for i in old}
    f.write_text(json.dumps(old + [i for i in items if i["link"] not in seen], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    import tempfile
    assert score("Laba BBCA naik 12%, saham menguat") == 1
    assert score("Laba BBCA turun, saham anjlok") == -1
    assert score("BBCA hari ini") == 0
    assert red_flag("BEI suspensi saham ABCD") and red_flag("ABCD disuspensi") and red_flag("Saham ABCD masuk UMA")
    assert not red_flag("umat")
    assert not red_flag("Saham ABCD naik")
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    rss = """<rss><channel>
      <item><title>Laba BBCA naik, saham menguat - Kontan</title><link>a</link>
            <pubDate>Mon, 16 Nov 2026 02:00:00 GMT</pubDate><source>Kontan</source></item>
      <item><title>IHSG ditutup melemah - CNBC</title><link>b</link><pubDate>Mon, 16 Nov 2026 03:00:00 GMT</pubDate></item>
      <item><title>BBCA disuspensi BEI - X</title><link>c</link><pubDate>Mon, 16 Nov 2026 04:00:00 GMT</pubDate></item>
      <item><title>BBCA lama - X</title><link>d</link><pubDate>Mon, 02 Nov 2026 04:00:00 GMT</pubDate></item>
    </channel></rss>"""
    items = parse(rss, "BBCA", now=now)
    assert [i["link"] for i in items] == ["c", "a"], items  # other stock and >7 days old dropped, newest first
    s = summary(items)
    assert s["n"] == 2 and s["pos"] == 1 and len(s["red"]) == 1
    with tempfile.TemporaryDirectory() as tmp:
        save(items, tmp, now)
        save(items, tmp, now)  # same links: no duplicates
        assert len(json.loads((Path(tmp) / "20261116.json").read_text())) == 2
    print("ok")
