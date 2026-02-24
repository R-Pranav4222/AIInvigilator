"""
Quick Test Helper for Hybrid Detection System
Shows which detections are working and provides testing guidance
"""

import cv2
import numpy as np
from colorama import init, Fore, Style
init(autoreset=True)

def print_header():
    print("\n" + "="*70)
    print(Fore.CYAN + Style.BRIGHT + "🎯 HYBRID DETECTION SYSTEM - TEST HELPER")
    print("="*70 + "\n")

def print_system_status():
    print(Fore.GREEN + "✅ ACTIVE SYSTEMS:")
    print("   1. Rule-Based CV (Pose Estimation + Geometric Rules)")
    print("   2. Custom ML Model (10 Malpractice Classes)")
    print("   3. Hybrid Voting (ANY mode - catches if either detects)")
    print()

def print_detectable_actions():
    print(Fore.YELLOW + "📋 DETECTABLE ACTIONS:\n")
    
    actions = [
        ("1. LEANING", "Both", "Lean body >30° left/right", "Red"),
        ("2. PASSING PAPER", "Both", "Two people, wrists <50px apart", "Blue"),
        ("3. TURNING BACK", "Both", "Turn body/head >90° backward", "Magenta"),
        ("4. HAND RAISED", "Both", "Raise arm above shoulder", "Cyan"),
        ("5. PHONE/MOBILE", "Both", "Hold visible phone device", "Auto"),
        ("6. CHEAT MATERIAL", "ML Only", "Hold paper/notes", "N/A"),
        ("7. PEEKING", "ML Only", "Look at others' work", "N/A"),
    ]
    
    for action, system, how_to, color in actions:
        print(f"{Fore.WHITE}{action:18} | {Fore.GREEN}{system:8} | {how_to:35} | {Fore.BLUE}Color: {color}")
    print()

def print_indicators():
    print(Fore.CYAN + "🎯 DETECTION INDICATORS:\n")
    print(f"{Fore.WHITE}Display Text         Meaning")
    print(f"{Fore.WHITE}{'─'*50}")
    print(f"{Fore.RED}\"Leaning!\"           {Fore.WHITE}CV detected only")
    print(f"{Fore.RED}\"Leaning! [ML✓]\"     {Fore.GREEN}Both CV + ML detected (high confidence)")
    print(f"{Fore.RED}\"Leaning! [ML]\"      {Fore.YELLOW}ML only detected (rare)")
    print()

def print_console_stats():
    print(Fore.CYAN + "📊 CONSOLE STATS FORMAT:\n")
    print(f"{Fore.WHITE}FPS: 24.5 | ML: ✓12 ✗3 | FP Reduction: 20%")
    print()
    print(f"{Fore.WHITE}   FPS: 24.5          {Fore.GREEN}→ Processing speed (target: 23-26)")
    print(f"{Fore.WHITE}   ML: ✓12           {Fore.GREEN}→ ML verified 12 CV detections")
    print(f"{Fore.WHITE}   ML: ✗3            {Fore.YELLOW}→ ML rejected 3 false positives")
    print(f"{Fore.WHITE}   FP Reduction: 20% {Fore.GREEN}→ 20% fewer false alarms")
    print()

def print_testing_steps():
    print(Fore.MAGENTA + Style.BRIGHT + "\n🧪 TESTING PROCEDURE:\n")
    
    steps = [
        ("STEP 1", "Start front.py", "cd e:\\witcher\\AIINVIGILATOR\\AIINVIGILATOR\\ML", "python front.py"),
        ("STEP 2", "Verify GPU Loading", "Look for: \"Custom model optimized (FP32) on cuda:0\"", ""),
        ("STEP 3", "Test Each Action", "Perform actions from list above", "See on-screen text"),
        ("STEP 4", "Check ML Indicators", "Look for [ML✓] in detection text", ""),
        ("STEP 5", "Monitor Stats", "Console shows: ML: ✓X ✗Y every 30 frames", ""),
        ("STEP 6", "Verify FPS", "Should be stable 23-26 FPS", ""),
        ("STEP 7", "Review Videos", "Check output_*.mp4 files after", ""),
    ]
    
    for step, desc, detail, extra in steps:
        print(f"{Fore.CYAN}{step:7} → {Fore.WHITE}{desc:20} {Fore.YELLOW}{detail}")
        if extra:
            print(f"{'':10} {Fore.GREEN}{extra}")
    print()

