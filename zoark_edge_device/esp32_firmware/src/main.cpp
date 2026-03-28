/**
 * ============================================================
 *  Zero Edge Device — ESP32 Firmware v5
 *  Ultra-Realistic Animated Eyes + IMU + Haptic + Touch
 *
 *  Eye rendering:
 *    - Iris fiber texture (16 radial spokes)
 *    - Concentric iris rings (limbal + inner highlight)
 *    - Upper eyelid shadow strip
 *    - Tear-duct dot at inner corner
 *    - Primary + secondary corneal reflections
 *    - Twinkling corner sparkles (happy)
 *
 *  "Color" via hardware inversion:
 *    - ANGRY  → invertDisplay ON  = white bg, black eyes (fierce/harsh)
 *    - DIZZY  → invertDisplay strobes every 200ms (disorienting)
 *    - All others → normal (white eye on black)
 *
 *  States: OPEN, BLINKING, DIZZY, SPEAK, ANGRY, HAPPY, SAD, BOOT, THINK
 *  New in v5: EYE_THINK, expressive brows, animated status bar
 *
 *  Hardware
 *  ────────
 *  Left  OLED SSD1306 128×64 : I2C0  SDA=19  SCL=18  (0x3C)
 *  Right OLED SSD1306 128×64 : I2C1  SDA=32  SCL=33  (0x3C)
 *  MPU-6050 IMU               : I2C0  (0x68)
 *  Haptic motor               : GPIO 25
 *  Pi Zero UART               : UART2  TX=17  RX=16  115200
 *  Capacitive touch           : GPIO 4 (T0)
 *  Both OLEDs mounted upside-down → hardware 180° rotation applied
 * ============================================================
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <MPU6050_tockn.h>
#include <ArduinoJson.h>
#include <math.h>

// ── Display ───────────────────────────────────────────────────
#define SCREEN_W  128
#define SCREEN_H   64
#define OLED_ADDR 0x3C

// ── Pins ──────────────────────────────────────────────────────
#define I2C0_SDA   19
#define I2C0_SCL   18
#define I2C1_SDA   32
#define I2C1_SCL   33
#define HAPTIC_PIN 25
#define UART2_TX   17
#define UART2_RX   16
#define TOUCH_PIN   4

// ── Thresholds ────────────────────────────────────────────────
#define SHAKE_THRESHOLD    18000L
#define HAPTIC_PULSE_MS      200
#define BLINK_INTERVAL_MS   2400
#define UART_INTERVAL_MS     100
#define TOUCH_THRESHOLD       40
#define TOUCH_DEBOUNCE_MS    400

// ── Eye geometry ──────────────────────────────────────────────
// 48px tall (not 64) → 8px margin top (brow) and bottom (status)
#define EYE_W       110
#define EYE_H        48
#define EYE_X       ((SCREEN_W - EYE_W) / 2)   // =  9
#define EYE_Y       ((SCREEN_H - EYE_H) / 2)   // =  8
#define EYE_RADIUS   14

// Iris layers (inner → outer)
#define PUPIL_R       8    // solid black pupil radius
#define INNER_RING_R  11   // white highlight ring around pupil
#define FIBER_R0      12   // start of iris fiber zone
#define FIBER_R1      18   // end of iris fiber zone
#define LIMBAL_R      20   // outermost iris (dark outer ring)

// ── Brow geometry ─────────────────────────────────────────────
#define BROW_Y   (EYE_Y - 4)           // = 4
#define BROW_X0  (EYE_X + 8)           // = 17
#define BROW_X1  (EYE_X + EYE_W - 8)  // = 111
#define BROW_MID (SCREEN_W / 2)        // = 64

// ── Equalizer bar layout ──────────────────────────────────────
// 7 bars of width 4px, 3px gap → 46px, centred in 128px → x0=41
#define EQ_X0   41
#define EQ_STEP  7
#define EQ_BARS  7

// ── Wander ────────────────────────────────────────────────────
#define WANDER_X  18
#define WANDER_Y  10

// ── Objects ───────────────────────────────────────────────────
Adafruit_SSD1306 leftEye (SCREEN_W, SCREEN_H, &Wire,  -1);
Adafruit_SSD1306 rightEye(SCREEN_W, SCREEN_H, &Wire1, -1);
MPU6050 mpu(Wire);

bool hasLeftOLED  = false;
bool hasRightOLED = false;
bool hasMPU       = false;

// ── Eye states ────────────────────────────────────────────────
enum EyeState {
    EYE_OPEN, EYE_BLINKING, EYE_DIZZY, EYE_SPEAK,
    EYE_ANGRY, EYE_HAPPY, EYE_SAD, EYE_BOOT, EYE_THINK
};

volatile EyeState eyeState = EYE_BOOT;
volatile bool shaking  = false;
volatile bool hapticOn = false;

// ── Timers ────────────────────────────────────────────────────
uint32_t lastBlink   = 0;
uint32_t lastReport  = 0;
uint32_t hapticStart = 0;
uint32_t exprEndMs   = 0;
uint32_t lastTouch   = 0;

// ── Pupil ─────────────────────────────────────────────────────
float pupilX = 0, pupilY = 0;
float pupilTargetX = 0, pupilTargetY = 0;
uint32_t pupilChangeMs = 0;

// ── Display inversion state ───────────────────────────────────
bool displayInverted = false;

// ── Forward declarations ──────────────────────────────────────
void setInvert       (bool inv);
void drawBrow        (Adafruit_SSD1306 &d, EyeState state, bool flipX);
void drawStatusBar   (Adafruit_SSD1306 &d, EyeState state, int frame, bool flipX);
void drawEye         (Adafruit_SSD1306 &d, float blinkFrac, int px, int py,
                      EyeState state, int frame, bool flipX);
void drawBothEyes    (float blinkFrac = 1.0f, EyeState st = EYE_OPEN, int frame = 0);
void bootAnimation   ();
void triggerHaptic   ();
void handleUARTIn    ();
void reportState     ();

// ─────────────────────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial.println("[Zero] Booting v5...");

    Serial2.begin(115200, SERIAL_8N1, UART2_RX, UART2_TX);
    Wire.begin(I2C0_SDA, I2C0_SCL);
    Wire1.begin(I2C1_SDA, I2C1_SCL);

    pinMode(HAPTIC_PIN, OUTPUT);
    digitalWrite(HAPTIC_PIN, LOW);

    auto initOLED = [](Adafruit_SSD1306 &d, const char *label) -> bool {
        if (!d.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
            Serial.printf("[ERROR] %s OLED\n", label);
            return false;
        }
        d.ssd1306_command(SSD1306_SETCONTRAST);
        d.ssd1306_command(255);
        // Screens are mounted upside-down: rotate 180° in hardware
        d.ssd1306_command(SSD1306_SEGREMAP);    // 0xA0 → flip horizontal
        d.ssd1306_command(SSD1306_COMSCANINC);  // 0xC0 → flip vertical
        d.clearDisplay(); d.display();
        Serial.printf("[OK] %s OLED (rotated 180)\n", label);
        return true;
    };
    hasLeftOLED  = initOLED(leftEye,  "Left");
    hasRightOLED = initOLED(rightEye, "Right");

    Wire.beginTransmission(0x68);
    if (Wire.endTransmission() == 0) {
        hasMPU = true;
        mpu.begin();
        Serial.println("[OK] MPU6050");
    } else {
        Serial.println("[WARN] MPU6050 not found");
    }

    bootAnimation();
    eyeState = EYE_OPEN;
    lastBlink = millis();
    Serial.println("[Zero] Running v5!");
}

// ─────────────────────────────────────────────────────────────
//  MAIN LOOP
// ─────────────────────────────────────────────────────────────
void loop() {
    uint32_t now = millis();

    // ── IMU ──────────────────────────────────────────────────
    if (hasMPU) {
        mpu.update();
        long ax = abs((long)mpu.getRawAccX());
        long ay = abs((long)mpu.getRawAccY());
        long az = abs((long)mpu.getRawAccZ() - 16384L);
        bool nowShaking = (ax + ay + az) > SHAKE_THRESHOLD;
        if (nowShaking && !shaking) {
            shaking   = true;
            eyeState  = EYE_DIZZY;
            exprEndMs = 0;
            triggerHaptic();
        } else if (!nowShaking && shaking) {
            shaking = false;
            if (eyeState == EYE_DIZZY) { eyeState = EYE_OPEN; lastBlink = now; }
        }
    }

    // ── Haptic timeout ────────────────────────────────────────
    if (hapticOn && (now - hapticStart >= HAPTIC_PULSE_MS)) {
        digitalWrite(HAPTIC_PIN, LOW);
        hapticOn = false;
    }

    // ── Capacitive touch ─────────────────────────────────────
    if (now - lastTouch >= TOUCH_DEBOUNCE_MS) {
        if (touchRead(TOUCH_PIN) < TOUCH_THRESHOLD) {
            lastTouch = now;
            eyeState  = EYE_HAPPY;
            exprEndMs = now + 3000;
            triggerHaptic();
            Serial2.println("{\"event\":\"petted\"}");
        }
    }

    // ── Expression timeout ────────────────────────────────────
    if (exprEndMs > 0 && now >= exprEndMs) {
        exprEndMs = 0;
        eyeState  = shaking ? EYE_DIZZY : EYE_OPEN;
        lastBlink = now;
    }

    // ── UART ─────────────────────────────────────────────────
    handleUARTIn();

    // ── Pupil targets per state ───────────────────────────────
    if (eyeState == EYE_OPEN && (now - pupilChangeMs > 1500)) {
        pupilChangeMs = now;
        pupilTargetX  = random(-WANDER_X, WANDER_X + 1);
        pupilTargetY  = random(-WANDER_Y, WANDER_Y + 1);
    }
    if (eyeState == EYE_HAPPY)  { pupilTargetY = -8; pupilTargetX *= 0.5f; }
    if (eyeState == EYE_SAD)    { pupilTargetY =  6; }
    if (eyeState == EYE_ANGRY)  { pupilTargetY =  0; }
    if (eyeState == EYE_THINK)  { pupilTargetY = -8; pupilTargetX = 0; }
    if (eyeState == EYE_SPEAK)  { pupilTargetY =  0; }
    pupilX += (pupilTargetX - pupilX) * 0.15f;
    pupilY += (pupilTargetY - pupilY) * 0.15f;

    // ── Render ────────────────────────────────────────────────
    int frame = (now / 100) % 8;   // 0-7, advances every 100ms

    if (eyeState == EYE_OPEN) {
        if (now - lastBlink >= BLINK_INTERVAL_MS) {
            lastBlink = now;
            eyeState  = EYE_BLINKING;
            for (int i = 10; i >= 0; i--) { drawBothEyes(i / 10.0f, EYE_OPEN); delay(16); }
            delay(45);
            for (int i = 0; i <= 10; i++)  { drawBothEyes(i / 10.0f, EYE_OPEN); delay(16); }
            eyeState = EYE_OPEN;
        } else {
            drawBothEyes(1.0f, EYE_OPEN, frame);
        }
    } else if (eyeState != EYE_BLINKING) {
        drawBothEyes(1.0f, eyeState, frame);
    }

    // ── UART report 10Hz ─────────────────────────────────────
    if (now - lastReport >= UART_INTERVAL_MS) {
        lastReport = now;
        reportState();
    }

    delay(12);
}

// ─────────────────────────────────────────────────────────────
//  DISPLAY INVERSION HELPER
//  ANGRY  = white-bg black-eye (harsh/fierce "red-eye" feel)
//  DIZZY  = strobe (alternates every 2 frames = 200ms)
// ─────────────────────────────────────────────────────────────
void setInvert(bool inv) {
    if (inv == displayInverted) return;
    displayInverted = inv;
    if (hasLeftOLED)  leftEye.invertDisplay(inv);
    if (hasRightOLED) rightEye.invertDisplay(inv);
}

// ─────────────────────────────────────────────────────────────
//  EYEBROWS  (y = 0..EYE_Y-2, drawn 2px thick at BROW_Y=4)
// ─────────────────────────────────────────────────────────────
void drawBrow(Adafruit_SSD1306 &d, EyeState state, bool flipX) {
    if (state == EYE_DIZZY || state == EYE_BOOT) return;

    switch (state) {
        case EYE_OPEN:
        case EYE_SPEAK: {
            // Gently flat — very slight outer upturn
            for (int x = BROW_X0; x <= BROW_X1; x++) {
                float t = (float)(x - BROW_MID) / ((BROW_X1 - BROW_X0) * 0.5f);
                int y   = constrain(BROW_Y + (int)(t * t), 0, EYE_Y - 2);
                d.drawPixel(x, y,     SSD1306_WHITE);
                d.drawPixel(x, y + 1, SSD1306_WHITE);
            }
            break;
        }
        case EYE_THINK: {
            // Inner side slightly raised — curious/questioning
            for (int x = BROW_X0; x <= BROW_X1; x++) {
                float t     = (float)(x - BROW_MID) / ((BROW_X1 - BROW_X0) * 0.5f);
                float inner = flipX ? -t : t;
                int y       = constrain(BROW_Y - (int)(2.5f * max(0.0f, inner)), 0, EYE_Y - 2);
                d.drawPixel(x, y,     SSD1306_WHITE);
                d.drawPixel(x, y + 1, SSD1306_WHITE);
            }
            break;
        }
        case EYE_HAPPY: {
            // High graceful arch — peaks at centre
            for (int x = BROW_X0; x <= BROW_X1; x++) {
                float t = (float)(x - BROW_MID) / ((BROW_X1 - BROW_X0) * 0.5f);
                int y   = constrain((BROW_Y - 3) + (int)(4.0f * t * t), 0, EYE_Y - 2);
                d.drawPixel(x, y,     SSD1306_WHITE);
                d.drawPixel(x, y + 1, SSD1306_WHITE);
            }
            break;
        }
        case EYE_ANGRY: {
            // V-scowl: outer HIGH, inner LOW (furrow toward nose)
            int xOuter = flipX ? BROW_X1 : BROW_X0;
            int xInner = flipX ? BROW_X0 : BROW_X1;
            for (int off = 0; off <= 2; off++)
                d.drawLine(xOuter, BROW_Y - 3 + off, xInner, BROW_Y + 2 + off, SSD1306_WHITE);
            break;
        }
        case EYE_SAD: {
            // Droopy: inner HIGH, outer LOW
            int xOuter = flipX ? BROW_X1 : BROW_X0;
            int xInner = flipX ? BROW_X0 : BROW_X1;
            for (int off = 0; off <= 1; off++)
                d.drawLine(xOuter, BROW_Y + 2 + off, xInner, BROW_Y - 3 + off, SSD1306_WHITE);
            break;
        }
        default: break;
    }
}

// ─────────────────────────────────────────────────────────────
//  STATUS BAR  (y = 56..63, bottom 8px)
// ─────────────────────────────────────────────────────────────
void drawStatusBar(Adafruit_SSD1306 &d, EyeState state, int frame, bool flipX) {

    if (state == EYE_DIZZY) {
        // Spinning corner stars (alternate positions each frame)
        bool a   = (frame % 2 == 0);
        int sx1  = a ? 7 : 11,  sx2 = a ? 121 : 117;
        int sy   = SCREEN_H - 4;
        for (int sx : {sx1, sx2}) {
            d.fillCircle(sx, sy, 2, SSD1306_WHITE);
            d.drawPixel(sx - 3, sy, SSD1306_WHITE);
            d.drawPixel(sx + 3, sy, SSD1306_WHITE);
            d.drawPixel(sx, sy - 3, SSD1306_WHITE);
            d.drawPixel(sx, sy + 3, SSD1306_WHITE);
        }
        return;
    }

    switch (state) {
        case EYE_SPEAK: {
            // 7-bar animated equalizer
            for (int b = 0; b < EQ_BARS; b++) {
                float phase = frame * 0.785f + b * 0.898f;
                int h = max(1, (int)(4.0f + 3.5f * sinf(phase)));
                d.fillRect(EQ_X0 + b * EQ_STEP, SCREEN_H - h, 4, h, SSD1306_WHITE);
            }
            break;
        }
        case EYE_OPEN: {
            // Three pulsing heartbeat dots
            int beat = (frame / 2) % 3;
            for (int i = 0; i < 3; i++) {
                int r = (i == beat) ? 3 : 2;
                d.fillCircle(56 + i * 8, SCREEN_H - 1 - r, r, SSD1306_WHITE);
            }
            break;
        }
        case EYE_THINK: {
            // Classic bouncing "..." loading dots
            int active = (frame / 2) % 3;
            for (int i = 0; i < 3; i++) {
                int y = (i == active) ? (SCREEN_H - 6) : (SCREEN_H - 4);
                d.fillCircle(56 + i * 8, y, 2, SSD1306_WHITE);
            }
            break;
        }
        case EYE_HAPPY: {
            // Bouncing heart ♥
            int yBob = (frame % 4 < 2) ? 0 : -1;
            int hx = 64, hy = SCREEN_H - 4 + yBob;
            d.fillCircle(hx - 2, hy - 2, 2, SSD1306_WHITE);
            d.fillCircle(hx + 2, hy - 2, 2, SSD1306_WHITE);
            d.fillTriangle(hx - 4, hy - 1, hx + 4, hy - 1, hx, hy + 3, SSD1306_WHITE);
            break;
        }
        case EYE_ANGRY: {
            // !! marks on inner side
            int sx = flipX ? 76 : 49;
            d.fillRect(sx,     SCREEN_H - 7, 3, 4, SSD1306_WHITE);
            d.fillRect(sx,     SCREEN_H - 2, 3, 2, SSD1306_WHITE);
            d.fillRect(sx + 5, SCREEN_H - 7, 3, 4, SSD1306_WHITE);
            d.fillRect(sx + 5, SCREEN_H - 2, 3, 2, SSD1306_WHITE);
            break;
        }
        case EYE_SAD: {
            // Tear drops falling from outer corner
            int tx = flipX ? (EYE_X + EYE_W - 7) : (EYE_X + 5);
            for (int t = 0; t < 2; t++) {
                int ty = 57 + ((frame * 2 + t * 4) % 8);
                if (ty < SCREEN_H) d.fillCircle(tx, ty, 2, SSD1306_WHITE);
            }
            break;
        }
        default: break;
    }
}

// ─────────────────────────────────────────────────────────────
//  DRAW ONE EYE  (ultra-realistic iris)
// ─────────────────────────────────────────────────────────────
void drawEye(Adafruit_SSD1306 &d, float blinkFrac, int px, int py,
             EyeState state, int frame, bool flipX) {
    d.clearDisplay();

    int cx = SCREEN_W / 2;   // 64
    int cy = SCREEN_H / 2;   // 32

    // ── DIZZY — animated spinning X ──────────────────────────
    if (state == EYE_DIZZY) {
        int s = 20;
        d.drawRoundRect(8, 6, SCREEN_W - 16, SCREEN_H - 14, 10, SSD1306_WHITE);
        float ang = frame * 0.196f;
        int   dx  = (int)(s * cosf(ang)), dy = (int)(s * sinf(ang));
        d.drawLine(cx - dx, cy - dy, cx + dx, cy + dy, SSD1306_WHITE);
        d.drawLine(cx - dy, cy + dx, cx + dy, cy - dx, SSD1306_WHITE);
        d.fillCircle(cx - s, cy - s, 3, SSD1306_WHITE);
        d.fillCircle(cx + s, cy - s, 3, SSD1306_WHITE);
        d.fillCircle(cx - s, cy + s, 3, SSD1306_WHITE);
        d.fillCircle(cx + s, cy + s, 3, SSD1306_WHITE);
        drawBrow(d, state, flipX);
        drawStatusBar(d, state, frame, flipX);
        d.display();
        return;
    }

    // ── Eye shape dimensions per state ───────────────────────
    int eyeW = EYE_W, eyeH = EYE_H;
    if      (state == EYE_ANGRY) eyeH = max(2, (int)(EYE_H * 0.58f * blinkFrac));
    else if (state == EYE_SAD)   eyeH = max(2, (int)(EYE_H * 0.84f * blinkFrac));
    else if (state == EYE_THINK) eyeH = max(2, (int)(EYE_H * 0.88f * blinkFrac));
    else if (state == EYE_SPEAK) {
        float sc = 0.72f + 0.28f * sinf(frame * 0.785f);
        eyeH = max(2, (int)(EYE_H * blinkFrac * sc));
        eyeW = (int)(EYE_W * (0.88f + 0.12f * sc));
    }
    else eyeH = max(2, (int)(EYE_H * blinkFrac));

    int rad = min(EYE_RADIUS, eyeH / 2);
    int ex  = (SCREEN_W - eyeW) / 2;
    int ey  = (SCREEN_H - eyeH) / 2;

    // ── 1. Sclera (white fill) ────────────────────────────────
    d.fillRoundRect(ex, ey, eyeW, eyeH, rad, SSD1306_WHITE);

    // ── 2. Upper eyelid shadow (depth illusion) ───────────────
    // A 3-row dithered shadow just inside the top of the sclera
    for (int row = 0; row < 3; row++) {
        int step = row + 1;   // row 0: every pixel, row 1: every 2px, row 2: every 3px
        int margin = (3 - row) * 3 + 8;
        for (int sx = ex + margin; sx < ex + eyeW - margin; sx += step) {
            d.drawPixel(sx, ey + 1 + row, SSD1306_BLACK);
        }
    }

    // ── 3. Shape cuts per state ───────────────────────────────
    if (state == EYE_ANGRY) {
        // Inner-corner brow cut
        int bix = flipX ? (ex + eyeW - 5) : (ex + 5);
        int box = flipX ? (ex + eyeW / 2 + 10) : (ex + eyeW / 2 - 10);
        for (int off = -1; off <= 1; off++)
            d.drawLine(bix + off, ey - 1, box + off, ey + eyeH / 3, SSD1306_BLACK);
    }
    if (state == EYE_SAD) {
        // Outer top-corner droop
        if (flipX) { for (int i = 0; i < 22; i++) d.drawLine(ex + eyeW - i, ey, ex + eyeW, ey + i, SSD1306_BLACK); }
        else        { for (int i = 0; i < 22; i++) d.drawLine(ex + i, ey, ex, ey + i, SSD1306_BLACK); }
    }
    if (state == EYE_HAPPY) {
        // Bottom inner-corner smile lift
        if (flipX) { for (int i = 0; i < 18; i++) d.drawLine(ex + i, ey + eyeH, ex, ey + eyeH - i, SSD1306_BLACK); }
        else        { for (int i = 0; i < 18; i++) d.drawLine(ex + eyeW - i, ey + eyeH, ex + eyeW, ey + eyeH - i, SSD1306_BLACK); }
        // Outer-corner sparkle (replaces old single sparkle)
        int spX = flipX ? (ex + eyeW - 12) : (ex + 12);
        int spY = ey + 7;
        d.drawPixel(spX,     spY - 4, SSD1306_BLACK);
        d.drawPixel(spX,     spY + 4, SSD1306_BLACK);
        d.drawPixel(spX - 4, spY,     SSD1306_BLACK);
        d.drawPixel(spX + 4, spY,     SSD1306_BLACK);
        d.fillCircle(spX, spY, 2, SSD1306_BLACK);
    }

    // ── 4. Tear duct (anatomical inner-corner detail) ─────────
    {
        int tdX = flipX ? (ex + eyeW - 6) : (ex + 6);
        int tdY = ey + eyeH / 2;
        d.fillCircle(tdX, tdY, 2, SSD1306_BLACK);
        d.drawPixel(tdX + (flipX ? -4 : 4), tdY, SSD1306_WHITE);  // highlight next to it
    }

    // ── 5. Pupil (if eye not closed) ─────────────────────────
    if (blinkFrac > 0.3f) {
        int puX = cx + px;
        int puY = cy + py;

        // Per-state pupil offset
        if (state == EYE_ANGRY)  puX += (flipX ? 6 : -6);
        if (state == EYE_SAD)    puY += 4;
        if (state == EYE_HAPPY)  puY -= 4;

        puX = constrain(puX, ex + LIMBAL_R + 2, ex + eyeW - LIMBAL_R - 2);
        puY = constrain(puY, ey + LIMBAL_R + 2, ey + eyeH - LIMBAL_R - 2);

        // ── Layer A: outer iris (dark) ──────────────────────
        d.fillCircle(puX, puY, LIMBAL_R, SSD1306_BLACK);

        // ── Layer B: iris fiber texture (16 radial spokes) ──
        for (int a = 0; a < 16; a++) {
            float ang  = a * (M_PI / 8.0f);
            float cosA = cosf(ang), sinA = sinf(ang);
            for (int r = FIBER_R0; r <= FIBER_R1; r++) {
                // Alternate pixels for organic fibre look
                if ((r + a) % 2 == 0) {
                    int ix = puX + (int)(r * cosA);
                    int iy = puY + (int)(r * sinA);
                    if (ix > ex + 1 && ix < ex + eyeW - 1 &&
                        iy > ey + 1 && iy < ey + eyeH - 1)
                        d.drawPixel(ix, iy, SSD1306_WHITE);
                }
            }
        }

        // ── Layer C: limbal ring (bright outer iris edge) ───
        d.drawCircle(puX, puY, LIMBAL_R - 1, SSD1306_WHITE);

        // ── Layer D: inner highlight ring around pupil ──────
        d.drawCircle(puX, puY, INNER_RING_R,     SSD1306_WHITE);
        d.drawCircle(puX, puY, INNER_RING_R + 1, SSD1306_WHITE);

        // ── Layer E: pupil (deepest black) ──────────────────
        d.fillCircle(puX, puY, PUPIL_R, SSD1306_BLACK);

        // ── Layer F: primary corneal reflex (upper-left) ────
        d.fillCircle(puX - 5, puY - 6, 3, SSD1306_WHITE);
        d.drawPixel(puX - 8,  puY - 4, SSD1306_WHITE);   // diffuse edge

        // ── Layer G: secondary corneal reflex (lower-right) ─
        d.fillCircle(puX + 5, puY + 4, 1, SSD1306_WHITE);

        // ── Layer H: THINK — tiny star above pupil ──────────
        if (state == EYE_THINK) {
            int stX = puX + (flipX ? -8 : 8);
            int stY = puY - 8;
            if (stX > ex + 2 && stX < ex + eyeW - 2 && stY > ey + 2) {
                d.drawPixel(stX,     stY,     SSD1306_WHITE);
                d.drawPixel(stX - 2, stY,     SSD1306_WHITE);
                d.drawPixel(stX + 2, stY,     SSD1306_WHITE);
                d.drawPixel(stX,     stY - 2, SSD1306_WHITE);
                d.drawPixel(stX,     stY + 2, SSD1306_WHITE);
            }
        }
    }

    // ── 6. HAPPY: twinkling corner stars ─────────────────────
    if (state == EYE_HAPPY) {
        // Stars blink in the outer corners of the screen (outside the eye shape)
        int csX = flipX ? (SCREEN_W - 5) : 4;
        // Upper star
        if ((frame + (flipX ? 1 : 0)) % 4 < 2) {
            d.fillCircle(csX, 10, 1, SSD1306_WHITE);
            d.drawPixel(csX - 3, 10, SSD1306_WHITE);
            d.drawPixel(csX + 3, 10, SSD1306_WHITE);
            d.drawPixel(csX, 7,  SSD1306_WHITE);
            d.drawPixel(csX, 13, SSD1306_WHITE);
        }
        // Lower star (opposite phase)
        if ((frame + (flipX ? 3 : 2)) % 4 < 2) {
            d.fillCircle(csX, SCREEN_H - 11, 1, SSD1306_WHITE);
            d.drawPixel(csX - 3, SCREEN_H - 11, SSD1306_WHITE);
            d.drawPixel(csX + 3, SCREEN_H - 11, SSD1306_WHITE);
            d.drawPixel(csX, SCREEN_H - 14,     SSD1306_WHITE);
            d.drawPixel(csX, SCREEN_H - 8,      SSD1306_WHITE);
        }
    }

    // ── 7. Brow + status bar ─────────────────────────────────
    drawBrow(d, state, flipX);
    drawStatusBar(d, state, frame, flipX);

    d.display();
}

// ─────────────────────────────────────────────────────────────
//  DRAW BOTH EYES  (handles inversion before drawing)
// ─────────────────────────────────────────────────────────────
void drawBothEyes(float blinkFrac, EyeState state, int frame) {
    // Inversion "color" mode:
    //   ANGRY  → always inverted (white bg = harsh fierce look)
    //   DIZZY  → strobe (alternates every 2 frames)
    //   others → normal
    bool inv = false;
    if      (state == EYE_ANGRY)                   inv = true;
    else if (state == EYE_DIZZY && frame % 2 == 0) inv = true;
    setInvert(inv);

    int px = (int)pupilX, py = (int)pupilY;
    if (hasLeftOLED)  drawEye(leftEye,  blinkFrac, px, py, state, frame, false);
    if (hasRightOLED) drawEye(rightEye, blinkFrac, px, py, state, frame, true);
}

// ─────────────────────────────────────────────────────────────
//  BOOT ANIMATION  (scan-line → ZERO text → iris expand)
// ─────────────────────────────────────────────────────────────
void bootAnimation() {
    // Phase 1: blank
    if (hasLeftOLED)  { leftEye.clearDisplay();  leftEye.display(); }
    if (hasRightOLED) { rightEye.clearDisplay(); rightEye.display(); }
    delay(300);

    // Phase 2: scan lines sweep top → bottom
    for (int y = 0; y < SCREEN_H; y++) {
        if (hasLeftOLED)  { leftEye.drawFastHLine(0, y, SCREEN_W, SSD1306_WHITE);  leftEye.display(); }
        if (hasRightOLED) { rightEye.drawFastHLine(0, y, SCREEN_W, SSD1306_WHITE); rightEye.display(); }
        delay(8);
    }
    delay(80);

    // Phase 3: "ZERO" text (setTextSize 2 → 12×16 per char, 4 chars = 48px; centred x=40)
    for (Adafruit_SSD1306 *d : {hasLeftOLED ? &leftEye : (Adafruit_SSD1306*)nullptr,
                                 hasRightOLED ? &rightEye : (Adafruit_SSD1306*)nullptr}) {
        if (!d) continue;
        d->clearDisplay();
        d->setTextColor(SSD1306_WHITE);
        d->setTextSize(2);
        d->setCursor(40, 24);
        d->print("ZERO");
        d->display();
    }
    delay(700);

    // Phase 4: iris expand from centre
    for (Adafruit_SSD1306 *d : {hasLeftOLED ? &leftEye : (Adafruit_SSD1306*)nullptr,
                                 hasRightOLED ? &rightEye : (Adafruit_SSD1306*)nullptr}) {
        if (!d) continue;
        d->clearDisplay(); d->display();
    }
    delay(60);

    for (int r = 2; r <= 34; r += 3) {
        for (Adafruit_SSD1306 *d : {hasLeftOLED ? &leftEye : (Adafruit_SSD1306*)nullptr,
                                     hasRightOLED ? &rightEye : (Adafruit_SSD1306*)nullptr}) {
            if (!d) continue;
            d->clearDisplay();
            d->fillCircle(SCREEN_W/2, SCREEN_H/2, r, SSD1306_WHITE);
            int pr = max(2, r - 8);
            d->fillCircle(SCREEN_W/2, SCREEN_H/2, pr, SSD1306_BLACK);
            d->display();
        }
        delay(32);
    }
    delay(80);

    // Phase 5: full eyes + double blink + haptic
    for (int i = 0; i <= 10; i++) { drawBothEyes(i / 10.0f, EYE_OPEN); delay(28); }
    delay(280);
    for (int i = 10; i >= 0; i--) { drawBothEyes(i / 10.0f, EYE_OPEN); delay(14); }
    delay(55);
    for (int i = 0; i <= 10; i++)  { drawBothEyes(i / 10.0f, EYE_OPEN); delay(14); }
    delay(160);
    triggerHaptic();
}

// ─────────────────────────────────────────────────────────────
//  HAPTIC
// ─────────────────────────────────────────────────────────────
void triggerHaptic() {
    digitalWrite(HAPTIC_PIN, HIGH);
    hapticOn    = true;
    hapticStart = millis();
}

// ─────────────────────────────────────────────────────────────
//  UART IN
// ─────────────────────────────────────────────────────────────
void handleUARTIn() {
    static String buf;
    while (Serial2.available()) {
        char c = (char)Serial2.read();
        if (c == '\n') {
            buf.trim();
            if (buf.length() > 0) {
                JsonDocument doc;
                if (!deserializeJson(doc, buf)) {
                    const char* cmd = doc["command"];
                    if (cmd) {
                        String s(cmd);
                        uint32_t now = millis();
                        if      (s == "speak_anim") { eyeState = EYE_SPEAK;  exprEndMs = now + 6000; }
                        else if (s == "think")      { eyeState = EYE_THINK;  exprEndMs = now + 30000; }
                        else if (s == "angry")      { eyeState = EYE_ANGRY;  exprEndMs = now + 4000; triggerHaptic(); }
                        else if (s == "happy")      { eyeState = EYE_HAPPY;  exprEndMs = now + 4000; }
                        else if (s == "sad")        { eyeState = EYE_SAD;    exprEndMs = now + 4000; }
                        else if (s == "blink")      { lastBlink = 0; }
                        else if (s == "open")       { eyeState = EYE_OPEN;   exprEndMs = 0; }
                        Serial.printf("[CMD] %s\n", cmd);
                    }
                }
            }
            buf = "";
        } else {
            buf += c;
            if (buf.length() > 200) buf = "";
        }
    }
}

// ─────────────────────────────────────────────────────────────
//  UART OUT  (10 Hz state report to Pi)
// ─────────────────────────────────────────────────────────────
void reportState() {
    float gz = hasMPU ? mpu.getAccZ() : 1.0f;
    JsonDocument doc;
    doc["motion"]      = shaking ? "shaking" : "stable";
    doc["orientation"] = (gz > 0) ? "up" : "down";
    String out;
    serializeJson(doc, out);
    Serial2.println(out);
}
