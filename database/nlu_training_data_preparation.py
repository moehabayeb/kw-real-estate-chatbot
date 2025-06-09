# C:\xampp\htdocs\ClassWork\Backend\database\nlu_training_data_preparation.py
import json
import os
import re 
import spacy 

# --- Initialize a blank spaCy nlp object for tokenization verification ---
nlp_for_verification = None 
try:
    nlp_for_verification = spacy.blank("en")
    print("spaCy blank model loaded for offset verification helper.")
except Exception as e:
    print(f"Could not load spaCy model for verification: {e}. Offset verification helper might not work.")
# --- End spaCy object for verification ---

# --- Define your Intents ---
INTENTS = [
    "greet", "goodbye", "thank_you", "search_properties_initial", 
    "provide_search_criteria", "affirm_generic", "deny_generic", 
    "request_more_results", "express_interest_in_shown_property",
    "request_agent_contact_general", "accept_agent_contact_offer", 
    "decline_agent_contact_offer", "out_of_scope" 
]

def create_cats_for_intent(target_intent, all_intents_list):
    cats = {intent: 0.0 for intent in all_intents_list}
    if target_intent in cats:
        cats[target_intent] = 1.0
    else:
        print(f"Warning: Target intent '{target_intent}' is not in the global INTENTS list during cats creation.")
    return cats

