import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path


import pandas as pd
import requests

API_URL = "https://api.frankfurter.app/{date}"
RAW = Path("data/raw/fx")
TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 1

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

class FxError(Exception):
    """ An Expected failure: bad date , rejected request, bad response ,or retries used up."""


def validate_date(date):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise FxError(f"Invalid Date: {date!r}. Expected YYYY-MM-DD.") from None


def fetch_rate(date, base="BRL", quote="INR"):
    """ Call the API. Retry only on failures that can fix themselves"""
    params = {"from": base, "to":quote}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(API_URL.format(date=date), params=params, timeout=TIMEOUT_SECONDS)
        except (requests.Timeout, requests.ConnectionError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                try: 
                    return resp.json()
                except ValueError:
                    raise FxError("API returned 200 but the body was not valid JSON") from None
            if resp.status_code == 429 or resp.status_code >=500:
                reason = f"HTTP {resp.status_code}"
            else:
                 # 4xx (e.g. 404): our request is wrong, retrying cannot help
                raise FxError(f"API rejected request for {date}: HTTP {resp.status_code}")

        if attempt == MAX_ATTEMPTS:
            raise FxError(f"Gave up after {MAX_ATTEMPTS} attempts for {date}: {reason}")
        wait = BACKOFF_SECONDS * 2 ** (attempt - 1) #1s, 2s, 4s
        log.warning("Attempt %d/%d failed (%s); retrying in %ds", attempt, MAX_ATTEMPTS, reason, wait)
        time.sleep(wait)

def build_dataframe(requested_date, payload, base="BRL", quote="INR"):
    try:
        rate_date = payload["date"]
        rate = float(payload["rates"][quote])
    except (KeyError, TypeError, ValueError):
        raise FxError(f"Unexpected API response shape: {payload!r}") from None
    if rate_date != requested_date:
        log.warning("Requested %s but the API returned the rate for %s (no rate published)", requested_date, rate_date)
    return pd.DataFrame([{
        "requested_date" : requested_date,
        "rate_date": rate_date,
        "base": base,
        "quote": quote,
        "rate": rate,
    }])
                


#Implement a function that makes the request with timeout= and decides whether to retry.
# A function that makes the request with timeout= and decides whether to retry


# A write step with the same idempotent pattern as Task B: clear old files, then write.

def to_clean_old_files_and_write(df,date):
    """
    Clears old files in the output directory and writes the DataFrame to a new file.
    """
    out_dir = RAW / f"ingest_date={date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.parquet"):
        old.unlink()
    df.to_parquet(out_dir / "fx.parquet", index=False)
    log.info("Wrote %d rows to %s", len(df), out_dir)   

def ingest_fx(date):
    validate_date(date)
    payload = fetch_rate(date)
    df = build_dataframe(date, payload)
    to_clean_old_files_and_write(df, date)

# A main that catches the expected errors, logs one clear line and exits 1.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="YYYY-MM-DD")
    args = parser.parse_args()
    try:
        ingest_fx(args.date)
    except FxError as exc:
        log.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()