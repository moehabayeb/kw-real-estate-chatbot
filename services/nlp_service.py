# C:\xampp\htdocs\ClassWork\Backend\services\nlp_service.py
import spacy
import re
from fuzzywuzzy import process as fuzzy_process

try:
    nlp = spacy.load("en_core_web_sm") # Using the custom model you trained for intent/NER
    # If you have a successfully trained custom model, load it instead:
    # backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # MODEL_NAME_OR_PATH = os.path.join(backend_dir, "services", "custom_nlu_model_vX", "model-best") # Replace vX
    # nlp = spacy.load(MODEL_NAME_OR_PATH)
    print("spaCy model (en_core_web_sm or custom if path updated) loaded successfully.")
except OSError:
    print("Warning: Default spaCy model 'en_core_web_sm' not found or custom model path incorrect. Downloading en_core_web_sm as fallback.")
    try:
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
        print("Fallback model en_core_web_sm loaded.")
    except:
        print("FATAL: Could not load any spaCy model. NLP features will be severely limited.")
        nlp = None # Ensure nlp is None if loading fails completely
except Exception as e:
    print(f"An unexpected error occurred loading spaCy model: {e}")
    nlp = None


# --- Known Entities & Keywords ---
LOCATION_SYNONYM_MAP = {
    "duba": "dubai", "dbi": "dubai", 
    "jbr": "jumeirah beach residence", "jltowers": "jumeirah lake towers"
}
KNOWN_LOCATIONS = [ 
    "dubai", "abu dhabi", "sharjah", "ajman", "jumeirah", "marina", "dubai marina",
    "meydan", "downtown dubai", "jumeirah lake towers", "jlt", "dubai hills estate", 
    "dubai investment park", "dip", "jumeirah village circle", "jvc", "business bay", 
    "palm jumeirah", "arjan", "al furjan", "dubai south", "wasl gate", "city of lights", 
    "al reem island", "expo city", "discovery gardens", "al barsha", "the springs", 
    "arabian ranches", "motor city", "sports city", "dubailand", "al khail", "sheikh zayed road",
    "jumeirah beach residence" 
]
KNOWN_PROPERTY_TYPES = {
    "apartment": ["apartment", "flat", "unit", "studio", "loft", "duplex apartment", "1br", "2br", "3br", "4br", "1bhk", "2bhk", "3bhk"],
    "villa": ["villa", "house", "home", "mansion", "compound villa", "bungalow"],
    "townhouse": ["townhouse", "town house"],
    "penthouse": ["penthouse"],
    "land": ["land", "plot"],
    "office": ["office", "commercial space", "shop", "retail", "warehouse", "showroom"]
}
GREETING_KEYWORDS = ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", "sup", "yo", "heya", "howdy"]

# --- Refined Preference Map ---
PREFERENCE_KEYWORDS_MAP = { 
    "luxury": ["luxury", "luxurious", "high-end", "premium", "exclusive", "deluxe", "opulent", "upscale"],
    "view": ["view", "sea view", "marina view", "burj khalifa view", "golf view", "panoramic", "skyline view", "waterfront", "lake view", "park view", "canal view"],
    "new_property": ["new", "brand new", "newly built", "off-plan", "offplan", "modern build", "contemporary design", "recent build"],
    "quiet_area": ["quiet area", "quiet neighborhood", "quiet", "peaceful", "secluded", "tranquil", "serene", "calm location"],
    "furnished_property": ["furnished", "fully furnished", "partially furnished", "semi furnished"],
    "spacious_property": ["spacious", "large", "big", "roomy", "expansive", "ample space", "large layout"],
    "near_metro": ["metro", "near metro", "close to metro", "metro access", "metro station", "walking distance to metro"],
    "family_friendly_area": ["family friendly", "families", "kids friendly", "good for family", "family area", "family community", "family oriented"],
    "good_investment": ["roi", "high roi", "good investment", "rental yield", "investment opportunity", "capital appreciation", "investment deal"],
    "pet_friendly": ["pet friendly", "pets allowed", "dog friendly", "cat friendly", "allow pets"],
    "near_good_schools": ["schools", "good school", "good schools", "near school", "near schools", "close to schools", "school district"],
    "has_pool": ["pool", "swimming pool", "private pool", "shared pool", "community pool", "with a pool"],
    "has_gym": ["gym", "fitness center", "health club", "fitness suite", "with a gym"],
    "has_balcony_terrace": ["balcony", "terrace", "patio", "outdoor space", "large balcony", "private garden", "garden", "yard"],
    "near_beach": ["beach", "beachfront", "near beach", "beach access", "close to beach", "seafront", "by the sea"],
    "parking_available": ["parking", "car park", "covered parking", "private parking", "garage", "with parking"]
}

