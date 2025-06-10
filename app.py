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
# --- NLP SERVICE LOGIC (from services/nlp_service.py) ---
# ==============================================================================
try:
    nlp = spacy.load("en_core_web_sm")
    print("spaCy model (en_core_web_sm) loaded successfully.")
except Exception as e:
    print(f"Error loading spaCy model: {e}")
    nlp = None

# Add your KNOWN_LOCATIONS, KNOWN_PROPERTY_TYPES etc. from nlp_service.py here
KNOWN_LOCATIONS = ["dubai", "abu dhabi", "sharjah", "jumeirah", "marina", "downtown dubai", "jvc"]
KNOWN_PROPERTY_TYPES = {"apartment": ["apartment", "flat"], "villa": ["villa", "house"]}
# ... and so on for all your keyword lists ...

def process_query(query_text_original_case):
    # This should be the FULL process_query function from your nlp_service.py
    # This is a simplified example, you must paste your real one here.
    if not nlp: return {}
    query_lower = query_text_original_case.lower()
    extracted = {'location': None, 'property_type': None, 'budget': None, 'bedrooms': None}
    for loc in KNOWN_LOCATIONS:
        if loc in query_lower:
            extracted['location'] = loc
            break
    for type, synonyms in KNOWN_PROPERTY_TYPES.items():
        for syn in synonyms:
            if syn in query_lower:
                extracted['property_type'] = type
                break
    budget_match = re.search(r'(\d+)\s*m', query_lower)
    if budget_match:
        extracted['budget'] = int(budget_match.group(1)) * 1000000
    
    return extracted

# ==============================================================================
# --- SUITABILITY SCORER LOGIC (from services/suitability_scorer.py) ---
# ==============================================================================
WEIGHTS = {
    'property_type': 25,
    'budget': 30,
    'bedrooms': 20,
    'preferences': 15,
    'purpose': 10
}
def calculate_suitability_score(property_data, user_criteria):
    # This should be the FULL calculate_suitability_score function from your scorer file
    score = 0
    total_weight = 0
    if user_criteria.get('property_type'):
        total_weight += WEIGHTS['property_type']
        if user_criteria['property_type'].lower() in property_data.get('propertyTy', '').lower():
            score += WEIGHTS['property_type']
    # ... add the rest of your scoring logic ...
    return round((score / total_weight) * 100, 2) if total_weight > 0 else 0


# ==============================================================================
# --- DATABASE LOGIC (from database/database.py) ---
# ==============================================================================
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'properties.db')

def get_properties(filters):
    # Using a with statement ensures the connection is closed
    with sqlite3.connect(DATABASE_PATH) as conn:
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

        print(f"Executing SQL: {query} with params: {params}")
        
        cursor.execute(query, params)
        properties = [dict(row) for row in cursor.fetchall()]
        return properties


# ==============================================================================
# --- MAIN FLASK APPLICATION ---
# ==============================================================================

app = Flask(__name__)

# --- CORS FIX FOR LIVE DEPLOYMENT ---
CORS(app, resources={
    r"/search": {"origins": "https://incredible-sprinkles-9e8229.netlify.app"},
    r"/log_feedback": {"origins": "https://incredible-sprinkles-9e8229.netlify.app"}
})
# --- END CORS FIX ---

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set.")

FEEDBACK_TAG = "[ASK_FOR_FEEDBACK]"
SYSTEM_PROMPT = """You are a world-class conversational AI for Keller Williams Dubai...
(--- Paste your full SYSTEM_PROMPT string here ---)"""


@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    # This entire block should be your complete search function logic
    if request.method == 'OPTIONS':
        # This handles the pre-flight request for CORS
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "https://incredible-sprinkles-9e8229.netlify.app")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response
    
    data = request.get_json()
    user_message = data.get('query', '').strip()
    criteria = data.get('criteria_so_far', {}) 
    conversation_history = data.get('conversation_history', [])

    if user_message == "__INITIATE_CHAT__":
        initial_ai_response = generate_ai_response("User opened chat", {}, [], [])
        return jsonify({"bot_dialogue_message": initial_ai_response})

    nlp_results = process_query(user_message) # This calls the function defined above

    has_new_search_info = any(nlp_results.get(key) for key in ['location', 'property_type', 'bedrooms', 'budget'])

    if has_new_search_info:
        for key, value in nlp_results.items():
            if value is not None: criteria[key] = value
    
    properties_from_db = []
    if criteria.get('location') and criteria.get('property_type') and has_new_search_info:
        properties_from_db = get_properties(criteria) # Calls the DB function above
        if properties_from_db:
            for prop in properties_from_db:
                prop['suitability_score'] = calculate_suitability_score(prop, criteria) # Calls the scorer function above
            properties_from_db = sorted(properties_from_db, key=lambda x: x['suitability_score'], reverse=True)
            
    ai_bot_response_text = generate_ai_response(user_message, criteria, properties_from_db, conversation_history)
    
    ask_for_feedback_flag = FEEDBACK_TAG in ai_bot_response_text
    if ask_for_feedback_flag:
        ai_bot_response_text = ai_bot_response_text.replace(FEEDBACK_TAG, "").strip()

    return jsonify({
        "bot_dialogue_message": ai_bot_response_text,
        "search_results": properties_from_db,
        "current_search_criteria_for_frontend": criteria,
        "ask_for_feedback": ask_for_feedback_flag
    })


def generate_ai_response(user_message, criteria, properties, conversation_history):
    # This entire block should be your complete generate_ai_response function
    if not OPENAI_API_KEY:
        return "Sorry, the AI service is currently unavailable."

    prompt = f"{SYSTEM_PROMPT}..." # Build your full prompt here
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error from OpenAI: {e}")
        return "Sorry, I'm having trouble thinking right now."


@app.route('/log_feedback', methods=['POST'])
def log_feedback():
    # This should be your complete log_feedback function
    return jsonify({"status": "success"})