# --- TRAINING DATA with MANUAL Character Offsets ---
# YOU MUST REVIEW AND EXPAND THIS LIST, AND ENSURE ALL OFFSETS ARE PERFECT.
# USE THE VERIFY HELPER AT THE BOTTOM.
TRAIN_DATA = [
    # === greet ===
    ("hello", {"cats": create_cats_for_intent("greet", INTENTS), "entities": []}),
    ("Hi there", {"cats": create_cats_for_intent("greet", INTENTS), "entities": []}),
    ("good morning", {"cats": create_cats_for_intent("greet", INTENTS), "entities": []}),
    ("hey", {"cats": create_cats_for_intent("greet", INTENTS), "entities": []}),
    ("yo", {"cats": create_cats_for_intent("greet", INTENTS), "entities": []}),
    ("start", {"cats": create_cats_for_intent("greet", INTENTS), "entities": []}),

    # === goodbye ===
    ("bye", {"cats": create_cats_for_intent("goodbye", INTENTS), "entities": []}),
    ("goodbye for now", {"cats": create_cats_for_intent("goodbye", INTENTS), "entities": []}),
    ("see you", {"cats": create_cats_for_intent("goodbye", INTENTS), "entities": []}),
    ("exit chat", {"cats": create_cats_for_intent("goodbye", INTENTS), "entities": []}),
    ("I'm done thanks", {"cats": create_cats_for_intent("goodbye", INTENTS), "entities": []}), 

    # === thank_you ===
    ("thanks", {"cats": create_cats_for_intent("thank_you", INTENTS), "entities": []}),
    ("thank you very much", {"cats": create_cats_for_intent("thank_you", INTENTS), "entities": []}),
    ("appreciate it", {"cats": create_cats_for_intent("thank_you", INTENTS), "entities": []}),

    # === search_properties_initial (With previously discussed corrected offsets) ===
    ("I’m looking to buy a villa in Dubai around 2 million AED.", {"cats": create_cats_for_intent("search_properties_initial", INTENTS),
        "entities": [(21, 26, "PROPERTY_TYPE"),(30, 35, "LOCATION"),(42, 54, "BUDGET")]}),
    ("Can you find an apartment in Downtown Dubai for under 3 million AED?", {"cats": create_cats_for_intent("search_properties_initial", INTENTS),
        "entities": [(16, 25, "PROPERTY_TYPE"),(29, 44, "LOCATION"),(50, 67, "BUDGET")]}), 
    ("I want a penthouse in Business Bay that costs about 5 million AED.", {"cats": create_cats_for_intent("search_properties_initial", INTENTS),
        "entities": [(9, 18, "PROPERTY_TYPE"),(22, 34, "LOCATION"),(46, 60, "BUDGET")]}),
    ("Looking for a townhouse in Arabian Ranches for less than 4 million AED.", {"cats": create_cats_for_intent("search_properties_initial", INTENTS),
        "entities": [(14, 23, "PROPERTY_TYPE"),(27, 42, "LOCATION"),(48, 70, "BUDGET")]}),
    ("Can you find a studio in JVC priced at 1.2 million AED?", {"cats": create_cats_for_intent("search_properties_initial", INTENTS),
        "entities": [(16, 22, "PROPERTY_TYPE"),(26, 29, "LOCATION"),(39, 53, "BUDGET")]}),
    ("I need a duplex in Palm Jumeirah for around 6.5 million AED.", {"cats": create_cats_for_intent("search_properties_initial", INTENTS),
        "entities": [(9, 15, "PROPERTY_TYPE"),(19, 33, "LOCATION"),(38, 54, "BUDGET")]}),
    ("Is there an apartment available in Marina for 2.3 million AED?", {"cats": create_cats_for_intent("search_properties_initial", INTENTS),
        "entities": [(12, 21, "PROPERTY_TYPE"),(36, 42, "LOCATION"),(47, 61, "BUDGET")]}),
    ("Find me a studio in Downtown Dubai costing about 1.5 million AED.", {"cats": create_cats_for_intent("search_properties_initial", INTENTS),
        "entities": [(11, 17, "PROPERTY_TYPE"),(21, 36, "LOCATION"),(47, 62, "BUDGET")]}),
    ("find houses near JLT with 3 bedrooms", {"cats": create_cats_for_intent("search_properties_initial", INTENTS), 
        "entities": [(5, 11, "PROPERTY_TYPE"), (17, 20, "LOCATION"), (26, 36, "NUM_BEDROOMS")]}),
    ("what listings do you have for sale", {"cats": create_cats_for_intent("search_properties_initial", INTENTS), "entities": []}),
    ("I want to buy a property in Sharjah with 2 beds for my family", {"cats": create_cats_for_intent("search_properties_initial", INTENTS), # Length 61
        "entities": [(25,32,"LOCATION"), (38,44,"NUM_BEDROOMS"), (52,61,"PURPOSE") ]}), # "Sharjah", "2 beds", "my family" (52 to end)

    # === provide_search_criteria ===
    ("in Palm Jumeirah", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(3,16,"LOCATION")]}),
    ("an apartment please", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(3,12,"PROPERTY_TYPE")]}),
    ("my budget is about 1.5 million", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(19,30,"BUDGET")]}),
    ("we need 4 beds actually", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(8,14,"NUM_BEDROOMS")]}),
    ("it is for investment purposes", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(10,20,"PURPOSE")]}),
    ("with a private pool", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(7,19,"AMENITY_PREFERENCE")]}),
    ("and a sea view", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(6,14,"AMENITY_PREFERENCE")]}),
    ("only show new properties that are furnished", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), 
        "entities": [(10, 24, "AMENITY_PREFERENCE"), (34, 43, "AMENITY_PREFERENCE")]}), 
    ("I prefer JVC", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(9,12,"LOCATION")]}),
    ("pet friendly is important", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(0,12,"AMENITY_PREFERENCE")]}),
    ("to live there", {"cats": create_cats_for_intent("provide_search_criteria", INTENTS), "entities": [(0,11,"PURPOSE")]}), 

    # ... (Continue adding MANY more examples for all other intents) ...
    ("yes", {"cats": create_cats_for_intent("affirm_generic", INTENTS), "entities": []}),
    ("no", {"cats": create_cats_for_intent("deny_generic", INTENTS), "entities": []}),
    ("show more", {"cats": create_cats_for_intent("request_more_results", INTENTS), "entities":[]}),
    ("i like it", {"cats": create_cats_for_intent("express_interest_in_shown_property", INTENTS), "entities":[]}),
    ("talk to agent", {"cats": create_cats_for_intent("request_agent_contact_general", INTENTS), "entities": []}),
    ("yes give contact", {"cats": create_cats_for_intent("accept_agent_contact_offer", INTENTS), "entities": []}),
    ("no not yet", {"cats": create_cats_for_intent("decline_agent_contact_offer", INTENTS), "entities": []}),
    ("what is the time now", {"cats": create_cats_for_intent("out_of_scope", INTENTS), "entities": []}),

]
# --- END OF TRAIN_DATA list --- 

