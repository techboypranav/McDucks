import sqlite3
from werkzeug.security import generate_password_hash
import time

DB_NAME = "agri_logistics.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    
    # Warehouses
    c.execute('''CREATE TABLE IF NOT EXISTS warehouses 
                 (id INTEGER PRIMARY KEY, name TEXT, region TEXT, capacity INTEGER, current_load INTEGER, lat REAL, lon REAL)''')
    
    # Orders (Updated with Contact Number and Timestamp)
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY, 
                  trader_id TEXT,
                  farmer_name TEXT, 
                  contact_number TEXT,
                  crop_type TEXT, 
                  region TEXT, 
                  quantity INTEGER, 
                  grade TEXT, 
                  warehouse_id INTEGER, 
                  status TEXT, 
                  simulated_lat REAL, 
                  simulated_lon REAL,
                  timestamp REAL,
                  FOREIGN KEY(warehouse_id) REFERENCES warehouses(id))''')

    # Seed Data
    user = c.execute("SELECT * FROM users WHERE username = ?", ('trader1',)).fetchone()
    if not user:
        pwhash = generate_password_hash('trader_pass_2026')
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('trader1', pwhash, 'TRADER'))

    wh_check = c.execute("SELECT count(*) FROM warehouses").fetchone()[0]
    if wh_check == 0:
        warehouses = [
            ('North_Hub_1', 'NORTH', 1000, 0, 28.7041, 77.1025),
            ('South_Hub_1', 'SOUTH', 2000, 0, 13.0827, 80.2707),
            ('West_Hub_1', 'WEST', 1500, 0, 19.0760, 72.8777),
        ]
        c.executemany("INSERT INTO warehouses (name, region, capacity, current_load, lat, lon) VALUES (?,?,?,?,?,?)", warehouses)

    conn.commit()
    conn.close()
    print("Database Initialized.")