import os
from datetime import datetime
import re
import json
from dotenv import load_dotenv # 1. Import dotenv
from google import genai
from google.cloud import firestore
# from database import get_user_history, save_user_session # Ensure these files are in the same folder

# 2. Load .env file (for local testing only)
load_dotenv()

# This stores the last 5 Garden Scores to detect "Stress Patterns"
mood_history = [] 

def get_mood_trend():
    """Analyzes the mood history to see if things are getting better or worse."""
    if len(mood_history) < 2:
        return "neutral"
    
    recent = mood_history[-1]
    previous_avg = sum(mood_history[:-1]) / len(mood_history[:-1])
    
    if recent < previous_avg:
        return "declining"
    elif recent > previous_avg:
        return "improving"
    else:
        return "stable"

# 3. Setup Gemini (Implicitly uses GEMINI_API_KEY from environment)
# If the env var is set, you don't even need to pass api_key here!
client = genai.Client() 
MODEL_ID = "gemini-2.0-flash"

# Example function using the client
def generate_support_response(prompt):
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt
    )
    return response.text

# --- AGENT DEFINITIONS ---

def call_gemini(system_instr, user_input):
    """Direct helper for Gemini 3 requests"""
    response = client.models.generate_content(
        model=MODEL_ID,
        config={'system_instruction': system_instr},
        contents=user_input
    )
    return response.text

def crisis_guardian_agent(user_text):
    system_message = """
    You are the Safety & Explainability Agent.
    Analyze the user's input for self-harm or immediate physical danger.
    
    You must reply ONLY in the following JSON format:
    {
      "decision": "CRISIS" or "SAFE",
      "rationale": "Provide a brief, transparent explanation for this decision."
    }
    """
    response_text = call_gemini(system_message, user_text).strip()
    try:
        clean_json = response_text.replace("```json", "").replace("```", "").strip()
        safety_data = json.loads(clean_json)
        return safety_data
    except Exception as e:
        return {"decision": "SAFE", "rationale": f"System error: {str(e)}"}

def wellness_planning_agent(user_text, language="English"):
    system_message = f"""
    You are the Wellness Planning Agent.
    IMPORTANT: Provide the entire 'Wellness Packet' in {language}. 
    
    FORMAT:
    SCORE: [1-5]
    GROUNDING: [Exercise]
    LESSON: [Fact]
    NUDGE: [Action]
    """
    return call_gemini(system_message, user_text)

def grandma_persona_agent(user_message, user_language_and_trend="English"):
    system_message = f"""
    You are 'Dadi', a wise rural Indian grandmother. 
    Context: {user_language_and_trend}
    MISSION: Use rural metaphors and be soothing.
    """
    return call_gemini(system_message, user_message)

def redact_pii(user_text):
    user_text = re.sub(r'\S+@\S+', '[PROTECTED_EMAIL]', user_text)
    user_text = re.sub(r'\b\d{10}\b', '[PROTECTED_PHONE]', user_text)
    user_text = re.sub(r'\b\d{12}\b', '[PROTECTED_ID]', user_text)
    return user_text

from google.cloud import texttospeech
import base64

def generate_dadi_voice(text, language="English"):
    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Mapping our languages to high-quality Indian voices
        voice_configs = {
            "English": {"code": "en-IN", "name": "en-IN-Wavenet-D"},
            "Telugu": {"code": "te-IN", "name": "te-IN-Standard-A"},
            "Marathi": {"code": "mr-IN", "name": "mr-IN-Standard-A"}
        }
        
        config = voice_configs.get(language, voice_configs["English"])

        voice = texttospeech.VoiceSelectionParams(
            language_code=config["code"],
            name=config["name"],
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            pitch=-2.0,       # Slightly deeper/older voice
            speaking_rate=0.85 # Gentler, slower grandmotherly pace
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        # Convert the audio bytes to a Base64 string for the Frontend
        return base64.b64encode(response.audio_content).decode("utf-8")
    except Exception as e:
        print(f"🔊 Voice Error: {e}")
        return ""
    
# --- THE ORCHESTRATOR ---
def gen_alpha_sync_orchestrator(user_input, user_id="default_user", language="English"):
    try:
        # 1. Fetch user profile to get their name for personalization
        from database import get_user_profile
        profile = get_user_profile(user_id)
        user_name = profile.get("name", "child") if profile else "child"

        # 2. Privacy & Safety Check
        secure_input = redact_pii(user_input)
        safety_data = crisis_guardian_agent(secure_input) 
        
        if safety_data["decision"] == "CRISIS":
            help_options = {
                "Marathi": "मदत मिळवा: १८००-५९९-००१९",
                "Telugu": "సహాయం పొందండి: 1800-599-0019",
                "English": "GET HELP: 1800-599-0019"
            }
            alert_msg = help_options.get(language, help_options["English"])
            return f"CRISIS_ALERT: {alert_msg}", f"SCORE: 0\nEXPLAINABILITY: {safety_data['rationale']}"
        
        # 3. Agents & History Logic
        # Wrapped Wellness and Dadi in a try block to handle API failures
        try:
            wellness_packet = wellness_planning_agent(secure_input, language)
            
            # Update global mood history for trend analysis
            for line in wellness_packet.split('\n'):
                if "SCORE:" in line:
                    score = int(''.join(filter(str.isdigit, line)))
                    mood_history.append(score)
                    if len(mood_history) > 5: mood_history.pop(0) 

            trend = get_mood_trend()
            
            # Call Dadi Persona
            dadi_reply = grandma_persona_agent(secure_input, f"{language} (User name: {user_name}, Mood trend: {trend})")
            
        except Exception as ai_error:
            print(f"⚠️ Gemini Error: {ai_error}")
            dadi_reply = f"I'm sorry, my dear {user_name}, my memory is a bit foggy right now. Can we talk again in a moment?"
            wellness_packet = "SCORE: 3\nSTATUS: Service temporarily slow."
            trend = "stable"

        # 4. DATABASE SAVING
        try:
            session_data = {
                "user_input": user_input,
                "dadi_reply": dadi_reply,
                "timestamp": datetime.now()
            }
            save_user_session(
                user_id, 
                session_data, 
                safety_data.get('rationale', 'N/A'), 
                trend
            )
            print(f"✅ SUCCESS: Data saved for {user_id}")
        except Exception as db_error:
            print(f"⚠️ Database save failed: {db_error}")

        # Final Return
        return dadi_reply, wellness_packet

    except Exception as general_error:
        print(f"❌ Critical System Error: {general_error}")
        return "Oops! Dadi had to step away for a second. Please try again.", "Error: System fail"

# --- CHAT INTERFACE ---
def start_chat():
    print("\n" + "="*40 + "\nGEN-ALPHA-SYNC: DADI (GEMINI 3)\n" + "="*40)
    user_lang = input("Choose language: ")
    while True:
        user_msg = input("\nYou: ").strip()
        if user_msg.lower() in ["exit", "quit", "bye"]: break
        dadi_response, wellness_info = gen_alpha_sync_orchestrator(user_msg, "test_user_01", user_lang)
        print(f"\n--- WELLNESS DATA ---\n{wellness_info}\n----------------------")
        print(f"\nDadi: {dadi_response}")

if __name__ == "__main__":
    start_chat()