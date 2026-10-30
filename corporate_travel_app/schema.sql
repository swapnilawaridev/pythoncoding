-- Corporate travel portal schema (SQLite)

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    company_size TEXT,
    monthly_trips TEXT,
    message TEXT,
    source TEXT DEFAULT 'website',
    status TEXT NOT NULL DEFAULT 'new',      -- new, contacted, proposal, won, lost
    notes TEXT DEFAULT '',
    company_id INTEGER REFERENCES companies(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gst_number TEXT,
    billing_address TEXT,
    max_trip_budget REAL DEFAULT 0,          -- 0 = no limit
    approval_required INTEGER NOT NULL DEFAULT 1,
    allowed_flight_class TEXT DEFAULT 'economy',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,                      -- agency_admin, company_admin, employee
    company_id INTEGER REFERENCES companies(id),
    department TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS travel_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    requested_by INTEGER NOT NULL REFERENCES users(id),
    trip_type TEXT NOT NULL,                 -- flight, hotel, flight_hotel, train, cab, visa
    origin TEXT,
    destination TEXT NOT NULL,
    depart_date TEXT NOT NULL,
    return_date TEXT,
    travelers INTEGER NOT NULL DEFAULT 1,
    travel_class TEXT DEFAULT 'economy',
    purpose TEXT,
    budget REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending_approval',
        -- pending_approval, approved, quoted, quote_accepted, booked, rejected, cancelled
    quote_amount REAL,
    quote_details TEXT,
    booking_reference TEXT,
    booking_details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES travel_requests(id),
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
