# ==============================================================================
# All necessary imports are now at the top
# ==============================================================================
import sys
import os
import re
import json
import sqlite3
from datetime import datetime
from math import exp
import spacy
from fuzzywuzzy import process as fuzzy_process
import openai
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS

# ==============================================================================
# --- NLP SERVICE LOGIC (from services/nlp_service.py) ---
# ==============================================================================
try:
    nlp = spacy.load("en_core_web_sm")
    print("spaCy model (en_core_web_sm) loaded successfully.")
except Exception as e:
    print(f"FATAL: Could not load spaCy model: {e}")
    nlp = None

LOCATION_SYNONYM_MAP = {"duba": "dubai", "dbi": "dubai", "jbr": "jumeirah beach residence", "jltowers": "jumeirah lake towers"}
KNOWN_LOCATIONS = [ "dubai", "abu dhabi", "sharjah", "ajman", "jumeirah", "marina", "dubai marina", "meydan", "downtown dubai", "jumeirah lake towers", "jlt", "dubai hills estate", "dubai investment park", "dip", "jumeirah village circle", "jvc", "business bay", "palm jumeirah", "arjan", "al furjan", "dubai south", "wasl gate", "city of lights", "al reem island", "expo city", "discovery gardens", "al barsha", "the springs", "arabian ranches", "motor city", "sports city", "dubailand", "al khail", "sheikh zayed road", "jumeirah beach residence" ]
KNOWN_PROPERTY_TYPES = {
    "apartment": ["apartment", "flat", "unit", "studio", "loft", "duplex apartment", "1br", "2br", "3br", "4br", "1bhk", "2bhk", "3bhk"],
    "villa": ["villa", "house", "home", "mansion", "compound villa", "bungalow"],
    "townhouse": ["townhouse", "town house"], "penthouse": ["penthouse"], "land": ["land", "plot"],
    "office": ["office", "commercial space", "shop", "retail", "warehouse", "showroom"]
}
GREETING_KEYWORDS = ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", "sup", "yo", "heya", "howdy"]
PREFERENCE_KEYWORDS_MAP = { "luxury": ["luxury", "luxurious", "high-end", "premium", "exclusive"], "view": ["view", "sea view", "marina view"], "new_property": ["new", "brand new", "off-plan"], "quiet_area": ["quiet", "peaceful", "secluded"], "furnished_property": ["furnished"], "spacious_property": ["spacious", "large", "big"], "near_metro": ["metro", "near metro"], "family_friendly_area": ["family friendly", "for family"], "good_investment": ["roi", "investment", "rental yield"], "pet_friendly": ["pet friendly", "pets allowed"], "has_pool": ["pool", "swimming pool"], "has_gym": ["gym", "fitness"], "has_balcony_terrace": ["balcony", "terrace", "garden"], "near_beach": ["beach", "beachfront"], "parking_available": ["parking", "garage"] }

