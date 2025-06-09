import pandas as pd
import sqlite3
import os

print("Attempting to create/update database...")

script_dir = os.path.dirname(os.path.abspath(__file__))

# Get the parent directory (e.g., /home/user/project/) which is our main backend/project directory
backend_dir = os.path.dirname(script_dir)

# load the Excel file 
EXCEL_FILE_NAME = 'propertiesDB.xlsx'
EXCEL_FILE_PATH = os.path.join(script_dir, EXCEL_FILE_NAME) 

print(f"Loading Excel file from: {EXCEL_FILE_PATH}")

try:
    df = pd.read_excel(EXCEL_FILE_PATH)
    print("Excel file loaded successfully.")
except FileNotFoundError:
    print(f"ERROR: Excel file not found at {EXCEL_FILE_PATH}")
    print("Please ensure the file exists at that exact path relative to this script.")
    exit()
except Exception as e:
    print(f"ERROR: Could not read Excel file. Error: {e}")
    exit()

print(f"Original Excel columns: {df.columns.tolist()}")

# to Renaming 'displayAddress' to 'location'
if 'displayAddress' in df.columns:
    df = df.rename(columns={'displayAddress': 'location'})
    print("Renamed 'displayAddress' to 'location'")
else:
    print("Column 'displayAddress' not found, skipping rename to 'location'.")

#the column for property type is named 'propertyTy' in DataFrame
potential_property_type_columns = ['PropertyType', 'Property Type', 'property type', 'property_type', 'PropertyTy', 'propertyType']
actual_property_type_col_in_df = None
for col_name in potential_property_type_columns:
    if col_name in df.columns:
        if col_name != 'propertyTy':
            df = df.rename(columns={col_name: 'propertyTy'})
            print(f"Renamed Excel column '{col_name}' to 'propertyTy' in DataFrame.")
        else:
            print("DataFrame already has a column named 'propertyTy'.")
        actual_property_type_col_in_df = 'propertyTy'
        break

if not actual_property_type_col_in_df and 'propertyTy' not in df.columns:
    print("WARNING: Could not find a suitable column to rename to 'propertyTy'.")
    print("Please ensure your Excel has a property type column (e.g., 'PropertyType', 'propertyTy', etc.)")

# 3. Create or open SQLite database
DB_FILE_NAME = 'properties.db'
DB_FULL_PATH = os.path.join(backend_dir, DB_FILE_NAME)

print(f"Current working directory (where script is run from): {os.getcwd()}") # For debugging on server
print(f"Script directory: {script_dir}")
print(f"Backend directory (for DB): {backend_dir}")
print(f"Attempting to create/update database at: {DB_FULL_PATH}")

if os.path.exists(DB_FULL_PATH):
    try:
        os.remove(DB_FULL_PATH)
        print(f"Deleted existing database file: {DB_FULL_PATH}")
    except Exception as e:
        print(f"ERROR: Could not delete existing database file {DB_FULL_PATH}. Error: {e}")
        print("Please close any programs using it (like DB Browser for SQLite) and try again.")
        exit()

conn = sqlite3.connect(DB_FULL_PATH)
cursor = conn.cursor()

# This CREATE TABLE is a fallback, df.to_sql with if_exists='replace' will define the schema.
expected_columns_sql = '''
    CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY, 
        title TEXT,
        location TEXT, 
        bathrooms INTEGER,
        bedrooms INTEGER,
        addedOn TEXT,
        type TEXT,
        rera TEXT,
        propertyTy TEXT, 
        price REAL,
        country TEXT
    )
'''
cursor.execute(expected_columns_sql)
print("Executed CREATE TABLE IF NOT EXISTS statement (as a fallback).")

# Add 'id' column if it doesn't exist from Excel
if 'id' not in df.columns:
    df.insert(0, 'id', range(1, 1 + len(df)))
    print("Added 'id' column to DataFrame as it was missing.")
elif df['id'].isnull().any() or df['id'].duplicated().any(): # If 'id' exists but is problematic
    print("Warning: 'id' column has nulls or duplicates. Regenerating 'id' column.")
    df = df.drop(columns=['id'], errors='ignore')
    df.insert(0, 'id', range(1, 1 + len(df)))


print(f"DataFrame columns just before df.to_sql: {df.columns.tolist()}")
try:
    # Ensure all columns from expected_columns_sql (minus id if auto-generated) are in df
    df.to_sql('properties', conn, if_exists='replace', index=False)
    print("DataFrame successfully written to 'properties' table, replacing old table if it existed.")
except Exception as e:
    print(f"ERROR: df.to_sql failed. Error: {e}")
    conn.close()
    exit()

conn.commit()
conn.close()
print(f" Database created/updated successfully at: {DB_FULL_PATH}")
print("Please restart your Flask application (app.py) if it's running.")