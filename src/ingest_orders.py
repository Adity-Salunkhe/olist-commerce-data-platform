import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime


import pandas as pd


INBOX = Path("data/inbox/orders")
RAW = Path("data/raw/orders")
EXPECTED_COLUMNS = {
    "order_id", "customer_id","order_status", "order_purchase_timestamp",
    "order_approved_at", "order_delivered_carrier_date",
    "order_delivered_customer_date","order_estimated_delivery_date",
}


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def ingest(date):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date: {date!r}. Expected YYYY-MM-DD.") from None
    src = INBOX / f"{date}.csv"
    if not src.exists():
        raise FileNotFoundError(f"Input file not found:{src}")


    df = pd.read_csv(src,dtype=str)
    if len(df) == 0:
        log.warning("No rows found in %s", src)
    log.info("Read %d rows from %s", len(df), src)


    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")
        
    out_dir =  RAW / f"ingest_date={date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.parquet"):
        old.unlink()
    df.to_parquet(out_dir / "orders.parquet", index=False)
    log.info("Wrote %d rows to %s", len(df), out_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="YYYY-MM-DD")
    args = parser.parse_args()
    try:
        ingest(args.date)
    except(FileNotFoundError, ValueError) as exc:
        log.error("%s", exc)
        sys.exit(1)

if __name__ == "__main__":
    main()