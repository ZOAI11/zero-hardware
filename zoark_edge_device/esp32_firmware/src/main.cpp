/**
 * ============================================================
 *  Zero Edge Device — ESP32 Firmware v6
 *  Ultra-Realistic Eyes + Animated Eyelids + Scrolling Text
 *
 *  New in v6 vs v5:
 *    - Curved upper eyelid (per-column scanline, emotion-shaped)
 *    - Lower eyelid / waterline (2-3px dark band at eye bottom)
 *    - Eyelash ticks along lash lines
 *    - Pupil dilation per emotion (animated radius)
 *    - Scrolling text ticker in status bar (text sent from Pi)
 *    - Eyebrows 3px thick with hair-texture dither
 *    - Micro-saccade jitter when idle (hyper-realistic)
 *    - Flash-label on emotion change (2-char glyph centred)
 *    - UART now reads "text" field: {"command":"speak_anim","text":"Hi!"}
 *
 *  Layout per 128×64 OLED:
 *    y 0- 3   brow zone
 *    y 4- 7   gap (brow drawn at y=4)
 *    y 8-55   eye opening (EYE_H = 48px)
 *    y56-63   status bar (8px) — scrolling text OR emotion animation
 *
 *  Hardware (unchanged from v5)
 *  ────────────────────────────
 *  Left  OLED SSD1306 128×64 : I2C0  SDA=19 SCL=18  (0x3C)
 *  Right OLED SSD1306 128×64 : I2C1  SDA=32 SCL=33  (0x3C)
 *  MPU-6050                  : I2C0  (0x68)
 *  Haptic motor              : GPIO 25
 *  Pi Zero UART              : UART2  TX=17  RX=16  115200
 *  Capacitive touch          : GPIO 4 (T0)
 *  Both OLEDs mounted upside-down → 180° hardware rotation
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
#define BLINK_INTERVAL_MS   2600
#define UART_INTERVAL_MS     100
#define TOUCH_THRESHOLD       40
#define TOUCH_DEBOUNCE_MS    400

// ── Eye geometry ──────────────────────────────────────────────
#define EYE_W       110
#define EYE_H        48
#define EYE_X       ((SCREEN_W - EYE_W) / 2)   // =  9
#define EYE_Y       ((SCREEN_H - EYE_H) / 2)   // =  8
#define EYE_RADIUS   14

// Iris layers
#define PUPIL_R_BASE  8    // base pupil radius (dilates/constricts per emotion)
#define INNER_RING_R 11
#define FIBER_R0     12
#define FIBER_R1     18
#define LIMBAL_R     20

// ── Brow geometry ─────────────────────────────────────────────
#define BROW_Y   (EYE_Y - 4)           // = 4
#define BROW_X0  (EYE_X + 10)          // = 19
#define BROW_X1  (EYE_X + EYE_W - 10) // = 109
#define BROW_MID (SCREEN_W / 2)        // = 64

// ── Equalizer bar layout ──────────────────────────────────────
#define EQ_X0   41
#define EQ_STEP  7
#define EQ_BARS  7

// ── Wander (idle pupil roam) ──────────────────────────────────
#define WANDER_X  18
#define WANDER_Y  10

// ── Scrolling text ────────────────────────────────────────────
#define SCROLL_TEXT_MAX  80
#define SCROLL_PX_PER_FRAME  1    // px per render tick
#define STATUS_Y  56              // top of status bar

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
volatile bool     shaking  = false;
volatile bool     hapticOn = false;

// ── Timers ────────────────────────────────────────────────────
uint32_t lastBlink    = 0;
uint32_t lastReport   = 0;
uint32_t hapticStart  = 0;
uint32_t exprEndMs    = 0;
uint32_t lastTouch    = 0;
uint32_t lastScrollMs = 0;

// ── Pupil position (smooth wander) ───────────────────────────
float pupilX = 0, pupilY = 0;
float pupilTargetX = 0, pupilTargetY = 0;
uint32_t pupilChangeMs = 0;

// ── Pupil radius (animated dilation) ─────────────────────────
float pupilR       = PUPIL_R_BASE;
float pupilRTarget = PUPIL_R_BASE;

// ── Micro-saccade jitter (idle realism) ──────────────────────
float jitterX = 0, jitterY = 0;
uint32_t lastJitterMs = 0;

// ── Display inversion ─────────────────────────────────────────
bool displayInverted = false;

// ── Scrolling text state ──────────────────────────────────────
char  scrollText[SCROLL_TEXT_MAX + 1] = "";
int   scrollPx       = 0;
int   scrollLoops    = 0;       // count full scrolls; clear text after 2
int   scrollTextPxW  = 0;       // precomputed pixel width of text

// ── Emotion label flash ───────────────────────────────────────
char  emotionLabel[8]  = "";    // e.g. "HAPPY"  shown briefly
uint32_t labelEndMs    = 0;

// ── Forward declarations ──────────────────────────────────────
void setInvert         (bool inv);
void drawBrow          (Adafruit_SSD1306 &d, EyeState state, bool flipX);
void drawUpperEyelid   (Adafruit_SSD1306 &d, int ex, int ey, int eyeW, int eyeH,
                        EyeState state, bool flipX);
void drawLowerEyelid   (Adafruit_SSD1306 &d, int ex, int ey, int eyeW, int eyeH);
void drawStatusBar     (Adafruit_SSD1306 &d, EyeState state, int frame, bool flipX);
void drawScrollingText (Adafruit_SSD1306 &d, int scrollOff, const char *text);
void drawEye           (Adafruit_SSD1306 &d, float blinkFrac, int px, int py,
                        EyeState state, int frame, bool flipX);
void drawBothEyes      (float blinkFrac = 1.0f, EyeState st = EYE_OPEN, int frame = 0);
void bootAnimation     ();
void triggerHaptic     ();
void handleUARTIn      ();
void reportState       ();
void setScrollText     (const char *text);
void setEmotionLabel   (const char *label);

// ─────────────────────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial.println("[Zero] Booting v6...");

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
        // Screens mounted upside-down → rotate 180° in hardware
        d.ssd1306_command(SSD1306_SEGREMAP);
        d.ssd1306_command(SSD1306_COMSCANINC);
        d.clearDisplay(); d.display();
        Serial.printf("[OK] %s OLED\n", label);
        return true;
    };
    hasLeftOLED  = initOLED(leftEye,  "Left");
    hasRightOLED = initOLED(rightEye, "Right");

    Wire.beginTransmission(0x68);
    if (Wire.endTransmission() == 0) {
        hasMPU = true;
        mpu.begin();
        Serial.println("[OK] MPU6050");
    }

    bootAnimation();
    eyeState  = EYE_OPEN;
    lastBlink = millis();
    Serial.println("[Zero] Running v6!");
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
            setEmotionLabel("^^");
            Serial2.println("{\"event\":\"petted\"}");
        }
    }

    // ── Expression timeout ────────────────────────────────────
    if (exprEndMs > 0 && now >= exprEndMs) {
        exprEndMs = 0;
        eyeState  = shaking ? EYE_DIZZY : EYE_OPEN;
        lastBlink = now;
    }

    // ── Emotion label timeout ─────────────────────────────────
    if (labelEndMs > 0 && now >= labelEndMs) {
        labelEndMs = 0;
        emotionLabel[0] = '\0';
    }

    // ── UART ─────────────────────────────────────────────────
    handleUARTIn();

    // ── Pupil targets per state ───────────────────────────────
    if (eyeState == EYE_OPEN && (now - pupilChangeMs > 1600)) {
        pupilChangeMs = now;
        pupilTargetX  = random(-WANDER_X, WANDER_X + 1);
        pupilTargetY  = random(-WANDER_Y, WANDER_Y + 1);
    }

    // Per-state overrides
    switch (eyeState) {
        case EYE_HAPPY:  pupilTargetY = -6; pupilRTarget = PUPIL_R_BASE + 2; break;
        case EYE_SAD:    pupilTargetY =  5; pupilRTarget = PUPIL_R_BASE;     break;
        case EYE_ANGRY:  pupilTargetY =  0; pupilRTarget = PUPIL_R_BASE - 2; break;
        case EYE_THINK:  pupilTargetY = -7; pupilTargetX = 6; pupilRTarget = PUPIL_R_BASE - 1; break;
        case EYE_SPEAK:  pupilTargetY =  0; pupilRTarget = PUPIL_R_BASE + 1; break;
        default:         pupilRTarget = PUPIL_R_BASE; break;
    }

    // Smooth interpolation
    pupilX  += (pupilTargetX - pupilX) * 0.13f;
    pupilY  += (pupilTargetY - pupilY) * 0.13f;
    pupilR  += (pupilRTarget  - pupilR) * 0.08f;

    // ── Micro-saccade jitter (idle only) ─────────────────────
    if (eyeState == EYE_OPEN && (now - lastJitterMs > 250)) {
        lastJitterMs = now;
        jitterX = (random(0, 3) - 1) * 0.5f;   // ±0.5px
        jitterY = (random(0, 3) - 1) * 0.5f;
    }

    // ── Scroll text tick ─────────────────────────────────────
    if (scrollText[0] && (now - lastScrollMs >= 40)) {
        lastScrollMs = now;
        scrollPx++;
        int cycle = scrollTextPxW + SCREEN_W;
        if (cycle > 0 && scrollPx >= cycle) {
            scrollPx = 0;
            scrollLoops++;
            if (scrollLoops >= 2) {           // clear after 2 full passes
                scrollText[0]  = '\0';
                scrollPx       = 0;
                scrollLoops    = 0;
                scrollTextPxW  = 0;
            }
        }
    }

    // ── Render ────────────────────────────────────────────────
    int frame = (now / 100) % 8;

    if (eyeState == EYE_OPEN) {
        if (now - lastBlink >= BLINK_INTERVAL_MS) {
            lastBlink = now;
            eyeState  = EYE_BLINKING;
            for (int i = 10; i >= 0; i--) { drawBothEyes(i / 10.0f, EYE_OPEN); delay(14); }
            delay(40);
            for (int i = 0; i <= 10; i++)  { drawBothEyes(i / 10.0f, EYE_OPEN); delay(14); }
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

    delay(10);
}

// ─────────────────────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────────────────────
void setInvert(bool inv) {
    if (inv == displayInverted) return;
    displayInverted = inv;
    if (hasLeftOLED)  leftEye.invertDisplay(inv);
    if (hasRightOLED) rightEye.invertDisplay(inv);
}

void setScrollText(const char *text) {
    strncpy(scrollText, text, SCROLL_TEXT_MAX);
    scrollText[SCROLL_TEXT_MAX] = '\0';
    scrollPx      = 0;
    scrollLoops   = 0;
    scrollTextPxW = strlen(scrollText) * 6;  // size-1 font: 6px/char
}

void setEmotionLabel(const char *label) {
    strncpy(emotionLabel, label, 7);
    emotionLabel[7] = '\0';
    labelEndMs = millis() + 1200;
}

// ─────────────────────────────────────────────────────────────
//  EYEBROWS  — 3px thick, textured, emotion-shaped
// ─────────────────────────────────────────────────────────────
void drawBrow(Adafruit_SSD1306 &d, EyeState state, bool flipX) {
    if (state == EYE_DIZZY || state == EYE_BOOT) return;

    // Draw three rows for each x to make thick brows
    // Middle row = solid, top/bottom rows = dithered (hair texture)
    auto browPixel = [&](int x, int y, int row) {
        // row 0 = main, 1 = outer edge (dithered), -1 = inner edge (dithered)
        if (row == 0) {
            d.drawPixel(x, y, SSD1306_WHITE);
        } else {
            // Dither every other pixel for hair-like texture
            if ((x + abs(row)) % 2 == 0) d.drawPixel(x, y, SSD1306_WHITE);
        }
    };

    switch (state) {
        case EYE_OPEN:
        case EYE_SPEAK: {
            // Gentle arch, slightly higher in centre
            for (int x = BROW_X0; x <= BROW_X1; x++) {
                float t = (float)(x - BROW_MID) / ((BROW_X1 - BROW_X0) * 0.5f);
                int   y = constrain(BROW_Y + (int)(2.5f * t * t), 0, EYE_Y - 2);
                browPixel(x, y - 1, -1);
                browPixel(x, y,      0);
                browPixel(x, y + 1,  1);
            }
            break;
        }
        case EYE_THINK: {
            // Curious: inner side raised, outer flat
            for (int x = BROW_X0; x <= BROW_X1; x++) {
                float t     = (float)(x - BROW_MID) / ((BROW_X1 - BROW_X0) * 0.5f);
                float inner = flipX ? -t : t;   // positive toward nose
                int   y     = constrain(BROW_Y - (int)(3.0f * max(0.0f, inner)), 0, EYE_Y - 2);
                browPixel(x, y - 1, -1);
                browPixel(x, y,      0);
                browPixel(x, y + 1,  1);
            }
            break;
        }
        case EYE_HAPPY: {
            // High graceful arch peaking at centre
            for (int x = BROW_X0; x <= BROW_X1; x++) {
                float t = (float)(x - BROW_MID) / ((BROW_X1 - BROW_X0) * 0.5f);
                int   y = constrain((BROW_Y - 4) + (int)(5.0f * t * t), 0, EYE_Y - 2);
                browPixel(x, y - 1, -1);
                browPixel(x, y,      0);
                browPixel(x, y + 1,  1);
            }
            break;
        }
        case EYE_ANGRY: {
            // V-scowl: outer HIGH, inner LOW — 3px thick
            int xOuter = flipX ? BROW_X1 : BROW_X0;
            int xInner = flipX ? BROW_X0 : BROW_X1;
            for (int off = 0; off <= 2; off++)
                d.drawLine(xOuter, BROW_Y - 4 + off, xInner, BROW_Y + 3 + off, SSD1306_WHITE);
            break;
        }
        case EYE_SAD: {
            // Droopy: inner HIGH, outer LOW — 3px thick
            int xOuter = flipX ? BROW_X1 : BROW_X0;
            int xInner = flipX ? BROW_X0 : BROW_X1;
            for (int off = 0; off <= 2; off++)
                d.drawLine(xOuter, BROW_Y + 3 + off, xInner, BROW_Y - 4 + off, SSD1306_WHITE);
            break;
        }
        default: break;
    }
}

// ─────────────────────────────────────────────────────────────
//  UPPER EYELID  — per-column scanline droop
// ─────────────────────────────────────────────────────────────
void drawUpperEyelid(Adafruit_SSD1306 &d, int ex, int ey, int eyeW, int eyeH,
                     EyeState state, bool flipX) {
    for (int x = ex; x < ex + eyeW; x++) {
        // t: 0 at outer corner, 1 at inner corner (eye midline is nose-side)
        float t      = (float)(x - ex) / (float)eyeW;
        float inner  = flipX ? t : (1.0f - t);   // 1 = inner/nose side
        float outer  = 1.0f - inner;

        // Per-state droop fraction (0 = open/top of eye, 0.5 = half-closed)
        float droop = 0.0f;
        switch (state) {
            case EYE_ANGRY:  droop = 0.06f + 0.24f * inner; break; // scowl on inner
            case EYE_SAD:    droop = 0.04f + 0.20f * outer; break; // droop on outer
            case EYE_HAPPY:  droop = 0.0f;                  break; // wide open
            case EYE_THINK:  droop = 0.04f + 0.10f * inner; break; // slight inner raise
            case EYE_SPEAK:  droop = 0.02f;                 break;
            default:         droop = 0.03f;                 break; // barely visible
        }

        int lid_y = ey + (int)(droop * eyeH);

        // Fill eyelid area (black skin above lash line)
        for (int y = ey; y < lid_y && y < ey + eyeH - 2; y++) {
            d.drawPixel(x, y, SSD1306_BLACK);
        }

        // Lash line: the edge row — add 1px white crease then black lash ticks
        if (lid_y > ey) {
            // White crease line just below eyelid skin
            d.drawPixel(x, lid_y, SSD1306_WHITE);
        }
        // Eyelash ticks: every 4px along lash line, 2px downward spike
        if ((x - ex) % 4 == 1 && lid_y + 2 < ey + eyeH) {
            d.drawPixel(x, lid_y + 1, SSD1306_BLACK);
            d.drawPixel(x, lid_y + 2, SSD1306_BLACK);
        }
    }
}

// ─────────────────────────────────────────────────────────────
//  LOWER EYELID  — waterline + lower lashes
// ─────────────────────────────────────────────────────────────
void drawLowerEyelid(Adafruit_SSD1306 &d, int ex, int ey, int eyeW, int eyeH) {
    int bot = ey + eyeH - 1;
    for (int x = ex + 6; x < ex + eyeW - 6; x++) {
        // Parabolic waterline: 3px at centre, 1px at edges
        float t    = 2.0f * (float)(x - ex) / eyeW - 1.0f;  // -1 to +1
        int   h    = max(1, (int)(3.0f - 2.5f * t * t));
        for (int i = 0; i < h; i++) {
            d.drawPixel(x, bot - i, SSD1306_BLACK);
        }
        // Lower lash tick every 5px
        if ((x - ex) % 5 == 0 && bot + 2 < SCREEN_H) {
            d.drawPixel(x, bot + 1, SSD1306_BLACK);
        }
    }
}

// ─────────────────────────────────────────────────────────────
//  SCROLLING TEXT RENDERER (bottom status bar)
// ─────────────────────────────────────────────────────────────
void drawScrollingText(Adafruit_SSD1306 &d, int scrollOff, const char *text) {
    int len = strlen(text);
    if (len == 0) return;

    // Each char is 6px wide in size-1 font
    // Start x scrolls from right edge leftward
    int totalPx = len * 6;
    int startX  = SCREEN_W - 1 - scrollOff;  // start pixel

    d.setTextSize(1);
    d.setTextColor(SSD1306_WHITE, SSD1306_BLACK);

    for (int i = 0; i < len; i++) {
        int cx = startX + i * 6;
        if (cx > -6 && cx < SCREEN_W) {
            d.drawChar(cx, STATUS_Y, text[i], SSD1306_WHITE, SSD1306_BLACK, 1);
        }
    }
}

// ─────────────────────────────────────────────────────────────
//  STATUS BAR  (y=56..63) — text OR emotion animation
// ─────────────────────────────────────────────────────────────
void drawStatusBar(Adafruit_SSD1306 &d, EyeState state, int frame, bool flipX) {

    // ── Emotion-label flash (1.2s after state change) ─────────
    if (emotionLabel[0] && labelEndMs > millis()) {
        d.setTextSize(1);
        d.setTextColor(SSD1306_WHITE, SSD1306_BLACK);
        int lw = strlen(emotionLabel) * 6;
        d.setCursor((SCREEN_W - lw) / 2, STATUS_Y);
        d.print(emotionLabel);
        return;
    }

    // ── Scrolling text takes priority ─────────────────────────
    if (scrollText[0]) {
        drawScrollingText(d, scrollPx, scrollText);
        return;
    }

    // ── DIZZY — spinning stars ────────────────────────────────
    if (state == EYE_DIZZY) {
        bool a  = (frame % 2 == 0);
        int sx1 = a ? 7 : 11, sx2 = a ? 121 : 117;
        int sy  = SCREEN_H - 4;
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
            // Animated 7-bar equalizer
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
            // Bouncing "..." loading dots
            int active = (frame / 2) % 3;
            for (int i = 0; i < 3; i++) {
                int y = (i == active) ? (SCREEN_H - 6) : (SCREEN_H - 4);
                d.fillCircle(56 + i * 8, y, 2, SSD1306_WHITE);
            }
            break;
        }
        case EYE_HAPPY: {
            // Bouncing heart ♥ + sparkle dots
            int yBob = (frame % 4 < 2) ? 0 : -1;
            int hx = 64, hy = SCREEN_H - 4 + yBob;
            d.fillCircle(hx - 2, hy - 2, 2, SSD1306_WHITE);
            d.fillCircle(hx + 2, hy - 2, 2, SSD1306_WHITE);
            d.fillTriangle(hx - 4, hy - 1, hx + 4, hy - 1, hx, hy + 3, SSD1306_WHITE);
            // Side sparkles
            if (frame % 2 == 0) {
                d.drawPixel(40, SCREEN_H - 3, SSD1306_WHITE);
                d.drawPixel(88, SCREEN_H - 3, SSD1306_WHITE);
                d.drawPixel(38, SCREEN_H - 5, SSD1306_WHITE);
                d.drawPixel(90, SCREEN_H - 5, SSD1306_WHITE);
            }
            break;
        }
        case EYE_ANGRY: {
            // !! marks with pulsing glow
            int sx = flipX ? 76 : 49;
            int blink_h = (frame % 4 < 3) ? 4 : 3;
            d.fillRect(sx,     SCREEN_H - blink_h - 2, 3, blink_h, SSD1306_WHITE);
            d.fillRect(sx,     SCREEN_H - 2, 3, 2, SSD1306_WHITE);
            d.fillRect(sx + 5, SCREEN_H - blink_h - 2, 3, blink_h, SSD1306_WHITE);
            d.fillRect(sx + 5, SCREEN_H - 2, 3, 2, SSD1306_WHITE);
            break;
        }
        case EYE_SAD: {
            // Tear drops with ripple rings
            int tx = flipX ? (EYE_X + EYE_W - 8) : (EYE_X + 6);
            for (int t = 0; t < 2; t++) {
                int ty = 57 + ((frame * 2 + t * 4) % 8);
                if (ty < SCREEN_H) d.fillCircle(tx, ty, 2, SSD1306_WHITE);
            }
            // Ripple ring at bottom
            int ry = SCREEN_H - 2;
            if (frame % 3 == 0) d.drawCircle(tx, ry, 3, SSD1306_WHITE);
            break;
        }
        default: break;
    }
}

// ─────────────────────────────────────────────────────────────
//  DRAW ONE EYE
// ─────────────────────────────────────────────────────────────
void drawEye(Adafruit_SSD1306 &d, float blinkFrac, int px, int py,
             EyeState state, int frame, bool flipX) {
    d.clearDisplay();

    int cx = SCREEN_W / 2;
    int cy = SCREEN_H / 2;

    // ── DIZZY — animated spinning cross ──────────────────────
    if (state == EYE_DIZZY) {
        int s = 20;
        d.drawRoundRect(8, 6, SCREEN_W - 16, SCREEN_H - 14, 10, SSD1306_WHITE);
        float ang = frame * 0.196f;
        int   dx  = (int)(s * cosf(ang)), dy = (int)(s * sinf(ang));
        d.drawLine(cx - dx, cy - dy, cx + dx, cy + dy, SSD1306_WHITE);
        d.drawLine(cx - dy, cy + dx, cx + dy, cy - dx, SSD1306_WHITE);
        // Corner stars
        for (int sx : {10, SCREEN_W - 10}) {
            d.fillCircle(sx, 10, 2, SSD1306_WHITE);
            d.fillCircle(sx, SCREEN_H - 10, 2, SSD1306_WHITE);
        }
        drawBrow(d, state, flipX);
        drawStatusBar(d, state, frame, flipX);
        d.display();
        return;
    }

    // ── Eye shape per state ───────────────────────────────────
    int eyeW = EYE_W, eyeH = EYE_H;
    if      (state == EYE_ANGRY) eyeH = max(2, (int)(EYE_H * 0.56f * blinkFrac));
    else if (state == EYE_SAD)   eyeH = max(2, (int)(EYE_H * 0.82f * blinkFrac));
    else if (state == EYE_THINK) eyeH = max(2, (int)(EYE_H * 0.86f * blinkFrac));
    else if (state == EYE_SPEAK) {
        float sc = 0.74f + 0.26f * sinf(frame * 0.785f);
        eyeH = max(2, (int)(EYE_H * blinkFrac * sc));
        eyeW = (int)(EYE_W * (0.90f + 0.10f * sc));
    }
    else eyeH = max(2, (int)(EYE_H * blinkFrac));

    int rad = min(EYE_RADIUS, eyeH / 2);
    int ex  = (SCREEN_W - eyeW) / 2;
    int ey  = (SCREEN_H - eyeH) / 2;

    // ── 1. Sclera (white) ─────────────────────────────────────
    d.fillRoundRect(ex, ey, eyeW, eyeH, rad, SSD1306_WHITE);

    // ── 2. Upper eyelid (realistic droop per emotion) ─────────
    drawUpperEyelid(d, ex, ey, eyeW, eyeH, state, flipX);

    // ── 3. Shape cuts per state ───────────────────────────────
    if (state == EYE_ANGRY) {
        // Inner-corner brow cut — deepens the scowl
        int bix = flipX ? (ex + eyeW - 4) : (ex + 4);
        int box = flipX ? (ex + eyeW / 2 + 12) : (ex + eyeW / 2 - 12);
        for (int off = -1; off <= 1; off++)
            d.drawLine(bix + off, ey - 1, box + off, ey + eyeH / 3, SSD1306_BLACK);
    }
    if (state == EYE_SAD) {
        // Outer top-corner droop (petal effect)
        if (flipX) {
            for (int i = 0; i < 24; i++)
                d.drawLine(ex + eyeW - i, ey, ex + eyeW, ey + i, SSD1306_BLACK);
        } else {
            for (int i = 0; i < 24; i++)
                d.drawLine(ex + i, ey, ex, ey + i, SSD1306_BLACK);
        }
    }
    if (state == EYE_HAPPY) {
        // Bottom inner-corner lift (smile squint)
        if (flipX) {
            for (int i = 0; i < 20; i++)
                d.drawLine(ex + i, ey + eyeH, ex, ey + eyeH - i, SSD1306_BLACK);
        } else {
            for (int i = 0; i < 20; i++)
                d.drawLine(ex + eyeW - i, ey + eyeH, ex + eyeW, ey + eyeH - i, SSD1306_BLACK);
        }
    }

    // ── 4. Lower eyelid + waterline ──────────────────────────
    if (blinkFrac > 0.5f) {
        drawLowerEyelid(d, ex, ey, eyeW, eyeH);
    }

    // ── 5. Tear duct ──────────────────────────────────────────
    {
        int tdX = flipX ? (ex + eyeW - 7) : (ex + 7);
        int tdY = ey + eyeH / 2;
        d.fillCircle(tdX, tdY, 2, SSD1306_BLACK);
        d.drawPixel(tdX + (flipX ? -4 : 4), tdY, SSD1306_WHITE);
    }

    // ── 6. Pupil + iris ───────────────────────────────────────
    if (blinkFrac > 0.3f) {
        // Apply micro-saccade jitter when open
        float jx = (state == EYE_OPEN) ? jitterX : 0;
        float jy = (state == EYE_OPEN) ? jitterY : 0;

        int puX = cx + (int)(px + jx);
        int puY = cy + (int)(py + jy);
        int pR  = (int)pupilR;

        // Per-state pupil offset
        if (state == EYE_ANGRY) puX += (flipX ? 5 : -5);
        if (state == EYE_SAD)   puY += 3;
        if (state == EYE_HAPPY) puY -= 3;

        int clampR = LIMBAL_R + 2;
        puX = constrain(puX, ex + clampR, ex + eyeW - clampR);
        puY = constrain(puY, ey + clampR, ey + eyeH - clampR);

        // A: outer iris (dark limbal zone)
        d.fillCircle(puX, puY, LIMBAL_R, SSD1306_BLACK);

        // B: iris fiber texture — 16 radial spokes
        for (int a = 0; a < 16; a++) {
            float ang  = a * (M_PI / 8.0f);
            float cosA = cosf(ang), sinA = sinf(ang);
            for (int r = FIBER_R0; r <= FIBER_R1; r++) {
                if ((r + a) % 2 == 0) {
                    int ix = puX + (int)(r * cosA);
                    int iy = puY + (int)(r * sinA);
                    if (ix > ex + 2 && ix < ex + eyeW - 2 &&
                        iy > ey + 2 && iy < ey + eyeH - 2)
                        d.drawPixel(ix, iy, SSD1306_WHITE);
                }
            }
        }

        // C: limbal ring (bright outer iris edge)
        d.drawCircle(puX, puY, LIMBAL_R - 1, SSD1306_WHITE);

        // D: inner highlight rings
        d.drawCircle(puX, puY, INNER_RING_R,     SSD1306_WHITE);
        d.drawCircle(puX, puY, INNER_RING_R + 1, SSD1306_WHITE);

        // E: pupil — animated radius
        d.fillCircle(puX, puY, pR, SSD1306_BLACK);

        // F: primary corneal reflex (upper-left)
        d.fillCircle(puX - 5, puY - 6, 3, SSD1306_WHITE);
        d.drawPixel (puX - 8, puY - 4,    SSD1306_WHITE);

        // G: secondary corneal reflex (lower-right, smaller)
        d.fillCircle(puX + 5, puY + 4, 1, SSD1306_WHITE);

        // H: THINK — tiny star near pupil
        if (state == EYE_THINK) {
            int stX = puX + (flipX ? -9 : 9);
            int stY = puY - 9;
            if (stX > ex + 2 && stX < ex + eyeW - 2 && stY > ey + 2) {
                d.drawPixel(stX,     stY,     SSD1306_WHITE);
                d.drawPixel(stX - 2, stY,     SSD1306_WHITE);
                d.drawPixel(stX + 2, stY,     SSD1306_WHITE);
                d.drawPixel(stX,     stY - 2, SSD1306_WHITE);
                d.drawPixel(stX,     stY + 2, SSD1306_WHITE);
            }
        }
    }

    // ── 7. HAPPY — twinkling corner stars ────────────────────
    if (state == EYE_HAPPY) {
        int csX = flipX ? (SCREEN_W - 5) : 4;
        if ((frame + (flipX ? 1 : 0)) % 4 < 2) {
            d.fillCircle(csX, 10, 1, SSD1306_WHITE);
            d.drawPixel(csX - 3, 10, SSD1306_WHITE);
            d.drawPixel(csX + 3, 10, SSD1306_WHITE);
            d.drawPixel(csX,  7,     SSD1306_WHITE);
            d.drawPixel(csX, 13,     SSD1306_WHITE);
        }
        if ((frame + (flipX ? 3 : 2)) % 4 < 2) {
            d.fillCircle(csX, SCREEN_H - 11, 1, SSD1306_WHITE);
            d.drawPixel(csX - 3, SCREEN_H - 11, SSD1306_WHITE);
            d.drawPixel(csX + 3, SCREEN_H - 11, SSD1306_WHITE);
            d.drawPixel(csX, SCREEN_H - 14,     SSD1306_WHITE);
            d.drawPixel(csX, SCREEN_H -  8,     SSD1306_WHITE);
        }
    }

    // ── 8. Brow + status bar ─────────────────────────────────
    drawBrow(d, state, flipX);
    drawStatusBar(d, state, frame, flipX);

    d.display();
}

// ─────────────────────────────────────────────────────────────
//  DRAW BOTH EYES
// ─────────────────────────────────────────────────────────────
void drawBothEyes(float blinkFrac, EyeState state, int frame) {
    bool inv = false;
    if      (state == EYE_ANGRY)                   inv = true;
    else if (state == EYE_DIZZY && frame % 2 == 0) inv = true;
    setInvert(inv);

    int px = (int)pupilX, py = (int)pupilY;
    if (hasLeftOLED)  drawEye(leftEye,  blinkFrac, px, py, state, frame, false);
    if (hasRightOLED) drawEye(rightEye, blinkFrac, px, py, state, frame, true);
}

// ─────────────────────────────────────────────────────────────
//  BOOT ANIMATION
// ─────────────────────────────────────────────────────────────
void bootAnimation() {
    if (hasLeftOLED)  { leftEye.clearDisplay();  leftEye.display(); }
    if (hasRightOLED) { rightEye.clearDisplay(); rightEye.display(); }
    delay(200);

    // Phase 1: scanlines sweep
    for (int y = 0; y < SCREEN_H; y += 2) {
        if (hasLeftOLED)  { leftEye.drawFastHLine(0, y, SCREEN_W, SSD1306_WHITE);  leftEye.display(); }
        if (hasRightOLED) { rightEye.drawFastHLine(0, y, SCREEN_W, SSD1306_WHITE); rightEye.display(); }
        delay(6);
    }
    delay(60);

    // Phase 2: "ZERO" large text centred
    for (Adafruit_SSD1306 *d : {hasLeftOLED  ? &leftEye  : (Adafruit_SSD1306*)nullptr,
                                 hasRightOLED ? &rightEye : (Adafruit_SSD1306*)nullptr}) {
        if (!d) continue;
        d->clearDisplay();
        d->setTextColor(SSD1306_WHITE);
        d->setTextSize(2);
        d->setCursor(40, 24);
        d->print("ZERO");
        d->display();
    }
    delay(600);

    // Phase 3: iris expand from centre
    for (int r = 2; r <= 36; r += 3) {
        for (Adafruit_SSD1306 *d : {hasLeftOLED  ? &leftEye  : (Adafruit_SSD1306*)nullptr,
                                     hasRightOLED ? &rightEye : (Adafruit_SSD1306*)nullptr}) {
            if (!d) continue;
            d->clearDisplay();
            d->fillCircle(SCREEN_W / 2, SCREEN_H / 2, r, SSD1306_WHITE);
            d->fillCircle(SCREEN_W / 2, SCREEN_H / 2, max(2, r - 9), SSD1306_BLACK);
            d->display();
        }
        delay(28);
    }
    delay(60);

    // Phase 4: open eyes + double blink + haptic
    for (int i = 0; i <= 10; i++) { drawBothEyes(i / 10.0f, EYE_OPEN); delay(24); }
    delay(250);
    for (int i = 10; i >= 0; i--) { drawBothEyes(i / 10.0f, EYE_OPEN); delay(12); }
    delay(50);
    for (int i = 0; i <= 10; i++)  { drawBothEyes(i / 10.0f, EYE_OPEN); delay(12); }
    delay(140);
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
//  UART IN  — parse commands + optional "text" field
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
                    const char *cmd  = doc["command"];
                    const char *text = doc["text"];

                    // If there's text to display, queue it for scrolling
                    if (text && strlen(text) > 0) {
                        setScrollText(text);
                    }

                    if (cmd) {
                        String s(cmd);
                        uint32_t now = millis();

                        if (s == "speak_anim") {
                            eyeState  = EYE_SPEAK;
                            exprEndMs = now + 8000;
                        } else if (s == "think") {
                            eyeState  = EYE_THINK;
                            exprEndMs = now + 30000;
                            setScrollText("..thinking..");
                        } else if (s == "angry") {
                            eyeState  = EYE_ANGRY;
                            exprEndMs = now + 4000;
                            triggerHaptic();
                            setEmotionLabel(">:(");
                        } else if (s == "happy") {
                            eyeState  = EYE_HAPPY;
                            exprEndMs = now + 4000;
                            setEmotionLabel("^^");
                        } else if (s == "sad") {
                            eyeState  = EYE_SAD;
                            exprEndMs = now + 4000;
                            setEmotionLabel(":'(");
                        } else if (s == "blink") {
                            lastBlink = 0;
                        } else if (s == "open") {
                            eyeState  = EYE_OPEN;
                            exprEndMs = 0;
                        }
                        Serial.printf("[CMD] %s  text=%s\n", cmd, text ? text : "");
                    }
                }
            }
            buf = "";
        } else {
            buf += c;
            if (buf.length() > 250) buf = "";
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
