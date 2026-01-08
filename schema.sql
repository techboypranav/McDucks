DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS warehouses;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE warehouses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location_address TEXT NOT NULL,
    region TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    capacity INTEGER NOT NULL,
    current_load INTEGER DEFAULT 0,
    manager_name TEXT,
    contact_number TEXT
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trader_id INTEGER,
    farmer_name TEXT NOT NULL,
    farmer_address TEXT NOT NULL,
    crop TEXT NOT NULL,
    grade TEXT,
    quantity REAL NOT NULL,
    assigned_warehouse_id INTEGER,
    distance_km REAL,
    eta_mins INTEGER,
    status TEXT DEFAULT 'In Transit',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(assigned_warehouse_id) REFERENCES warehouses(id)
);