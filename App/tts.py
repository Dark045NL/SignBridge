"""
tts.py – Text-to-Speech voor SignBridge
Zuyd Hogeschool | Lectoraat Data Intelligence

Platform-detectie: Windows SAPI > macOS say > Linux espeak > pyttsx3
Elke speak()-aanroep is non-blocking via een daemon-thread + lock.
"""

import threading, platform, subprocess

_lock = threading.Lock()

def _detect() -> str | None:
    if platform.system() == "Windows":
        try:
            import win32com.client
            win32com.client.Dispatch("SAPI.SpVoice")
            return "sapi"
        except Exception:
            pass
    if platform.system() == "Darwin":
        return "say"
    if platform.system() == "Linux":
        if subprocess.run(["which", "espeak"], capture_output=True).returncode == 0:
            return "espeak"
    try:
        import pyttsx3
        e = pyttsx3.init(); e.stop()
        return "pyttsx3"
    except Exception:
        pass
    return None

METHOD    = _detect()
AVAILABLE = METHOD is not None

if AVAILABLE:
    print(f"  [TTS] {METHOD}")
else:
    print("  [TTS] niet beschikbaar — pip install pywin32  of  espeak")


def speak(text: str) -> None:
    """Spreek tekst non-blocking uit. Overlap wordt overgeslagen."""
    if not AVAILABLE or not text:
        return

    def _run():
        if not _lock.acquire(blocking=False):
            return
        try:
            if METHOD == "sapi":
                import win32com.client
                sapi = win32com.client.Dispatch("SAPI.SpVoice")
                for v in sapi.GetVoices():
                    desc = v.GetDescription().lower()
                    if "nl" in desc or "dutch" in desc or "netherlands" in desc:
                        sapi.Voice = v
                        break
                sapi.Rate = 1
                sapi.Speak(text)
            elif METHOD == "say":
                subprocess.run(["say", "-r", "180", text],
                               capture_output=True, timeout=10)
            elif METHOD == "espeak":
                subprocess.run(["espeak", "-v", "nl", "-s", "160", text],
                               capture_output=True, timeout=10)
            elif METHOD == "pyttsx3":
                import pyttsx3
                eng = pyttsx3.init()
                eng.setProperty("rate", 155)
                nl = next((v for v in eng.getProperty("voices")
                           if "nl" in v.id.lower()), None)
                if nl:
                    eng.setProperty("voice", nl.id)
                eng.say(text)
                eng.runAndWait()
                eng.stop()
        except Exception:
            pass
        finally:
            _lock.release()

    threading.Thread(target=_run, daemon=True).start()
