"""Step 2 (Marvin's piece, done by Elia): FAA ATADS/OPSNET tower operations.

Source: https://aspm.faa.gov/opsnet/sys/Airport.asp (public, no login). The page builds an SQL string
in the browser and posts it to opsnet-server-x.asp; this script sends the same form.

Outputs (alan/elia_output/data/processed/):
  opsnet_lax_monthly.csv          LAX monthly operations by category, 2015-01 to 2025-12
  opsnet_daily_superbowl.csv      daily operations at LAX and nearby GA fields around Super Bowl LVI
                                  (13 Feb 2022, SoFi) and the same calendar window in control years
  opsnet_vs_lawa_crosscheck.csv   LAX monthly OPSNET vs LAWA TCOM (from fetch_lawa_tcom.py)

Columns follow the ATADS standard report: itinerant air_carrier, air_taxi, general_aviation, military,
local civil (local_ga), local military, total. One operation = one takeoff or one landing.
"""
import csv
import datetime as dt
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # alan/elia_output/
OUT = ROOT / "data" / "processed"
FORM = "https://www.aspm.faa.gov/opsnet/sys/Airport.asp"
SERVER = "https://www.aspm.faa.gov/opsnet/sys/opsnet-server-x.asp"
COLS = ["air_carrier", "air_taxi", "general_aviation", "military", "itinerant_total",
        "local_ga", "local_military", "local_total", "total"]
CALC = (" ,SUM(IFR_ITIN_AC) AS IFR_ITIN_AC,SUM(IFR_ITIN_AT) AS IFR_ITIN_AT,SUM(IFR_ITIN_GA) AS IFR_ITIN_GA,"
        "SUM(IFR_ITIN_MI) AS IFR_ITIN_MI,SUM(IFR_ITIN_AC+IFR_ITIN_AT+IFR_ITIN_GA+IFR_ITIN_MI) AS TOT_ITII,"
        "SUM(VFR_ITIN_AC) AS VFR_ITIN_AC,SUM(VFR_ITIN_AT) AS VFR_ITIN_AT,SUM(VFR_ITIN_GA) AS VFR_ITIN_GA,"
        "SUM(VFR_ITIN_MI) AS VFR_ITIN_MI,SUM(VFR_ITIN_AC+VFR_ITIN_AT+VFR_ITIN_GA+VFR_ITIN_MI) AS TOT_ITIV,"
        "SUM(AC) AS AC,SUM(ATAXI) AS ATAXI,SUM(IFR_ITIN_GA+VFR_ITIN_GA) AS GA,SUM(IFR_ITIN_MI+VFR_ITIN_MI) AS MIL,"
        "SUM(AC+ATAXI+IFR_ITIN_GA+VFR_ITIN_GA+IFR_ITIN_MI+VFR_ITIN_MI) AS TOT_ITI,SUM(LOCAL_GA) AS LOCAL_GA,"
        "SUM(LOCAL_MIL) AS LOCAL_MIL,SUM(LOCAL_GA+LOCAL_MIL) AS TOT_LOC,SUM(TOTAL) AS TOTAL ")
# LAX plus the towered GA airports business jets use for LA events (Santa Monica kept although it shortened its runway in 2017)
EVENT_AIRPORTS = ["LAX", "VNY", "BUR", "HHR", "LGB", "SMO"]
# Super Bowl LVI week (game Sun 13 Feb 2022) and the same window in control years; 2023 game was in Phoenix
EVENT_WINDOWS = {2022: ("20220130", "20220226"), 2019: ("20190130", "20190226"),
                 2023: ("20230130", "20230226"), 2024: ("20240130", "20240226")}


