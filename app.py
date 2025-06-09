# C:\xampp\htdocs\ClassWork\Backend\app.py
import sys
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from services.nlp_service import process_query
from services.suitability_scorer import calculate_suitability_score
from database.database import get_properties
import os
import openai
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- OpenAI API Key Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY environment variable not set. LLM features will be disabled.")
# --- End OpenAI API Key Configuration ---


# --- Constants for Bot and LLM ---
FEEDBACK_TAG = "[ASK_FOR_FEEDBACK]"
AGENT_CONTACT_MESSAGE = "Would you like me to connect you with one of our expert agents for more details or to schedule a viewing?"

SYSTEM_PROMPT = f"""You are a world-class conversational AI, acting as a friendly, proactive, and highly capable real estate assistant for Keller Williams Dubai. Your goal is to guide the user to their perfect property.

Core Behaviours:
- Be Natural & Conversational: Respond to greetings, thanks, and small talk like a human.
- Be Proactive & Guiding: Don't just wait for information. If the user seems stuck or gives a vague response, guide them to the next logical step.
- Be Context-Aware: Use the conversation history and current criteria to inform every response. Never ask for information you already have.
- Be Engaging & Persuasive: When showing properties, highlight what makes them special and connect them to the user's needs.

Your "Conversational Toolkit":
1.  If new search criteria ARE provided: Acknowledge the new info and present the updated search results.
2.  If NO new search criteria are provided and the user gives a vague positive response (e.g., "ok", "yes", "sounds good"):
    - Look at the properties you just showed them.
    - Ask a specific, engaging question about those properties. Examples: "Great! Do any of those catch your eye?", "Which one of these apartments seems closer to what you're looking for?", "The villa with the private garden is quite popular. What are your thoughts on that one?"
3.  If NO new search criteria are provided and there are NO properties to discuss:
    - Look at the current criteria.
    - Ask the next most logical clarifying question to narrow the search. Examples: "To help me narrow this down, what's your approximate budget?", "Are you looking for a specific number of bedrooms?", "Is this property for you to live in, or is it for investment?"
4.  Concluding a Conversation:
    - If the user expresses satisfaction, thanks you, or says goodbye, offer final assistance (e.g., agent contact) and then end your response with the special tag: {FEEDBACK_TAG}
"""

MAX_PROPERTIES_TO_DISPLAY_FROM_DB = 20


