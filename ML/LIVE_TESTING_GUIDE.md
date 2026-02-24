# 🎯 Live Testing Guide - Hybrid Detection System

## ✅ System Status: HYBRID MODE ACTIVE

Your system is now running **BOTH**:
- ✅ **Rule-based CV** (pose estimation + geometric rules)
- ✅ **Custom Trained ML Model** (10 malpractice classes)
- ✅ **Voting Mode: ANY** (catches if either system detects)

---

## 📊 Detectable Actions

### 🔴 Actions Detected by BOTH Systems:

| Action | Rule-Based CV | Custom ML Model | Hybrid Result |
|--------|---------------|-----------------|---------------|
| **1. Leaning** | ✅ Pose angles | ✅ Class: normal/cheating | Best of both |
| **2. Passing Paper** | ✅ Wrist proximity | ✅ Class: passing | Best of both |
| **3. Turning Back** | ✅ Pose orientation | ✅ Class: turning_back | Best of both |
| **4. Hand Raised** | ✅ Arm elevation | ✅ Class: hand_raise | Best of both |

### 🟡 Additional ML Model Detections:

| ML Class | Description | CV Support |
|----------|-------------|------------|
| **phone** | Phone/mobile device | ✅ YOLO mobile detector |
| **cheat_material** | Cheat notes/sheets | ❌ ML only |
| **peeking** | Looking at others | ❌ ML only |
| **talking** | Verbal communication | ❌ ML only |
| **suspicious** | General suspicious behavior | ❌ ML only |

---

## 🧪 LIVE TESTING INSTRUCTIONS

