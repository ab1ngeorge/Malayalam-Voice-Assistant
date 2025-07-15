
import os
import queue
import sounddevice as sd
import vosk
import sys
import json
from gtts import gTTS
import playsound
from fuzzywuzzy import fuzz
import google.generativeai as genai

MODEL_PATH = "vosk-model-malayalam-trigram"
SAMPLE_RATE = 16000
USE_GUI = True
GEMINI_API_KEY = "AIzaSyA99yo7shSoVnrjio457jLU_KqH2KzBOgQ"  # <-- Replace with your Gemini API key

if USE_GUI:
    import tkinter as tk
    from PIL import Image, ImageTk

    class AssistantGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("Malayalam Voice Assistant")
            self.root.geometry("600x500")
            self.root.configure(bg="#f0f0f0")
            self.label_query = tk.Label(root, text="നിങ്ങൾ പറഞ്ഞു:", font=("Arial", 14), bg="#f0f0f0")
            self.label_query.pack(pady=(20, 5))
            self.text_query = tk.Label(root, text="", font=("Arial", 16, "bold"), fg="#333", bg="#f0f0f0", wraplength=550)
            self.text_query.pack(pady=(0, 20))
            self.label_response = tk.Label(root, text="അസിസ്റ്റന്റ്:", font=("Arial", 14), bg="#f0f0f0")
            self.label_response.pack()
            self.text_response = tk.Label(root, text="", font=("Arial", 15), fg="#005500", bg="#f0f0f0", wraplength=550)
            self.text_response.pack(pady=(0, 20))
            self.image_label = tk.Label(root, bg="#f0f0f0")
            self.image_label.pack(pady=10)
            self.root.update()

        def show_query(self, text):
            self.text_query.config(text=text)
            self.root.update()

        def show_response(self, text):
            self.text_response.config(text=text)
            self.root.update()

        def show_image(self, image_path):
            try:
                img = Image.open(image_path)
                img = img.resize((180, 180))
                img_tk = ImageTk.PhotoImage(img)
                self.image_label.config(image=img_tk)
                self.image_label.image = img_tk
                self.root.update()
            except Exception:
                self.image_label.config(image="")
                self.root.update()

        def clear_image(self):
            self.image_label.config(image="")
            self.root.update()

FAQS = {
    "പ്രിൻസിപ്പൽ": "കോളേജിന്റെ പ്രിൻസിപ്പൽ: ഡോ. രമേശ് കുമാർ.",
    "ഫീസ്": "B.Tech ഫീസ് 15,000 രൂപയാണ്.",
    "അറിയിപ്പുകൾ": "ഇപ്പോൾത്തെ പ്രധാന അറിയിപ്പുകൾ: പ്രവേശന തീയതി ജൂൺ 10.",
    "കോഴ്സ്": "B.Tech, M.Tech, MCA എന്നിവയാണ് ലഭ്യമായ കോഴ്സുകൾ.",
    "ഹോസ്റ്റൽ": "ഹോസ്റ്റൽ സൗകര്യം ലഭ്യമാണ്.",
    "അധ്യാപകർ": "Maths ഡിപ്പാർട്ടുമെന്റിൽ 5 അധ്യാപകരുണ്ട്.",
    "സമ്പർക്കം": "ഫോൺ: 0484-1234567, Email: info@college.edu",
    "ലൈബ്രറി": "കോളേജിൽ വലിയ ലൈബ്രറി സൗകര്യവും ഉണ്ട്.",
    "ലാബ്": "കോളേജിൽ വിവിധ ലാബുകൾ ലഭ്യമാണ്.",
    "ബസ്": "കോളേജിന് ബസ് സൗകര്യവും ലഭ്യമാണ്.",
    "സ്കോളർഷിപ്പ്": "SC/ST വിദ്യാർത്ഥികൾക്ക് സ്കോളർഷിപ്പ് ലഭ്യമാണ്.",
    "റിസർവേഷൻ": "വിദ്യാർത്ഥികൾക്ക് റിസർവേഷൻ ലഭ്യമാണ്.",
    "ഓൺലൈൻ പോർട്ടൽ": "ഓൺലൈൻ പോർട്ടൽ വഴി അപേക്ഷ സമർപ്പിക്കാം.",
    "സീറ്റ്": "കഴിഞ്ഞ വർഷം 25000 റാങ്ക് വരെ സീറ്റ് ലഭ്യമായിരുന്നു.",
    "റാങ്ക്": "നിങ്ങളുടെ റാങ്ക് പറയൂ, ഞാൻ സീറ്റ് സാധ്യത പറയാം.",
    "ഹെൽപ്പ്": "നിങ്ങൾക്ക് എന്ത് സഹായം വേണമെന്ന് ചോദിക്കൂ.",
    "അഡ്മിഷൻ": "അഡ്മിഷൻ സംബന്ധിച്ച വിവരങ്ങൾ കോളേജ് വെബ്സൈറ്റിൽ ലഭ്യമാണ്.",
    "ഡോക്യുമെന്റ്സ്": "അഡ്മിഷനു വേണ്ടിയുള്ള പ്രധാന രേഖകൾ: SSLC, Plus Two, TC, Conduct Certificate.",
    "ഡെഡ്‌ലൈൻ": "അപേക്ഷ സമർപ്പിക്കാനുള്ള അവസാന തീയതി ജൂൺ 30 ആണ്.",
    "ഓറിയന്റേഷൻ": "ഓറിയന്റേഷൻ സെഷൻ ജൂലൈ 5ന് നടക്കും.",
}

