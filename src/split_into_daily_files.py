import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

SOURCE_DIR = Path("data/source")
INBOX_DIR = Path("data/inbox")


#reading CSV file and returning a list of dictionaries
def read_csv(path):
    '''Return (col names, list of eows of dicts)'''
    with open(path,mode='r',newline='',encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames,list(reader)


#check for date if any malformed on blank date exists
def purchase_date(timestamp):
    ''' '2017-10-02 10:56:33' -> '2017-10-02' Fails loudly on bad data '''
    day=timestamp[:10]
    date.fromisoformat(day)  # raises ValueError if bad
    return day


#build order_date_lookup(orders): mapping of order_id -> order_date
def build_order_date_lookup(orders):
    return{ row["order_id"]:purchase_date(row["order_purchase_timestamp"])
        for row in orders}


def group_by_date(rows,date_of):
    groups = defaultdict(list)
    for row in rows:
        groups[date_of(row)].append(row)
    return groups


def write_daily_files(groups,fieldnames,out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for old_file in out_dir.glob("*.csv"):
        old_file.unlink()
    for day,rows in groups.items():
        with open(out_dir/f"{day}.csv",mode='w',newline='',encoding='utf-8') as f:
            writer = csv.DictWriter(f,fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

def count_rows_on_disk(out_dir):
    """Re-read what was actually written, not what we think we wrote."""
    total=0
    for path in out_dir.glob("*.csv"):
        with open(path,mode='r',newline='',encoding='utf-8') as f:
            total += sum(1 for _ in csv.DictReader(f))  # skip header
    return total


def main():
    order_fields, orders = read_csv(SOURCE_DIR / "olist_orders_dataset.csv")
    item_fields, items = read_csv(SOURCE_DIR / "olist_order_items_dataset.csv")

    order_dates = build_order_date_lookup(orders)

    #Every item must have an order (we proved 0 orphans earlier)
    orphans = [r["order_id"] for r in items if r["order_id"] not in order_dates]
    if orphans: 
        raise ValueError(f"{len(orphans)} items have no matching order, e.g{orphans[0]}")

    orders_by_day = group_by_date(orders, lambda r: order_dates[r["order_id"]])
    items_by_day = group_by_date(items, lambda r: order_dates[r["order_id"]])

    write_daily_files(orders_by_day, order_fields, INBOX_DIR / "orders")
    write_daily_files(items_by_day, item_fields, INBOX_DIR / "items")       


    #Rows should be same or equal rows in the source vs disk
    order_on_disk = count_rows_on_disk(INBOX_DIR / "orders")
    item_on_disk = count_rows_on_disk(INBOX_DIR / "items")  
    if order_on_disk != len(orders):
        raise ValueError(f"Orders on disk {order_on_disk} != source {len(orders)}")
    if item_on_disk != len(items):
        raise ValueError(f"Items on disk {item_on_disk} != source {len(items)}")

    days = sorted(orders_by_day)
    print(f"Orders: source={len(orders)} disk={order_on_disk}")
    print(f"Items:  source={len(items)} disk={item_on_disk}")
    print(f"Distinct dates: {len(days)}  earliest={days[0]}  latest={days[-1]}")
    print(f"Days with orders but no item file: {len(set(orders_by_day) - set(items_by_day))}")


if __name__ == "__main__":
    main()