@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    
    try:
        if not request.is_json:
            print("ERROR: Request is not JSON")
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.get_json()
        user_message = data.get('query', '').strip()
        criteria = data.get('criteria_so_far', {}) 
        conversation_history = data.get('conversation_history', [])

        print(f"\n--- New Request ---")
        print(f"User message: '{user_message}'")
        print(f"Criteria SO FAR from frontend: {criteria}")

        if user_message == "__INITIATE_CHAT__":
            print("DEBUG: '__INITIATE_CHAT__' signal received. Sending initial greeting via LLM.")
            initial_ai_response = generate_ai_response(user_message="User has just opened the chat.", criteria={}, properties=[], conversation_history=[])
            return jsonify({
                "bot_dialogue_message": initial_ai_response,
                "search_results": [],
                "current_search_criteria_for_frontend": {},
                "search_performed_with_criteria": False,
                "ask_for_feedback": False
            })

        nlp_results = process_query(user_message)
        print(f"NLP Extracted: {nlp_results}")

        has_new_search_info = any(
            nlp_results.get(key) for key in ['location', 'property_type', 'bedrooms', 'budget', 'purpose', 'preferences']
        )

        if has_new_search_info:
            print("New substantive criteria found in user message.")
            for key, value in nlp_results.items():
                if key in ['is_greeting', 'keywords']: continue
                if value is not None and value != []:
                    criteria[key] = value
        else:
            print("No new substantive criteria found in user message. Relying on conversation.")

        print(f"Updated Criteria: {criteria}")
        
        properties_from_db = []
        search_was_performed_this_turn = False

        can_search_db = criteria.get('location') and criteria.get('property_type')

        if can_search_db and has_new_search_info:
            print("Sufficient criteria AND new information provided. Performing DB search.")
            search_was_performed_this_turn = True
            db_query_params_cleaned = {k: v for k, v in criteria.items() if v is not None and k in ['location', 'property_type', 'budget', 'bedrooms']}
            
            properties_from_db = get_properties(db_query_params_cleaned)
            print(f"DB Results: Found {len(properties_from_db)} properties with params: {db_query_params_cleaned}")
            
            if properties_from_db:
                for prop in properties_from_db:
                    prop['suitability_score'] = calculate_suitability_score(prop, criteria)
                properties_from_db = sorted(properties_from_db, key=lambda x: x['suitability_score'], reverse=True)
        
        ai_bot_response_text = generate_ai_response(
            user_message=user_message,
            criteria=criteria,
            properties=properties_from_db[:MAX_PROPERTIES_TO_DISPLAY_FROM_DB],
            conversation_history=conversation_history
        )
        
        ask_for_feedback_flag = False
        if FEEDBACK_TAG in ai_bot_response_text:
            ai_bot_response_text = ai_bot_response_text.replace(FEEDBACK_TAG, "").strip()
            ask_for_feedback_flag = True

        final_response_payload = {
            "bot_dialogue_message": ai_bot_response_text,
            "search_results": properties_from_db,
            "current_search_criteria_for_frontend": criteria,
            "search_performed_with_criteria": search_was_performed_this_turn and bool(properties_from_db),
            "ask_for_feedback": ask_for_feedback_flag
        }
        
        return jsonify(final_response_payload)

    except Exception as e:
        print(f"ERROR in /search route: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "An unexpected server error occurred.", "message": str(e)}), 500

def generate_ai_response(user_message, criteria, properties, conversation_history):
    if not OPENAI_API_KEY:
        print("LLM Response: OpenAI API Key not configured. Using fallback response.")
        if not criteria.get('location'): return "I can help with that. Where are you looking?"
        if not criteria.get('property_type'): return f"Okay, in {criteria.get('location')}. What type of property?"
        if properties: return f"I found {len(properties)} options. Here are the top ones... (LLM functionality disabled)"
        return f"I couldn't find matching properties. Try adjusting your criteria? {FEEDBACK_TAG}"

    history_for_prompt = ""
    for turn in conversation_history[-3:]:
        history_for_prompt += f"User: {turn.get('user', '')}\nBot: {turn.get('bot', '')}\n"
    
    criteria_summary_parts = [f"{k}: {v}" for k, v in criteria.items() if v and k != 'preferences']
    if criteria.get('preferences'):
        criteria_summary_parts.append(f"preferences: {', '.join(criteria['preferences'])}")
    current_state_summary = f"Current accumulated criteria: {', '.join(criteria_summary_parts) if criteria_summary_parts else 'None yet'}."

    properties_summary_for_prompt = ""
    if properties:
        properties_summary_for_prompt = f"Database Search Results: Found {len(properties)} properties. Details of top 3:\n"
        for i, p in enumerate(properties[:3]):
            properties_summary_for_prompt += f"Prop{i+1}: Title: {p.get('title')}, Loc: {p.get('location')}, Price: {p.get('price')}, Beds: {p.get('bedrooms')}\n"
    else:
        properties_summary_for_prompt = "Database Search Results: No properties found matching current criteria."

    prompt = f"""{SYSTEM_PROMPT}

# CONTEXT
Conversation History:
{history_for_prompt}
User's LATEST message: "{user_message}"

{current_state_summary}
{properties_summary_for_prompt}

# YOUR TASK
Based on all the context above, formulate the best possible response. Use your "Conversational Toolkit" from the system prompt to decide what to do.
- Remember to be proactive and guide the conversation forward.
- If properties are available and the user says something vague like 'ok', ask them a question about the properties.
- If no properties are available, ask a question to get more criteria.
Your response:
"""
    
    print(f"\n--- LLM PROMPT --- \n{prompt[:1000]}...\n--- END LLM PROMPT ---")

    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        ai_text_response = response.choices[0].message.content.strip()
        print(f"LLM Generated Response: {ai_text_response}")
        return ai_text_response
    except Exception as e:
        print(f"Error generating AI response from LLM: {e}")
        return "I'm having a little trouble connecting to my advanced knowledge base right now. Could you please rephrase?"

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
    return response

FEEDBACK_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "services", "user_feedback_log.jsonl")
@app.route('/log_feedback', methods=['POST'])
def log_feedback():
    try:
        feedback_data = request.get_json()
        if not feedback_data:
            return jsonify({"status": "error", "message": "No feedback data received"}), 400
        
        feedback_data['timestamp'] = datetime.utcnow().isoformat()
        print(f"Received feedback: {feedback_data}")
        
        with open(FEEDBACK_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_data) + "\n")
            
        return jsonify({"status": "success", "message": "Feedback logged successfully"}), 200
    except Exception as e:
        print(f"Error logging feedback: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

