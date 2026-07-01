"""
BillWise AI — Advanced APIs for Premium Features
Analytics, recommendations, budgets, achievements, etc.
"""

import json
from datetime import datetime, timedelta
from flask import request, jsonify
import pymysql
from functools import wraps

# ====== HELPERS ======

def get_user_id_from_request():
    """Extract user_id from session or request"""
    # In a real app, this would come from session/JWT
    # For now, we'll use a header or default to 1 for development
    return request.headers.get('X-User-ID', 1)

def db_query(query, params=None):
    """Execute database query"""
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            database='billwise_ai',
            charset='utf8mb4'
        )
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        cursor.execute(query, params or ())
        connection.commit()
        return cursor, connection
    except Exception as e:
        print(f"DB Error: {e}")
        return None, None

# ====== ANALYTICS APIs ======

def get_dashboard_stats(user_id):
    """Get dashboard statistics"""
    cursor, conn = db_query("""
        SELECT 
            COUNT(*) as total_bills,
            SUM(amount) as total_spending,
            AVG(amount) as avg_bill,
            MAX(amount) as highest_expense,
            MIN(amount) as lowest_expense,
            COUNT(DISTINCT category) as categories_count,
            AVG(ocr_confidence) as avg_ocr_confidence
        FROM bills
        WHERE user_id = %s
    """, (user_id,))
    
    if cursor:
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    return None

def get_category_breakdown(user_id):
    """Get spending by category"""
    cursor, conn = db_query("""
        SELECT 
            category,
            COUNT(*) as bill_count,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount
        FROM bills
        WHERE user_id = %s
        GROUP BY category
        ORDER BY total_amount DESC
    """, (user_id,))
    
    if cursor:
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    return []

def get_monthly_trend(user_id):
    """Get monthly spending trend"""
    cursor, conn = db_query("""
        SELECT 
            DATE_FORMAT(bill_date, '%Y-%m') as month,
            COUNT(*) as bill_count,
            SUM(amount) as total_amount
        FROM bills
        WHERE user_id = %s
        GROUP BY DATE_FORMAT(bill_date, '%Y-%m')
        ORDER BY month DESC
        LIMIT 12
    """, (user_id,))
    
    if cursor:
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    return []

def get_top_vendors(user_id, limit=10):
    """Get top spending vendors"""
    cursor, conn = db_query("""
        SELECT 
            shop_name,
            COUNT(*) as bill_count,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount
        FROM bills
        WHERE user_id = %s
        GROUP BY shop_name
        ORDER BY total_amount DESC
        LIMIT %s
    """, (user_id, limit))
    
    if cursor:
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    return []

# ====== FINANCIAL HEALTH SCORE ======