def print_test_action(action_num, action_name, how_to, expected):
    """Print detailed test instructions for one action"""
    print("\n" + "─"*70)
    print(f"{Fore.CYAN}TEST #{action_num}: {Fore.YELLOW + Style.BRIGHT}{action_name}")
    print("─"*70)
    print(f"{Fore.WHITE}How to perform:")
    for step in how_to:
        print(f"  {Fore.GREEN}→ {step}")
    print(f"\n{Fore.WHITE}What to expect:")
    for expect in expected:
        print(f"  {Fore.BLUE}✓ {expect}")
    print()

def interactive_test_menu():
    """Interactive menu to guide through testing each action"""
    print_header()
    print_system_status()
    
    while True:
        print(Fore.CYAN + "\n" + "="*70)
        print(Fore.WHITE + "Choose action to test (or 'q' to quit):\n")
        print("  1. Leaning")
        print("  2. Passing Paper")
        print("  3. Turning Back")
        print("  4. Hand Raised")
        print("  5. Phone/Mobile")
        print("  6. Cheat Material (ML Only)")
        print("  7. Peeking (ML Only)")
        print("  8. Show all detectable actions")
        print("  9. Show indicators & stats guide")
        print("  0. Show testing procedure")
        print("  q. Quit")
        
        choice = input(f"\n{Fore.YELLOW}Enter choice: {Fore.WHITE}").strip().lower()
        
        if choice == 'q':
            print(f"\n{Fore.GREEN}Happy testing! 🚀")
            break
        elif choice == '1':
            print_test_action(
                1, "LEANING",
                ["Sit upright normally (baseline)", 
                 "Slowly lean your body left or right (>30° angle)",
                 "Hold lean position for 2-3 seconds"],
                ["Red dots appear on upper body keypoints",
                 "Top left shows: \"Leaning!\" in red text",
                 "If ML agrees: \"Leaning! [ML✓]\"",
                 "Console: ML: ✓1 ✗0"]
            )
        elif choice == '2':
            print_test_action(
                2, "PASSING PAPER",
                ["Position 2 people within camera view",
                 "Extend arms toward each other",
                 "Get wrists close together (<50px apart)",
                 "Hold position for 2-3 seconds"],
                ["Blue dots on wrists of both people",
                 "Top left: \"Passing Paper!\" in blue",
                 "If ML agrees: \"Passing Paper! [ML✓]\"",
                 "Higher chance with visible paper/object"]
            )
        elif choice == '3':
            print_test_action(
                3, "TURNING BACK",
                ["Face the camera normally",
                 "Turn your body/head to look behind (>90°)",
                 "Maintain turned position for 2-3 seconds"],
                ["Top left: \"Turning Back!\" in magenta",
                 "If ML agrees: \"Turning Back! [ML✓]\"",
                 "Console shows ML stats updating"]
            )
        elif choice == '4':
            print_test_action(
                4, "HAND RAISED",
                ["Raise one or both arms above shoulder level",
                 "Keep hand elevated for 2-3 seconds",
                 "Optional: Wave slightly"],
                ["Top left: \"Hand Raised!\" in cyan",
                 "If ML agrees: \"Hand Raised! [ML✓]\"",
                 "Detection continues while arm elevated"]
            )
        elif choice == '5':
            print_test_action(
                5, "PHONE/MOBILE",
                ["Hold phone visible to camera",
                 "Simulate phone use (looking down at it)",
                 "Keep in frame for 2-3 seconds"],
                ["YOLO detects phone object (class 67)",
                 "ML model detects 'phone' class",
                 "Higher confidence with both systems",
                 "Console: ML stats update"]
            )
        elif choice == '6':
            print_test_action(
                6, "CHEAT MATERIAL (ML Only)",
                ["Hold paper/notes visibly",
                 "Look down at paper as if reading",
                 "Move paper around slightly"],
                ["ML model detects 'cheat_material' class",
                 "No CV rule - pure ML detection",
                 "May show as generic detection",
                 "Console shows ML activity: ML: ✓X"]
            )
        elif choice == '7':
            print_test_action(
                7, "PEEKING (ML Only)",
                ["Turn head to side and lean",
                 "Look toward another person's workspace",
                 "Maintain suspicious gaze for 2-3 seconds"],
                ["ML model detects 'peeking' class",
                 "May combine with leaning detection",
                 "Pure ML - no CV rule",
                 "Console: ML: ✓X"]
            )
        elif choice == '8':
            print_detectable_actions()
        elif choice == '9':
            print_indicators()
            print_console_stats()
        elif choice == '0':
            print_testing_steps()
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.")
        
        input(f"\n{Fore.YELLOW}Press Enter to continue...")

def main():
    """Main entry point"""
    try:
        interactive_test_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.GREEN}Testing guide closed. Good luck! 🚀\n")

if __name__ == "__main__":
    main()