def process_query(query_text_original_case):
    if not nlp: return {"error": "NLP model unavailable"}
    query_lower = query_text_original_case.lower()
    doc = nlp(query_text_original_case) 
    extracted = {"is_greeting": False, "location": None, "property_type": None, "bedrooms": None, "budget": None, "preferences": [], "purpose": None}
    if any(greet_word in query_lower for greet_word in GREETING_KEYWORDS) and len(doc) < 4:
        extracted["is_greeting"] = True
        return extracted
    # Location Extraction
    found_location = None
    for loc_phrase in sorted([loc for loc in KNOWN_LOCATIONS if " " in loc], key=len, reverse=True):
        if loc_phrase in query_lower: found_location = loc_phrase; break
    if not found_location:
        potential_words = [token.text for token in doc if token.pos_ in ["PROPN", "NOUN"] and not token.is_stop]
        for word in potential_words:
            word_lower = word.lower()
            if word_lower in KNOWN_LOCATIONS: found_location = word_lower; break
            match, score = fuzzy_process.extractOne(word_lower, KNOWN_LOCATIONS)
            if score >= 85: found_location = match; break
    extracted["location"] = found_location
    # Property Type Extraction
    found_property_type = None
    for main_type, synonyms in KNOWN_PROPERTY_TYPES.items():
        if found_property_type: break
        for syn in synonyms:
            if syn in query_lower: found_property_type = main_type; break
    extracted["property_type"] = found_property_type
    # Bedroom and Budget Extraction
    bedroom_match = re.search(r'(\d+)\s*(?:br\b|bed|bhk|bedroom)', query_lower)
    if bedroom_match: extracted["bedrooms"] = int(bedroom_match.group(1))
    budget_match = re.search(r'(\d[\d,]*\.?\d*)\s*(million|k|thousand|aed|dhs)', query_lower, re.IGNORECASE)
    if budget_match:
        value = float(budget_match.group(1).replace(',', ''))
        qualifier = budget_match.group(2).lower()
        if "million" in qualifier: extracted["budget"] = int(value * 1000000)
        elif "k" in qualifier or "thousand" in qualifier: extracted["budget"] = int(value * 1000)
        else: extracted["budget"] = int(value)
    # Preferences and Purpose Extraction
    current_preferences = []
    for pref_key, pref_syns in PREFERENCE_KEYWORDS_MAP.items():
        if any(re.search(r'\b' + re.escape(s) + r'\b', query_lower) for s in pref_syns):
            current_preferences.append(pref_key)
    extracted["preferences"] = list(set(current_preferences))
    if "investment" in query_lower or "roi" in query_lower: extracted["purpose"] = "investment"
    elif "live" in query_lower or "family" in query_lower: extracted["purpose"] = "living"
    return extracted


# ==============================================================================
# --- SUITABILITY SCORER LOGIC (from services/suitability_scorer.py) ---
# ==============================================================================
WEIGHTS = {'property_type': 25, 'budget': 30, 'bedrooms': 20, 'preferences': 15, 'purpose': 10}
PREFERENCE_BOOSTS = {'must_have': 1.5, 'important': 1.2, 'nice_to_have': 0.8}

def calculate_suitability_score(property_details, user_criteria):
    score, total_weight = 0, 0
    uc = {k.lower(): v for k, v in user_criteria.items()}
    uc.setdefault('preferences', [])
    pd_details = {k.lower(): v for k, v in property_details.items()}
    
    if uc.get('property_type') and pd_details.get('propertyty'):
        total_weight += WEIGHTS['property_type']
        if uc['property_type'].lower() in pd_details['propertyty'].lower(): score += WEIGHTS['property_type']
            
    if uc.get('budget') and pd_details.get('price') is not None:
        total_weight += WEIGHTS['budget']
        if pd_details['price'] <= uc['budget']: score += WEIGHTS['budget']

    if uc.get('bedrooms') is not None and pd_details.get('bedrooms') is not None:
        total_weight += WEIGHTS['bedrooms']
        if uc['bedrooms'] == pd_details['bedrooms']: score += WEIGHTS['bedrooms']
    
    if uc.get('preferences'):
        total_weight += WEIGHTS['preferences']
        matched_prefs = 0
        prop_title = pd_details.get('title', '').lower()
        for pref in uc['preferences']:
            if pref.replace('_', ' ') in prop_title: matched_prefs += 1
        if uc['preferences']: score += (matched_prefs / len(uc['preferences'])) * WEIGHTS['preferences']

    return round((score / total_weight) * 100, 2) if total_weight > 0 else 0


# ==============================================================================
# --- DATABASE LOGIC (from database/database.py) ---
# ==============================================================================
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'properties.db')

