# Needle Insertion Mechanism — Precision Motion Visualization Progress Report

**Project**: Robotic Needle Insertion Mechanism Teleoperation & Kinematic Visualization  
**Workspace**: `C:\Users\PRIYANSHU\OneDrive\Desktop\dp\proj-DP`  
**Status**: **COMPLETED & OPERATIONAL (TRUE RCM ALIGNED)**  
**Timestamp**: 2026-11-18  

---

## 1. Executive Summary & Research Kinematics

The visualization has been engineered to reflect the **Target-Constrained Remote Center of Motion (RCM) Architecture** of the physical mechanism:

- **Interactive Interface**: [`visualization.html`](file:///C:/Users/PRIYANSHU/OneDrive/Desktop/dp/proj-DP/visualization.html)
- **Kinematic Focus**: The needle trajectory strictly pivots around a **focal target point at depth $d$ under the ultrasound probe face**, matching the curvature of the arc guide.

---

## 2. Research Kinematic Architecture: Target-Constrained RCM

```
[ ULTRASOUND PROBE ]
       │  (Probe Face at Y = 492)
       ▼
   Acoustic Beam
       │
       ▼  Depth d = 50.0 mm
[ TARGET FOCAL POINT (240, 542) ] ◄── Needle Trajectory ALWAYS Passes Through Here!
       ▲                                 ▲
       │                                 │
 [ CIRCULAR ARC GUIDE ] ──(Carriage)─── [ LINEAR RACK & PINION ]
 (Center of Curvature at Target)       (Slides Toward & Through Target)
```

### 2.1 The Curved Arc Guide (Axis 2 — Angular Pitch)
- The curved boom and track form a **circular arc whose center of curvature is situated directly at the target location under the ultrasound transducer face at depth $d$**.
- As the tool carriage moves along this curved arc guide (controlled by Axis 2, $\pm 25^\circ$):
  - The mechanism tilts/pitches across a range of entry angles.
  - **The needle trajectory line ALWAYS points directly at the target point at depth $d$!**
  - This guarantees that no matter which insertion angle is chosen, the needle is guaranteed to intersect the ultrasound imaging field at the desired target depth.

### 2.2 The Linear Insertion Rack (Axis 1 — Insertion Depth)
- Mounted atop the tilting tool carriage is the straight rack and pinion assembly.
- The linear rack advances the needle cannula **straight along the targeted ray directly into and through the focal depth $d$**:
  - At $0.00\text{ mm}$ (reference pose), the needle tip is retracted before entering the tissue.
  - As positive mm are applied ($+0.00$ to $+50.00\text{ mm}$), the needle advances forward-downward directly into the target point at depth $d$.
  - Negative mm retract the needle away from the target point.

### 2.3 Adjustable Target Depth $d$
- The interface provides a live **Target Depth $d$** configuration slider ($20\text{ mm}$ to $80\text{ mm}$).
- Changing depth $d$ moves the RCM target focus marker along the central ultrasound beam axis, and the entire kinematic ray adapts accordingly.

---

## 3. Workstation UI Highlights

- **Left Telemetry Panel**:
  - **Linear Insertion Depth (Axis 1)**: Digital readout (`+0.00 mm`), bipolar travel meter, step buttons, direct input.
  - **Arc Guide Pitch (Axis 2)**: Digital readout (`+0.0°`), angle arc dial, bipolar angle meter, step buttons, direct input.
  - **Target Depth $d$ Slider**: Allows adjusting depth $d$ under the probe face ($20.0$ to $80.0\text{ mm}$).
  - **Status Matrix**: Live telemetry with target lock indicator (`Target Locked 🎯`).
  - **Sparkline Graph**: 10 Hz Canvas plotting linear advancement and pitch angle over time.
- **Right Simulation Panel**:
  - Visual ultrasound transducer and acoustic imaging beam fan.
  - Target focal crosshair at depth $d$ with pulsing indicator.
  - Concentric circular arc guide with inner toothed track.
  - Tilting tool carriage with pinion gear and linear rack.
  - Surgical needle with glowing trajectory line continuously aligned to depth $d$.
  - Keyboard teleoperation: <kbd>W</kbd>/<kbd>S</kbd> (Linear), <kbd>A</kbd>/<kbd>D</kbd> (Pitch along arc), <kbd>R</kbd> (Reset All), <kbd>Space</kbd> (Halt).

---

## 4. Verification Checklist

| # | Check | Status | Verification Detail |
|---|---|---|---|
| 1 | Needle always aims at bottom of probe at depth $d$ | ✅ PASS | Center of rotation anchored at $(240, 492 + d)$ |
| 2 | Arc guide curvature matches circle around target | ✅ PASS | Concentric arc centered at target depth point |
| 3 | Linear guide advances along target trajectory | ✅ PASS | Translates along the ray passing through depth $d$ |
| 4 | Reload starts at $(0.00\text{ mm}, 0.0^\circ)$ | ✅ PASS | Clean reference state initialization |
| 5 | Reset All restores reference view | ✅ PASS | Smooth cubic ease-out animation to $(0,0)$ |
| 6 | Target depth $d$ is adjustable | ✅ PASS | Dynamic slider updates target position in real-time |
| 7 | Full offline compatibility | ✅ PASS | Self-contained single-file HTML/CSS/SVG/JS |
