"""
STEP-BY-STEP: Integrate Hybrid Detection into front.py
Follow these steps to combine rule-based + ML detection in your system
"""

# =============================================================================
# STEP 1: Update imports at the top of front.py
# =============================================================================

# REPLACE THIS:
"""
try:
    from hybrid_detector import HybridDetector
    HYBRID_DETECTION_AVAILABLE = True
except ImportError:
    print("⚠️ Hybrid detector not found, using CV-only mode")
    HYBRID_DETECTION_AVAILABLE = False
"""

# WITH THIS:
"""
try:
    from front_integration import FrontPyHybridIntegration
    HYBRID_DETECTION_AVAILABLE = True
    print("✅ Enhanced hybrid detection available!")
except ImportError:
    print("⚠️ Hybrid detector not found, using CV-only mode")
    HYBRID_DETECTION_AVAILABLE = False
    FrontPyHybridIntegration = None
"""


# =============================================================================
# STEP 2: Initialize hybrid detector (after loading YOLO models)
# =============================================================================

# FIND THIS SECTION (around line 150-200):
"""
# Load YOLO models
pose_model = YOLO(POSE_MODEL_PATH)
mobile_model = YOLO(MOBILE_MODEL_PATH)
"""

# ADD AFTER IT:
"""
# Initialize hybrid detector
hybrid_detector = None
if HYBRID_DETECTION_AVAILABLE and FrontPyHybridIntegration:
    try:
        hybrid_detector = FrontPyHybridIntegration(
            custom_model_path="runs/train/malpractice_detector/weights/best.pt",
            voting_mode='any',  # Options: 'any', 'majority', 'all'
            enable_visual_feedback=True
        )
        print("✅ Hybrid detection initialized!")
    except Exception as e:
        print(f"⚠️ Could not initialize hybrid detector: {e}")
        hybrid_detector = None
"""


# =============================================================================
# STEP 3: Update passing paper detection logic
# =============================================================================

# FIND THIS CODE (around line 590-700):
"""
passing_detected, close_pairs = detect_passing_paper(wrist_positions, all_keypoints)

if passing_detected:
    cv2.putText(frame, PASSING_ACTION + "!", (850, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 1, blue_color, 3)
"""

# REPLACE WITH:
"""
# Get CV detection result
passing_detected_cv, close_pairs = detect_passing_paper(wrist_positions, all_keypoints)

# Enhance with hybrid detection
passing_detected = passing_detected_cv
passing_confidence = 0.7  # Default CV confidence

if hybrid_detector is not None:
    # Get hybrid result
    passing_detected, passing_confidence, method = hybrid_detector.check_detection(
        frame=frame,
        detection_type='passing',
        cv_detected=passing_detected_cv,
        bbox=None
    )
    
    # Show detection with confidence
    if passing_detected:
        frame = hybrid_detector.draw_detection_text(frame, 'passing', passing_confidence)
        
        # Log method for debugging
        if method == 'both_agree':
            print(f"🔥 PASSING PAPER: Both CV and ML agree! (conf: {passing_confidence:.2f})")
        elif method == 'cv_only':
            print(f"⚠️  PASSING PAPER: CV detected (ML missed)")
        elif method == 'ml_only':
            print(f"🤖 PASSING PAPER: ML detected (CV missed)")
else:
    # Fallback to CV-only
    if passing_detected_cv:
        cv2.putText(frame, PASSING_ACTION + "!", (850, 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, blue_color, 3)

passing_this_frame = passing_detected
"""


# =============================================================================
# STEP 4: Update other detections (optional but recommended)
# =============================================================================

# For MOBILE detection, FIND:
"""
mobile_detected = False
# ... mobile detection code ...
if mobile_detected:
    cv2.putText(frame, MOBILE_ACTION + "!", ...)
"""

