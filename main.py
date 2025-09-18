import cv2
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, JavascriptException
import time
from pynput import keyboard
import base64

app_state = {
    "effect_index": 0,
    "effects": [],
    "effect_names": [],
    "running": True,
    "video_element": None,
    "next_btn": None,
    "prev_btn": None,
    "listener": None
}

def no_effect(frame):
    return frame

def rotate_180(frame):
    return cv2.rotate(frame, cv2.ROTATE_180)

app_state["effects"] = [no_effect, rotate_180]
app_state["effect_names"] = ["No Effect", "Rotate 180°"]

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
    print(f"Current effect: {app_state['effect_names'][app_state['effect_index']]}")

def prev_effect():
    app_state["effect_index"] = (app_state["effect_index"] - 1 + len(app_state["effects"])) % len(app_state["effects"])
    print(f"Current effect: {app_state['effect_names'][app_state['effect_index']]}")

def quit_app():
    if app_state["running"]:
        print("Shutting down...")
        app_state["running"] = False
        if app_state.get("listener"):
            app_state["listener"].stop()

def setup_selenium():
    print("Setting up Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--mute-audio")
    # This flag is necessary to bypass the CORS policy that prevents canvas data extraction
    options.add_argument("--disable-web-security")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print("\n" + "="*60)
        print("ERROR: Could not start Selenium.")
        print("This might be because Google Chrome is not installed or not in the system's PATH.")
        print("Please ensure Google Chrome is installed correctly.")
        print(f"Selenium Error: {e}")
        print("="*60)
        return None

    driver.get("https://www.tiktok.com/en")
    print("\n" + "="*50)
    print("Please complete any login or CAPTCHA in the browser.")
    print("Once you see the live videos, press 's' in this terminal to start.")
    print("="*50)

    while True:
        try:
            if input().lower() == 's':
                break
        except (EOFError, KeyboardInterrupt):
            print("\nExiting setup.")
            driver.quit()
            exit()
            
    print("Starting video processing...")
    return driver

def find_video_element(driver):
    try:
        wait = WebDriverWait(driver, 10)
        video_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, "video")))
        return video_element
    except TimeoutException:
        print("Could not find the video element. The page structure may have changed.")
        print("Please ensure a live video is actively playing.")
        return None

def get_frame_via_canvas(driver):
    js_script = """
        const video = document.querySelector('video');
        if (!video) { return null; }

        // Set crossOrigin to 'anonymous' to prevent canvas tainting from cross-domain video feeds.
        if (video.crossOrigin !== 'anonymous') {
            video.crossOrigin = 'anonymous';
        }

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

        // Use JPEG for performance. 0.8 is a good quality/size balance.
        return canvas.toDataURL('image/jpeg', 0.8);
    """
    try:
        data_url = driver.execute_script(js_script)
        if data_url is None:
            return None
        
        # Strip the header and decode the base64 string
        header, encoded = data_url.split(",", 1)
        decoded_data = base64.b64decode(encoded)
        
        # Convert to a numpy array for OpenCV
        np_arr = np.frombuffer(decoded_data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame
    except JavascriptException as e:
        # Avoid spamming the console with the same error.
        if "Tainted canvases" not in str(e):
             print(f"JavaScript error while capturing frame: {e}")
        return None
    except Exception as e:
        print(f"Error processing canvas frame: {e}")
        return None
    
def find_next_prev_btns(driver):
    try:
        # div[class*="DivFeedNavigationContainer"]
        wait = WebDriverWait(driver, 10)
        nav_container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='DivFeedNavigationContainer']")))
        buttons = nav_container.find_elements(By.TAG_NAME, "button")
        app_state["prev_btn"] = buttons[0]
        app_state["next_btn"] = buttons[1]
    except TimeoutException:
        print("Could not find navigation buttons.")
        return None


def main():
    driver = setup_selenium()
    
    if driver is None:
        return

    def on_press(key):
        if not app_state["running"]:
            return False 
        try:
            if key == keyboard.Key.right:
                next_video(driver)
            elif key == keyboard.Key.left:
                prev_video(driver)
            elif key == keyboard.Key.up:
                next_effect()
            elif key == keyboard.Key.down:
                prev_effect()
            elif key.char == 'q':
                quit_app()
        except AttributeError:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    app_state["listener"] = listener

    cv2.namedWindow("TikTok Live Feed", cv2.WINDOW_NORMAL)

    while app_state["running"]:
        try:
            # Find navigation buttons if they are missing
            if app_state["next_btn"] is None or app_state["prev_btn"] is None:
                find_next_prev_btns(driver)

            frame = get_frame_via_canvas(driver)

            if frame is not None:
                active_effect_func = app_state["effects"][app_state["effect_index"]]
                processed_frame = active_effect_func(frame)
                
                effect_name = app_state["effect_names"][app_state["effect_index"]]
                cv2.putText(processed_frame, f"Effect: {effect_name}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

                cv2.imshow("TikTok Live Feed", processed_frame)
            else:
                # If no frame, wait a moment before trying again
                time.sleep(0.1)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                quit_app()

        except StaleElementReferenceException:
            print("Page changed. Re-finding navigation buttons...")
            app_state["next_btn"] = None
            app_state["prev_btn"] = None
            time.sleep(0.5)
        except Exception as e:
            print(f"An unexpected error occurred in the main loop: {e}")
            try:
                if not driver.window_handles:
                    print("Browser window was closed.")
                    quit_app()
            except:
                quit_app()

    listener.join()
    driver.quit()
    cv2.destroyAllWindows()
    print("Application closed.")

if __name__ == "__main__":
    main()

