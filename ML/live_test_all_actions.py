"""
Live Action Testing Guide
Test all 9 detectable actions systematically
"""

from colorama import init, Fore, Style
init(autoreset=True)

def print_header():
    print("\n" + "="*80)
    print(Fore.CYAN + Style.BRIGHT + "🧪 LIVE ACTION TESTING - COMPLETE GUIDE")
    print("="*80)

def print_action_colors():
    print(f"\n{Fore.YELLOW + Style.BRIGHT}📊 DETECTION COLORS & METRICS:\n")
    
    print(f"{Fore.WHITE}{'='*80}")
    print(f"{Fore.WHITE}{'Action':<25} {'Color':<15} {'Detection Method':<20} {'Position'}")
    print(f"{Fore.WHITE}{'='*80}")
    
    # Hybrid detections
    print(f"{Fore.RED}1. Leaning               Red           CV + ML Hybrid       (850, 100)")
    print(f"{Fore.MAGENTA}2. Turning Back          Magenta       CV + ML Hybrid       (850, 130)")
    print(f"{Fore.CYAN}3. Hand Raised           Cyan          CV + ML Hybrid       (850, 160)")
    print(f"{Fore.BLUE}4. Passing Paper         Blue          CV + ML Hybrid       (850, 190)")
    print(f"{Fore.WHITE}5. Phone/Mobile          Auto-detect   CV + ML Hybrid       Special")
    
    print(f"{Fore.WHITE}{'─'*80}")
    
    # ML-only detections  
    print(f"{Fore.YELLOW}ML-ONLY DETECTIONS:")
    print(f"\033[38;2;0;140;255m6. Cheat Material        Orange        ML Only [ML]        (850, 220)\033[0m")
    print(f"{Fore.MAGENTA}7. Peeking               Purple        ML Only [ML]        (850, 250)")
    print(f"{Fore.GREEN}8. Talking               Green         ML Only [ML]        (850, 280)")
    print(f"{Fore.YELLOW}9. Suspicious Behavior   Yellow        ML Only [ML]        (850, 310)")
    print(f"{Fore.WHITE}{'='*80}\n")

def print_test_instructions():
    print(f"\n{Fore.CYAN + Style.BRIGHT}🎯 LIVE TESTING INSTRUCTIONS:\n")
    
    print(f"{Fore.WHITE}BEFORE STARTING:")
    print(f"{Fore.GREEN}1. Ensure good lighting (ML detection quality depends on it)")
    print(f"{Fore.GREEN}2. Position yourself fully visible to camera")
    print(f"{Fore.GREEN}3. Have test props ready: paper, phone, etc.")
    print(f"{Fore.GREEN}4. Start the program: {Fore.CYAN}python front.py\n")
    
    print(f"{Fore.WHITE}VERIFY SYSTEM STARTUP:")
    print(f"{Fore.YELLOW}Look for these messages:")
    print(f"{Fore.GREEN}  ✓ \"Custom model optimized (FP32) on cuda:0\"")
    print(f"{Fore.GREEN}  ✓ \"Hybrid Detector initialized!\"")
    print(f"{Fore.GREEN}  ✓ \"ML Verification: ENABLED\"\n")

