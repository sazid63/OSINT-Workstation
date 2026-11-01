"""Screenshot helper for physical QA of the OSINT Toolkit GUI."""
import sys, time, os
from PIL import ImageGrab

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "shot"
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    time.sleep(delay)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.png")
    img = ImageGrab.grab()
    img.save(path)
    print(path)

if __name__ == "__main__":
    main()