# --- Offset Verification Helper Function ---
def verify_offsets_example(text_to_check, entities_to_check, nlp_verifier_obj):
    if not nlp_verifier_obj:
        # print("  Skipping verification for this item as spaCy NLP object for verification not loaded.")
        return True 
    
    doc = nlp_verifier_obj.make_doc(text_to_check)
    item_all_ok = True
    # print(f"  Verifying text: '{text_to_check}'") 
    # print("    Tokens by spaCy: ", end="")
    # for token in doc: print(f"'{token.text}'({token.idx}) ", end="")
    # print()

    for start, end, label in entities_to_check:
        entity_text_from_span = ""
        try:
            entity_text_from_span = text_to_check[start:end]
        except IndexError:
            print(f"    ----> [OFFSET VALIDATION ERROR] Span ({start},{end}) for '{label}' is out of bounds for text (len {len(text_to_check)}): '{text_to_check}'")
            item_all_ok = False
            continue # Skip char_span check if offsets are already bad

        span_obj = doc.char_span(start, end, label=label, alignment_mode="contract")
        if span_obj is None:
            print(f"    ----> [ALIGNMENT WARNING] spaCy could NOT align entity '{entity_text_from_span}' ({label}) in \"{text_to_check}\" with span ({start},{end}). This entity will be SKIPPED during training.")
            item_all_ok = False
        elif span_obj.text != entity_text_from_span:
             print(f"    ----> [TEXT MISMATCH WARNING] spaCy aligned to '{span_obj.text}' but your span text was '{entity_text_from_span}'. Label: {label}, Span: ({start},{end}) in \"{text_to_check}\"")
    return item_all_ok

