import os
import time
import pygetwindow as gw

def test_active_window():
    os.system("start spotify:playlist:3TKkZAP3k6FVMfnFqUMvpL")
    time.sleep(1.5)
    active = gw.getActiveWindow()
    print(f"Active window is: {active.title if active else 'None'}")

if __name__ == "__main__":
    test_active_window()
