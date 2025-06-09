import pandas as pd
import sqlite3
import os

# Load Excel file
df = pd.read_excel("propertiesDB.xlsx")

# Create the SQLite database
db_path = os.path.join(os.path.dirname(__file__), "properties.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Optional: Drop the table if it exists
cursor.execute("DROP TABLE IF EXISTS properties")

# Create table (customize fields based on your Excel columns)
cursor.execute("""
    CREATE TABLE properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT,
        size TEXT,
        property_type TEXT,
        price INTEGER
    )
""")

# Insert data
for _, row in df.iterrows():
    cursor.execute("""
        INSERT INTO properties (location, size, property_type, price)
        VALUES (?, ?, ?, ?)
    """, (
        row['CountryNameEn'],
        str(row['Size']),
        row['PropertyTypeEn'],
        int(row['ProcedureValue']) if not pd.isna(row['ProcedureValue']) else 0
    ))

conn.commit()
conn.close()
print("✅ Database imported successfully!")