def print_test_checklist():
    print(f"\n{Fore.MAGENTA + Style.BRIGHT}📋 TESTING CHECKLIST:\n")
    
    tests = [
        ("1. LEANING", [
            "Sit upright (baseline - should show no detection)",
            "Lean left >30° - hold 3 seconds",
            "Return to upright",
            "Lean right >30° - hold 3 seconds",
        ], "Red text \"Leaning!\" or \"Leaning! [ML✓]\"", "Red dots on upper body keypoints"),
        
        ("2. TURNING BACK", [
            "Face camera normally",
            "Turn head/body >90° to look behind",
            "Hold position for 3 seconds",
        ], "Magenta text \"Turning Back!\" or \"Turning Back! [ML✓]\"", "Console: ML stats update"),
        
        ("3. HAND RAISED", [
            "Keep arms at sides (baseline)",
            "Raise one arm above shoulder",
            "Hold for 3 seconds",
            "Lower arm and raise the other",
        ], "Cyan text \"Hand Raised!\"", "Detection continuous while arm up"),
        
        ("4. PASSING PAPER", [
            "Need 2 people for this test",
            "Both extend arms toward each other",
            "Get wrists close (<50px apart)",
            "Hold position for 3 seconds",
        ], "Blue text \"Passing Paper!\" or \"Passing Paper! [ML✓]\"", "Blue dots on both wrists"),
        
        ("5. PHONE/MOBILE", [
            "Hold phone visible to camera",
            "Look down at phone (simulating use)",
            "Keep in frame for 3 seconds",
            "Move phone around slightly",
        ], "Mobile detection alert", "YOLO + ML verification"),
        
        ("6. CHEAT MATERIAL [ML]", [
            "Hold paper/notes in hand",
            "Position clearly visible to camera",
            "Look down at paper as if reading",
            "Hold for 3 seconds minimum",
        ], "Orange text \"Cheat Material [ML]\" at (850, 220)", "Recorded to output_cheat_material.mp4"),
        
        ("7. PEEKING [ML]", [
            "Turn head to side (45-90°)",
            "Lean slightly toward neighbor's area",
            "Hold suspicious gaze for 3 seconds",
            "Move eyes as if reading others' work",
        ], "Purple text \"Peeking [ML]\" at (850, 250)", "Recorded to output_peeking.mp4"),
        
        ("8. TALKING [ML]", [
            "Open mouth as if speaking",
            "Make talking gestures (if alone)",
            "OR actually talk to another person",
            "Continue for 3 seconds",
        ], "Green text \"Talking [ML]\" at (850, 280)", "Recorded to output_talking.mp4"),
        
        ("9. SUSPICIOUS BEHAVIOR [ML]", [
            "Make unusual movements",
           "Look around nervously (exaggerated)",
            "Fidget with items suspiciously",
            "Combine subtle actions that appear odd",
        ], "Yellow text \"Suspicious Behavior [ML]\" at (850, 310)", "Recorded to output_suspicious.mp4"),
    ]
    
    for action, steps, expected_screen, expected_result in tests:
        print(f"\n{Fore.BLUE}{'─'*80}")
        print(f"{Fore.CYAN + Style.BRIGHT}{action}")
        print(f"{Fore.BLUE}{'─'*80}")
        print(f"{Fore.WHITE}Steps:")
        for i, step in enumerate(steps, 1):
            print(f"  {Fore.GREEN}{i}. {step}")
        print(f"\n{Fore.WHITE}Expected on screen:")
        print(f"  {Fore.YELLOW}→ {expected_screen}")
        print(f"\n{Fore.WHITE}Additional indicators:")
        print(f"  {Fore.YELLOW}→ {expected_result}")

def print_ml_indicators():
    print(f"\n\n{Fore.MAGENTA + Style.BRIGHT}🎯 UNDERSTANDING ML INDICATORS:\n")
    
    print(f"{Fore.WHITE}Text Suffix Meanings:")
    print(f"{Fore.GREEN}  \"Action!\"           {Fore.WHITE}→ CV detected only")
    print(f"{Fore.GREEN}  \"Action! [ML✓]\"     {Fore.WHITE}→ Both CV + ML agreed (HIGH confidence)")
    print(f"{Fore.GREEN}  \"Action! [ML]\"      {Fore.WHITE}→ ML only detected (pure ML classes)")
    print()
    
    print(f"{Fore.WHITE}Console Stats (every 30 frames):")
    print(f"{Fore.YELLOW}  FPS: 24.5 | ML: ✓12 ✗3 | FP Reduction: 20%")
    print()
    print(f"{Fore.WHITE}  FPS: 24.5           → Processing speed (target: 23-26)")
    print(f"{Fore.WHITE}  ML: ✓12            → ML verified 12 CV detections")
    print(f"{Fore.WHITE}  ML: ✗3             → ML rejected 3 false positives")
    print(f"{Fore.WHITE}  FP Reduction: 20%  → 20% fewer false alarms")

