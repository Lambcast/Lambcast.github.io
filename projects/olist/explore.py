import duckdb

conn = duckdb.connect()

# Point to your data folder
data = "C:/Users/alamb/OneDrive/Alans Work Folder/Lambcast/olist/data/"

# Load the two tables we need first
orders = conn.execute(f"SELECT * FROM read_csv_auto('{data}olist_orders_dataset.csv')").df()

print(orders.columns.tolist())
print(orders.shape)
print(orders.head())