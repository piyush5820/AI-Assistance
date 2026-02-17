"""
JARVIS - A Python-based desktop assistant (starter kit)

Features:
- Wake word: "jarvis" (typed or spoken)
- Speech-to-text using speech_recognition (Google's API by default)
- Text-to-speech using pyttsx3 (offline)
- Optional Google Gemini integration for advanced conversational replies (requires GEMINI_API_KEY)
- Handlers for: time/date, web search, Wikipedia summary, open applications/websites, play music, system commands (shutdown/logoff), simple notes

Limitations & Safety:
- This is a starter template. Do NOT run system shutdown commands unless you understand them.
- Speech recognition using the default Google API requires internet. For fully offline STT, integrate VOSK or similar.
- If you enable Gemini, your prompts and replies go to Google Gemini API.

Requirements (install via pip):
- pip install SpeechRecognition pyttsx3 wikipedia google-generativeai pyaudio
  * On Windows, you may need to install PyAudio from wheel if pip install fails.

Usage:
- Set environment variable GEMINI_API_KEY if you want Gemini-powered responses (optional).
- Run: python jarvis_assistant.py
- Speak after the prompt or type commands. Say (or type) "exit" or "shutdown assistant" to stop.

Customization:
- Add new command handlers in `handle_command()`.
- Replace wake-word logic with continuous hotword detector (e.g., snowboy or Porcupine) for always-on.

---

Below is the full single-file code. Save as `jarvis_assistant.py` and run.

"""

import os
import time
import webbrowser
import subprocess
import sys
import threading
from datetime import datetime

try:
    import speech_recognition as sr
    import pyttsx3
    import wikipedia
except Exception as e:
    print("One or more dependencies are missing. Please install requirements as described in the header.")
    print(e)
    sys.exit(1)

# Optional: Google Gemini for advanced replies
USE_GEMINI = False
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        USE_GEMINI = True
    except Exception:
        USE_GEMINI = False

# Initialize TTS engine
engine = pyttsx3.init()
engine.setProperty('rate', 160)  # speaking rate
voices = engine.getProperty('voices')
# pick a voice that sounds assistant-like if available
if voices:
    engine.setProperty('voice', voices[0].id)

# Thread lock for safe engine access
engine_lock = threading.Lock()

def speak(text):
    """Speak text (non-blocking)."""
    def _s():
        with engine_lock:
            engine.say(text)
            engine.runAndWait()
    t = threading.Thread(target=_s, daemon=True)
    t.start()

# Initialize recognizer
recognizer = sr.Recognizer()
mic = None

# Try to get default microphone
try:
    mic = sr.Microphone()
except Exception:
    mic = None


def select_microphone():
    """List available microphones and allow user to select one. Returns mic or None."""
    global mic
    try:
        names = sr.Microphone.list_microphone_names()
    except Exception as e:
        print("Could not list microphones:", e)
        return None
    if not names:
        print("No microphone devices found.")
        return None
    print("Available microphone devices:")
    for i, n in enumerate(names):
        print(f"{i}: {n}")
    choice = input("Select microphone index or press Enter to cancel: ").strip()
    if choice == '':
        return None
    try:
        idx = int(choice)
        mic = sr.Microphone(device_index=idx)
        print(f"Selected microphone: {names[idx]}")
        return mic
    except Exception as e:
        print("Failed to initialize selected microphone:", e)
        mic = None
        return None

WELCOME = "Hello sir, Jarvis at your service. Say a command or type it."

def listen(timeout=3, phrase_time_limit=8):
    """Listen from microphone and return recognized text (or None)."""
    if mic is None:
        print('No microphone available. Run `First.py` to list devices or select one when prompted.')
        return None
    with mic as source:
        try:
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            print("Listening...")
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            print('Listen timed out: no speech detected within timeout window.')
            return None
        except Exception as e:
            print('Error capturing audio:', e)
            return None
    try:
        text = recognizer.recognize_google(audio)
        print("You said:", text)
        return text.lower()
    except sr.UnknownValueError:
        print('Could not understand audio (UnknownValueError).')
        return None
    except sr.RequestError:
        print("Speech recognition service is unavailable. Check your internet or use offline STT.")
        return None
    except Exception as e:
        print('Recognition error:', e)
        return None


def ask_gemini(prompt):
    if not USE_GEMINI:
        return None
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print("Gemini request failed:", e)
        return None


def search_wikipedia(query, sentences=2):
    try:
        return wikipedia.summary(query, sentences=sentences)
    except Exception as e:
        return f"Wikipedia search failed: {e}"