def calculate_financial_health_score(user_id):
    """Calculate financial health score (0-100)"""
    # Get budget health
    cursor, conn = db_query("""
        SELECT 
            COUNT(*) as total_budgets,
            SUM(CASE WHEN spent_amount > limit_amount THEN 1 ELSE 0 END) as exceeded_count,
            AVG(CASE WHEN spent_amount > 0 THEN (spent_amount / limit_amount * 100) ELSE 0 END) as avg_utilization
        FROM budgets
        WHERE user_id = %s AND month_year = DATE_FORMAT(NOW(), '%Y-%m')
    """, (user_id,))
    
    budget_data = cursor.fetchone() if cursor else None
    if cursor: cursor.close()
    if conn: conn.close()
    
    # Calculate scores
    budget_health = 100
    if budget_data:
        exceeded = budget_data.get('exceeded_count', 0)
        total = budget_data.get('total_budgets', 1)
        if total > 0:
            budget_health = max(0, 100 - (exceeded / total * 50))
    
    # Get spending trend health
    cursor, conn = db_query("""
        SELECT 
            AVG(monthly_total) as avg_spending,
            MAX(monthly_total) as max_spending
        FROM (
            SELECT SUM(amount) as monthly_total
            FROM bills
            WHERE user_id = %s
            GROUP BY DATE_FORMAT(bill_date, '%Y-%m')
            ORDER BY bill_date DESC
            LIMIT 3
        ) as recent_months
    """, (user_id,))
    
    spending_data = cursor.fetchone() if cursor else None
    if cursor: cursor.close()
    if conn: conn.close()
    
    spending_health = 75  # Default
    
    # Get savings
    cursor, conn = db_query("""
        SELECT 
            SUM(CASE WHEN month_year = DATE_FORMAT(NOW(), '%Y-%m') 
                THEN limit_amount - spent_amount ELSE 0 END) as potential_savings
        FROM budgets
        WHERE user_id = %s
    """, (user_id,))
    
    savings_data = cursor.fetchone() if cursor else None
    if cursor: cursor.close()
    if conn: conn.close()
    
    savings_health = 60 + (savings_data.get('potential_savings', 0) > 0) * 15
    
    # Calculate final score
    final_score = int((budget_health * 0.3 + spending_health * 0.4 + savings_health * 0.3))
    
    return {
        'score': min(100, max(0, final_score)),
        'budget_health': int(budget_health),
        'spending_health': int(spending_health),
        'savings_health': int(savings_health),
        'status': 'Excellent' if final_score >= 75 else 'Good' if final_score >= 50 else 'Poor'
    }

# ====== DUPLICATE DETECTION ======

def detect_duplicate_bill(user_id, vendor, bill_date, amount, tolerance=0.5):
    """Detect if bill is duplicate based on vendor, date, and amount"""
    cursor, conn = db_query("""
        SELECT id, shop_name, bill_date, amount
        FROM bills
        WHERE user_id = %s 
        AND shop_name = %s
        AND ABS(amount - %s) <= %s
        AND ABS(DATEDIFF(bill_date, %s)) <= 1
        LIMIT 1
    """, (user_id, vendor, amount, tolerance, bill_date))
    
    if cursor:
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    return None

# ====== RECURRING BILL DETECTION ======

def detect_recurring_bills(user_id):
    """Automatically detect recurring bills"""
    cursor, conn = db_query("""
        SELECT 
            shop_name,
            category,
            COUNT(*) as occurrence_count,
            AVG(amount) as avg_amount,
            STDDEV(amount) as std_dev,
            MAX(bill_date) as last_date,
            MIN(bill_date) as first_date
        FROM bills
        WHERE user_id = %s
        GROUP BY shop_name, category
        HAVING COUNT(*) >= 2
        ORDER BY occurrence_count DESC
    """, (user_id,))
    
    if cursor:
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        recurring = []
        for bill in results:
            # Calculate frequency
            if bill['occurrence_count'] >= 12:
                frequency = 'monthly'
            elif bill['occurrence_count'] >= 4:
                frequency = 'quarterly'
            else:
                frequency = 'irregular'
            
            bill['frequency'] = frequency
            recurring.append(bill)
        
        return recurring
    return []

# ====== BUDGET PREDICTION ======

def predict_budget_usage(user_id, category):
    """Predict budget usage and alert risk"""
    current_month = datetime.now().strftime('%Y-%m')
    
    cursor, conn = db_query("""
        SELECT 
            limit_amount,
            spent_amount,
            alert_threshold,
            DATEDIFF(LAST_DAY(CURDATE()), CURDATE()) as days_remaining
        FROM budgets
        WHERE user_id = %s AND category = %s AND month_year = %s
    """, (user_id, category, current_month))
    
    if cursor:
        budget = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if budget:
            daily_rate = budget['spent_amount'] / max(1, (30 - budget['days_remaining']))
            projected = budget['spent_amount'] + (daily_rate * budget['days_remaining'])
            risk = 'High' if projected > budget['limit_amount'] else 'Medium' if projected > (budget['limit_amount'] * 0.8) else 'Low'
            
            return {
                'limit': budget['limit_amount'],
                'spent': budget['spent_amount'],
                'projected': projected,
                'days_remaining': budget['days_remaining'],
                'risk': risk,
                'expected_overspend': max(0, projected - budget['limit_amount'])
            }
    
    return None

