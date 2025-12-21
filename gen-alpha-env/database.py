import os
from google.cloud import firestore
from datetime import datetime

# 1. Initialize Firestore
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service-account.json"
db = firestore.Client(
    project="gen-lang-client-0954110485",
)

# --- NEW: UPDATE PROFILE / SETTINGS FUNCTION ---
def update_user_profile(user_id, new_data):
    """
    Updates specific fields in the user's document.
    Example: update_user_profile("user123", {"preferred_language": "Telugu"})
    """
    try:
        doc_ref = db.collection("users").document(user_id)
        # .update() only changes the specific fields sent in new_data
        doc_ref.update(new_data) 
        print(f"✅ Settings/Profile updated for {user_id}")
        return True
    except Exception as e:
        print(f"❌ Update failed: {e}")
        return False

# --- SIGNUP FUNCTION ---
def signup_user(user_id, name, age, language):
    """Creates a new user profile. Returns True if successful."""
    try:
        doc_ref = db.collection("users").document(user_id)
        
        if doc_ref.get().exists:
            print(f"⚠️ User {user_id} already exists.")
            return False

        doc_ref.set({
            "name": name,
            "age": age,
            "preferred_language": language,
            "signup_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "history": [],
            "current_trend": "neutral"
        })
        print(f"✅ User {name} signed up successfully!")
        return True
    except Exception as e:
        print(f"❌ Signup error: {e}")
        return False

# --- LOGIN / GET PROFILE FUNCTION ---
def get_user_profile(user_id):
    """Retrieves full profile for a user (Login/Profile page check)."""
    doc = db.collection("users").document(user_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

# --- CHAT & HISTORY FUNCTIONS ---
def save_user_session(user_id, session_data, rationale, trend):
    """Saves mood data and safety logs with timestamps."""
    doc_ref = db.collection("users").document(user_id)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = {
        "timestamp": timestamp,
        "user_input": session_data.get("user_input"),
        "dadi_reply": session_data.get("dadi_reply"),
        "rationale": rationale
    }

    doc_ref.set({
        "last_updated": timestamp,
        "current_trend": trend,
        "safety_audit_trail": firestore.ArrayUnion([log_entry])
    }, merge=True)
    print(f"✅ Chat saved to Firestore for {user_id}")

def get_user_history(user_id):
    """Retrieves the last 5 scores for trend analysis."""
    doc = db.collection("users").document(user_id).get()
    if doc.exists:
        return doc.to_dict().get("history", [])[-5:]
    return []

# Function to add a travel sticker to the child's passport
def add_sticker_to_db(user_id, country_name, sticker_id):
    try:
        user_ref = db.collection("users").document(user_id)
        # Using set with merge=True creates the document if it's missing
        user_ref.set({
            "passport_stickers": firestore.ArrayUnion([{
                "country": country_name,
                "sticker": sticker_id,
                "unlocked_at": datetime.now()
            }])
        }, merge=True)
        return True
    except Exception as e:
        print(f"❌ Firestore Error: {e}")
        return False

# Function to save a drawing to the child's gallery
def save_artwork_to_db(user_id, art_name, drawing_data):
    try:
        art_ref = db.collection("users").document(user_id).collection("gallery").document()
        art_ref.set({
            "art_name": art_name,
            "drawing_data": drawing_data, # This could be a Base64 string or image URL
            "created_at": datetime.now()
        })
        return True
    except Exception as e:
        print(f"Error saving artwork: {e}")
        return False