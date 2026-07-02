import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Create and return a MySQL connection (supports localhost and Aiven SSL)."""

    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", 3306))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "billwise_ai")

    connection_args = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }

    if host != "localhost" and host != "127.0.0.1":
        connection_args["ssl"] = {
        "ca": os.getenv("MYSQL_SSL_CA")
    }

    return pymysql.connect(**connection_args)


def save_bill(image_name, shop_name, bill_date, amount, extracted_text, category, confidence):
    """Insert a new bill record and return its ID."""
    sql = """
        INSERT INTO bills
            (image_name, shop_name, bill_date, amount, extracted_text, category, confidence)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s)
    """

    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    image_name,
                    shop_name,
                    bill_date,
                    amount,
                    extracted_text,
                    category,
                    confidence
                )
            )

        conn.commit()
        return cur.lastrowid

    finally:
        conn.close()


def get_all_bills(search="", category=""):
    """Fetch all bills with optional search and category filter."""
    conditions = []
    params = []

    if search:
        conditions.append("shop_name LIKE %s")
        params.append(f"%{search}%")

    if category:
        conditions.append("category = %s")
        params.append(category)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    sql = f"""
        SELECT *
        FROM bills
        {where}
        ORDER BY created_at DESC
    """

    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    finally:
        conn.close()


def get_recent_bills(limit=10):
    """Return the most recent N bills."""
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM bills
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,)
            )

            return cur.fetchall()

    finally:
        conn.close()


def get_dashboard_stats():
    """Return aggregated statistics for the dashboard."""
    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # 1. Total spending and total number of bills
            cur.execute("""
                SELECT
                    COALESCE(SUM(amount), 0) AS total_spending,
                    COUNT(*) AS total_bills
                FROM bills
            """)
            totals = cur.fetchone()

            # 2. Spending during the current month
            cur.execute("""
                SELECT
                    COALESCE(SUM(amount), 0) AS month_spending
                FROM bills
                WHERE MONTH(created_at) = MONTH(CURDATE())
                AND YEAR(created_at) = YEAR(CURDATE())
            """)
            month = cur.fetchone()

            # 3. Category-wise spending
            cur.execute("""
                SELECT
                    category,
                    COALESCE(SUM(amount), 0) AS total
                FROM bills
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY total DESC
            """)
            categories = cur.fetchall()

            top_category = categories[0]["category"] if categories else "No data"

            # 4. Monthly spending for the last 6 months
            # MIN(created_at) makes this compatible with ONLY_FULL_GROUP_BY
            cur.execute("""
                SELECT
                    DATE_FORMAT(MIN(created_at), '%b %Y') AS month_label,
                    COALESCE(SUM(amount), 0) AS month_total
                FROM bills
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                GROUP BY YEAR(created_at), MONTH(created_at)
                ORDER BY YEAR(created_at), MONTH(created_at)
            """)
            monthly = cur.fetchall()

            # 5. Recent bills
            cur.execute("""
                SELECT
                    id,
                    image_name,
                    shop_name,
                    bill_date,
                    amount,
                    category,
                    confidence,
                    created_at
                FROM bills
                ORDER BY created_at DESC
                LIMIT 5
            """)
            recent_bills = cur.fetchall()

            return {
                "total_spending": float(totals["total_spending"] or 0),
                "total_bills": int(totals["total_bills"] or 0),
                "this_month_spending": float(month["month_spending"] or 0),
                "highest_category": top_category,
                "category_spending": [
                    {
                        "category": item["category"],
                        "amount": float(item["total"] or 0)
                    }
                    for item in categories
                ],
                "monthly_spending": [
                    {
                        "month": item["month_label"],
                        "amount": float(item["month_total"] or 0)
                    }
                    for item in monthly
                ],
                "recent_bills": recent_bills
            }

    finally:
        conn.close()


def delete_bill(bill_id):
    """Delete a bill by ID. Returns True if deleted."""
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM bills WHERE id = %s",
                (bill_id,)
            )

        conn.commit()
        return cur.rowcount > 0

    finally:
        conn.close()

def ensure_users_table():
    """Create the users table if it does not exist."""
    sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    finally:
        conn.close()


def get_user_by_username(username):
    """Return a user record by username."""
    sql = "SELECT * FROM users WHERE username = %s LIMIT 1"
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, (username,))
            return cur.fetchone()

    finally:
        conn.close()


def create_user(username, password_hash):
    """Insert a new user record."""
    sql = """
        INSERT INTO users (username, password_hash)
        VALUES (%s, %s)
    """
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, (username, password_hash))
        conn.commit()
        return cur.lastrowid

    finally:
        conn.close()

def test_connection():
    """Quick health-check — returns True if DB is reachable."""
    try:
        conn = get_connection()
        conn.ping()
        conn.close()
        return True

    except Exception as error:
        print(f"DB connection failed: {error}")
        return False