# ====== AI RECOMMENDATIONS ======

def generate_ai_recommendations(user_id):
    """Generate AI recommendations based on spending patterns"""
    recommendations = []
    
    # Get top spending category
    cursor, conn = db_query("""
        SELECT category, SUM(amount) as total
        FROM bills
        WHERE user_id = %s AND bill_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY category
        ORDER BY total DESC LIMIT 1
    """, (user_id,))
    
    if cursor:
        top_category = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if top_category:
            recommendations.append({
                'text': f"Your highest spending category is {top_category['category']} (₹{top_category['total']:.0f}). Consider budgeting for this.",
                'category': top_category['category'],
                'priority': 'high',
                'action_type': 'monitor'
            })
    
    # Check for budget overruns
    cursor, conn = db_query("""
        SELECT category, spent_amount, limit_amount
        FROM budgets
        WHERE user_id = %s AND month_year = DATE_FORMAT(NOW(), '%Y-%m')
        AND spent_amount > limit_amount
    """, (user_id,))
    
    if cursor:
        overruns = cursor.fetchall()
        cursor.close()
        conn.close()
        
        for overrun in overruns:
            overspend = overrun['spent_amount'] - overrun['limit_amount']
            recommendations.append({
                'text': f"⚠️ {overrun['category']} budget exceeded by ₹{overspend:.0f}",
                'category': overrun['category'],
                'priority': 'high',
                'action_type': 'reduce'
            })
    
    return recommendations

# ====== API ROUTE HANDLERS ======

def register_advanced_apis(app):
    """Register all advanced API endpoints"""
    
    @app.route('/api/dashboard/stats', methods=['GET'])
    def api_dashboard_stats():
        user_id = get_user_id_from_request()
        stats = get_dashboard_stats(user_id)
        return jsonify(stats or {})
    
    @app.route('/api/analytics/category-breakdown', methods=['GET'])
    def api_category_breakdown():
        user_id = get_user_id_from_request()
        data = get_category_breakdown(user_id)
        return jsonify(data)
    
    @app.route('/api/analytics/monthly-trend', methods=['GET'])
    def api_monthly_trend():
        user_id = get_user_id_from_request()
        data = get_monthly_trend(user_id)
        return jsonify(data)
    
    @app.route('/api/analytics/top-vendors', methods=['GET'])
    def api_top_vendors():
        user_id = get_user_id_from_request()
        limit = request.args.get('limit', 10, type=int)
        data = get_top_vendors(user_id, limit)
        return jsonify(data)
    
    @app.route('/api/health/financial-score', methods=['GET'])
    def api_financial_score():
        user_id = get_user_id_from_request()
        score = calculate_financial_health_score(user_id)
        return jsonify(score)
    
    @app.route('/api/bills/detect-duplicate', methods=['POST'])
    def api_detect_duplicate():
        user_id = get_user_id_from_request()
        data = request.json
        duplicate = detect_duplicate_bill(
            user_id,
            data.get('vendor'),
            data.get('date'),
            data.get('amount'),
            data.get('tolerance', 0.5)
        )
        return jsonify({'is_duplicate': duplicate is not None, 'duplicate': duplicate})
    
    @app.route('/api/bills/recurring', methods=['GET'])
    def api_recurring_bills():
        user_id = get_user_id_from_request()
        recurring = detect_recurring_bills(user_id)
        return jsonify(recurring)
    
    @app.route('/api/budget/predict', methods=['POST'])
    def api_predict_budget():
        user_id = get_user_id_from_request()
        data = request.json
        prediction = predict_budget_usage(user_id, data.get('category'))
        return jsonify(prediction or {})
    
    @app.route('/api/ai/recommendations', methods=['GET'])
    def api_recommendations():
        user_id = get_user_id_from_request()
        recommendations = generate_ai_recommendations(user_id)
        return jsonify(recommendations)