class Opsnet:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [("User-Agent", "Mozilla/5.0 (SpartHill Hacks research)"), ("Referer", FORM)]
        page = self.op.open(FORM, timeout=60).read().decode("latin-1")
        self.defaults = self._form_defaults(page)

    @staticmethod
    def _form_defaults(page):
        form = page[page.find('name="mainForm"'):]
        form = form[:form.find("</form>")]
        out = {}
        for attrs in re.findall(r"<input([^>]*)>", form, re.I):
            name = re.search(r'name="?([^"\s>]+)', attrs, re.I)
            kind = (re.search(r'type="?([a-z]+)', attrs, re.I) or [None, "text"])[1].lower()
            if not name or kind in ("button", "submit"):
                continue
            if kind in ("checkbox", "radio") and not re.search(r"\bchecked\b", attrs, re.I):
                continue
            val = re.search(r'value="([^"]*)"|value=([^\s>]+)', attrs, re.I)
            out[name.group(1)] = (val.group(1) if val.group(1) is not None else val.group(2)) if val else ""
        return out

    def query(self, keys, where, style, dfld, start, end, locids):
        sql = f"select {keys}{CALC} from tower_day where {where} group by {keys} order by {keys}".upper()
        form = dict(self.defaults)
        form.update({"dstyle": style, "dfld": dfld, "dlist": "", "fromdate": start, "todate": end,
                     "keylist": keys, "llist": ",".join(f"'{x}'" for x in locids), "line": sql,
                     "cmd": "air_bas", "nopage": "y", "nost": "y", "oktosave": "y",
                     "additi": "y", "addloc": "y", "avgdays": "1", "reportformat": "asp"})
        for attempt in range(3):
            try:
                body = self.op.open(SERVER, data=urllib.parse.urlencode(form).encode(), timeout=120).read()
                break
            except urllib.error.HTTPError:
                time.sleep(3 * (attempt + 1))
        else:
            raise RuntimeError(f"OPSNET query failed: {sql[:120]}")
        return self._rows(body.decode("latin-1"))

    @staticmethod
    def _rows(page):
        rows = []
        for tr in re.findall(r"<tr>(.*?)</tr>", page, re.S | re.I):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
            if len(cells) == 11 and re.fullmatch(r"\d{2}/\d{2}(/\d{4})?|\d{2}/\d{4}", cells[0]):
                rows.append([cells[0], cells[1]] + [int(c.replace(",", "")) for c in cells[2:]])
        return rows


def write(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    api = Opsnet()

    monthly = []
    for year in range(2015, 2026):  # one year per request keeps responses small
        for date, loc, *vals in api.query("yyyymm,LOCID", f"yyyymm>={year}01 and yyyymm<={year}12 and locid in ('LAX')",
                                          "m", "yyyymm", f"{year}01", f"{year}12", ["LAX"]):
            m, y = date.split("/")
            monthly.append([int(y), int(m), loc, *vals, y in ("2020", "2021", "2022"), "verified_public", FORM, retrieved])
    write(OUT / "opsnet_lax_monthly.csv",
          ["year", "month", "locid", *COLS, "excluded_covid", "data_classification", "source", "retrieved_utc"], monthly)

    daily = []
    for year, (start, end) in EVENT_WINDOWS.items():
        for date, loc, *vals in api.query("yyyymmdd,LOCID", f"yyyymmdd>={start} and yyyymmdd<={end} and locid in ("
                                          + ",".join(f"'{a}'" for a in EVENT_AIRPORTS) + ")",
                                          "r", "yyyymmdd", start, end, EVENT_AIRPORTS):
            mm, dd, yy = date.split("/")
            daily.append([f"{yy}-{mm}-{dd}", loc.strip(), *vals, year == 2022, "verified_public", FORM, retrieved])
    write(OUT / "opsnet_daily_superbowl.csv",
          ["date", "locid", *COLS, "super_bowl_lvi_window", "data_classification", "source", "retrieved_utc"], daily)

    lawa_path = OUT / "lax_monthly_movements.csv"
    if lawa_path.exists():
        lawa = {(int(r["year"]), int(r["month"])): r for r in csv.DictReader(open(lawa_path))}
        cross = []
        for r in monthly:
            l = lawa.get((r[0], r[1]))
            if not l:
                continue
            o = dict(zip(COLS, r[3:3 + len(COLS)]))
            cross.append([r[0], r[1],
                          o["air_taxi"], int(l["air_taxi"]), o["air_taxi"] - int(l["air_taxi"]),
                          o["general_aviation"] + o["local_ga"], int(l["general_aviation"]),
                          o["general_aviation"] + o["local_ga"] - int(l["general_aviation"]),
                          o["total"], int(l["total"]), o["total"] - int(l["total"])])
        write(OUT / "opsnet_vs_lawa_crosscheck.csv",
              ["year", "month", "air_taxi_opsnet", "air_taxi_lawa", "air_taxi_diff",
               "ga_opsnet_itin_plus_local", "ga_lawa", "ga_diff", "total_opsnet", "total_lawa", "total_diff"], cross)
    print(f"{len(monthly)} monthly rows, {len(daily)} daily rows")


if __name__ == "__main__":
    main()
