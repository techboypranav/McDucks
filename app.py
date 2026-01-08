import sqlite3
import math
import os
import urllib.parse
import urllib.request
import json
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'build2break_secure_key_2026'
DB_NAME = "supply_chain.db"

# --- Config ---
# Simulating traffic density: 1.0 = clear, 1.5 = heavy traffic
TRAFFIC_MULTIPLIERS = {
    'North': 1.2,
    'South': 1.1,
    'East': 1.4,
    'West': 1.0
}
BASE_SPEED_KMPH = 40

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    try:
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
        
        # Check if we need to seed users
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM users")
        if cur.fetchone()[0] == 0:
            print("🌱 Seeding Admin & Trader accounts...")
            p1 = generate_password_hash('trader_pass_2026')
            p2 = generate_password_hash('admin_2026')
            cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('trader1', p1, 'trader'))
            cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', p2, 'admin'))
            
            # ⚠️ REMOVED: Warehouse seeding lines are deleted.
            # The 'warehouses' table will now be empty on startup.
            
        conn.commit()
    except Exception as e:
        print(f"DB Init Error: {e}")
    finally:
        conn.close()

# Ensure DB exists on start
if not os.path.exists(DB_NAME):
    init_db()

# --- Haversine Formula ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# --- Middleware (Robust Version) ---
def login_required(allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            if allowed_roles:
                # Handle single string or list of roles
                roles_list = [allowed_roles] if isinstance(allowed_roles, str) else allowed_roles
                if session.get('role') not in roles_list:
                    return redirect(url_for('login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.is_json:
            data = request.json
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form['username']
            password = request.form['password']
            
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['username'] = user['username']
            
            if user['role'] == 'admin':
                return jsonify({'success': True, 'redirect': url_for('admin_dashboard')})
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
            
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- TRADER PORTAL ---

@app.route('/dashboard')
@login_required('trader')
def dashboard():
    return render_template('dashboard.html', active_tab='dashboard')

@app.route('/new-order')
@login_required('trader')
def new_order():
    return render_template('new_order.html', active_tab='new_order')

@app.route('/history')
@login_required('trader')
def history():
    conn = get_db_connection()
    orders = conn.execute('''
        SELECT o.*, w.name as warehouse_name, w.lat as wh_lat, w.lng as wh_lng 
        FROM orders o 
        LEFT JOIN warehouses w ON o.assigned_warehouse_id = w.id
        WHERE o.trader_id = ? 
        ORDER BY o.timestamp DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('history.html', active_tab='history', orders=orders)

@app.route('/api/stats')
@login_required('trader')
def get_stats():
    conn = get_db_connection()
    total = conn.execute('SELECT COUNT(*) FROM orders WHERE trader_id = ?', (session['user_id'],)).fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM orders WHERE trader_id = ? AND timestamp >= datetime('now', '-15 minutes')", (session['user_id'],)).fetchone()[0]
    volume = conn.execute('SELECT SUM(quantity) FROM orders WHERE trader_id = ?', (session['user_id'],)).fetchone()[0] or 0
    
    recent_orders = conn.execute('''
        SELECT o.*, w.name as warehouse_name, w.lat as wh_lat, w.lng as wh_lng 
        FROM orders o
        JOIN warehouses w ON o.assigned_warehouse_id = w.id
        WHERE trader_id = ? 
        ORDER BY id DESC LIMIT 5
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    return jsonify({
        'total': total,
        'active': active,
        'volume': volume,
        'orders': [dict(row) for row in recent_orders]
    })

# --- ALLOCATION ENGINE (Proximity Based) ---
@app.route('/api/allocate', methods=['POST'])
@login_required('trader')
def allocate_order():
    data = request.json
    try:
        farmer_lat = float(data['lat'])
        farmer_lng = float(data['lng'])
        farmer_addr = data['farmerAddress']
        qty = float(data['quantity'])
        
        if qty <= 0: return jsonify({'error': 'Quantity must be positive'}), 400

        conn = get_db_connection()
        
        # Check ALL warehouses with capacity (Ignoring Region)
        warehouses = conn.execute('''
            SELECT * FROM warehouses 
            WHERE (capacity - current_load) >= ?
        ''', (qty,)).fetchall()

        if not warehouses:
            conn.close()
            return jsonify({'success': False, 'error': f'No warehouses have {qty}kg capacity available.'}), 404

        # Find Nearest
        best_wh = None
        min_dist = float('inf')

        for wh in warehouses:
            dist = calculate_distance(farmer_lat, farmer_lng, wh['lat'], wh['lng'])
            if dist < min_dist:
                min_dist = dist
                best_wh = wh

        # Calculate ETA
        traffic_factor = TRAFFIC_MULTIPLIERS.get(best_wh['region'], 1.0)
        travel_time_hours = (min_dist / BASE_SPEED_KMPH) * traffic_factor
        eta_minutes = round(travel_time_hours * 60) + 15

        conn.execute('''
            INSERT INTO orders 
            (trader_id, farmer_name, farmer_address, crop, grade, quantity, assigned_warehouse_id, distance_km, eta_mins) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], data['farmerName'], farmer_addr, data['cropType'], data['grade'], qty, best_wh['id'], round(min_dist, 2), eta_minutes))
        
        conn.execute('UPDATE warehouses SET current_load = current_load + ? WHERE id = ?', (qty, best_wh['id']))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True, 
            'message': 'Allocated by Proximity', 
            'warehouse': best_wh['name'],
            'wh_lat': best_wh['lat'],
            'wh_lng': best_wh['lng'],
            'eta': f"{eta_minutes} mins"
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# --- GEOCODING PROXY (Admins & Traders) ---
@app.route('/api/geocode', methods=['GET'])
@login_required(['trader', 'admin']) 
def geocode_proxy():
    address = request.args.get('address')
    if not address:
        return jsonify({'error': 'No address provided'}), 400
    
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json&limit=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Build2Break-Hackathon-Project/1.0'})
        
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        if data:
            return jsonify({'success': True, 'lat': data[0]['lat'], 'lon': data[0]['lon']})
        else:
            return jsonify({'success': False, 'error': 'Address not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': f"API Error: {str(e)}"}), 500


# --- ADMIN PORTAL ---
@app.route('/admin')
@login_required('admin')
def admin_dashboard():
    conn = get_db_connection()
    warehouses = conn.execute('SELECT * FROM warehouses').fetchall()
    conn.close()
    
    wh_data = []
    for wh in warehouses:
        percent = (wh['current_load'] / wh['capacity']) * 100
        wh_data.append({
            **dict(wh),
            'percent': round(percent, 1),
            'color': 'bg-red-500' if percent > 90 else ('bg-yellow-500' if percent > 70 else 'bg-emerald-500')
        })
        
    return render_template('admin.html', warehouses=wh_data)

@app.route('/admin/add_warehouse', methods=['POST'])
@login_required('admin')
def add_warehouse():
    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO warehouses (name, location_address, region, lat, lng, capacity, manager_name, contact_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request.form['name'],
            request.form['address'],
            request.form['region'],
            request.form['lat'],
            request.form['lng'],
            request.form['capacity'],
            request.form['manager'],
            request.form['contact']
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        return f"Error: {e}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)