def _extract_family_composition(query_text_lower):
    # (Keep this function as it was from our last working version)
    composition = {"adults": 0, "children": 0, "mentions_family_word": False}
    user_mentioned_self = any(p in query_text_lower for p in ["i ", "i'm", "me ", "my "])
    spouse_found = any(w in query_text_lower for w in ["wife", "husband", "spouse", "partner"])
    if user_mentioned_self: composition["adults"] = 1
    if spouse_found:
        if user_mentioned_self: composition["adults"] = 2
        else: composition["adults"] = max(composition["adults"], 1) 
    child_keywords = ["child", "children", "kid", "kids", "son", "daughter", "baby", "infant", "teenager", "teenagers"]
    child_count_match = re.search(r'(\d+|one|two|three|four|five|six)\s+(?:child|children|kid|kids|teen|teenagers|sons|daughters)', query_text_lower)
    if child_count_match:
        count_str = child_count_match.group(1).lower()
        num_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six":6}
        if count_str.isdigit(): composition["children"] = int(count_str)
        elif count_str in num_map: composition["children"] = num_map[count_str]
    elif any(kw in query_text_lower for kw in child_keywords): composition["children"] = 1 
    if "family" in query_text_lower:
        composition["mentions_family_word"] = True
        if composition["adults"] == 0 and composition["children"] == 0: composition["adults"] = 2 
    if (composition["children"] > 0 or composition["mentions_family_word"]) and composition["adults"] == 0: composition["adults"] = 1 
    return composition

def _infer_bedrooms_from_composition(composition, property_type, query_lower): # Added query_lower
    # (Keep this function as it was, ensure "is_studio_query" from composition is used if set)
    is_studio_explicitly_mentioned = "studio" in query_lower or \
                                 (composition.get("is_studio_query", False) and property_type == "apartment")

    if is_studio_explicitly_mentioned:
        return 0 

    total_people = composition["adults"] + composition["children"]
    if total_people == 0: return None
    if total_people == 1: return 1 
    if total_people == 2: return 1 
    if total_people == 3: return 2
    if total_people == 4: return 2 
    if total_people == 5: return 3
    if total_people >= 6: return 4 
    return None

