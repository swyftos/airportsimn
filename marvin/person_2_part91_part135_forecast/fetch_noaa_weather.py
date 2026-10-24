"""Download observed daily weather at LAX (NOAA GHCN-Daily station USW00023174) into data/noaa_lax_daily.csv.

Source: NOAA NCEI Access Data Service, dataset daily-summaries (public, no key).
Fields: PRCP precipitation (in), TMAX/TMIN (F), AWND average wind (mph), WSF2 fastest 2-minute wind (mph),
WT01 fog, WT02 heavy fog, WT08 smoke or haze (1 when observed, blank otherwise).
"""
import urllib.request
from pathlib import Path

URL = ('https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00023174'
       '&startDate=2015-01-01&endDate=2026-02-28&dataTypes=PRCP,TMAX,TMIN,AWND,WSF2,WT01,WT02,WT08'
       '&format=csv&units=standard&includeStationName=false')
OUT = Path(__file__).resolve().parent / 'data' / 'noaa_lax_daily.csv'

def main():
    OUT.parent.mkdir(exist_ok=True)
    body = urllib.request.urlopen(URL, timeout=120).read()
    if not body.startswith(b'"STATION","DATE"'):
        raise ValueError('Unexpected NOAA response')
    OUT.write_bytes(body)
    print(f'{body.count(b"\n") - 1} days written to {OUT}')

if __name__ == '__main__':
    main()