# ENHANCE WITH:
"""
mobile_detected_cv = False
# ... your existing mobile detection code ...

# Hybrid enhancement
if hybrid_detector is not None:
    mobile_detected, mobile_conf, method = hybrid_detector.check_detection(
        frame=frame,
        detection_type='mobile',
        cv_detected=mobile_detected_cv,
        bbox=None
    )
    if mobile_detected:
        frame = hybrid_detector.draw_detection_text(frame, 'mobile', mobile_conf)
else:
    mobile_detected = mobile_detected_cv
    if mobile_detected:
        cv2.putText(frame, MOBILE_ACTION + "!", ...)
"""

# Repeat similar pattern for:
# - leaning_detected
# - turning_detected
# - hand_raise_detected


# =============================================================================
# STEP 5: Update database logging (add confidence score)
# =============================================================================

# FIND THIS (around line 735):
"""
sql = '''
    INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
    VALUES (%s, %s, %s, %s, %s, %s)
'''
val = (date_db, time_db, PASSING_ACTION, proof_filename, hall_id, False)
"""

# OPTIONAL: Add confidence to logs (requires DB schema change)
"""
# If you add a 'confidence' column to your database:
sql = '''
    INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified, confidence)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
'''
val = (date_db, time_db, PASSING_ACTION, proof_filename, hall_id, False, passing_confidence)

# OR: Include confidence in malpractice text
malpractice_text = f"{PASSING_ACTION} (conf: {int(passing_confidence*100)}%)"
val = (date_db, time_db, malpractice_text, proof_filename, hall_id, False)
"""


# =============================================================================
# STEP 6: Print statistics at the end
# =============================================================================

# FIND the cleanup section at the end of your main loop:
"""
cap.release()
if recording:
    out.release()
cv2.destroyAllWindows()
"""

# ADD BEFORE IT:
"""
# Print hybrid detection statistics
if hybrid_detector is not None:
    print("\n" + "="*80)
    print("📊 SESSION STATISTICS")
    print("="*80)
    hybrid_detector.print_stats()
"""


# =============================================================================
# STEP 7: Test the integration
# =============================================================================

"""
1. Save your modified front.py
2. Run it: python front.py
3. Test with your passing paper video
4. Check console output for detection methods:
   - "🔥 Both CV and ML agree!" = High confidence
   - "⚠️ CV detected (ML missed)" = Medium confidence
   - "🤖 ML detected (CV missed)" = Caught by ML!
   
5. Check the visual feedback:
   - You should see "PASSING PAPER!" in blue on the right side
   - Confidence percentage below it (if < 95%)
   
6. Check database logs:
   - Entries should be created in app_malpraticedetection table
   - Proof videos should be saved
"""


# =============================================================================
# VOTING MODE TUNING
# =============================================================================

"""
After testing, tune the voting mode:

# Most sensitive (catch everything)
voting_mode='any'
→ Detects if EITHER CV OR ML sees it
→ Use for: Testing, high-stakes exams
→ May have more false positives

# Balanced (recommended for production)
voting_mode='majority'
→ Requires at least one clear detection
→ Use for: Regular exams
→ Good balance of accuracy and sensitivity

# Most strict (minimize false positives)
voting_mode='all'
→ Both CV AND ML must agree
→ Use for: When false accusations are very costly
→ May miss some subtle cases
"""


# =============================================================================
# TROUBLESHOOTING
# =============================================================================

"""
Problem: "Model not found"
Solution: Check path to best.pt:
   - Should be: runs/train/malpractice_detector/weights/best.pt
   - Or use absolute path: E:\\witcher\\AIINVIGILATOR\\AIINVIGILATOR\\ML\\runs\\train\\...

Problem: "Passing not detected"
Solution: 
   - Lower confidence threshold to 0.2 or 0.15
   - Use voting_mode='any' to catch CV-only detections
   - Check if CV rules are working: print(passing_detected_cv)

Problem: "Too many false positives"
Solution:
   - Switch to voting_mode='all'
   - Increase confidence threshold to 0.3 or 0.4
   - Tune CV rules (adjust distance thresholds)

Problem: "Slow performance"
Solution:
   - Model runs on GPU by default (fast)
   - Check GPU usage: nvidia-smi
   - Consider processing every 2nd frame for speed
"""

print(__doc__)
