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
# --- NLP SERVICE LOGIC (with new "express_interest" intent) ---
# ==============================================================================
try:
    nlp = spacy.load("en_core_web_sm")
    print("spaCy model (en_core_web_sm) loaded successfully.")
except Exception as e:
    print(f"FATAL: Could not load spaCy model: {e}")
    nlp = None

KNOWN_LOCATIONS = [ "dubai", "abu dhabi", "sharjah", "jumeirah", "marina", "downtown dubai", "jvc", "palm jumeirah", "business bay" ]
KNOWN_PROPERTY_TYPES = {"apartment": ["apartment", "flat", "studio"], "villa": ["villa", "house", "home"], "townhouse": ["townhouse"]}
INTEREST_KEYWORDS = ["like that", "tell me more", "interested in", "i liked", "that one seems good", "what about that first one"]

def process_query(query_text_original_case):
    if not nlp: return {}
    query_lower = query_text_original_case.lower()
    
    # --- NEW: Check for interest intent FIRST ---
    if any(keyword in query_lower for keyword in INTEREST_KEYWORDS):
        return {"intent": "express_interest"}
    
    # --- Existing logic continues if it's not an interest expression ---
    extracted = {'location': None, 'property_type': None, 'budget': None, 'bedrooms': None, "intent": "search_properties"}
    for loc in KNOWN_LOCATIONS:
        if loc in query_lower:
            extracted['location'] = loc
            break
    for p_type, synonyms in KNOWN_PROPERTY_TYPES.items():
        for syn in synonyms:
            if syn in query_lower:
                extracted['property_type'] = p_type
                break
    # Add other extraction logic here (budget, bedrooms, etc.)
    return extracted

# ==============================================================================
# --- SUITABILITY SCORER LOGIC (Unchanged) ---
# ==============================================================================
WEIGHTS = {'property_type': 25, 'budget': 30, 'bedrooms': 20}
def calculate_suitability_score(property_details, user_criteria):
    score, total_weight = 0, 0
    if user_criteria.get('property_type'):
        total_weight += WEIGHTS['property_type']
        if user_criteria['property_type'].lower() in property_details.get('propertyTy', '').lower(): score += WEIGHTS['property_type']
    if user_criteria.get('budget') and property_details.get('price') is not None:
        total_weight += WEIGHTS['budget']
        if property_details['price'] <= user_criteria['budget']: score += WEIGHTS['budget']
    if user_criteria.get('bedrooms') is not None and property_details.get('bedrooms') is not None:
        total_weight += WEIGHTS['bedrooms']
        if user_criteria['bedrooms'] == property_details['bedrooms']: score += WEIGHTS['bedrooms']
    return round((score / total_weight) * 100, 2) if total_weight > 0 else 0

# ==============================================================================
# --- DATABASE LOGIC (Unchanged) ---
# ==============================================================================
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'properties.db')
def get_properties(filters):
    try:
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
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        return []

# ==============================================================================
# --- MAIN FLASK APPLICATION ---
# ==============================================================================

app = Flask(__name__)
CORS(app)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
FEEDBACK_TAG = "[ASK_FOR_FEEDBACK]"

# --- REFINED SYSTEM PROMPT with new rule ---
SYSTEM_PROMPT = """You are a world-class conversational AI, acting as a friendly, proactive, and highly capable real estate assistant for Keller Williams Dubai.

Your Core Directives:
- You MUST politely decline any off-topic questions (like trivia or jokes) and redirect to real estate.
- Use conversation history to stay in context.

Your "Conversational Toolkit":
1.  If the user provides new search criteria: Acknowledge it and present the new search results.
2.  If the user gives a vague response (e.g., "ok cool") after you've shown properties: Ask a specific question about those properties to guide them, like "Great, did any of those options catch your eye?".
3.  If the user expresses interest in a specific property you just showed: Acknowledge their choice, confirm which one they mean, and offer to connect them with an agent for more details or to schedule a viewing.
4.  If there are no properties to discuss: Ask a clarifying question to get more search criteria.
5.  If the user says goodbye or thanks: Conclude politely and add the [ASK_FOR_FEEDBACK] tag.
"""

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "Invalid JSON"}), 400

        user_message = data.get('query', '').strip()
        criteria = data.get('criteria_so_far', {}) 
        conversation_history = data.get('conversation_history', [])

        if user_message == "__INITIATE_CHAT__":
            ai_response = generate_ai_response("User has opened the chat.", {}, [], [])
            return jsonify({ "bot_dialogue_message": ai_response, "search_results": [], "current_search_criteria_for_frontend": {}, "ask_for_feedback": False })

        nlp_results = process_query(user_message)

        # --- NEW LOGIC: Check for the interest intent first ---
        if nlp_results.get("intent") == "express_interest":
            print("User expressed interest. Skipping search and generating contextual response.")
            # We send an empty properties list so the AI knows not to list them again.
            ai_response = generate_ai_response(user_message, criteria, [], conversation_history)
            return jsonify({"bot_dialogue_message": ai_response, "search_results": [], "current_search_criteria_for_frontend": criteria, "ask_for_feedback": False})

        # --- Existing logic continues if it's a search query ---
        has_new_search_info = any(nlp_results.get(key) for key in ['location', 'property_type', 'bedrooms', 'budget'])
        
        if has_new_search_info:
            print("New substantive criteria found in user message.")
            for key, value in nlp_results.items():
                if value is not None: criteria[key] = value

        properties_from_db = []
        if criteria.get('location') and criteria.get('property_type') and has_new_search_info:
            properties_from_db = get_properties(criteria)
            if properties_from_db:
                for prop in properties_from_db:
                    prop['suitability_score'] = calculate_suitability_score(prop, criteria)
                properties_from_db.sort(key=lambda x: x['suitability_score'], reverse=True)

        ai_response = generate_ai_response(user_message, criteria, properties_from_db, conversation_history)
        
        ask_for_feedback = FEEDBACK_TAG in ai_response
        ai_response = ai_response.replace(FEEDBACK_TAG, "").strip()

        return jsonify({
            "bot_dialogue_message": ai_response,
            "search_results": properties_from_db,
            "current_search_criteria_for_frontend": criteria,
            "ask_for_feedback": ask_for_feedback
        })

    except Exception as e:
        print(f"!!! SERVER ERROR in /search: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred."}), 500

def generate_ai_response(user_message, criteria, properties, conversation_history):
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY environment variable is not set on the server.")
        return "Sorry, my AI capabilities are currently offline."

    history_for_prompt = "\n".join([f"{'User' if k=='user' else 'Bot'}: {v}" for turn in conversation_history[-4:] for k, v in turn.items()])
    criteria_summary = ", ".join([f"{k}: {v}" for k, v in criteria.items() if v]) or "None"
    prop_summary = "No new properties found for this query."
    if properties:
        prop_summary = f"Found {len(properties)} properties. Top results are:\n" + "\n".join([f"- {p.get('title')}" for p in properties[:3]])
    
    prompt = f"{SYSTEM_PROMPT}\n\n# CONTEXT\n{history_for_prompt}\nUser: {user_message}\n\nCurrent Search Criteria: {criteria_summary}\nDatabase Search: {prop_summary}\n\n# YOUR TASK\nProvide the next single, concise response for the bot:"
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"!!! ERROR calling OpenAI: {e}")
        return "Sorry, I'm having trouble thinking right now."

@app.route('/log_feedback', methods=['POST'])
def log_feedback():
    print(f"Received feedback: {request.get_json()}")
    return jsonify({"status": "success"})
