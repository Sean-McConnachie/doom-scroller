import cv2
import numpy as np
import undetected_chromedriver as uc # Changed from selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import time
from pynput import keyboard
import base64
from effects import * # Import all effect classes
import math
import threading
import logging

# --- Web Server Imports ---
from flask import Flask, render_template
from flask_socketio import SocketIO

# --- Constants ---
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080

# --- App State ---
app_state = {
    "effect_index": 0,
    "effects": [
        NoEffect(),
        Rotate180(),
        ChromaticAberration(),
        HueShift(),
        WaveWarp(),
        Kaleidoscope(),
        GlitchLines(),
        Strobe(),
        FractalZoom(),
        Bloom(),
        Negative(),
    ],
    "running": True,
    "next_btn": None,
    "prev_btn": None,
    "listener": None
}

# --- Flask and SocketIO Setup ---
app = Flask(__name__)
socketio = SocketIO(app)
# Suppress noisy server logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def index():
    """Serves the remote control webpage."""
    return render_template('index.html')

def tile_frame_to_canvas(frame, target_width, target_height):
    """
    Resizes the frame to fit the target height and then tiles it
    horizontally to fill the target width.
    """
    h, w = frame.shape[:2]
    
    # Resize frame to match target height while maintaining aspect ratio
    aspect_ratio = w / h
    new_h = target_height
    new_w = int(new_h * aspect_ratio)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Calculate how many tiles are needed
    num_tiles = math.ceil(target_width / new_w)
    
    # Create a tiled strip
    tiled_strip = np.hstack([resized] * num_tiles)
    
    # Crop the strip to the exact target width
    return tiled_strip[:, :target_width]


# --- Navigation and Control Functions ---
def next_video(driver):
    print("Navigating to next video...")
    try:
        app_state["next_btn"].click()
    except Exception as e:
        print(f"Could not navigate to next video: {e}")

def prev_video(driver):
    print("Navigating to previous video...")
    try:
        app_state["prev_btn"].click()
    except Exception as e:
        print(f"Could not navigate to previous video: {e}")

def next_effect():
    app_state["effect_index"] = (app_state["effect_index"] + 1) % len(app_state["effects"])
    print(f"Current effect: {app_state['effects'][app_state['effect_index']].name}")

def prev_effect():
    app_state["effect_index"] = (app_state["effect_index"] - 1 + len(app_state["effects"])) % len(app_state["effects"])
    print(f"Current effect: {app_state['effects'][app_state['effect_index']].name}")

def quit_app():
    if app_state["running"]:
        print("Shutting down...")
        app_state["running"] = False
        if app_state.get("listener"):
            app_state["listener"].stop()

# --- Selenium and Frame Capture Functions ---
def setup_selenium():
    """Initializes and returns an undetected_chromedriver instance."""
    print("Setting up undetected-chromedriver...")
    options = uc.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-web-security")

    try:
        # Use undetected_chromedriver
        driver = uc.Chrome(options=options, use_subprocess=True)
    except Exception as e:
        print(f"\n{'='*60}\nERROR: Could not start Selenium.\n{e}\n{'='*60}")
        return None

    driver.get("https://www.tiktok.com/en")
    print(f"\n{'='*50}\nPlease complete any login/CAPTCHA in the browser.\n"
          f"Once ready, press 's' in this terminal to start.\n{'='*50}")

    while True:
        try:
            if input().lower() == 's': break
        except (EOFError, KeyboardInterrupt):
            print("\nExiting setup.")
            driver.quit()
            exit()
            
    print("Starting video processing...")
    return driver

def get_frame_via_canvas(driver):
    js_script = """
        const video = document.querySelector('video');
        if (!video || video.readyState < 2) { return null; }
        var canvas = document.getElementById('__gemini_canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.id = '__gemini_canvas';
            canvas.style.display = 'none';
            document.body.appendChild(canvas);
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL('image/jpeg', 0.8);
    """
    try:
        data_url = driver.execute_script(js_script)
        if not data_url: return None
        
        header, encoded = data_url.split(",", 1)
        decoded_data = base64.b64decode(encoded)
        np_arr = np.frombuffer(decoded_data, np.uint8)
        return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except Exception:
        return None
    
def find_next_prev_btns(driver):
    try:
        wait = WebDriverWait(driver, 10)
        nav_container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='DivFeedNavigationContainer']")))
        buttons = nav_container.find_elements(By.TAG_NAME, "button")
        app_state["prev_btn"] = buttons[0]
        app_state["next_btn"] = buttons[1]
    except TimeoutException:
        print("Could not find navigation buttons.")

# --- Main Application Logic ---
def main():
    driver = setup_selenium()
    if not driver: return
    
    # --- SocketIO Event Handlers ---
    @socketio.on('control_event')
    def handle_control_event(data):
        """Handles commands received from the web client."""
        command = data.get('command')
        if not command: return
        
        print(f"Received command from web: {command}")
        
        if command == 'next_video':
            next_video(driver)
        elif command == 'prev_video':
            prev_video(driver)
        elif command == 'next_effect':
            next_effect()
        elif command == 'prev_effect':
            prev_effect()

    # --- Start Web Server in a separate thread ---
    def run_web_server():
        # Using eventlet is recommended. host='0.0.0.0' makes it accessible on your local network.
        socketio.run(app, host='0.0.0.0', port=5000)

    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True # Allows main app to exit even if server thread is running
    server_thread.start()
    print("\n" + "="*50)
    print("✅ Web controller is running!")
    print("   Open a browser on your phone/computer and go to:")
    print("   http://<YOUR-COMPUTER-IP-ADDRESS>:5000")
    print("="*50 + "\n")


    def on_press(key):
        if not app_state["running"]: return False 
        try:
            actions = {
                keyboard.Key.right: lambda: next_video(driver),
                keyboard.Key.left:  lambda: prev_video(driver),
                keyboard.Key.up:    next_effect,
                keyboard.Key.down:  prev_effect,
            }
            if key in actions:
                actions[key]()
            elif key.char == 'q':
                quit_app()
        except AttributeError:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    app_state["listener"] = listener

    window_name = "TikTok Live Feed"
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


    while app_state["running"]:
        try:
            if not app_state["next_btn"] or not app_state["prev_btn"]:
                find_next_prev_btns(driver)

            frame = get_frame_via_canvas(driver)

            if frame is not None and frame.size > 0:
                tiled_frame = tile_frame_to_canvas(frame, OUTPUT_WIDTH, OUTPUT_HEIGHT)
                
                active_effect = app_state["effects"][app_state["effect_index"]]
                processed_frame = active_effect.apply(tiled_frame.copy())
                
                # effect_name = active_effect.name
                # cv2.putText(processed_frame, f"Effect: {effect_name}", (20, 50),
                #             cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3, cv2.LINE_AA)

                cv2.imshow("TikTok Live Feed", processed_frame)
            else:
                time.sleep(0.05)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                quit_app()

        except StaleElementReferenceException:
            print("Page changed. Re-finding navigation buttons...")
            app_state["next_btn"], app_state["prev_btn"] = None, None
            time.sleep(0.5)
        except Exception as e:
            print(f"An unexpected error occurred in the main loop: {e}")
            if not driver.window_handles:
                print("Browser window was closed.")
                quit_app()

    listener.join()
    driver.quit()
    cv2.destroyAllWindows()
    print("Application closed.")

if __name__ == "__main__":
    main()