import pandas as pd
from math import exp
import sys
sys.path.append(r'C:\xampp\htdocs\ClassWork\Backend\services')
class SuitabilityScorer:
    """
    Enhanced property suitability scorer with:
    - Normalized scoring (0-100 scale)
    - More nuanced matching logic
    - Better handling of edge cases
    - Configurable weights
    """
    
    # Configurable scoring weights (sum should be ~100 for base categories)
    WEIGHTS = {
        'property_type': 25,
        'budget': 30,
        'bedrooms': 20,
        'preferences': 15,
        'purpose': 10
    }
    
    # Preference boost multipliers (applied to base preference score)
    PREFERENCE_BOOSTS = {
        'must_have': 1.5,
        'important': 1.2,
        'nice_to_have': 0.8
    }

    @classmethod
    def calculate_suitability_score(cls, property_details, user_criteria):
        """
        Calculates normalized suitability score (0-100) with detailed matching.
        """
        score = 0
        
        # Normalize inputs
        uc = {k.lower(): v for k, v in user_criteria.items()}
        uc.setdefault('preferences', [])
        pd = {k.lower(): v for k, v in property_details.items()}
        
        # --- Property Type Matching ---
        type_score = cls._calculate_type_match(
            pd.get('propertyty'),
            uc.get('property_type')
        )
        score += type_score * cls.WEIGHTS['property_type']
        
        # --- Budget Fit ---
        budget_score = cls._calculate_budget_fit(
            pd.get('price'),
            uc.get('budget')
        )
        score += budget_score * cls.WEIGHTS['budget']
        
        # --- Bedroom Fit ---
        bedroom_score = cls._calculate_bedroom_fit(
            pd.get('bedrooms'),
            uc.get('bedrooms'),
            uc.get('family_composition', {}).get('is_studio_query', False)
        )
        score += bedroom_score * cls.WEIGHTS['bedrooms']
        
        # --- Preference Matching ---
        pref_score = cls._calculate_preference_match(
            pd.get('title', ''),
            uc.get('preferences', [])
        )
        score += pref_score * cls.WEIGHTS['preferences']
        
        # --- Purpose Fit ---
        purpose_score = cls._calculate_purpose_fit(
            pd.get('title', ''),
            pd.get('propertyty'),
            uc.get('purpose'),
            uc.get('preferences', [])
        )
        score += purpose_score * cls.WEIGHTS['purpose']
        
        # Ensure score is within bounds
        return max(0, min(100, round(score, 2)))

    @classmethod
    def _calculate_type_match(cls, prop_type, user_type):
        """Calculates property type match score (0-1)"""
        if not prop_type or not user_type:
            return 0.5  # Neutral score if missing data
            
        prop_type = prop_type.lower()
        user_type = user_type.lower()
        
        # Exact match
        if prop_type == user_type:
            return 1.0
            
        # Partial matches (e.g., "apartment" vs "studio")
        type_groups = {
            'villa': ['villa', 'townhouse'],
            'apartment': ['apartment', 'studio', 'flat']
        }
        
        for group, types in type_groups.items():
            if user_type in types and prop_type in types:
                return 0.8
                
        return 0  # No match

    @classmethod
    def _calculate_budget_fit(cls, prop_price, user_budget):
        """Calculates budget fit score (0-1) with exponential decay for over-budget"""
        if prop_price is None or user_budget is None:
            return 0.5  # Neutral score
            
        # Perfect fit
        if prop_price <= user_budget:
            # Bonus for being close to budget (70-100% of budget)
            budget_ratio = prop_price / user_budget
            if budget_ratio >= 0.7:
                return 1.0
            # Still good but not ideal
            return 0.7 + (budget_ratio * 0.3)
            
        # Over budget penalty with exponential decay
        over_ratio = (prop_price - user_budget) / user_budget
        return exp(-over_ratio * 2)  # Drops quickly as price exceeds budget

    @classmethod
    def _calculate_bedroom_fit(cls, prop_beds, user_beds, is_studio_query):
        """Calculates bedroom fit score (0-1)"""
        if prop_beds is None:
            return 0.5  # Neutral if property has no bedroom data
            
        try:
            prop_beds = int(prop_beds)
            user_beds = int(user_beds) if user_beds is not None else None
        except (ValueError, TypeError):
            return 0.5
            
        # Studio special case
        if prop_beds == 0 and is_studio_query:
            return 1.0
            
        # No bedroom preference
        if user_beds is None:
            return 0.7  # Slight preference for properties with bedrooms
            
        # Exact match
        if prop_beds == user_beds:
            return 1.0
            
        # Near matches
        diff = abs(prop_beds - user_beds)
        if diff == 1:
            return 0.8
        if diff == 2:
            return 0.6
            
        return 0.2  # Large mismatch

    @classmethod
    def _calculate_preference_match(cls, prop_title, user_preferences):
        """Calculates preference match score (0-1)"""
        if not user_preferences:
            return 0.5  # Neutral if no preferences
            
        prop_title = prop_title.lower()
        matches = 0
        
        for pref in user_preferences:
            # Handle different preference formats
            if isinstance(pref, dict):
                pref_type = pref.get('type')
                importance = pref.get('importance', 'nice_to_have')
                search_terms = [pref_type.replace('_', ' ')]
            else:
                search_terms = [pref.replace('_', ' ')]
                importance = 'nice_to_have'
                
            # Check for matches
            for term in search_terms:
                if term in prop_title:
                    matches += cls.PREFERENCE_BOOSTS.get(importance, 1.0)
                    break
                    
        # Normalize to 0-1 range
        max_possible = len(user_preferences) * max(cls.PREFERENCE_BOOSTS.values())
        return min(1.0, matches / max_possible) if max_possible > 0 else 0

    @classmethod
    def _calculate_purpose_fit(cls, prop_title, prop_type, user_purpose, user_preferences):
        """Calculates purpose fit score (0-1)"""
        if not user_purpose:
            return 0.5
            
        living_keywords = ["family", "spacious", "home", "garden", "quiet", "residential"]
        investment_keywords = ["roi", "investment", "rental", "yield", "tenanted"]
        
        score = 0
        title = prop_title.lower()
        prop_type = prop_type.lower() if prop_type else ""
        
        if user_purpose.lower() == 'living':
            # Property type bonuses
            if prop_type in ["villa", "townhouse"]:
                score += 0.3
            # Title keyword matches
            score += 0.1 * sum(kw in title for kw in living_keywords)
            # Specific preference matches
            if "family_friendly_area" in user_preferences:
                score += 0.2
                
        elif user_purpose.lower() == 'investment':
            # Property type bonuses
            if prop_type == "apartment":
                score += 0.2
            # Title keyword matches
            score += 0.15 * sum(kw in title for kw in investment_keywords)
            # Specific preference matches
            if "good_investment" in user_preferences:
                score += 0.25
                
        return min(1.0, score)


# Test block remains the same
if __name__ == '__main__':
    sample_property_villa = {
        'id': 1, 'title': 'Luxury Sea View Villa with Private Pool and Garden', 'location': 'Palm Jumeirah, Dubai', 
        'bathrooms': 5, 'bedrooms': 4, 'addedOn': '2024-05-01T10:00:00+00:00', 
        'type': 'buy', 'rera': None, 'propertyTy': 'villa', 'price': 15000000, 'country': 'Dubai'
    }
    sample_criteria_lux_villa = { 
        "location": "palm jumeirah", "property_type": "villa", "bedrooms": 4, 
        "budget": 20000000, "preferences": [
            {"type": "luxury", "importance": "must_have"},
            {"type": "view", "importance": "important"},
            "has_pool",  # Shorthand for nice-to-have
            "balcony_terrace"
        ], 
        "purpose": "living",
        "family_composition": {"adults": 2, "children": 2} 
    }
    
    score = SuitabilityScorer.calculate_suitability_score(sample_property_villa, sample_criteria_lux_villa)
    print(f"Property: {sample_property_villa['title']}")
    print(f"Score: {score}/100")