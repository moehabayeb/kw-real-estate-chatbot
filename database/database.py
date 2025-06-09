# C:\xampp\htdocs\ClassWork\Backend\database\database.py
import sqlite3
import os

# DB_PATH points to properties.db in the 'Backend' directory
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "properties.db")

def connect_db():
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def initialize_db():
    """
    Initializes the database by creating the 'properties' table if it doesn't exist.
    """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY,
            title TEXT,
            location TEXT, 
            bathrooms INTEGER,
            bedrooms INTEGER, -- Changed NOT NULL to allow NULL if NLP doesn't find it
            addedOn TEXT,
            type TEXT,
            rera TEXT,
            propertyTy TEXT, 
            price REAL, -- Changed NOT NULL to allow NULL
            country TEXT -- Changed NOT NULL to allow NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully (if table needed creating)!")

def get_properties(processed_query):
    """
    Fetches properties from the database based on a processed query.
    """
    conn = connect_db()
    conn.row_factory = sqlite3.Row # To access columns by name
    cursor = conn.cursor()

    query = "SELECT * FROM properties WHERE 1=1"
    params = []

    location = processed_query.get('location')
    bedrooms = processed_query.get('bedrooms')
    budget = processed_query.get('budget')
    property_type_from_nlp = processed_query.get('property_type') # Renamed to avoid confusion

    if location:
        # The 'country' column in your DB seems to store location names like 'Dubai'
        query += " AND country LIKE ?" 
        params.append(f"%{location}%")

    if bedrooms is not None: # Check for None specifically, as 0 bedrooms could be valid
        query += " AND bedrooms = ?"
        params.append(bedrooms)

    if budget is not None: # Check for None
        query += " AND price <= ?"
        params.append(budget)

    if property_type_from_nlp:
        # FIX: Changed 'property_type' to 'propertyTy' to match your DB schema
        query += " AND propertyTy LIKE ?" 
        params.append(f"%{property_type_from_nlp}%")
    
    print(f"Executing SQL: {query}") # Log the query
    print(f"With params: {params}")   # Log the parameters

    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database query error: {e}")
        rows = [] 
    finally:
        conn.close()

    results = []
    if rows:
        for row in rows:
            results.append(dict(row)) # Convert each sqlite3.Row object to a dictionary
    
    return results

# If you run this file directly, initialize the DB (optional)
if __name__ == '__main__':
    print(f"Database path is: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("Database file not found. Consider running create_db_from_excel.py first.")
    else:
        print("Database file found.")
    initialize_db() 