def fuzzy_intent(query):
    best_score = 0
    best_key = None
    for key in FAQS:
        score = fuzz.partial_ratio(query, key)
        if score > best_score:
            best_score = score
            best_key = key
    if best_score > 40:  # Forgiving threshold
        return FAQS[best_key]
    return None

def seat_predictor(query):
    import re
    match = re.search(r'(\d{2,6})', query)
    if match:
        rank = int(match.group(1))
        if rank < 10000:
            return f"നിങ്ങളുടെ റാങ്ക് {rank} ആണ്. സീറ്റ് ലഭിക്കാൻ നല്ല സാധ്യതയുണ്ട്."
        elif rank < 25000:
            return f"നിങ്ങളുടെ റാങ്ക് {rank} ആണ്. ചില കോഴ്സുകളിൽ സീറ്റ് ലഭിക്കാൻ സാധ്യതയുണ്ട്."
        else:
            return f"നിങ്ങളുടെ റാങ്ക് {rank} ആണ്. സീറ്റ് ലഭിക്കാൻ സാധ്യത കുറവാണ്."
    return None

def gemini_answer(query):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"നീ ഒരു കോളേജ് ഹെൽപ് ഡെസ്ക് ആണ്. ഉപയോക്താവിന്റെ ചോദ്യത്തിന് സൗഹൃദപരമായും വ്യക്തമായും മലയാളത്തിൽ മാത്രം ഉത്തരം നൽകുക. ചോദ്യമിതാണ്: {query}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return None

def play_audio(filename):
    try:
        playsound.playsound(filename)
    except Exception as e:
        print("playsound failed, trying os.system:", e)
        try:
            os.system(f'start {filename}')  # Windows only
        except Exception as e2:
            print("os.system also failed:", e2)

if not os.path.exists(MODEL_PATH):
    print(f"Please download and extract the Malayalam Vosk model as '{MODEL_PATH}' in the current folder.")
    sys.exit(1)

model = vosk.Model(MODEL_PATH)
q = queue.Queue()

def callback(indata, frames, time, status):
    q.put(bytes(indata))

def listen_and_recognize():
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                           channels=1, callback=callback):
        rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        print("മലയാളത്തിൽ പറയൂ...")
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = rec.Result()
                text = json.loads(result)["text"]
                print("Vosk recognized:", text)  # Debug print
                return text

def respond(text, gui=None):
    seat_response = seat_predictor(text)
    if seat_response:
        response = seat_response
    else:
        response = fuzzy_intent(text)
        if not response:
            response = gemini_answer(text)
            if not response:
                response = "ക്ഷമിക്കണം, ഞാൻ ഉത്തരം കണ്ടെത്താനായില്ല. കൂടുതൽ വിവരങ്ങൾക്ക് ഓഫിസുമായി ബന്ധപ്പെടുക."
    print("\n==============================")
    print("🗣️  നിങ്ങൾ പറഞ്ഞു:", text)
    print("🤖 അസിസ്റ്റന്റ്:", response)
    print("==============================\n")
    if gui:
        gui.show_query(text)
        gui.show_response(response)
        gui.clear_image()
    tts = gTTS(response, lang='ml')
    tts.save("response.mp3")
    play_audio("response.mp3")
    os.remove("response.mp3")

def main():
    gui = None
    if USE_GUI:
        root = tk.Tk()
        gui = AssistantGUI(root)
        import threading
        def run_voice():
            while True:
                try:
                    user_query = listen_and_recognize()
                    respond(user_query, gui)
                except KeyboardInterrupt:
                    print("\nExiting. Goodbye!")
                    break
                except Exception as e:
                    print("Error:", e)
        threading.Thread(target=run_voice, daemon=True).start()
        root.mainloop()
    else:
        print("Malayalam Voice Assistant Started. Press Ctrl+C to exit.")
        while True:
            try:
                user_query = listen_and_recognize()
                respond(user_query)
            except KeyboardInterrupt:
                print("\nExiting. Goodbye!")
                break
            except Exception as e:
                print("Error:", e)

if __name__ == "__main__":
    main()