# --- Main execution block to validate and save this data ---
if __name__ == "__main__":
    print("Validating and saving spaCy formatted training data (with manual offsets)...")
    
    current_script_dir = os.path.dirname(os.path.abspath(__file__)) 
    backend_dir = os.path.dirname(current_script_dir) 
    services_dir = os.path.join(backend_dir, "services")
    if not os.path.exists(services_dir):
        os.makedirs(services_dir)
        print(f"Created directory: {services_dir}")
    output_file_path = os.path.join(services_dir, "spacy_manual_training_data.json")

    valid_data_for_saving = []
    overall_data_structurally_valid = True # CORRECTED VARIABLE NAME HERE
    
    print("\n--- Running Detailed Offset Verifications on TRAIN_DATA (using local nlp_for_verification) ---")
    num_alignment_issues_this_run = 0
    if not TRAIN_DATA:
        print("TRAIN_DATA list is empty! Please add examples.")
        overall_data_structurally_valid = False # Mark as invalid for saving

    if overall_data_structurally_valid: # Only proceed if TRAIN_DATA is not empty
        for i, train_item in enumerate(TRAIN_DATA):
            # Structural check for the train_item itself
            if not isinstance(train_item, tuple) or len(train_item) != 2:
                print(f"  ERROR (Entry {i+1}): Item is not a tuple of (text, annotations_dict). Found: {train_item}")
                overall_data_structurally_valid = False; continue # Skip to next item
            
            text, annots = train_item
            current_item_annotations_valid = True # Flag for current item's annotations

            if not isinstance(text, str):
                print(f"  ERROR (Entry {i+1}): Text part is not a string for item: {text}")
                current_item_annotations_valid = False; overall_data_structurally_valid = False
            
            if not isinstance(annots, dict):
                print(f"  ERROR (Entry {i+1}): Annotations part is not a dictionary for text: '{text}'. Found: {annots}")
                current_item_annotations_valid = False; overall_data_structurally_valid = False
            else:
                # Check 'cats' structure
                if "cats" not in annots or not isinstance(annots["cats"], dict) or \
                   not any(annots["cats"].get(intent_name) == 1.0 for intent_name in INTENTS if intent_name in annots["cats"]):
                    print(f"  ERROR (Entry {i+1}): Missing or invalid 'cats' definition for text: '{text}'. Expected one intent to be 1.0. Cats: {annots.get('cats')}")
                    current_item_annotations_valid = False; overall_data_structurally_valid = False
                
                # Check 'entities' structure and basic offset validity
                if "entities" not in annots or not isinstance(annots["entities"], list):
                    print(f"  ERROR (Example {i+1}): Missing or invalid 'entities' list for text: '{text}'. Found: {annots.get('entities')}")
                    current_item_annotations_valid = False; overall_data_structurally_valid = False
                else:
                    for start, end, label in annots.get("entities", []):
                        if not (isinstance(start, int) and isinstance(end, int) and isinstance(label, str) and \
                                start >= 0 and end > start and end <= len(text)):
                            print(f"  ERROR (Entry {i+1}): Structurally invalid offset/label for entity '{label}' span in text: '{text}'. Offsets: ({start},{end}), Text Length: {len(text)}")
                            current_item_annotations_valid = False; overall_data_structurally_valid = False; break 
                
                # If structurally sound so far, do detailed spaCy alignment check
                if current_item_annotations_valid and nlp_for_verification:
                    if not verify_offsets_example(text, annots.get("entities", []), nlp_for_verification):
                        num_alignment_issues_this_run +=1 
                        # We still consider it "structurally valid" for saving, but training might skip entities
            
            if current_item_annotations_valid: # If the basic structure of text and annots was okay
                 valid_data_for_saving.append((text, annots)) # Add item for saving

    # Report final status
    if not overall_data_structurally_valid:
        print("\n!!! CRITICAL STRUCTURAL ERRORS found in TRAIN_DATA definition (e.g. not tuple/dict, bad offsets). JSON file NOT saved. Fix TRAIN_DATA list structure. !!!")
    elif num_alignment_issues_this_run > 0 :
        print(f"\n--- CAUTION: Found {num_alignment_issues_this_run} potential entity alignment issues by the spaCy verification helper. ---")
        print("--- Review warnings above. These entities might be skipped by spaCy during NER training if not perfectly token-aligned. ---")
    else:
        print("\nAll TRAIN_DATA examples appear structurally valid and passed detailed offset verification.")
    
    # Saving logic
    if overall_data_structurally_valid and TRAIN_DATA: 
        # Path setup already done
        try:
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(valid_data_for_saving, f, indent=2) 
            print(f"\nSuccessfully saved {len(valid_data_for_saving)} examples to {output_file_path}")
            print("Next step: Review any warnings above. If alignment warnings, fix TRAIN_DATA & re-run. Otherwise, run train_nlu_model.py.")
        except Exception as e:
            print(f"Error saving processed training data: {e}")
    elif not TRAIN_DATA:
         print("TRAIN_DATA is empty. No data to save.")
    
    # Print intent counts from what would be saved (if no structural errors)
    print("\nFinal counts per intent (from validated structural data, before alignment check):")
    intent_counts_final = {}
    for text, annots in valid_data_for_saving: # Use valid_data_for_saving for this count
        if isinstance(annots, dict) and "cats" in annots and isinstance(annots["cats"], dict):
            for intent_name, present_flag in annots.get("cats", {}).items():
                if present_flag >= 0.5 : 
                    intent_counts_final[intent_name] = intent_counts_final.get(intent_name, 0) + 1
    for intent_name_key in INTENTS: 
        count = intent_counts_final.get(intent_name_key, 0)
        print(f"- {intent_name_key}: {count}")
        if count == 0: print(f"  CRITICAL WARNING: Intent '{intent_name_key}' has NO examples!")
        elif count < 5 and intent_name_key not in ["affirm_generic", "deny_generic"]: 
            print(f"  WARNING: Intent '{intent_name_key}' has very few examples ({count}).")

    # --- Individual Verification Example Call Section (uncomment to use) ---
    # if __name__ == "__main__" and nlp_for_verification:
    #     print("\n--- Manual Single Example Verification ---")
    #     verify_offsets_example(
    #         text_to_check = "Looking for a townhouse in Arabian Ranches for less than 4 million AED.",
    #         entities_to_check = [
    #            (14, 23, "PROPERTY_TYPE"), 
    #            (27, 42, "LOCATION"), # Corrected example for "Arabian Ranches"
    #            (48, 70, "BUDGET")   
    #         ],
    #         nlp_verifier_obj=nlp_for_verification 
    #     )