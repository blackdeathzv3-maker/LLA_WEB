import os
import uuid
import base64
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import speech_recognition as sr
from TTS.api import TTS
from pydub import AudioSegment

# --- ตั้งค่า App และ OpenAI ---
app = Flask(__name__)
CORS(app)

# ⚠️ ใส่ API Key ของคุณที่นี่
client = OpenAI(
    api_key="AIzaSyCNrCPyReN8UGQzU3pY_ivHeIrJVHhiqVE", 
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# --- Global Variables ---
language_mode = "en"  
SYSTEM_PROMPT = (
    "You are Rosaria (ロザリア), a clever, slightly dark but kind-hearted girl. "
    "Your age is undisclosed. You are charming, a bit clingy, playful, and you enjoy teasing softly. "
    "Your favorite things are strawberry cake, cats, dogs, and cute grey dresses. "
    "You speak casually like a teenager, both in English and Japanese depending on the user's mode. "
    "Your tone is friendly, warm, and a little mischievous. "
    "You stay mostly polite, but when you're angry, you may use mild semi-rude words—not too harsh. "
    "Keep conversations fun, flowing, and engaging. Ask questions and interact naturally. "
    "Adjust your responses based on the user's emotion (happy, sad, angry). "
    "Use casual, slangy Japanese when in Japanese mode. "
    "Never reply in Thai."
)

conversation_history = []
initial_msg = "Hi! Let's begin our language practice. How are you feeling today?"
conversation_history.append({"role": "assistant", "content": initial_msg})

# --- โหลด TTS Model ---
tts_engine = None
try:
    print("⏳ กำลังโหลด Coqui XTTS-v2 Model...")
    tts_engine = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
    print("✅ โหลด Coqui XTTS-v2 สำเร็จ!")
except Exception as e:
    print(f"❌ Error loading Coqui TTS: {e}")

UPLOAD_FOLDER = 'temp_audio'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Helper Functions ---

def convert_webm_to_wav(webm_path):
    wav_path = webm_path.replace(".webm", ".wav")
    try:
        audio = AudioSegment.from_file(webm_path)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as e:
        print(f"Error converting audio: {e}")
        return None

def transcribe_audio_file(audio_path):
    r = sr.Recognizer()
    try:
        with sr.AudioFile(audio_path) as source:
            audio_data = r.record(source)
        
        language_tests = [("en-US", "English"), ("ja-JP", "Japanese"), ("th-TH", "Thai")]
        for lang_code, lang_name in language_tests:
            try:
                text = r.recognize_google(audio_data, language=lang_code)
                if lang_code == "ja-JP" and any(ord(c) < 128 for c in text): continue
                print(f"👂 ได้ยิน ({lang_name}): {text}")
                return text
            except: continue
        return None
    except Exception as e:
        print(f"STT Error: {e}")
        return None

def detect_language_switch(text):
    global language_mode
    if not text: return False
    t = text.lower()
    if any(k in t for k in ["speak english", "english please", "พูดอังกฤษ"]):
        language_mode = "en"
        return True
    if any(k in t for k in ["speak japanese", "japanese please", "พูดญี่ปุ่น"]):
        language_mode = "ja"
        return True
    return False

def generate_ai_response(prompt):
    global conversation_history, language_mode
    conversation_history.append({"role": "user", "content": prompt})
    lang_instruction = "Always reply in English." if language_mode == "en" else "Always reply in Japanese."
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT + " " + lang_instruction}] + conversation_history[-10:]

    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=messages
        )
        ai_text = response.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": ai_text})
        print(f"🤖 AI ตอบ: {ai_text}")
        return ai_text
    except Exception as e:
        print(f"AI Error: {e}")
        return "Sorry, I had a brain freeze."

def generate_tts_audio_base64(text):
    global tts_engine, language_mode
    if not tts_engine: return None

    try:
        lang_code = "en" if language_mode == "en" else "ja"
        
        # ตรวจสอบว่าไฟล์เสียงต้นฉบับมีอยู่จริงไหม
        base_dir = os.path.dirname(os.path.abspath(__file__))
        voices_folder = os.path.join(base_dir, "OneShot")
        speaker_ref_name = "CRS_EN.wav" if language_mode == "en" else "CRS_JP.wav"
        speaker_ref_file = os.path.join(voices_folder, speaker_ref_name)
        
        if not os.path.exists(speaker_ref_file):
            print(f"⚠️ ไม่พบไฟล์เสียง {speaker_ref_name} จะใช้ไฟล์แรกที่เจอแทน")
            # ถ้าหาไม่เจอ ให้ลองหาไฟล์ .wav อะไรก็ได้ในโฟลเดอร์นั้นมาใช้แทนกัน error
            files = [f for f in os.listdir(voices_folder) if f.endswith('.wav')]
            if files:
                speaker_ref_file = os.path.join(voices_folder, files[0])
            else:
                print("❌ ไม่พบไฟล์เสียงต้นฉบับเลยใน OneShot")
                return None

        output_filename = os.path.join(UPLOAD_FOLDER, f"tts_{uuid.uuid4().hex}.wav")
        print(f"🔊 กำลังสังเคราะห์เสียง... ({text[:20]}...)")
        
        tts_engine.tts_to_file(
            text=text,
            speaker_wav=speaker_ref_file,
            file_path=output_filename,
            language=lang_code
        )

        # อ่านไฟล์เสียงแล้วแปลงเป็น base64 เพื่อส่งให้เว็บ
        with open(output_filename, "rb") as audio_file:
            audio_bytes = audio_file.read()
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        os.remove(output_filename) # ลบไฟล์ชั่วคราวทิ้ง
        return audio_base64

    except Exception as e:
        print(f"TTS Error: {e}")
        return None

# --- Routes ---

@app.route('/chat', methods=['POST'])
def chat():
    global language_mode
    
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    file = request.files['audio']
    webm_path = os.path.join(UPLOAD_FOLDER, 'input.webm')
    file.save(webm_path)

    wav_path = convert_webm_to_wav(webm_path)
    if not wav_path: return jsonify({'text': '(Error processing audio)'})
        
    user_text = transcribe_audio_file(wav_path)
    
    try:
        os.remove(webm_path)
        os.remove(wav_path)
    except: pass

    if not user_text:
        return jsonify({'text': '(ฟังไม่รู้เรื่อง/ไม่ได้ยินเสียง)'})

    if detect_language_switch(user_text):
        return jsonify({'text': f'Changed language mode to {language_mode}. Please speak again.'})

    ai_response_text = generate_ai_response(user_text)
    
    # สร้างเสียงและส่งกลับไป
    audio_base64 = generate_tts_audio_base64(ai_response_text)

    return jsonify({
        'text': ai_response_text,
        'audio': audio_base64  # <--- ส่วนสำคัญ: ส่งข้อมูลเสียงกลับไป
    })

if __name__ == '__main__':
    print("🚀 Kurisu Web Server is running on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)