# Zero Body — V2/V3 Vision & Reference

This document captures the full enhancement vision for Zero's physical body beyond v1.
Use this when planning the v2 and v3 board revisions.

---

## Why This Exists

V1 board establishes the base: ESP32 reflexes + Pi Zero 2W executive + eyes + voice + IMU.
V2/V3 transforms Zero into a full embodied AI assistant with screen, depth sensing, and interactive projection.

---

## Compute Upgrade (V2)

Pi Zero 2W cannot handle real-time camera, OpenCV, or projection mapping.

| Capability | Pi Zero 2W | Pi 5 (4GB) |
|---|---|---|
| Real-time camera feed to screen | Barely | Yes |
| OpenCV face/gesture tracking | No | Yes |
| Interactive projection mapping | No | Yes |
| Local LLM inference (small models) | No | Possible |
| Multiple USB peripherals | 1 (OTG only) | 4 |
| Power draw | ~0.5W idle | ~3-5W idle |

**Target:** Pi 5 (4GB) or Pi 4 (4GB). Same 40-pin GPIO header — PCB connector unchanged.

---

## Full Sensor Stack (V2)

```
Vision:      Pi Camera Module 3 (12MP, autofocus, HDR) — CSI connector on v1 board
Depth:       VL53L5CX 8×8 ToF array (60Hz, I2C) — LCSC: C2649541
Hearing:     ReSpeaker 4-mic array (far-field, 360°, beamforming) — replaces INMP441
Motion:      Upgrade MPU-6050 → ICM-42688-P (higher precision, lower noise)
Touch:       AT42QT1070 capacitive touch strip on head/face
Environment: SHT40 (temp/humidity) + SGP41 (VOC/NOx) + BH1750 (ambient light)
```

---

## Display Layer (V2)

```
Face eyes:   2× SSD1306 OLED (already on v1)
Status TFT:  2.8" IPS TFT 320×240, SPI interface to Pi
             Shows: camera feed, agent state, conversation transcript
             Driver: ILI9341
Projector:   Pico DLP module (see V3 section)
Mood ring:   WS2812B LED ring around face (already on v1 as single LED)
```

---

## Actuation Layer (V2)

```
Voice:    MAX98357A already present — upgrade speaker to 5W full-range driver
Haptic:   Already on v1
Head pan: Servo on J8 header (already on v1)
Head tilt: Second servo on J8 header (already on v1)
```

---

## Interactive Projection System (V3)

### Concept

```
1. Pico projector throws image onto any flat surface
2. IR LED array illuminates the surface (850nm, invisible to humans)
3. Pi Camera detects IR finger reflection as bright blob
4. OpenCV computes homography: camera pixel → projected pixel coordinate
5. Finger position becomes touch event in software
6. Pi renders updated UI frame → sends to projector via HDMI
```
Target latency: 50–80ms end-to-end. Achievable on Pi 5.

### Projector Module Options

| Module | Resolution | Interface | Cost | Notes |
|---|---|---|---|---|
| AAXA P2-A Pico | 854×480 | HDMI | ~$150 | Best choice — self-contained, plug-and-play |
| Nebula Capsule II | 1280×720 | HDMI | ~$300 | Android built-in, overkill |
| TI DLP2000EVM | 640×360 | SPI/I2C | ~$99 | Most hackable, no lens included |

**Recommended:** AAXA P2-A — HDMI to Pi, USB-C power, compact enough to mount on robot body.

### Depth / Touch Detection Hardware

```
Primary:  VL53L5CX (STMicro) — 8×8 ToF zone ranging at 60Hz
          I2C to Pi GPIO | Range: 2cm–400cm | Size: 6.4×3.4mm
          Detects hand presence + approximate XY position

Fine tracking: OV2640 camera module (IR-sensitive)
               + 5× 850nm IR LEDs around projector lens
               IRLZ44N MOSFET (Pi GPIO-controlled) driving LED array
```

### Schematic Additions for V3

```
Pi GPIO  → VL53L5CX via I2C (J_DEPTH: VCC_3V3, GND, SDA, SCL)
Pi GPIO  → IRLZ44N gate → 5× 850nm IR LED array (J_IR_LED: 2-pin)
Pi CSI   → Pi Camera Module 3 (finger tracking in IR)
Pi HDMI  → Pico projector (J_PROJ: HDMI passthrough + VCC_5V power)
```

### Software Stack (Pi, Python/OpenCV)

```python
# Simplified projection interaction loop
depth_map   = vl53l5cx.read()           # 8×8 depth grid at 60Hz
finger_pos  = camera.detect_bright()    # IR blob in camera frame
surface     = fit_plane(depth_map)      # locate the projection surface
touch_point = project_to_surface(finger_pos, surface)  # homography
ui.handle_touch(touch_point)            # trigger interaction
frame       = ui.render()               # draw updated UI
projector.send_frame(frame)             # HDMI output to projector
```

Runs at 30fps on Pi 5 with OpenCV + NumPy.

---

## New PCB Connectors Needed (V2/V3 Board)

| Connector | Pins | Purpose |
|---|---|---|
| J_DEPTH | 4 (VCC, GND, SDA, SCL) | VL53L5CX ToF depth sensor |
| J_IR_LED | 2 (VCC_5V, GATE) | IR LED array for projection touch |
| J_SCREEN | 8 (MOSI, MISO, CLK, CS, DC, RST, BL, GND) | 2.8" IPS TFT SPI |
| J_MIC_ARRAY | 6 | ReSpeaker 4-mic array (replaces J_MIC) |
| J_PROJ | 4 (HDMI passthrough + VCC_5V + GND) | Pico projector power |
| J_CAM | 15-pin FFC | Pi Camera Module 3 (already on v1) |
| J_ENV | 4 (I2C) | SHT40 + SGP41 + BH1750 environmental sensors |

---

## Power Budget (V2/V3)

```
V1 (ESP32 + Pi Zero 2W):         ~1.0A @ 5V =  5W
V2 (ESP32 + Pi 5 + TFT):         ~2.5A @ 5V = 12.5W
V3 full load (+ projector, servos, LEDs): ~4.0A @ 5V = 20W
```

### Power System Upgrades Required for V2/V3

- Replace LM2596 module header with integrated TPS54360 (3.5A, 60V input, high-efficiency)
- Add FUSB302 USB-C PD negotiation chip — pulls 20V/3A from PD charger → step-down to 5V
- Or: Dedicated DC barrel jack (12V/3A) as primary power input for desktop use
- LiPo battery path: Replace J_BAT with proper BMS circuit (TP5100 charger + DW01A protection)

---

## LCSC Part Numbers for V2/V3 Components

| Component | Part | LCSC |
|---|---|---|
| VL53L5CX ToF sensor | STMicro VL53L5CX | C2649541 |
| ICM-42688-P IMU | TDK ICM-42688-P | C2757096 |
| SHT40 temp/humidity | Sensirion SHT40-AD1B | C2961609 |
| FUSB302 USB-C PD | ON Semi FUSB302BMPX | C275647 |
| ILI9341 TFT controller | (on module) | — |
| IRLZ44N IR LED driver | Vishay IRLZ44N | C49039 |
| 850nm IR LED | Everlight IR333C | C108474 |

---

*Reference Version: 1.0 | Created: 2026-03-28 | Use when planning V2/V3 board*
