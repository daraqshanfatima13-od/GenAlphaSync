from database import db
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agents import gen_alpha_sync_orchestrator 
from database import signup_user, update_user_profile, get_user_profile
from fastapi import HTTPException
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 1. Security: Allows your HTML files to talk to your Python API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. ROUTE: Open the home page automatically
@app.get("/")
async def read_index():
    return FileResponse('frontend/index.html')

# 3. MOUNT: Link all your other files (CSS, JS, other HTMLs)
# This makes everything in the frontend folder available at http://127.0.0.1:8000/
app.mount("/", StaticFiles(directory="frontend"), name="frontend")

# ... (Keep your @app.post routes like /chat and /mood/save-entry below this)
# --- DATA MODELS ---

class ChatRequest(BaseModel):
    user_id: str = "guest_user"
    message: str
    language: str = "English"

class SignupRequest(BaseModel):
    user_id: str
    name: str
    age: int
    language: str = "English"

# NEW: Model for updating settings/profile
class SettingsUpdateRequest(BaseModel):
    user_id: str
    language: str = None
    name: str = None

# --- ROUTES ---

@app.get("/")
def home():
    return {"status": "Gen-Alpha-Sync Backend is running!"}

@app.post("/signup")
def signup(request: SignupRequest):
    success = signup_user(
        user_id=request.user_id, 
        name=request.name, 
        age=request.age, 
        language=request.language
    )
    if success:
        return {"status": "success", "message": f"Welcome to the garden, {request.name}!"}
    raise HTTPException(status_code=400, detail="User already exists or database error.")

# NEW: Endpoint for changing language or name
@app.post("/update_settings")
def update_settings(request: SettingsUpdateRequest):
    """Finds the user and updates their specific settings."""
    # We build a dictionary of only what the user wants to change
    changes = {}
    if request.language:
        changes["preferred_language"] = request.language
    if request.name:
        changes["name"] = request.name

    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided.")

    success = update_user_profile(request.user_id, changes)
    
    if success:
        return {"status": "success", "message": "Settings updated!", "updated_to": changes}
    raise HTTPException(status_code=404, detail="User not found.")

# NEW: Endpoint to get profile data (for the Profile Section)
@app.get("/profile/{user_id}")
def get_profile(user_id: str):
    profile = get_user_profile(user_id)
    if profile:
        return profile
    raise HTTPException(status_code=404, detail="Profile not found.")

@app.post("/chat")
def chat_with_dadi(request: ChatRequest): 
    dadi_response, wellness_info = gen_alpha_sync_orchestrator(
        user_input=request.message, 
        user_id=request.user_id, 
        language=request.language
    )
    return {
        "dadi_reply": dadi_response,
        "wellness_data": wellness_info,
        "session_id": request.user_id
    }

from database import add_sticker_to_db, save_artwork_to_db
from pydantic import BaseModel

@app.get("/mood/history/{user_id}")
def get_mood_history(user_id: str):
    # Import EVERYTHING we need from database at the top of the function
    from database import db 
    try:
        # Ensure 'docs' is indented exactly like this
        docs = db.collection("users").document(user_id).collection("mood_diary").stream()
        
        history = []
        for doc in docs:
            history.append(doc.to_dict())
            
        history.sort(key=lambda x: x.get('date', ''))
        return {"history": history}
    except Exception as e:
        print(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Models for the new features
class StickerRequest(BaseModel):
    user_id: str
    country: str
    sticker_id: str

class ArtRequest(BaseModel):
    user_id: str
    art_name: str
    drawing_data: str

# Endpoint for Passport Explorer
@app.post("/passport/add")
def add_sticker(request: StickerRequest):
    success = add_sticker_to_db(request.user_id, request.country, request.sticker_id)
    if success:
        return {"status": "success", "message": f"Sticker for {request.country} added!"}
    
    # This sends a REAL 500 error to the browser/terminal
    raise HTTPException(status_code=500, detail="Failed to update passport in Firestore")

# Endpoint for Coloring Zone
@app.post("/coloring/save")
def save_art(request: ArtRequest):
    success = save_artwork_to_db(request.user_id, request.art_name, request.drawing_data)
    if success:
        return {"status": "success", "message": "Masterpiece saved in the gallery!"}
    return {"status": "error", "message": "Failed to save art"}, 500