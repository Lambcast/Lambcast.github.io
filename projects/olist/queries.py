import duckdb

conn =  duckdb.connect()
data = "C:/Users/alamb/OneDrive/Alans Work Folder/Lambcast/olist/data/"

result = conn.execute("""
WITH monthly_orders AS (
    SELECT
        YEAR(order_purchase_timestamp) AS year,
        MONTH(order_purchase_timestamp) AS month,
        COUNT(*) AS order_count
    FROM read_csv_auto('""" + data + """olist_orders_dataset.csv')
    WHERE order_purchase_timestamp >= '2017-01-01'
    AND order_purchase_timestamp <= '2018-09-01'
    GROUP BY year, month
    ORDER BY year, month
)

SELECT 
        year,
        month,
        order_count,
        LAG(order_count) OVER (ORDER BY year, month) AS prev_month_count,
        (order_count - prev_month_count) / prev_month_count *100 AS mom_growth
    FROM monthly_orders
""").df()

print(result)

result2 = conn.execute("""
    SELECT
        cat.product_category_name_english AS category,
        ROUND(SUM(items.price), 2) AS total_revenue
    FROM read_csv_auto('""" + data + """olist_order_items_dataset.csv') AS items
    JOIN read_csv_auto('""" + data + """olist_products_dataset.csv') AS products
        ON items.product_id = products.product_id
    JOIN read_csv_auto('""" + data + """product_category_name_translation.csv') AS cat
        ON products.product_category_name = cat.product_category_name
    GROUP BY cat.product_category_name_english
    ORDER BY total_revenue DESC
    LIMIT 10
""").df()

print(result2)


result3 = conn.execute("""
    SELECT
        cat.product_category_name_english AS category,
        ROUND(AVG(DATEDIFF('day', orders.order_purchase_timestamp, orders.order_delivered_customer_date)), 1) AS avg_delivery_days
    FROM read_csv_auto('""" + data + """olist_orders_dataset.csv') AS orders
    JOIN read_csv_auto('""" + data + """olist_order_items_dataset.csv') AS items
        ON items.order_id = orders.order_id
    JOIN read_csv_auto('""" + data + """olist_products_dataset.csv') AS products
        ON items.product_id = products.product_id
    JOIN read_csv_auto('""" + data + """product_category_name_translation.csv') AS cat
        ON products.product_category_name = cat.product_category_name
    GROUP BY cat.product_category_name_english
    ORDER BY avg_delivery_days DESC
    LIMIT 10
""").df()

print(result3)


result4 = conn.execute("""
    WITH customer_orders AS (
        SELECT
            c.customer_unique_id,
    COUNT(*) AS order_count
    FROM read_csv_auto('""" + data + """olist_customers_dataset.csv') AS c
    JOIN read_csv_auto('""" + data + """olist_orders_dataset.csv') AS o
        ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
    )
    SELECT
        COUNT(*) AS total_customers,
        SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
        ROUND(SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS repeat_rate_pct
    FROM customer_orders
""").df()

print(result4)


result5 = conn.execute("""
    WITH seller_revenue AS (
        SELECT
            items.seller_id,
            cat.product_category_name_english AS category,
            ROUND(SUM(items.price), 2) AS total_revenue
        FROM read_csv_auto('""" + data + """olist_order_items_dataset.csv') AS items
        JOIN read_csv_auto('""" + data + """olist_products_dataset.csv') AS products
            ON items.product_id = products.product_id
        JOIN read_csv_auto('""" + data + """product_category_name_translation.csv') AS cat
            ON products.product_category_name = cat.product_category_name
        GROUP BY items.seller_id, cat.product_category_name_english
    ),
    ranked AS (
        SELECT
            seller_id,
            category,
            total_revenue,
            RANK() OVER (PARTITION BY category ORDER BY total_revenue DESC) AS revenue_rank
        FROM seller_revenue
    )
    SELECT * FROM ranked
    WHERE revenue_rank <= 3
    ORDER BY category, revenue_rank
""").df()

print(result5)


result6 = conn.execute("""
    SELECT
        CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END AS is_late,
        ROUND(AVG(r.review_score), 2) AS avg_review_score,
        COUNT(*) AS order_count
    FROM read_csv_auto('""" + data + """olist_order_reviews_dataset.csv') AS r
    JOIN read_csv_auto('""" + data + """olist_orders_dataset.csv') AS o
        ON r.order_id = o.order_id
    WHERE o.order_delivered_customer_date IS NOT NULL
    GROUP BY is_late
""").df()

print(result6)

import matplotlib.pyplot as plt

# Chart 1: Monthly order growth
fig, ax = plt.subplots(figsize=(12, 5))
ax.bar(range(len(result)), result['order_count'], color='steelblue')
ax.set_xticks(range(len(result)))
ax.set_xticklabels([f"{int(r.year)}-{int(r.month):02d}" for r in result.itertuples()], rotation=45)
ax.set_title('Olist Monthly Order Volume (2017–2018)')
ax.set_ylabel('Orders')
plt.tight_layout()
plt.savefig('C:/Users/alamb/OneDrive/Alans Work Folder/Lambcast/olist/charts/monthly_orders.png', dpi=150)
plt.close()

# Chart 2: Top 10 categories by revenue
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(result2['category'], result2['total_revenue'], color='steelblue')
ax.set_title('Top 10 Product Categories by Revenue')
ax.set_xlabel('Total Revenue (BRL)')
plt.tight_layout()
plt.savefig('C:/Users/alamb/OneDrive/Alans Work Folder/Lambcast/olist/charts/top_categories.png', dpi=150)
plt.close()

# Chart 3: Slowest delivery categories
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(result3['category'], result3['avg_delivery_days'], color='steelblue')
ax.set_title('Top 10 Slowest Categories by Average Delivery Time')
ax.set_xlabel('Average Delivery Days')
plt.tight_layout()
plt.savefig('C:/Users/alamb/OneDrive/Alans Work Folder/Lambcast/olist/charts/delivery_times.png', dpi=150)
plt.close()

# Chart 4: Top sellers by revenue in top 5 categories
top_cats = ['health_beauty', 'watches_gifts', 'bed_bath_table', 'sports_leisure', 'computers_accessories']
chart_data = result5[result5['category'].isin(top_cats) & (result5['revenue_rank'] == 1)]

fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(chart_data['category'], chart_data['total_revenue'], color='steelblue')
ax.set_title('Top Seller Revenue by Category')
ax.set_xlabel('Total Revenue (BRL)')
plt.tight_layout()
plt.savefig('C:/Users/alamb/OneDrive/Alans Work Folder/Lambcast/olist/charts/top_sellers.png', dpi=150)
plt.close()

# Chart 5: Late vs on-time review scores
fig, ax = plt.subplots(figsize=(7, 5))
ax.bar(['On Time', 'Late'], result6['avg_review_score'], color=['steelblue', 'tomato'])
ax.set_title('Average Review Score: On-Time vs Late Deliveries')
ax.set_ylabel('Average Review Score (1-5)')
ax.set_ylim(0, 5)
plt.tight_layout()
plt.savefig('C:/Users/alamb/OneDrive/Alans Work Folder/Lambcast/olist/charts/late_reviews.png', dpi=150)
plt.close()

print("Charts saved.")