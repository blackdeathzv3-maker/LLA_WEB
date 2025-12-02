from openai import OpenAI
import speech_recognition as sr
import os
import uuid
from threading import Thread
import keyboard
import playsound 
import time
from TTS.api import TTS 

client = OpenAI(
    api_key="AIzaSyCNrCPyReN8UGQzU3pY_ivHeIrJVHhiqVE",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

mic_enabled = True 
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

tts_engine = None

try:
    tts_engine = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu") 
    print(" โหลด Coqui XTTS-v2 Model บน CPU สำเร็จ!")
except Exception as e:
    print(f" Error loading Coqui TTS: {e}. ใช้ gTTS เป็นตัวสำรองแทน.")
    from gtts import gTTS
    print(" ใช้ gTTS TTS สำรอง")

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print(" พูดได้เลย..." if mic_enabled else " ไมค์ปิด กด 'm' เพื่อเปิด")
        audio = r.listen(source)

    language_tests = [
        ("th-TH", "Thai"),
        ("en-US", "English"),
        ("ja-JP", "Japanese")
    ]

    for lang_code, lang_name in language_tests:
        try:
            text = r.recognize_google(audio, language=lang_code)
            if lang_code == "ja-JP" and any(ord(c) < 128 for c in text):
                continue
            print(f" คุณพูดเป็น {lang_name}: {text}")
            return text, lang_code
        except:
            continue

    print(" ฟังไม่ชัด ลองใหม่")
    return None, None

def detect_language_switch(text):
    global language_mode
    if not text:
        return False

    t = text.lower()
    
    if any(k in t for k in ["speak english", "english please", "พูดอังกฤษ", "เปลี่ยนเป็นอังกฤษ"]):
        language_mode = "en"
        print(" เปลี่ยนโหมดเป็น: English")
        return True

    if any(k in t for k in ["speak japanese", "japanese please", "พูดญี่ปุ่น", "เปลี่ยนเป็นญี่ปุ่น", "日本語"]):
        language_mode = "ja"
        print(" เปลี่ยนโหมดเป็น: Japanese")
        return True

    return False

def chat_ai(prompt, history):
    history.append({"role": "user", "content": prompt})

    lang_instruction = (
        "Always reply in English."
        if language_mode == "en"
        else "Always reply in Japanese."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + " " + lang_instruction}
    ] + history

    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=messages
    )

    ai_text = response.choices[0].message.content
    print(" AI:", ai_text)

    history.append({"role": "assistant", "content": ai_text})
    return ai_text

def speak(text):
    global tts_engine 
    
    if tts_engine:
        def run_tts_coqui(text_to_speak, language_mode):
            try:
                lang_code = "en" if language_mode == "en" else "ja"
                
                base_dir = os.path.dirname(os.path.abspath(__file__))
                voices_folder = os.path.join(base_dir, "OneShot")

                if language_mode == "en":
                    speaker_ref_name = "CRS_EN.wav"
                elif language_mode == "ja":
                    speaker_ref_name = "CRS_JP.wav"
                else:
                    speaker_ref_name = "CRS_EN.wav"

                speaker_ref_file = os.path.join(voices_folder, speaker_ref_name)
                filename = f"tts_{uuid.uuid4().hex}.wav"

                if not os.path.exists(speaker_ref_file):
                    print(f" คำเตือน: ไม่พบไฟล์เสียง {speaker_ref_name} ใน {voices_folder}")
                    fallback = "CRS_EN.wav"
                    speaker_ref_file = os.path.join(voices_folder, fallback)

                print(f" สังเคราะห์เสียง ({lang_code}) ใช้ไฟล์: {speaker_ref_name}...")
                
                tts_engine.tts_to_file(
                    text=text_to_speak,
                    speaker_wav=speaker_ref_file,
                    file_path=filename,
                    language=lang_code
                )
                
                try:
                    playsound.playsound(filename)
                    time.sleep(1)
                    os.remove(filename) 
                except PermissionError:
                    print(f" ลบไฟล์ไม่ได้ (Windows ล็อกไฟล์ไว้): {filename} จะปล่อยทิ้งไว้")
                except Exception as e:
                    print(f" เกิดข้อผิดพลาดตอนเล่นเสียง: {e}")
                
            except Exception as e:
                print(f" Error Coqui TTS: {e}")

        Thread(target=run_tts_coqui, args=(text, language_mode), daemon=True).start()
        return
    
    try:
        from gtts import gTTS
        lang = "en" if language_mode == "en" else "ja"
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)
        def play_and_remove(filename):
            try:
                playsound.playsound(filename)
                time.sleep(1)
                os.remove(filename)
            except:
                pass
        Thread(target=play_and_remove, args=(filename,), daemon=True).start()
    except:
        pass

def toggle_mic():
    global mic_enabled
    mic_enabled = not mic_enabled
    print(f" ไมค์ {'เปิด' if mic_enabled else 'ปิด'}")

keyboard.add_hotkey('m', toggle_mic)
print("กด 'm' เพื่อเปิด/ปิดไมค์")

conversation_history = []
initial = "Hi! Let's begin our language practice. How are you feeling today?"
conversation_history.append({"role": "assistant", "content": initial})
speak(initial)

while True:
    if not mic_enabled:
        keyboard.wait('m')
        continue

    user_input, lang_code = listen()
    if not user_input:
        continue

    if user_input.lower() in ["หยุด", "พอแล้ว", "stop", "exit"]:
        speak("Goodbye! See you next time!")
        break

    if detect_language_switch(user_input):
        speak("Language mode changed!")
        continue

    ai_reply = chat_ai(user_input, conversation_history)
    speak(ai_reply)