def get_properties(processed_query):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM properties WHERE 1=1"
        params = []
        if processed_query.get('location'):
            query += " AND country LIKE ?"
            params.append(f"%{processed_query['location']}%")
        if processed_query.get('bedrooms') is not None:
            query += " AND bedrooms = ?"
            params.append(processed_query['bedrooms'])
        if processed_query.get('budget') is not None:
            query += " AND price <= ?"
            params.append(processed_query['budget'])
        if processed_query.get('property_type'):
            query += " AND propertyTy LIKE ?"
            params.append(f"%{processed_query['property_type']}%")
        
        print(f"Executing SQL: {query} with params: {params}")
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# ==============================================================================
# --- MAIN FLASK APPLICATION ---
# ==============================================================================
app = Flask(__name__)
CORS(app, resources={
    r"/search": {"origins": "https://incredible-sprinkles-9e8229.netlify.app"},
    r"/log_feedback": {"origins": "https://incredible-sprinkles-9e8229.netlify.app"}
})

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY: print("WARNING: OPENAI_API_KEY not set.")

FEEDBACK_TAG = "[ASK_FOR_FEEDBACK]"
SYSTEM_PROMPT = """You are a world-class conversational AI, acting as a friendly, proactive, and highly capable real estate assistant for Keller Williams Dubai... 
(--- You must paste your full, detailed SYSTEM_PROMPT string here ---)"""


@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "https://incredible-sprinkles-9e8229.netlify.app")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response

    data = request.get_json()
    user_message = data.get('query', '').strip()
    criteria = data.get('criteria_so_far', {}) 
    conversation_history = data.get('conversation_history', [])

    if user_message == "__INITIATE_CHAT__":
        initial_ai_response = generate_ai_response("User has opened the chat.", {}, [], [])
        return jsonify({ "bot_dialogue_message": initial_ai_response, "search_results": [], "current_search_criteria_for_frontend": {}, "ask_for_feedback": False })

    nlp_results = process_query(user_message)
    has_new_search_info = any(nlp_results.get(key) for key in ['location', 'property_type', 'bedrooms', 'budget', 'purpose', 'preferences'])

    if has_new_search_info:
        for key, value in nlp_results.items():
            if value is not None and value != []: criteria[key] = value
    
    properties_from_db = []
    if criteria.get('location') and criteria.get('property_type') and has_new_search_info:
        properties_from_db = get_properties(criteria)
        if properties_from_db:
            for prop in properties_from_db:
                prop['suitability_score'] = calculate_suitability_score(prop, criteria)
            properties_from_db = sorted(properties_from_db, key=lambda x: x['suitability_score'], reverse=True)
            
    ai_bot_response_text = generate_ai_response(user_message, criteria, properties_from_db[:5], conversation_history)
    
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
    if not OPENAI_API_KEY: return "AI service is currently unavailable."
    history_for_prompt = "\n".join([f"User: {turn.get('user', '')}\nBot: {turn.get('bot', '')}" for turn in conversation_history[-3:]])
    criteria_summary = ", ".join([f"{k}: {v}" for k, v in criteria.items() if v]) or "None yet"
    properties_summary = "No properties found."
    if properties:
        properties_summary = f"Found {len(properties)} properties. Top 3 are:\n" + "\n".join([f"Prop{i+1}: {p.get('title')}, Price: {p.get('price')}" for i, p in enumerate(properties[:3])])
    
    prompt = f"{SYSTEM_PROMPT}\n\n# CONTEXT\nConversation History:\n{history_for_prompt}\nUser's LATEST message: \"{user_message}\"\n\nCurrent criteria: {criteria_summary}\nDatabase Search Results: {properties_summary}\n\n# YOUR TASK\nYour response:"
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error from OpenAI: {e}")
        return "Sorry, I'm having trouble thinking right now."

@app.route('/log_feedback', methods=['POST'])
def log_feedback():
    feedback_data = request.get_json()
    if not feedback_data: return jsonify({"status": "error", "message": "No data"}), 400
    print(f"Received feedback: {feedback_data}")
    # In a real app, save this to a more robust logging service or database.
    return jsonify({"status": "success"})

# Note: The if __name__ == '__main__': block is removed for server deployment