def print_video_outputs():
    print(f"\n\n{Fore.CYAN + Style.BRIGHT}🎥 VIDEO OUTPUTS:\n")
    
    print(f"{Fore.WHITE}After testing, check these files:")
    videos = [
        "output_leaning.mp4",
        "output_turningback.mp4",
        "output_handraise.mp4",
        "output_passing.mp4",
        "output_mobile.mp4",
        "output_cheat_material.mp4",
        "output_peeking.mp4",
        "output_talking.mp4",
        "output_suspicious.mp4",
    ]
    
    for video in videos:
        print(f"{Fore.GREEN}  ✓ {video}")
    
    print(f"\n{Fore.YELLOW}Note: Videos only created if action detected for >60 frames (2 seconds)")

def print_database_logging():
    print(f"\n\n{Fore.MAGENTA + Style.BRIGHT}💾 DATABASE LOGGING:\n")
    
    print(f"{Fore.WHITE}All detections logged to database:")
    print(f"{Fore.GREEN}  • Table: app_malpraticedetection")
    print(f"{Fore.GREEN}  • Fields: date, time, malpractice, proof (video), lecture_hall_id, verified")
    print()
    
    print(f"{Fore.WHITE}Action names in database:")
    actions = [
        "Leaning",
        "Turning Back",
        "Hand Raised",
        "Passing Paper",
        "Mobile Phone Detected",
        "Cheat Material",
        "Peeking",
        "Talking",
        "Suspicious Behavior",
    ]
    
    for action in actions:
        print(f"{Fore.CYAN}  → {action}")

def print_troubleshooting():
    print(f"\n\n{Fore.RED + Style.BRIGHT}🔧 TROUBLESHOOTING:\n")
    
    issues = [
        ("ML-only actions not detected", [
            "Check startup: \"Custom model optimized (FP32) on cuda:0\"",
            "Ensure good lighting - ML depends on visibility",
            "Make actions clear and exaggerated",
            "Hold position for full 3 seconds minimum",
        ]),
        
        ("No [ML✓] indicators", [
            "Hybrid detector may not be loaded",
            "Check console for \"Hybrid Detector initialized!\"",
            "ML threshold may be too high (default: 0.25)",
            "Try more obvious actions",
        ]),
        
        ("FPS drops below 20", [
            "Check GPU: nvidia-smi should show ~3GB usage",
            "Close other GPU applications",
            "Reduce camera resolution if needed",
            "Verify CUDA is active (not CPU fallback)",
        ]),
        
        ("Videos not saved", [
            "Check DISABLE_VIDEO_WRITE setting (should be False)",
            "Verify action detected for >60 frames",
            "Check disk space",
            "Check write permissions in directory",
        ]),
        
        ("Database errors", [
            "Verify MySQL connection",
            "Check LECTURE_HALL_NAME and BUILDING settings",
            "Ensure lecture hall exists in database",
            "Check database credentials",
        ]),
    ]
    
    for issue, solutions in issues:
        print(f"{Fore.YELLOW}Issue: {issue}")
        for sol in solutions:
            print(f"{Fore.WHITE}  → {sol}")
        print()

def main():
    print_header()
    print_action_colors()
    print_test_instructions()
    print_test_checklist()
    print_ml_indicators()
    print_video_outputs()
    print_database_logging()
    print_troubleshooting()
    
    print(f"\n{Fore.GREEN + Style.BRIGHT}{'='*80}")
    print(f"{Fore.GREEN + Style.BRIGHT}Ready to test! Run: {Fore.CYAN}python front.py")
    print(f"{Fore.GREEN + Style.BRIGHT}{'='*80}\n")

if __name__ == "__main__":
    main()