def handle_command(cmd):
    """Basic command dispatcher. Extend this with more capabilities."""
    if not cmd:
        return "I didn't catch that."
    cmd = cmd.lower()

    # Exit
    if any(kw in cmd for kw in ["exit", "quit", "goodbye", "shutdown assistant"]):
        speak("Shutting down. Have a good day, sir.")
        print("Exiting...")
        sys.exit(0)

    # Time / Date
    if 'time' in cmd:
        now = datetime.now().strftime('%I:%M %p')
        speak(f"The time is {now}")
        return f"Time: {now}"
    if 'date' in cmd:
        today = datetime.now().strftime('%A, %B %d, %Y')
        speak(f"Today is {today}")
        return f"Date: {today}"

    # Wikipedia
    if cmd.startswith('wikipedia') or 'who is' in cmd or 'what is' in cmd:
        q = cmd.replace('wikipedia', '').replace('who is', '').replace('what is', '').strip()
        if not q:
            return "Ask me who or what to search on Wikipedia."
        speak(f"Searching Wikipedia for {q}")
        summary = search_wikipedia(q, sentences=2)
        speak(summary)
        return summary

    # Open websites
    if cmd.startswith('open '):
        target = cmd.replace('open ', '').strip()
        if '.' in target or 'http' in target:
            url = target if target.startswith('http') else 'https://' + target
            webbrowser.open(url)
            speak(f"Opening {target}")
            return f"Opened {url}"
        # common sites
        mapping = {
            'youtube': 'https://youtube.com',
            'google': 'https://google.com',
            'github': 'https://github.com',
            'gmail': 'https://mail.google.com'
        }
        if target in mapping:
            webbrowser.open(mapping[target])
            speak(f"Opening {target}")
            return f"Opened {target}"

    # Web search
    if cmd.startswith('search ') or cmd.startswith('google '):
        q = cmd.replace('search ', '').replace('google ', '').strip()
        url = f"https://www.google.com/search?q={q.replace(' ', '+')}"
        webbrowser.open(url)
        speak(f"Here are the Google results for {q}")
        return f"Searched Google for: {q}"

    # Play music (open a folder or YouTube playlist)
    if 'play music' in cmd or cmd.startswith('play '):
        # If user provided a file or folder path, try to play it
        target = cmd.replace('play music', '').replace('play', '').strip()
        if target:
            # open the target in file explorer or browser
            if os.path.exists(target):
                if sys.platform.startswith('win'):
                    os.startfile(target)
                elif sys.platform.startswith('darwin'):
                    subprocess.Popen(['open', target])
                else:
                    subprocess.Popen(['xdg-open', target])
                speak(f"Playing {target}")
                return f"Playing {target}"
        # default: open YouTube music
        webbrowser.open('https://music.youtube.com')
        speak('Opening YouTube Music')
        return 'Opened YouTube Music'

    # System commands (dangerous) - require explicit keywords
    if 'shutdown' in cmd and 'computer' in cmd:
        speak('Shutting down the computer now. Goodbye.')
        if sys.platform.startswith('win'):
            subprocess.call(['shutdown', '/s', '/t', '5'])
        elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            subprocess.call(['sudo', 'shutdown', '-h', 'now'])
        return 'Shutdown initiated.'

    # Note taking
    if 'note' in cmd or 'remember' in cmd:
        note_text = cmd.replace('note', '').replace('remember', '').strip()
        if not note_text:
            return 'What should I note?'
        with open('jarvis_notes.txt', 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] {note_text}\n")
        speak('Noted.')
        return f'Noted: {note_text}'

    # If Gemini is enabled, defer to it for general chit-chat / complex replies
    if USE_GEMINI:
        speak('Thinking...')
        response = ask_gemini(cmd)
        if response:
            speak(response)
            return response

    # Default fallback
    speak("I can help with web search, Wikipedia, opening apps, playing music, and system info. Try: 'search', 'open youtube', 'time', or 'wikipedia <topic>'")
    return "I didn't understand that. Try asking something else."


def main_loop():
    print(WELCOME)
    speak(WELCOME)
    while True:
        print('\nChoose input method: (1) Speak  (2) Type  (3) Quit')
        choice = input('Your choice (1/2/3): ').strip()
        if choice == '3':
            print('Goodbye.')
            speak('Goodbye, sir.')
            break
        if choice == '1':
            # ensure a microphone is available; if not, offer selection
            if mic is None:
                print('No microphone was automatically detected.')
                sel = input('Would you like to select a microphone? (y/N): ').strip().lower()
                if sel == 'y':
                    select_microphone()
            text = listen()
            if not text:
                print('No speech detected — try typing instead.')
                continue
        else:
            text = input('Type your command: ').strip()
            if not text:
                continue

        # normalize input for wake-word handling (case-insensitive)
        if text:
            text = text.lower()

        # optional wake-word handling
        if 'jarvis' in text:
            # remove wake-word
            text = text.replace('jarvis', '').strip()

        print('Processing:', text)
        result = handle_command(text)
        print('Result:', result)

if __name__ == '__main__':
    try:
        main_loop()
    except KeyboardInterrupt:
        print('\nInterrupted. Exiting...')
        speak('Goodbye, sir.')
        time.sleep(0.5)
        sys.exit(0)