def process_query(query_text_original_case):
    if not nlp: # If spaCy model failed to load at all
        print("NLP Service: spaCy model not loaded. Cannot process query.")
        return {"error": "NLP model unavailable"}

    query_lower = query_text_original_case.lower()
    doc = nlp(query_text_original_case) 
    
    extracted = {
        "is_greeting": False, "location": None, "property_type": None, "bedrooms": None, 
        "budget": None, "keywords": [], 
        "family_composition": {"adults":0, "children":0, "mentions_family_word": False, "is_studio_query": False},
        "preferences": [], "purpose": None, "payment_method": None,
        "intent_ml": None # Placeholder for custom NLU model's intent output
    }

    # 1. Use Custom NLU Model if Available (Intent & Entities)
    # This is where you would use doc.cats and doc.ents IF your custom NLU model is loaded and trained
    # For now, we'll show how to extract and then integrate with rules.
    # If nlp is your custom model (not en_core_web_sm):
    # if nlp.meta.get("name") != "core_web_sm": # A way to check if it's not the base model
    #     if doc.cats:
    #         extracted["intent_ml"] = max(doc.cats, key=doc.cats.get)
    #         if extracted["intent_ml"] == "greet" and not any(ent for ent in doc.ents): # Pure greet
    #             extracted["is_greeting"] = True; return extracted
        
    #     for ent in doc.ents:
    #         # Map your trained entity labels to the 'extracted' dictionary keys
    #         # This requires your custom NER model to be effective.
    #         # Example:
    #         if ent.label_ == "LOCATION_ENTITY": extracted["location"] = ent.text
    #         elif ent.label_ == "PROPERTY_TYPE_ENTITY": extracted["property_type"] = ent.text # Normalize further
    #         # ... and so on for other entities you trained ...
    # else:
    #     # print("NLP using rules and base spaCy NER as custom model not primary.")
    #     pass

    # Fallback or primary rule-based extraction (can work alongside/after custom NLU)

    if any(greet_word in query_lower for greet_word in GREETING_KEYWORDS):
        is_pure_greeting = True
        # Simple check: if more than 3 words OR contains typical search keywords, not pure greeting
        if len(doc) > 3 or any(kw in query_lower for kw in ["apartment", "villa", "house", "dubai", "budget"]):
             is_pure_greeting = False
        if is_pure_greeting:
            extracted["is_greeting"] = True; return extracted

    # Location Extraction
    found_location = None
    # ... (keep your latest fuzzy matching logic for location, using KNOWN_LOCATIONS and LOCATION_SYNONYM_MAP) ...
    for loc_phrase in sorted([loc for loc in KNOWN_LOCATIONS if " " in loc], key=len, reverse=True):
        if loc_phrase in query_lower: found_location = loc_phrase; break
    if not found_location:
        for token in doc: 
            lemma = token.lemma_
            if lemma in KNOWN_LOCATIONS: found_location = lemma; break
            if lemma in LOCATION_SYNONYM_MAP: found_location = LOCATION_SYNONYM_MAP[lemma]; break
    if not found_location:
        for ent in doc.ents: # spaCy's pre-trained GPE
            if ent.label_ == "GPE":
                ent_text_lower = ent.text.lower()
                if ent_text_lower in KNOWN_LOCATIONS: found_location = ent_text_lower; break
                if ent_text_lower in LOCATION_SYNONYM_MAP: found_location = LOCATION_SYNONYM_MAP[ent_text_lower]; break
                match, score = fuzzy_process.extractOne(ent_text_lower, KNOWN_LOCATIONS)
                if score >= 80: found_location = match; break 
    if not found_location:
        potential_loc_words = [token.text for token in doc if token.pos_ in ["PROPN", "NOUN"] and not token.is_stop and not token.is_punct]
        for pot_loc_word_text in potential_loc_words:
            word_lower = pot_loc_word_text.lower()
            if word_lower in LOCATION_SYNONYM_MAP: found_location = LOCATION_SYNONYM_MAP[word_lower]; break
            match, score = fuzzy_process.extractOne(word_lower, KNOWN_LOCATIONS)
            if score >= 80: found_location = match; break 
    extracted["location"] = found_location
    
    # Property Type Extraction
    found_property_type = None; is_studio_explicitly_mentioned = "studio" in query_lower
    if is_studio_explicitly_mentioned: 
        found_property_type = "apartment"; extracted["family_composition"]["is_studio_query"] = True 
    if not found_property_type:
        for main_type, synonyms in KNOWN_PROPERTY_TYPES.items():
            for syn_phrase in sorted(synonyms, key=len, reverse=True): 
                 if syn_phrase in query_lower: 
                    found_property_type = main_type
                    if syn_phrase == "studio": extracted["family_composition"]["is_studio_query"] = True
                    break
            if found_property_type: break
    extracted["property_type"] = found_property_type
    if extracted["family_composition"]["is_studio_query"] and extracted["property_type"] == "apartment":
        if extracted["bedrooms"] is None : extracted["bedrooms"] = 0 

    # Explicit Bedroom Extraction
    bedroom_match = re.search(r'(\d+)\s*(?:br\b|bed|bedroom|bedrooms|bhk)', query_lower)
    if bedroom_match:
        try: extracted["bedrooms"] = int(bedroom_match.group(1))
        except ValueError: pass
    
    # Family Composition and Inferred Bedrooms
    current_family_comp = _extract_family_composition(query_lower)
    extracted["family_composition"] = current_family_comp # Store full composition
    
    if extracted["bedrooms"] is None: 
        inferred_beds = _infer_bedrooms_from_composition(extracted["family_composition"], extracted["property_type"], query_lower)
        if inferred_beds is not None: extracted["bedrooms"] = inferred_beds
    
    # Budget Extraction
    # ... (keep your latest robust budget extraction logic) ...
    extracted_budget_value = None
    budget_match_qualified = re.search(r'(\d[\d,]*\.?\d*)\s*(aed|dhs|dirhams|million|thousand|k)', query_lower, re.IGNORECASE)
    if budget_match_qualified:
        try:
            budget_str = budget_match_qualified.group(1).replace(',', ''); value = float(budget_str)
            qualifier = budget_match_qualified.group(2).lower()
            if "million" in qualifier: extracted_budget_value = int(value * 1000000)
            elif "thousand" in qualifier or "k" == qualifier : extracted_budget_value = int(value * 1000)
            else: extracted_budget_value = int(value)
        except ValueError: pass
    else:
        all_numbers = re.findall(r'\b(\d{4,}(?:,\d{3})*)\b', query_lower) 
        for num_str_match in all_numbers:
            num_str = num_str_match.replace(',', '')
            if re.search(r'\b' + re.escape(num_str) + r'\s*(?:bed|bedroom|bedrooms|bhk|person|people)\b', query_lower): continue
            if re.search(r'family of\s*' + re.escape(num_str) + r'\b', query_lower): continue
            try:
                potential_budget = int(num_str)
                if potential_budget > 10000: 
                    if extracted_budget_value is None or potential_budget < extracted_budget_value:
                         extracted_budget_value = potential_budget
            except ValueError: continue
    extracted["budget"] = extracted_budget_value
        
    # --- Enhanced Preference Keywords Extraction ---
    current_preferences = []
    for pref_key, pref_synonyms_list in PREFERENCE_KEYWORDS_MAP.items():
        # Check whole phrases first for multi-word synonyms
        for phrase_syn in [s for s in pref_synonyms_list if " " in s]:
            if phrase_syn in query_lower:
                if pref_key not in current_preferences: current_preferences.append(pref_key)
                break 
        if pref_key in current_preferences: continue # Already found this preference category

        # Then check single words
        for single_syn in [s for s in pref_synonyms_list if " " not in s]:
            # Use word boundaries for single word synonyms to avoid partial matches like 'new' in 'news'
            if re.search(r'\b' + re.escape(single_syn) + r'\b', query_lower):
                if pref_key not in current_preferences: current_preferences.append(pref_key)
                break
    extracted["preferences"] = list(set(current_preferences))
    # --- End Preference Keywords ---

    # General Keywords
    temp_keywords = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop and not token.is_punct]
    final_keywords = []
    for kw in temp_keywords: # Basic filtering of already captured concepts
        is_loc_part = found_location and kw in found_location.split()
        is_type_part = False
        if found_property_type and found_property_type in KNOWN_PROPERTY_TYPES:
            if kw in KNOWN_PROPERTY_TYPES[found_property_type]: is_type_part = True
        is_pref_word = any(kw in syn_list for pref_cat in extracted["preferences"] for syn_list in PREFERENCE_KEYWORDS_MAP.get(pref_cat,[]))
        if not is_loc_part and not is_type_part and not is_pref_word: final_keywords.append(kw)
    extracted["keywords"] = list(set(final_keywords))
    
    # Purpose
    if "investment" in query_lower or "invest" in query_lower or "roi" in query_lower or "good_investment" in extracted["preferences"]:
        extracted["purpose"] = "investment"
    elif any(word in query_lower for word in ["living", "live", "move", "relocate", "stay", "reside", "own use"]) or "family_friendly_area" in extracted["preferences"]: 
        extracted["purpose"] = "living"
        
    return extracted

# --- Test Section (Keep this for your own testing of this script) ---
if __name__ == "__main__":
    sample_queries = [
        "I have 3 kids who need a good school nearby, which one of these houses does?",
        "studio flat in marina for 1 person with a view and parking", 
        "show me new apartments in dubai with a pool, preferably pet friendly",
        "apartments in duba for my family, we are 3 people, need a quiet area", 
        "i have two children and a wife, looking for a quiet house in jvc, budget 3m aed, must be pet friendly near good schools",
    ]
    if nlp: # Only run tests if model loaded
        for q_text in sample_queries:
            print(f"\nQuery: {q_text}")
            processed_output = process_query(q_text)
            print(f"Processed: {processed_output}")
        print("-" * 40)
    else:
        print("Cannot run tests as NLP model did not load.")