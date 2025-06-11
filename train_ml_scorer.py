# train_ml_scorer.py
import pandas as pd
import sqlite3
import os
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder
import joblib # For saving the model

print("--- Starting ML Scorer Training ---")

# --- 1. Load Data ---
DB_PATH = 'properties.db'
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("SELECT * FROM properties", conn)
conn.close()
print(f"Loaded {len(df)} rows from the database.")

# --- 2. Create Target Variable 'suitability' ---
# This is a simplified "heuristic" to create training labels.
def create_suitability_label(row):
    if row['price'] and row['bedrooms']:
        # Example logic: good deals are more suitable
        if row['price'] / (row['bedrooms'] + 1) < 1000000:
            return 'Good Match'
    return 'Okay Match'

df['suitability'] = df.apply(create_suitability_label, axis=1)

# --- 3. Preprocess Data ---
df.dropna(subset=['location', 'propertyTy', 'price', 'bedrooms', 'bathrooms'], inplace=True)
features = ['location', 'propertyTy', 'price', 'bedrooms', 'bathrooms']
target = 'suitability'

label_encoders = {}
for column in ['location', 'propertyTy']:
    le = LabelEncoder()
    df[column] = le.fit_transform(df[column])
    label_encoders[column] = le

X = df[features]
y = df[target]

# --- 4. Train Model ---
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = DecisionTreeClassifier(random_state=42)
model.fit(X_train, X_test)

# --- 5. Evaluate and Save ---
predictions = model.predict(X_test)
print(f"ML Model Accuracy on test set: {accuracy_score(y_test, predictions) * 100:.2f}%")

joblib.dump(model, 'ml_suitability_model.joblib')
joblib.dump(label_encoders, 'ml_label_encoders.joblib')

print("--- ML Model and Encoders saved successfully! ---")