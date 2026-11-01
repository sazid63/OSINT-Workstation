"""Physical QA driver for OSINT Toolkit GUI."""
import sys
import time
import pyautogui
import pywinauto
from pywinauto import Application
from pywinauto.keyboard import send_keys
import os
from PIL import ImageGrab

# Disable pyautogui safety pause
pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True  # Move mouse to corner to abort

SHOT_DIR = os.path.join(os.path.dirname(__file__), "shots")
os.makedirs(SHOT_DIR, exist_ok=True)

def shot(name):
    """Take screenshot."""
    time.sleep(1)
    img = ImageGrab.grab()
    path = os.path.join(SHOT_DIR, f"{name}.png")
    img.save(path)
    print(f"[SHOT] {path}")
    return path

def find_window(title_pattern="OSINT Toolkit"):
    """Find the main app window."""
    apps = Application(backend="uia").connect(title_re=f".*{title_pattern}.*")
    return apps.top_window()

def move_to_button(button_name, wait=2):
    """Move mouse to a button by name."""
    time.sleep(wait)
    try:
        # Try pywinauto to find and move to button
        win = find_window()
        btn = win.child_window(title=button_name, control_type="Button")
        rect = btn.rectangle()
        x = rect.left + rect.width // 2
        y = rect.top + rect.height // 2
        pyautogui.moveTo(x, y)
        return True
    except Exception as e:
        print(f"  [WARN] Could not find button '{button_name}': {e}")
        return False

def click_button(button_name):
    """Click a button by name."""
    if move_to_button(button_name, wait=1):
        pyautogui.click()
        shot(f"after_click_{button_name.replace(' ', '_')}")
        return True
    return False

def type_text(text, delay=0.05):
    """Type text with typing animation."""
    pyautogui.write(text, interval=delay)

def navigate_to(page_name):
    """Navigate to a page via left sidebar."""
    nav_map = {
        "Dashboard": ["Dashboard"],
        "Tools": ["Tools"],
        "Run": ["Run"],
        "Results": ["Results"],
        "Assistant": ["Assistant"],
        "Settings": ["Settings"],
    }
    targets = nav_map.get(page_name, [page_name])
    for t in targets:
        if move_to_button(t, wait=0.5):
            pyautogui.click()
            time.sleep(0.5)
            break

def main():
    print("=" * 60)
    print("OSINT Toolkit Physical QA Driver")
    print("=" * 60)
    
    # Wait for window to appear
    print("\n[1] Connecting to app window...")
    try:
        win = find_window()
        print("  ✓ Window found")
        shot("01_window_found")
    except Exception as e:
        print(f"  ✗ Window not found: {e}")
        print("  Starting app...")
        os.system('cd osint-toolkit && python osint_toolkit/app.py')
        time.sleep(5)
        win = find_window()
        shot("01_after_launch")
    
    # Check for terms dialog
    print("\n[2] Checking for terms dialog...")
    try:
        # Look for accept/reject buttons
        for btn_name in ["Accept", "I Accept", "Agree"]:
            if move_to_button(btn_name, wait=1):
                print(f"  ✓ Found '{btn_name}' button - clicking...")
                click_button(btn_name)
                time.sleep(2)
                break
        shot("02_terms_accepted")
    except Exception as e:
        print(f"  Note: No terms dialog found: {e}")
    
    # Navigate through pages
    pages = ["Dashboard", "Tools", "Run", "Results", "Assistant", "Settings"]
    for page in pages:
        print(f"\n[3] Navigating to {page}...")
        navigate_to(page)
        shot(f"03_{page.lower()}")
    
    print("\n" + "=" * 60)
    print("QA Navigation Complete")
    print("=" * 60)
    print(f"\nScreenshots saved to: {SHOT_DIR}")

if __name__ == "__main__":
    main()