### Prerequisites:
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python front.py
```

**Look for startup confirmation:**
```
🚀 LIGHTWEIGHT HYBRID DETECTOR
📦 Loading custom model: runs/train/malpractice_detector/weights/best.pt
✅ Custom model optimized (FP32) on cuda:0  ← GPU confirmed!
```

---

## 📋 Test Each Action:

### ✅ TEST 1: LEANING
**How to perform:**
- Sit upright normally (baseline)
- Slowly lean your body to the left or right (>30° angle)
- Continue leaning for 2-3 seconds

**What to expect:**
- Red dots appear on upper body keypoints
- Top left: **"Leaning!"** in red
- If ML agrees: **"Leaning! [ML✓]"**
- Console shows: `ML: ✓1 ✗0`

**Indicators:**
- `[ML✓]` = Both CV and ML detected leaning
- No indicator = CV only (ML classified as "normal")
- `[ML]` = ML detected but CV missed

---

### ✅ TEST 2: PASSING PAPER
**How to perform:**
- Position 2 people within camera view
- Extend arms toward each other (wrists <50px apart)
- Hold position for 2-3 seconds

**What to expect:**
- Blue dots on wrists of both people
- Top left: **"Passing Paper!"** in blue
- If ML agrees: **"Passing Paper! [ML✓]"**
- Higher chance of [ML✓] if actual paper visible

**Indicators:**
- `[ML✓]` = Both systems detected passing motion
- Best detection when hands/paper clearly visible

---

### ✅ TEST 3: TURNING BACK
**How to perform:**
- Face the camera normally
- Turn your body/head to look behind you (>90°)
- Maintain position for 2-3 seconds

**What to expect:**
- Top left: **"Turning Back!"** in magenta
- If ML agrees: **"Turning Back! [ML✓]"**
- Console: `ML: ✓X ✗Y`

**Indicators:**
- `[ML✓]` = Both detected back-turning
- ML model trained on "turning_back" class

---

### ✅ TEST 4: HAND RAISED
**How to perform:**
- Raise one or both arms above shoulder level
- Keep hand elevated for 2-3 seconds
- Wave slightly (optional)

**What to expect:**
- Top left: **"Hand Raised!"** in cyan
- If ML agrees: **"Hand Raised! [ML✓]"**
- Detection continues while arm elevated

**Indicators:**
- `[ML✓]` = Both systems detected raised hand
- CV uses wrist Y-position > shoulder

---

### ✅ TEST 5: PHONE/MOBILE (ML-Enhanced)
**How to perform:**
- Hold phone visible to camera
- Simulate phone use (looking down at it)
- Keep in frame for 2-3 seconds

**What to expect:**
- YOLO detects object (class 67: cell phone)
- ML model detects "phone" class
- Higher confidence with both detections
- Console: `ML: ✓X`

**Note:** This uses existing YOLO + custom model for verification

---

### 🆕 TEST 6: CHEAT MATERIAL (ML Only)
**How to perform:**
- Hold paper/notes visibly
- Look down at paper as if reading
- Move paper around slightly

**What to expect:**
- ML model detects "cheat_material" class
- May show as generic detection
- Console shows ML activity: `ML: ✓X`

**Note:** No CV rule for this - pure ML detection

---

### 🆕 TEST 7: PEEKING (ML Only)
**How to perform:**
- Turn head to side and lean
- Look toward another person's workspace
- Maintain suspicious gaze

**What to expect:**
- ML model detects "peeking" class
- Combined with leaning may trigger multiple alerts
- Console: `ML: ✓X`

---

## 📊 Understanding the Display:

### On-Screen Indicators (Top Right):
```
FPS: 24.5              ← Processing speed
Device: GPU            ← GPU acceleration active
GPU: 3.2GB            ← Memory usage
ML: 12✓ 3✗            ← ML verified/rejected
FP: -20%              ← False positive reduction
```

### Console Output (Every 30 frames):
```
FPS: 24.5 | ML: ✓12 ✗3 | FP Reduction: 20%
```

### Detection Text Meanings:
- **"Action!"** = CV detected only
- **"Action! [ML✓]"** = Both CV and ML detected (high confidence)
- **"Action! [ML]"** = ML detected, CV missed (rare)

---

## 🎯 Expected Performance:

### FPS Targets:
- ✅ **23-26 FPS** with GPU (stable)
- ⚠️ If drops to 14-18: GPU may not be active
- ❌ If <10 FPS: Check GPU memory

### ML Verification Rates:
- **High agreement (70-90%)**: Leaning, Turning Back
- **Medium agreement (50-70%)**: Passing Paper, Hand Raise
- **Variable**: Phone (depends on visibility)

### False Positive Reduction:
- **Target: 40-80%** false positives eliminated
- ML rejects ambiguous CV detections
- Example: Stretching misclassified as leaning → ML rejects

---

## 🔧 Troubleshooting:

### Issue: No [ML✓] indicators
**Check startup:** Did you see "Custom model optimized (FP32) on cuda:0"?
- ❌ If "Custom model not found" → Model path issue
- ❌ If "loaded on CPU" → GPU optimization failed

**Fix:** Restart front.py, check for GPU messages

### Issue: FPS unstable (14→25→14)
**Cause:** GPU memory fragmentation or CPU fallback
**Fix:** Close other GPU applications, restart front.py

### Issue: ML: ✓0 ✗0 (always zero)
**Cause:** No CV detections to verify (ML only verifies CV detections)
**Fix:** Perform test actions to trigger CV detections

---

## 📈 Testing Checklist:

- [ ] Front.py started with GPU confirmation
- [ ] Tested: Leaning (saw red dots + text)
- [ ] Tested: Passing Paper (2 people, blue dots)
- [ ] Tested: Turning Back (magenta text)
- [ ] Tested: Hand Raised (cyan text)
- [ ] Tested: Phone detection (mobile visible)
- [ ] Saw [ML✓] indicator at least once
- [ ] Console shows ML stats: ✓X ✗Y
- [ ] FPS stable 23-26
- [ ] False positive reduction >0%

---

## 💡 Pro Tips:

1. **Good lighting** = better ML detection
2. **Full body visible** = better pose estimation
3. **Clear actions** = higher confidence scores
4. **Multiple people** = test passing paper effectively
5. **Record session** = Videos saved for review

---

## 🎥 Video Outputs:

When detections occur >60 frames:
- `output_leaning.mp4` - Leaning incidents
- `output_turningback.mp4` - Turning back incidents
- `output_passing.mp4` - Passing paper incidents
- `output_handraise.mp4` - Hand raise incidents

Check these videos after testing to see what was recorded!

---

## 📞 Quick Reference:

**Quit:** Press `q` while camera window is focused
**Pause:** Not available (continuous monitoring)
**Stats:** Printed at end of session (Total detections, ML stats)

**Model Classes:**
1. phone, 2. cheat_material, 3. peeking, 4. turning_back, 
5. hand_raise, 6. passing, 7. talking, 8. cheating, 
9. suspicious, 10. normal

Good luck with your testing! 🚀
