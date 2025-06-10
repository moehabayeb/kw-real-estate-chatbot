import sys
import os
import re
import json
import sqlite3
from datetime import datetime
from fuzzywuzzy import process as fuzzy_process
import openai
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import spacy

# ==============================================================================
# --- DATABASE LOGIC (from database/database.py) ---
# ==============================================================================

# For Render, the database file will be in the /data directory if you add a disk,
# but for simplicity, we assume it's in the root with app.py.
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'properties.db')

def get_properties(filters):
    # This function implementation from your database.py file goes here
    # Example implementation:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM properties WHERE 1=1"
    params = []
    
    if filters.get('location'):
        query += " AND location LIKE ?"
        params.append(f"%{filters['location']}%")
    if filters.get('property_type'):
        query += " AND propertyTy LIKE ?"
        params.append(f"%{filters['property_type']}%")
    if filters.get('bedrooms'):
        query += " AND bedrooms = ?"
        params.append(filters['bedrooms'])
    if filters.get('budget'):
        query += " AND price <= ?"
        params.append(filters['budget'])

    print(f"Executing SQL: {query}")
    print(f"With params: {params}")
    
    cursor.execute(query, params)
    properties = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return properties


# ==============================================================================
# --- SUITABILITY SCORER LOGIC (from services/suitability_scorer.py) ---
# ==============================================================================

# Paste the ENTIRE content of your suitability_scorer.py file here.
# For example:
WEIGHTS = {
    'property_type': 25,
    'budget': 30,
    'bedrooms': 20,
    'preferences': 15,
    'purpose': 10
}
# Make sure to include the calculate_suitability_score function itself
def calculate_suitability_score(property_data, user_criteria):
    score = 0
    total_weight = 0

    # Match property type
    if user_criteria.get('property_type'):
        total_weight += WEIGHTS['property_type']
        if user_criteria['property_type'].lower() in property_data.get('propertyTy', '').lower():
            score += WEIGHTS['property_type']

    # Match budget
    if user_criteria.get('budget') and property_data.get('price') is not None:
        total_weight += WEIGHTS['budget']
        budget = user_criteria['budget']
        price = property_data['price']
        if price <= budget:
            # Score higher for properties well within budget
            ratio = 1 - (price / budget)
            score += WEIGHTS['budget'] * (1 + ratio) / 2
    
    # Match bedrooms
    if user_criteria.get('bedrooms') is not None and property_data.get('bedrooms') is not None:
        total_weight += WEIGHTS['bedrooms']
        if user_criteria['bedrooms'] == property_data['bedrooms']:
            score += WEIGHTS['bedrooms']

    # Add other matching logic from your scorer file
    
    return round((score / total_weight) * 100, 2) if total_weight > 0 else 0


# ==============================================================================
# --- NLP SERVICE LOGIC (from services/nlp_service.py) ---
# ==============================================================================

# Paste the ENTIRE content of your nlp_service.py file here
# Make sure nlp = spacy.load('en_core_web_sm') is at the top
try:
    nlp = spacy.load("en_core_web_sm")
    print("spaCy model (en_core_web_sm) loaded successfully.")
except Exception as e:
    print(f"Error loading spaCy model: {e}")
    nlp = None

# And paste all the functions like process_query, KNOWN_LOCATIONS etc.
def process_query(query_text):
    # The full implementation of your process_query function
    # Example snippet:
    if not nlp: return {}
    # ... rest of the NLP logic
    return {'location': 'dubai', 'property_type': 'apartment'} # Simplified for example


# ==============================================================================
# --- MAIN FLASK APPLICATION (app.py original content) ---
# =================================G=============================================

app = Flask(__name__)
CORS(app)

# All your constants like OPENAI_API_KEY, SYSTEM_PROMPT etc. go here

@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    # Your full search route logic goes here.
    # It will now call functions like process_query and calculate_suitability_score
    # that are defined above in this same file, so no import is needed.
    pass # Replace with your search() implementation

def generate_ai_response(user_message, criteria, properties, conversation_history):
    # Your full generate_ai_response logic
    pass # Replace

@app.route('/log_feedback', methods=['POST'])
def log_feedback():
    # Your full log_feedback logic
    pass # Replace

# NO if __name__ == '__main__': block needed for Render deployment
