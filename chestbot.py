"""
TikTok Campaign Bot  ·  YOLO Edition
─────────────────────────────────────
pip install Pillow numpy ultralytics
python tiktok_campaign_bot.py
"""

import os, io, re, csv, json, time, shutil, threading, subprocess, traceback, shlex
import concurrent.futures as cf
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime, timezone

# ── Windows HD / DPI fix ──────────────────────────────────────────────────────
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import numpy as np
    NP_OK = True
except ImportError:
    NP_OK = False

try:
    from ultralytics import YOLO as _YOLO
    YOLO_OK = True
except ImportError:
    YOLO_OK = False

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "training_data")
IMAGES_DIR  = os.path.join(DATA_DIR, "images")
LABELS_DIR  = os.path.join(DATA_DIR, "labels")
MODEL_DIR   = os.path.join(BASE_DIR, "model")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
MODEL_PATH  = os.path.join(MODEL_DIR, "best.pt")
for _d in [DATA_DIR, IMAGES_DIR, LABELS_DIR, MODEL_DIR, RESULTS_DIR]:
    os.makedirs(_d, exist_ok=True)

# ── Campaigns ──────────────────────────────────────────────────────────────────
CLASSES = [
    ("treasure_chest", "🪙", "Treasure Chest", "#ffb340"),
]
CLASS_NAMES  = [c[0] for c in CLASSES]
CLASS_COLORS = {c[0]: c[3] for c in CLASSES}

TIKTOK_PKGS = [
    "com.zhiliaoapp.musically",
    "com.ss.android.ugc.trill",
    "com.tiktok.android",
]

# ── Modern Slate Dark Palette ──────────────────────────────────────────────────
BG0    = "#090D16"   # Deep slate background
BG1    = "#0F172A"   # Panel & navigation header
BG2    = "#1E293B"   # Elevated card background
BG3    = "#334155"   # Input background & hover state
LINE   = "#273549"   # Card border & separator line
ACCENT = "#FF2855"   # TikTok Crimson red CTA
CYAN   = "#00F2FE"   # Electric cyan highlight
GREEN  = "#10B981"   # Emerald vivid success
AMBER  = "#F59E0B"   # Warm amber warning
FG     = "#F8FAFC"   # Primary text (crisp white)
FG2    = "#94A3B8"   # Secondary text (slate 400)
FG3    = "#64748B"   # Muted labels / caps (slate 500)
WHITE  = "#FFFFFF"

# keep old names as aliases so existing code doesn't break
TEAL   = CYAN
RED    = ACCENT

def F(s=10, w="normal"): return ("Segoe UI", s, w)
FM = ("Cascadia Code", 9)
FN = ("Segoe UI", 11, "bold")   # numeric readout font


# ──────────────────────────────────────────────────────────────────────────────
#  ADB
# ──────────────────────────────────────────────────────────────────────────────
def find_adb():
    found = shutil.which("adb")
    if found: return found
    for p in [
        r"C:\Users\victo\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        r"C:\LDPlayer\LDPlayer9\adb.exe",
        r"C:\Users\victo\Downloads\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\adb.exe",
    ]:
        if os.path.exists(p): return p
    return "adb"

def find_scrcpy():
    found = shutil.which("scrcpy")
    if found: return found
    for p in [
        r"C:\Users\victo\Downloads\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\scrcpy.exe",
        r"C:\scrcpy\scrcpy.exe",
    ]:
        if os.path.exists(p): return p
    return None

ADB_EXE    = find_adb()
SCRCPY_EXE = find_scrcpy()


class ADBDevice:
    def __init__(self, serial):
        self.serial = serial
        self._w = self._h = None
        self._shell_proc = None

    def _get_shell(self):
        if self._shell_proc is None or self._shell_proc.poll() is not None:
            try:
                cmd = [ADB_EXE, "-s", self.serial, "shell"]
                self._shell_proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
            except Exception:
                self._shell_proc = None
        return self._shell_proc

    def close(self):
        if self._shell_proc:
            try:
                self._shell_proc.terminate()
            except Exception:
                pass
            self._shell_proc = None

    def _run(self, cmd, binary=False):
        try:
            if isinstance(cmd, str):
                cmd_parts = shlex.split(cmd)
            else:
                cmd_parts = list(cmd)
            args = [ADB_EXE, "-s", self.serial] + cmd_parts
            r = subprocess.run(args, capture_output=True, timeout=15)
            return r.stdout if binary else r.stdout.decode("utf-8", errors="replace").strip()
        except Exception as e:
            return b"" if binary else f"ERROR:{e}"

    def screencap(self):
        if not PIL_OK: return None
        raw = self._run("exec-out screencap -p", binary=True)
        if not raw or len(raw) < 1000: return None
        try: return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception: return None

    def size(self):
        if self._w: return self._w, self._h
        out = self._run("shell wm size")
        m = re.search(r"Override size:\s*(\d+)x(\d+)", out) or re.search(r"(\d+)x(\d+)", out)
        if m: self._w, self._h = int(m.group(1)), int(m.group(2))
        else:
            img = self.screencap()
            self._w, self._h = img.size if img else (720, 1440)
        return self._w, self._h

    def swipe_up(self, ms=180):
        w, h = self.size()
        proc = self._get_shell()
        if proc and proc.stdin:
            try:
                proc.stdin.write(f"input swipe {w//2} {int(h*.72)} {w//2} {int(h*.28)} {ms}\n".encode())
                proc.stdin.flush()
                return
            except Exception:
                self._shell_proc = None
        self._run(f"shell input swipe {w//2} {int(h*.72)} {w//2} {int(h*.28)} {ms}")

    def tap(self, x, y):
        proc = self._get_shell()
        if proc and proc.stdin:
            try:
                proc.stdin.write(f"input tap {x} {y}\n".encode())
                proc.stdin.flush()
                return
            except Exception:
                self._shell_proc = None
        self._run(f"shell input tap {x} {y}")

    def tap_text(self, texts):
        dump = self._run("shell uiautomator dump /dev/tty")
        # Match every opening <node tag — both self-closing (<node .../>) and
        # non-self-closing (<node ...>) since uiautomator uses both forms.
        # We only need the opening tag itself to get text= and bounds=.
        pairs = []
        for node in re.findall(r'<node\b[^>]*>', dump):
            tm = re.search(r'\btext="([^"]*)"', node)
            bm = re.search(r'\bbounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
            if tm and bm:
                pairs.append((tm.group(1),
                               int(bm.group(1)), int(bm.group(2)),
                               int(bm.group(3)), int(bm.group(4))))

        for t in texts:
            t_low = t.lower().strip()
            for label, x1, y1, x2, y2 in pairs:
                if t_low in label.lower():
                    self.tap((x1+x2)//2, (y1+y2)//2)
                    return True
        return False

    def send_text(self, text):
        # ADB input text doesn't handle unicode well — use clipboard paste instead
        safe = text.replace("'", "").replace('"', "").replace("\\", "")
        self._run(f"shell input text '{safe.replace(' ', '%s')}'")

    def press_enter(self): self._run("shell input keyevent 66")

    def wake(self): self._run("shell input keyevent 224"); time.sleep(0.3)

    def launch_app(self, pkg):
        self._run(f"shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

    def stop_app(self, pkg): self._run(f"shell am force-stop {pkg}")

    def find_package(self):
        installed = self._run("shell pm list packages")
        for p in TIKTOK_PKGS:
            if p in installed: return p
        return None

    def info(self):
        return {
            "model":   self._run("shell getprop ro.product.model").strip(),
            "android": self._run("shell getprop ro.build.version.release").strip(),
            "w": self.size()[0], "h": self.size()[1],
        }


def adb_devices():
    try:
        out = subprocess.run([ADB_EXE, "devices"],
                             capture_output=True, text=True, timeout=8).stdout
        return [l.split("\t")[0] for l in out.splitlines()[1:]
                if "\t" in l and "offline" not in l]
    except Exception: return []


# ──────────────────────────────────────────────────────────────────────────────
#  YOLO detector
# ──────────────────────────────────────────────────────────────────────────────
class YOLODetector:
    def __init__(self):
        self.model = None; self.model_path = None; self.loading = False
        self._load_async()

    def _load_async(self):
        if self.loading: return
        self.loading = True
        def do():
            self._load()
            self.loading = False
        threading.Thread(target=do, daemon=True).start()

    def _load(self):
        if not YOLO_OK or not os.path.exists(MODEL_PATH): return
        try: self.model = _YOLO(MODEL_PATH); self.model_path = MODEL_PATH
        except Exception: self.model = None

    def reload(self): self._load_async()
    def is_loaded(self): return self.model is not None and not self.loading

    def model_info(self):
        if self.loading: return "Loading model..."
        if not self.model_path: return "No model trained yet"
        t = datetime.fromtimestamp(os.path.getmtime(self.model_path))
        return f"best.pt  ·  {t.strftime('%d %b %Y  %H:%M')}"

    def detect(self, img, conf=0.45):
        if not self.model or not PIL_OK: return []
        try:
            res = self.model(img, verbose=False, conf=conf)[0]
            out = []
            for box in res.boxes:
                cid   = int(box.cls[0])
                cname = CLASS_NAMES[cid] if cid < len(CLASS_NAMES) else f"cls{cid}"
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                out.append({"class_name": cname,
                             "conf":       round(float(box.conf[0]), 3),
                             "box":        (int(x1), int(y1), int(x2), int(y2))})
            return out
        except Exception: return []


# ──────────────────────────────────────────────────────────────────────────────
#  Label helpers
# ──────────────────────────────────────────────────────────────────────────────
def count_labels():
    imgs = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith(".png")]
    labelled = boxes = 0
    for fn in imgs:
        lp = os.path.join(LABELS_DIR, os.path.splitext(fn)[0] + ".txt")
        if os.path.exists(lp):
            lines = [l for l in open(lp).read().splitlines() if l.strip()]
            if lines: labelled += 1; boxes += len(lines)
    return len(imgs), labelled, boxes

def save_label(image_path, annotations):
    lp = os.path.join(LABELS_DIR, os.path.splitext(os.path.basename(image_path))[0] + ".txt")
    with open(lp, "w") as f:
        for ann in annotations:
            f.write(" ".join(str(round(v, 6)) for v in ann) + "\n")

def load_label(image_path):
    lp = os.path.join(LABELS_DIR, os.path.splitext(os.path.basename(image_path))[0] + ".txt")
    if not os.path.exists(lp): return []
    out = []
    for line in open(lp):
        parts = line.strip().split()
        if len(parts) == 5: out.append(tuple(float(p) for p in parts))
    return out


# ──────────────────────────────────────────────────────────────────────────────
#  Training
# ──────────────────────────────────────────────────────────────────────────────
def run_training(epochs, log_fn, done_fn):
    def _go():
        try:
            from ultralytics import YOLO
            log_fn("Loading YOLOv8n base model...")
            m = YOLO("yolov8n.pt")
            yaml = os.path.join(DATA_DIR, "data.yaml")
            with open(yaml, "w") as f:
                f.write(f"path: {DATA_DIR}\ntrain: images\nval: images\n"
                        f"nc: {len(CLASSES)}\nnames: {CLASS_NAMES}\n")
            _, labelled, boxes = count_labels()
            log_fn(f"Dataset: {labelled} labelled images, {boxes} boxes")
            log_fn(f"Training {epochs} epochs...\n")
            m.train(data=yaml, epochs=epochs, imgsz=640,
                    project=MODEL_DIR, name="run", exist_ok=True, verbose=True)
            best = os.path.join(MODEL_DIR, "run", "weights", "best.pt")
            if os.path.exists(best):
                shutil.copy(best, MODEL_PATH)
                log_fn("\n✅ Training complete — model saved to model/best.pt")
                done_fn(True)
            else:
                log_fn("\n❌ Training finished but best.pt not found.")
                done_fn(False)
        except ImportError:
            log_fn("❌ Run: pip install ultralytics"); done_fn(False)
        except Exception as e:
            log_fn(f"\n❌ {e}\n{traceback.format_exc()}"); done_fn(False)
    threading.Thread(target=_go, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────────────
#  Bot
# ──────────────────────────────────────────────────────────────────────────────
class Bot:
    MODES = {"turbo": (0.3, 1), "fast": (0.6, 2), "deep": (1.0, 3)}

    def __init__(self, serial, pkg, cfg, log, on_result, on_done, detector):
        self.dev = ADBDevice(serial); self.pkg = pkg; self.cfg = cfg
        self.log = log; self.on_result = on_result; self.on_done = on_done
        self.detector = detector; self._stop = False

    def stop(self): self._stop = True

    def _is_on_live(self):
        try:
            img = self.dev.screencap()
            if not img: return False
            if NP_OK:
                arr = np.array(img.convert("L"), dtype=np.float32)
                return float(np.sum(arr < 50) / arr.size) > 0.25
            px = list(img.convert("L").getdata())
            return sum(1 for p in px if p < 50) / len(px) > 0.25
        except Exception: return False

    def goto_live(self):
        self.log("📡  Navigating to LIVE...")
        w, h = self.dev.size()
        self.dev._run("shell am start -a android.intent.action.VIEW -d 'tiktok://live'")
        time.sleep(2.5)
        if self._is_on_live(): self.log("    ✅  Deep link worked."); return
        top_y = int(h * 0.07)
        for _ in range(8):
            if self.dev.tap_text(["LIVE", "Live"]):
                time.sleep(1.5)
                if self._is_on_live(): self.log("    ✅  LIVE tab found."); return
            self.dev._run(f"shell input swipe {int(w*.75)} {top_y} {int(w*.25)} {top_y} 250")
            time.sleep(0.5)
        self.log("    ⚠️   Auto-navigate failed.")
        self.log("    👉  Open TikTok LIVE on your phone manually.")
        for i in range(60):
            time.sleep(1)
            if self._is_on_live(): self.log("    ✅  LIVE detected."); return
            if i % 15 == 14: self.log(f"    ⏳  Waiting... ({60-i-1}s)")
        self.log("    ⚠️   Timed out — starting from current screen.")

    def _collect_loop(self, tap_x=None, tap_y=None):
        """
        After tapping a treasure chest:
          1. Brief 0.3s pause for popup overlay to open.
          2. Positional-tap Open/Collect buttons immediately (85% and 89% height).
          3. Fast polling loop to tap collect & detect when chest popup closes.
          4. Deferred check for unexpected popups if popup stays open.
        """
        UNEXPECTED = [
            "request to join", "join as a guest",
            "share", "report", "block", "profile",
            "winning streak", "winning streaks",
            "how it works", "learn more",
            "share live to join", "share live", "share to join",
            "reach fan", "fan lv", "fan club", "view fan club",
        ]

        max_wait = 600  # 10 minutes hard ceiling
        w, h     = self.dev.size()
        btn_x    = w // 2
        btn_positions = [int(h * 0.85), int(h * 0.89)]

        # ── Brief wait for animation to start ─────────────────────────────
        time.sleep(0.3)

        # ── Positional taps for the Open button ───────────────────────────
        for btn_y in btn_positions:
            self.dev.tap(btn_x, btn_y)
            self.log(f"         👆  Positional tap ({btn_x}, {btn_y})")
            time.sleep(0.05)

        # ── Wait for countdown to end, collect when popup closes ──────────
        POLL  = 0.4
        ticks = int(max_wait / POLL)
        stable_low    = 0   # consecutive low-brightness readings
        failed_caps   = 0

        for t in range(ticks):
            if self._stop: return
            time.sleep(POLL)

            chk = self.dev.screencap()
            if not chk:
                failed_caps += 1
                if failed_caps >= 5:
                    self.log("         ❌  Screencap failed 5 times — device disconnected?")
                    return
                continue
            failed_caps = 0

            # Check if stream has changed (chest screen gone entirely)
            full = chk.convert("L")
            if NP_OK:
                full_bright = float(np.mean(np.array(full, dtype=np.float32)))
            else:
                px_full = list(full.getdata())
                full_bright = sum(px_full) / len(px_full)

            # Very dark screen = stream ended / navigated away
            if full_bright < 15:
                self.log("         ↩️   Stream ended — moving on.")
                return

            cw, ch = chk.size
            bot = chk.crop((0, ch // 2, cw, ch)).convert("L")
            if NP_OK:
                bright = float(np.mean(np.array(bot, dtype=np.float32)))
            else:
                px = list(bot.getdata())
                bright = sum(px) / len(px)

            if bright <= 140:
                stable_low += 1
                if stable_low >= 2:   # confirm across 2 frames to avoid false positive
                    elapsed = round(t * POLL, 1)
                    self.log(f"         🪙  Chest collected! ({elapsed}s)")
                    time.sleep(0.2)
                    return
            else:
                stable_low = 0
                # Tap collect button eagerly
                self.dev.tap(btn_x, btn_positions[0])

                # Deferred unexpected popup sanity check (only run after ~4 seconds if popup hasn't closed)
                if t == int(4.0 / POLL):
                    pre_dump = self.dev._run("shell uiautomator dump /dev/tty").lower()
                    if any(u in pre_dump for u in UNEXPECTED):
                        self.log("         ⚠️   Unexpected popup — dismissing and moving on.")
                        self.dev._run("shell input keyevent 4")
                        time.sleep(0.3)
                        return

            if t > 0 and t % int(30 / POLL) == 0:
                elapsed = round(t * POLL)
                self.log(f"         ⏳  Waiting... ({elapsed}s elapsed)")

        self.log("         ⚠️   Chest still open after 10min — moving on.")



    def run(self):
        try:
            info = self.dev.info()
            if not info["model"]:
                self.log("❌  Device not found."); self.on_done([]); return
            self.log(f"✅  {info['model']}  ·  Android {info['android']}  ·  {info['w']}×{info['h']}")

            if self.cfg.get("mirror") and SCRCPY_EXE:
                try:
                    subprocess.Popen([SCRCPY_EXE, "--serial", self.dev.serial,
                        "--window-title", "TikTok Bot  ·  Live View",
                        "--always-on-top", "--window-width", "380",
                        "--no-audio", "--stay-awake"])
                    self.log("📺  Mirror launched.")
                except Exception as e: self.log(f"⚠️   Mirror: {e}")
                time.sleep(1.5)

            self.dev.wake()

            if self.cfg.get("skip_nav"):
                self.log("📱  Manual mode — starting from current screen.")
                time.sleep(1)
            else:
                self.dev.stop_app(self.pkg); time.sleep(1)
                self.dev.launch_app(self.pkg); time.sleep(4)
                for t in ["Allow", "OK", "Skip", "Not now", "Later"]:
                    self.dev.tap_text([t]); time.sleep(0.3)
                self.goto_live()

            if not self.detector.is_loaded():
                self.log("\n⚠️   No model loaded — go to Train tab first.\n")

            n      = self.cfg["streams"]
            mode   = self.cfg.get("mode", "fast")
            delay  = self.cfg.get("delay", 0.4)
            conf   = self.cfg.get("conf", 0.45)
            tap    = self.cfg.get("tap", True)
            settle, passes = self.MODES.get(mode, self.MODES["fast"])

            self.log(f"\n  {mode.upper()}  ·  {n} streams  ·  conf ≥ {conf}")
            self.log(f"  {self.detector.model_info()}")
            self.log("  " + "─" * 42)

            results = []; t0 = time.time()

            for i in range(n):
                if self._stop: self.log("⏹   Stopped."); break

                # Wait for stream to stabilise — poll brightness variance
                # instead of sleeping a flat duration.
                entry_wait = self.cfg.get("entry_wait", 3.0)
                deadline   = time.time() + settle + entry_wait
                last_bright = None
                while time.time() < deadline:
                    probe = self.dev.screencap()
                    if probe:
                        if NP_OK:
                            arr_np = np.array(probe.convert("L"), dtype=np.float32)
                            bright = float(np.mean(arr_np))
                            var    = float(np.std(arr_np))
                        else:
                            arr = list(probe.convert("L").getdata())
                            bright = sum(arr) / len(arr)
                            var    = 0
                        # Stream is ready when brightness is stable (not still loading)
                        if last_bright is not None and abs(bright - last_bright) < 8 and bright > 30:
                            break
                        last_bright = bright
                    time.sleep(0.35)
                found = []; last_img = None

                # Pipelined scan: start next screencap while running inference
                # on the previous frame — reduces per-scan latency significantly.
                with cf.ThreadPoolExecutor(max_workers=1) as _pool:
                    _next_cap = _pool.submit(self.dev.screencap)
                    for p in range(passes):
                        img = _next_cap.result()
                        if p < passes - 1:
                            _next_cap = _pool.submit(self.dev.screencap)
                        if img:
                            last_img = img
                            dets = self.detector.detect(img, conf)
                            if dets: found = dets; break
                        elif p < passes - 1:
                            time.sleep(settle * 0.2)

                # Always save frame for future training
                if last_img:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
                    try: last_img.save(os.path.join(IMAGES_DIR, f"scan_{ts}.png"))
                    except Exception: pass

                # Filter: only treasure_chest
                found = [d for d in found if d["class_name"] == "treasure_chest"]

                elapsed = time.time() - t0
                spm     = f"{round((i+1)/elapsed*60, 1)}" if elapsed > 2 else "—"
                camps   = list({d["class_name"] for d in found})

                if found:
                    def _tag(d):
                        emoji = next((c[1] for c in CLASSES if c[0] == d["class_name"]), "?")
                        return f'{emoji} {d["class_name"]}  {round(d["conf"]*100)}%'
                    tags = "  ·  ".join(_tag(d) for d in found)
                    self.log(f"  {i+1:>4}/{n}  ✅  {tags}  ({spm}/min)")
                    if tap:
                        tap_w, tap_h = self.dev.size()
                        img_w, img_h = last_img.size if last_img else (tap_w, tap_h)
                        sx, sy = tap_w / img_w, tap_h / img_h

                        # Deduplicate — take one chest per detection pass
                        seen_classes = set()
                        targets = []
                        for d in found:
                            if d["class_name"] not in seen_classes:
                                seen_classes.add(d["class_name"])
                                targets.append(d)

                        for t_idx, orig in enumerate(targets):
                            if t_idx > 0:
                                time.sleep(0.5)

                            x1, y1, x2, y2 = orig["box"]
                            cx = int(((x1+x2)/2) * sx)
                            # Tap upper-third of bounding box — avoids bottom UI overlays
                            cy = int((y1 + (y2-y1)*0.35) * sy)

                            self.dev.tap(cx, cy)
                            self.log(f"         👆  {orig['class_name']} tapped ({cx}, {cy})")
                            self._collect_loop(cx, cy)
                    shot = os.path.join(RESULTS_DIR, f"hit_{i+1:04d}.png")
                    try:
                        if last_img: last_img.save(shot)
                    except Exception: shot = ""
                else:
                    self.log(f"  {i+1:>4}/{n}  —  ({spm}/min)")
                    shot = ""

                result = {
                    "index": i+1, "scan_time": datetime.now(timezone.utc).isoformat(),
                    "campaigns": camps, "has_campaign": bool(found), "screenshot": shot,
                    "detections": [{"class": d["class_name"], "conf": d["conf"]} for d in found],
                }
                results.append(result); self.on_result(result)
                self.dev.swipe_up(150); time.sleep(delay)

            with open(os.path.join(RESULTS_DIR, "results.json"), "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            with open(os.path.join(RESULTS_DIR, "results.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["index","has_campaign","campaigns",
                                                   "scan_time","screenshot"], extrasaction="ignore")
                w.writeheader()
                for r in results:
                    r2 = {**r}; r2["campaigns"] = "|".join(r2.get("campaigns",[])); w.writerow(r2)

            wc = [r for r in results if r["has_campaign"]]
            self.log(f"\n  {'─'*42}")
            self.log(f"  Done  ·  {len(wc)} hits from {len(results)} streams")
            self.on_done(results)
        finally:
            self.dev.close()


# ──────────────────────────────────────────────────────────────────────────────
#  Labeller window
# ──────────────────────────────────────────────────────────────────────────────
class LabelWindow(tk.Toplevel):
    def __init__(self, master, images, start_idx=0, on_close=None):
        super().__init__(master)
        self.title("Label Images")
        self.configure(bg=BG0)
        self.geometry("1060x760")
        self.grab_set()
        self.images = list(images); self.idx = start_idx
        self.on_close = on_close; self.annotations = []
        self.cur_class = tk.IntVar(value=0)
        self._pil_img = self._tk_img = None
        self._scale = 1.0; self._ox = self._oy = 0
        self._img_w = self._img_h = 1
        self._start = (0, 0); self._rect = None
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.images: self._load()

    def _build(self):
        top = tk.Frame(self, bg=BG2, height=46)
        top.pack(fill="x"); top.pack_propagate(False)
        self.nav_lbl = tk.Label(top, text="", font=F(10, "bold"), bg=BG2, fg=FG)
        self.nav_lbl.pack(side="left", padx=16)
        for txt, cmd, side, fg in [
            ("▶", self._next,   "right", FG2),
            ("◀", self._prev,   "right", FG2),
            ("Delete image", self._delete, "right", FG3),
        ]:
            tk.Button(top, text=txt, font=F(9), bg=BG2, fg=fg,
                      relief="flat", cursor="hand2", bd=0,
                      activebackground=BG3, activeforeground=FG,
                      command=cmd).pack(side=side, padx=8)

        body = tk.Frame(self, bg=BG0); body.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(body, bg="#050508", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>",   self._press)
        self.canvas.bind("<B1-Motion>",       self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Configure>",       self._redraw)

        sb = tk.Frame(body, bg=BG2, width=210)
        sb.pack(side="right", fill="y"); sb.pack_propagate(False)
        tk.Label(sb, text="CLASS", font=F(7, "bold"), bg=BG2, fg=FG3, anchor="w"
                 ).pack(fill="x", padx=16, pady=(16, 8))
        for i, (cid, emoji, label, color) in enumerate(CLASSES):
            tk.Radiobutton(sb, text=f"  {emoji}  {label}",
                           variable=self.cur_class, value=i,
                           font=F(10), bg=BG2, fg=FG, selectcolor=BG2,
                           activebackground=BG2, activeforeground=color,
                           indicatoron=0, relief="flat", cursor="hand2",
                           padx=14, pady=9, anchor="w", width=18,
                           highlightthickness=0).pack(fill="x")
        tk.Frame(sb, bg=LINE, height=1).pack(fill="x", padx=14, pady=12)
        tk.Label(sb, text="BOXES", font=F(7, "bold"), bg=BG2, fg=FG3, anchor="w"
                 ).pack(fill="x", padx=16, pady=(0, 6))
        self.box_frame = tk.Frame(sb, bg=BG2); self.box_frame.pack(fill="x", padx=8)
        tk.Frame(sb, bg=LINE, height=1).pack(fill="x", padx=14, pady=12)
        self.stats_lbl = tk.Label(sb, text="", font=FM, bg=BG2, fg=FG3,
                                  justify="left", anchor="w")
        self.stats_lbl.pack(fill="x", padx=16)

        bot = tk.Frame(self, bg=BG2, height=52)
        bot.pack(fill="x"); bot.pack_propagate(False)
        tk.Button(bot, text="Save & Next  ▶", font=F(10, "bold"),
                  bg=ACCENT, fg=WHITE, relief="flat", cursor="hand2", bd=0,
                  padx=20, activebackground="#cc2040", activeforeground=WHITE,
                  command=self._save_next).pack(side="left", padx=12, pady=10)
        for txt, cmd in [("Save", self._save), ("Skip", self._next)]:
            tk.Button(bot, text=txt, font=F(9), bg=BG3, fg=FG2,
                      relief="flat", cursor="hand2", bd=0, padx=14,
                      activebackground=LINE, activeforeground=FG,
                      command=cmd).pack(side="left", padx=(0, 6), pady=10)
        tk.Label(bot, text="Ctrl+Z  undo  ·  Enter  save & next",
                 font=F(8), bg=BG2, fg=FG3).pack(side="right", padx=16)
        self.bind("<Control-z>", lambda _: self._undo())
        self.bind("<Return>",    lambda _: self._save_next())

    def _load(self):
        if not self.images: return
        self.idx = max(0, min(self.idx, len(self.images) - 1))
        path = self.images[self.idx]
        try:
            img = Image.open(path).convert("RGB")
            self._img_w, self._img_h = img.size; self._pil_img = img
        except Exception: return
        self.annotations = load_label(path)
        self.nav_lbl.configure(
            text=f"{self.idx+1} / {len(self.images)}   —   {os.path.basename(path)}")
        self._redraw(); self._refresh_boxes()
        total, lab, boxes = count_labels()
        self.stats_lbl.configure(text=f"{total} images\n{lab} labelled\n{boxes} boxes")

    def _redraw(self, _=None):
        if not self._pil_img: return
        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 700
        scale = min(cw / self._img_w, ch / self._img_h, 1.0)
        self._scale = scale
        dw, dh = int(self._img_w * scale), int(self._img_h * scale)
        self._ox, self._oy = (cw - dw) // 2, (ch - dh) // 2
        self._tk_img = ImageTk.PhotoImage(self._pil_img.resize((dw, dh), Image.LANCZOS))
        self.canvas.delete("all")
        self.canvas.create_image(self._ox, self._oy, anchor="nw", image=self._tk_img)
        for ann in self.annotations:
            cid, cx, cy, w, h = ann
            s = self._scale
            x1 = self._ox + (cx-w/2) * self._img_w * s
            y1 = self._oy + (cy-h/2) * self._img_h * s
            x2 = self._ox + (cx+w/2) * self._img_w * s
            y2 = self._oy + (cy+h/2) * self._img_h * s
            col = CLASS_COLORS.get(CLASS_NAMES[int(cid)] if int(cid) < len(CLASS_NAMES) else "", TEAL)
            lbl_txt = CLASSES[int(cid)][2] if int(cid) < len(CLASSES) else f"#{int(cid)}"
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=col, width=2, tags="box")
            self.canvas.create_rectangle(x1, y1-16, x1+len(lbl_txt)*6+8, y1,
                                         fill=col, outline="", tags="box")
            self.canvas.create_text(x1+4, y1-8, anchor="w", text=lbl_txt,
                                    fill="white", font=F(7, "bold"), tags="box")

    def _col(self): return CLASS_COLORS.get(CLASS_NAMES[self.cur_class.get()], TEAL)
    def _press(self, e): self._start = (e.x, e.y)
    def _drag(self, e):
        if self._rect: self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(
            self._start[0], self._start[1], e.x, e.y,
            outline=self._col(), width=2, dash=(4, 2))
    def _release(self, e):
        if self._rect: self.canvas.delete(self._rect); self._rect = None
        sx, sy = self._start; ex, ey = e.x, e.y
        if abs(ex-sx) < 8 or abs(ey-sy) < 8: return
        s = self._scale
        x1 = (min(sx,ex) - self._ox) / (self._img_w * s)
        y1 = (min(sy,ey) - self._oy) / (self._img_h * s)
        x2 = (max(sx,ex) - self._ox) / (self._img_w * s)
        y2 = (max(sy,ey) - self._oy) / (self._img_h * s)
        x1,y1,x2,y2 = max(0,x1), max(0,y1), min(1,x2), min(1,y2)
        self.annotations.append((self.cur_class.get(), (x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1))
        self._redraw(); self._refresh_boxes()

    def _refresh_boxes(self):
        for w in self.box_frame.winfo_children(): w.destroy()
        for i, ann in enumerate(self.annotations):
            cid  = int(ann[0])
            name = CLASSES[cid][2] if cid < len(CLASSES) else f"class {cid}"
            col  = CLASS_COLORS.get(CLASS_NAMES[cid] if cid < len(CLASS_NAMES) else "", TEAL)
            row  = tk.Frame(self.box_frame, bg=BG2); row.pack(fill="x", pady=1)
            tk.Label(row, text=f"  {name}", font=FM, bg=BG2, fg=col).pack(side="left")
            tk.Button(row, text="✕", font=F(8), bg=BG2, fg=FG3,
                      relief="flat", cursor="hand2", bd=0,
                      command=lambda i=i: self._rm(i)).pack(side="right")

    def _rm(self, i):
        if 0 <= i < len(self.annotations):
            self.annotations.pop(i); self._redraw(); self._refresh_boxes()

    def _undo(self):
        if self.annotations: self.annotations.pop(); self._redraw(); self._refresh_boxes()

    def _save(self):
        if self.images: save_label(self.images[self.idx], self.annotations)

    def _save_next(self): self._save(); self._next()
    def _next(self):
        if self.idx < len(self.images) - 1: self.idx += 1; self._load()
    def _prev(self):
        if self.idx > 0: self.idx -= 1; self._load()

    def _delete(self):
        if not self.images: return
        p = self.images[self.idx]
        if not messagebox.askyesno("Delete", f"Delete {os.path.basename(p)}?", parent=self): return
        try:
            os.remove(p)
            lp = os.path.join(LABELS_DIR, os.path.splitext(os.path.basename(p))[0] + ".txt")
            if os.path.exists(lp): os.remove(lp)
        except Exception: pass
        self.images.pop(self.idx)
        if self.images:
            self.idx = min(self.idx, len(self.images) - 1); self._load()
        else:
            self.nav_lbl.configure(text="No images"); self.canvas.delete("all")

    def _on_close(self):
        self._save()
        if self.on_close: self.on_close()
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────
#  App
# ──────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        try:
            from tkinter import ttk as _t; _t.Style(self)
        except Exception: pass

        self.title("TikTok Campaign Bot")
        self.configure(bg=BG0)
        self.geometry("1060x700")
        self.minsize(900, 580)

        self.detector = YOLODetector()
        self.bot = None; self.running = False; self.results = []

        self.serial_var  = tk.StringVar()
        self.pkg_var     = tk.StringVar(value=TIKTOK_PKGS[0])
        self.mode_var    = tk.StringVar(value="fast")
        self.streams_var = tk.IntVar(value=500)
        self.delay_var   = tk.DoubleVar(value=0.4)
        self.conf_var    = tk.DoubleVar(value=0.45)
        self.mirror_var      = tk.BooleanVar(value=True)
        self.skip_nav        = tk.BooleanVar(value=True)
        self.tap_var         = tk.BooleanVar(value=True)
        self.entry_wait_var = tk.DoubleVar(value=3.0)
        self.epochs_var  = tk.IntVar(value=150)
        self.conn_info   = tk.StringVar(value="")

        self._build()
        self._center()
        self.after(500, self._refresh_devices)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth()-w)//2}+{(self.winfo_screenheight()-h)//2}")

    # ── Shell ──────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG1, height=56)
        hdr.pack(fill="x"); hdr.pack_propagate(False)

        # Left — wordmark with pro pill
        wm = tk.Frame(hdr, bg=BG1); wm.pack(side="left", padx=(20, 0), fill="y")
        tk.Label(wm, text="CHEST", font=("Segoe UI", 14, "bold"),
                 bg=BG1, fg=ACCENT).pack(side="left", pady=14)
        tk.Label(wm, text="BOT", font=("Segoe UI", 14, "bold"),
                 bg=BG1, fg=FG).pack(side="left", pady=14)
        
        badge = tk.Label(wm, text="  v2.0 PRO  ", font=F(8, "bold"),
                         bg=BG3, fg=CYAN, padx=6, pady=2)
        badge.pack(side="left", padx=(8, 0), pady=16)

        # Right — status pills
        pr = tk.Frame(hdr, bg=BG1); pr.pack(side="right", padx=20, fill="y")

        self._model_pill = tk.Label(pr, font=F(8, "bold"), padx=12, pady=3,
                                    bg=BG3, fg=FG3, relief="flat")
        self._model_pill.pack(side="right", padx=(8, 0), pady=14)

        self._status_pill = tk.Label(pr, text="● READY", font=F(8, "bold"),
                                     bg=BG3, fg=GREEN, padx=12, pady=3)
        self._status_pill.pack(side="right", pady=14)
        self._refresh_model_pill()

        # ── Tab bar ───────────────────────────────────────────────────────────
        nav = tk.Frame(self, bg=BG1)
        nav.pack(fill="x")

        self._tab_btns   = []
        self._active_tab = 0

        tab_defs = [("Run Dashboard", "▶"), ("Device Settings", "⬡"), ("Train Model", "◈"), ("User Guide", "?")]
        for i, (name, icon) in enumerate(tab_defs):
            b = tk.Button(nav, text=f"  {icon}  {name}  ",
                          font=F(9), bg=BG1, fg=FG3,
                          relief="flat", cursor="hand2", bd=0,
                          pady=12, activebackground=BG2, activeforeground=FG,
                          command=lambda i=i: self._show(i))
            b.pack(side="left", padx=(4 if i==0 else 0, 0))
            b.bind("<Enter>", lambda e, btn=b, idx=i: btn.configure(fg=FG, bg=BG2) if idx != self._active_tab else None)
            b.bind("<Leave>", lambda e, btn=b, idx=i: btn.configure(fg=FG3, bg=BG1) if idx != self._active_tab else None)
            self._tab_btns.append(b)

        # single sliding red indicator
        self._ind = tk.Frame(nav, bg=ACCENT, height=2)
        self._ind.place(x=0, y=0, width=1, height=2)

        # Separator
        tk.Frame(self, bg=LINE, height=1).pack(fill="x")

        # ── Content frames ────────────────────────────────────────────────────
        cont = tk.Frame(self, bg=BG0); cont.pack(fill="both", expand=True)
        self.frames = [tk.Frame(cont, bg=BG0) for _ in range(4)]
        for f in self.frames: f.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._build_run(self.frames[0])
        self._build_device(self.frames[1])
        self._build_train(self.frames[2])
        self._build_guide(self.frames[3])
        self.after(60, lambda: self._show(0))

    def _show(self, idx):
        self._active_tab = idx
        for i, (f, b) in enumerate(zip(self.frames, self._tab_btns)):
            active = i == idx
            (f.lift if active else f.lower)()
            b.configure(fg=FG if active else FG3,
                        bg=BG1,
                        font=F(9, "bold") if active else F(9))
        b = self._tab_btns[idx]
        b.update_idletasks()
        tx, tw = b.winfo_x(), b.winfo_width()
        self._slide_indicator(tx, tw)

    def _slide_indicator(self, target_x, target_w, steps=14):
        try:
            cur_x = self._ind.winfo_x()
            cur_w = self._ind.winfo_width()
        except Exception:
            cur_x, cur_w = target_x, target_w

        def step(n):
            if n <= 0:
                self._ind.place(x=target_x, width=target_w, height=2, rely=1.0, y=-2)
                return
            t    = 1 - (n / steps)
            ease = t * t * (3 - 2 * t)
            nx   = int(cur_x + (target_x - cur_x) * ease)
            nw   = int(cur_w + (target_w - cur_w) * ease)
            self._ind.place(x=nx, width=nw, height=2, rely=1.0, y=-2)
            self.after(14, lambda: step(n - 1))

        step(steps)

    def _refresh_model_pill(self):
        if getattr(self.detector, "loading", False):
            self._model_pill.configure(text="⏳ LOADING MODEL", fg=AMBER)
            self.after(400, self._refresh_model_pill)
        else:
            ok = self.detector.is_loaded()
            self._model_pill.configure(
                text="● MODEL READY" if ok else "○ NO MODEL",
                fg=GREEN if ok else FG3)
            info = self.detector.model_info()
            col = GREEN if ok else FG3
            if hasattr(self, "run_model_lbl"):
                self.run_model_lbl.configure(text=info, fg=col)
            if hasattr(self, "train_model_lbl"):
                self.train_model_lbl.configure(text=info, fg=col)

    # ── Widget helpers ─────────────────────────────────────────────────────────
    def _card(self, parent, bg=BG2):
        return tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=LINE)

    def _lbl(self, parent, text, bg=BG0):
        return tk.Label(parent, text=text, font=F(8, "bold"),
                        bg=bg, fg=FG3, anchor="w")

    def _section(self, parent, text, bg=BG0):
        """Section header with vibrant accent bar."""
        row = tk.Frame(parent, bg=bg); 
        tk.Frame(row, bg=ACCENT, width=3).pack(side="left", fill="y", pady=2)
        tk.Label(row, text=f"  {text.upper()}", font=F(8, "bold"),
                 bg=bg, fg=FG3, anchor="w").pack(side="left")
        return row

    def _entry(self, parent, var):
        return tk.Entry(parent, textvariable=var, font=FM, bg=BG3, fg=FG,
                        insertbackground=FG, relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=LINE)

    def _tbtn(self, parent, text, cmd, fg=FG2, accent=False):
        bg     = ACCENT if accent else BG3
        bg_hov = "#E11D48" if accent else LINE
        afg    = WHITE if accent else FG
        btn = tk.Button(parent, text=text, font=F(9, "bold" if accent else "normal"), bg=bg, fg=fg,
                        relief="flat", cursor="hand2", bd=0, padx=14, pady=8,
                        activebackground=bg_hov, activeforeground=afg, command=cmd)
        btn.bind("<Enter>", lambda e: btn.configure(bg=bg_hov, fg=afg))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg, fg=fg))
        return btn

    def _slider(self, parent, var, lo, hi, res=1, unit="", color=AMBER):
        row = tk.Frame(parent, bg=BG2); row.pack(fill="x", padx=14, pady=(10, 0))
        lv = tk.StringVar()
        def upd(*_):
            v = var.get()
            lv.set(f"{int(v) if res >= 1 else round(v, 2)}{unit}")
        var.trace_add("write", upd); upd()
        tk.Label(row, textvariable=lv, font=FN, bg=BG2, fg=color).pack(side="right")
        tk.Scale(parent, variable=var, from_=lo, to=hi, resolution=res,
                 orient="horizontal", bg=BG2, fg=FG3, troughcolor=BG3,
                 highlightthickness=0, showvalue=False, sliderlength=14,
                 activebackground=color, bd=0, relief="flat"
                 ).pack(fill="x", padx=14, pady=(2, 10))

    def _check(self, parent, text, var):
        return tk.Checkbutton(parent, text=f"  {text}", variable=var,
                              font=F(9), bg=BG2, fg=FG2, selectcolor=BG2,
                              activebackground=BG2, activeforeground=FG,
                              cursor="hand2", anchor="w")

    def _stat_card(self, parent, label, key, color=CYAN):
        """Big number stat card."""
        c = self._card(parent, BG2); c.pack(fill="x", pady=(0, 6))
        tk.Label(c, text=label, font=F(8, "bold"), bg=BG2, fg=FG3,
                 anchor="w", padx=12, pady=(8, 0)).pack(fill="x")
        v = tk.StringVar(value="—"); self.stat[key] = v
        tk.Label(c, textvariable=v, font=("Segoe UI", 16, "bold"),
                 bg=BG2, fg=color, anchor="w", padx=12, pady=(0, 8)).pack(fill="x")
        return c

    # ── Run tab ────────────────────────────────────────────────────────────────
    def _build_run(self, f):
        # ── Left — log area ───────────────────────────────────────────────────
        left = tk.Frame(f, bg=BG0)
        left.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)

        # Action bar
        ab = tk.Frame(left, bg=BG0); ab.pack(fill="x", pady=(0, 12))

        self.run_btn = tk.Button(ab, text="▶   START SCAN", font=F(10, "bold"),
                                 bg=ACCENT, fg=WHITE, relief="flat", cursor="hand2",
                                 bd=0, padx=24, pady=10,
                                 activebackground="#E11D48", activeforeground=WHITE,
                                 command=self._start)
        self.run_btn.pack(side="left")

        for txt, cmd, clr in [
            ("⏹  Stop",    self._stop_scan,   FG2),
            ("📺  Mirror",  self._mirror,      FG2),
            ("📸  Shot",    self._screenshot,  FG2),
            ("⌫  Clear",   self._clear_log,   FG2),
        ]:
            tk.Button(ab, text=txt, font=F(9), bg=BG2, fg=clr,
                      relief="flat", cursor="hand2", bd=0, padx=12, pady=10,
                      activebackground=BG3, activeforeground=FG,
                      command=cmd).pack(side="left", padx=(6, 0))

        self._tbtn(ab, "📂  Results Folder", self._open_results, fg=CYAN
                   ).pack(side="right")

        # Log box
        lw = tk.Frame(left, bg=BG2, highlightthickness=1, highlightbackground=LINE)
        lw.pack(fill="both", expand=True)

        self.log_box = tk.Text(lw, bg=BG2, fg=FG2, font=FM, relief="flat", bd=0,
                               wrap="word", highlightthickness=0,
                               insertbackground=FG, padx=14, pady=12)
        lsb = tk.Scrollbar(lw, orient="vertical", command=self.log_box.yview,
                           bg=BG2, troughcolor=BG2, relief="flat")
        self.log_box.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")
        self.log_box.tag_configure("hit",  foreground=GREEN)
        self.log_box.tag_configure("warn", foreground=AMBER)

        # Tip bar
        tip = tk.Frame(left, bg=BG2, highlightthickness=1, highlightbackground=LINE)
        tip.pack(fill="x", pady=(10, 0))
        tk.Label(tip, text="  💡  Open TikTok LIVE on your phone, then press Start Scan.",
                 font=F(8), bg=BG2, fg=FG2, anchor="w").pack(fill="x", ipady=6)

        # ── Right — scrollable control panel ─────────────────────────────────
        right_outer = tk.Frame(f, bg=BG0, width=240)
        right_outer.pack(side="right", fill="y", padx=(0, 20), pady=20)
        right_outer.pack_propagate(False)

        rc = tk.Canvas(right_outer, bg=BG0, highlightthickness=0, width=240)
        rs = tk.Scrollbar(right_outer, orient="vertical", command=rc.yview,
                          bg=BG0, troughcolor=BG0, relief="flat")
        rc.configure(yscrollcommand=rs.set)
        rs.pack(side="right", fill="y")
        rc.pack(side="left", fill="both", expand=True)

        right = tk.Frame(rc, bg=BG0, width=224)
        rc.create_window((0, 0), window=right, anchor="nw")
        right.bind("<Configure>", lambda e: rc.configure(scrollregion=rc.bbox("all")))
        rc.bind_all("<MouseWheel>", lambda e: rc.yview_scroll(int(-1*(e.delta/120)), "units"))

        # ── Stats ─────────────────────────────────────────────────────────────
        self._section(right, "LIVE ANALYTICS").pack(fill="x", pady=(0, 8))
        self.stat = {}

        # 2-col grid for stats
        sg = tk.Frame(right, bg=BG0); sg.pack(fill="x", pady=(0, 16))
        sg.columnconfigure(0, weight=1); sg.columnconfigure(1, weight=1)

        def _mini_stat(parent, label, key, color, r, c):
            card = tk.Frame(parent, bg=BG2,
                            highlightthickness=1, highlightbackground=LINE)
            card.grid(row=r, column=c,
                      padx=(0, 4) if c == 0 else (4, 0),
                      pady=(0, 4), sticky="ew")
            tk.Label(card, text=label, font=F(7, "bold"), bg=BG2, fg=FG3,
                     anchor="w", padx=10).pack(fill="x", pady=(6, 0))
            v = tk.StringVar(value="—"); self.stat[key] = v
            tk.Label(card, textvariable=v, font=("Segoe UI", 14, "bold"),
                     bg=BG2, fg=color, anchor="w", padx=10).pack(fill="x", pady=(0, 6))

        _mini_stat(sg, "SCANNED",  "n",    CYAN,   0, 0)
        _mini_stat(sg, "HITS",     "wc",   ACCENT, 0, 1)
        _mini_stat(sg, "HIT RATE", "rate", AMBER,  1, 0)
        _mini_stat(sg, "PER MIN",  "spm",  GREEN,  1, 1)

        # ── Detections ────────────────────────────────────────────────────────
        self._section(right, "LAST DETECTED").pack(fill="x", pady=(0, 6))
        self.det_list = tk.Listbox(right, bg=BG2, fg=FG, font=FM,
                                   selectbackground=BG3, relief="flat", bd=0,
                                   highlightthickness=1, highlightbackground=LINE,
                                   activestyle="none", height=3)
        self.det_list.pack(fill="x", pady=(0, 16))

        # ── Speed ─────────────────────────────────────────────────────────────
        self._section(right, "SCAN SPEED MODE").pack(fill="x", pady=(0, 6))
        spd = self._card(right, BG2); spd.pack(fill="x", pady=(0, 14))
        for val, label in [("turbo", "⚡  Turbo Mode"), ("fast", "🚀  Fast Mode"), ("deep", "🔍  Deep Scan")]:
            tk.Radiobutton(spd, text=label, variable=self.mode_var, value=val,
                           font=F(9), bg=BG2, fg=FG2, selectcolor=BG2,
                           activebackground=BG2, activeforeground=ACCENT,
                           indicatoron=0, relief="flat", cursor="hand2",
                           padx=14, pady=7, anchor="w",
                           highlightthickness=0).pack(fill="x")

        # ── Sliders ───────────────────────────────────────────────────────────
        self._section(right, "STREAMS LIMIT").pack(fill="x", pady=(0, 4))
        sc2 = self._card(right, BG2); sc2.pack(fill="x", pady=(0, 10))
        self._slider(sc2, self.streams_var, 50, 1000)

        self._section(right, "CONFIDENCE THRESHOLD").pack(fill="x", pady=(0, 4))
        cc = self._card(right, BG2); cc.pack(fill="x", pady=(0, 10))
        self._slider(cc, self.conf_var, 0.20, 0.90, res=0.01, color=CYAN)

        self._section(right, "ENTRY WAIT DELAY").pack(fill="x", pady=(0, 4))
        ewc = self._card(right, BG2); ewc.pack(fill="x", pady=(0, 10))
        self._slider(ewc, self.entry_wait_var, 1, 8, unit="s", color=GREEN)

        # ── Options ───────────────────────────────────────────────────────────
        self._section(right, "OPTIONS").pack(fill="x", pady=(0, 6))
        oc = self._card(right, BG2); oc.pack(fill="x", pady=(0, 14))
        self._check(oc, "Mirror screen on start",  self.mirror_var).pack(fill="x", padx=4, pady=3)
        self._check(oc, "Manual live navigation", self.skip_nav).pack(fill="x", padx=4, pady=3)
        self._check(oc, "Auto-tap chest on detect", self.tap_var).pack(fill="x", padx=4, pady=(3, 8))

        # ── Model ─────────────────────────────────────────────────────────────
        self._section(right, "MODEL FILE").pack(fill="x", pady=(0, 6))
        mc = self._card(right, BG2); mc.pack(fill="x")
        self.run_model_lbl = tk.Label(mc, text=self.detector.model_info(),
                                      font=F(8), bg=BG2,
                                      fg=GREEN if self.detector.is_loaded() else FG3,
                                      justify="left", anchor="w", wraplength=200,
                                      padx=12, pady=10)
        self.run_model_lbl.pack(fill="x")

    # ── Device tab ─────────────────────────────────────────────────────────────
    def _build_device(self, f):
        inner = tk.Frame(f, bg=BG0)
        inner.pack(fill="both", expand=True, padx=36, pady=28)
        inner.columnconfigure(0, weight=1); inner.columnconfigure(1, weight=1)

        left = tk.Frame(inner, bg=BG0)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 20))

        self._section(left, "CONNECTED DEVICES").pack(fill="x", pady=(0, 8))
        dc = self._card(left, BG2); dc.pack(fill="x", pady=(0, 16))
        dh = tk.Frame(dc, bg=BG2); dh.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(dh, text="ADB Devices", font=F(9, "bold"), bg=BG2, fg=FG2).pack(side="left")
        tk.Button(dh, text="↻ Refresh", font=F(8, "bold"), bg=BG3, fg=CYAN,
                  relief="flat", cursor="hand2", bd=0, padx=10, pady=4,
                  activebackground=LINE, activeforeground=FG,
                  command=self._refresh_devices).pack(side="right")
        self.dev_list = tk.Listbox(dc, bg=BG3, fg=FG, font=FM, height=4,
                                   relief="flat", bd=0, highlightthickness=0,
                                   activestyle="none", selectbackground=LINE)
        self.dev_list.pack(fill="x", padx=14, pady=(0, 12))
        self.dev_list.bind("<<ListboxSelect>>", self._pick_device)

        self._section(left, "DEVICE SERIAL").pack(fill="x", pady=(0, 6))
        self._entry(left, self.serial_var).pack(fill="x", pady=(0, 16),
                    ipady=6)

        self._section(left, "TIKTOK PACKAGE NAME").pack(fill="x", pady=(0, 6))
        pr = tk.Frame(left, bg=BG0); pr.pack(fill="x")
        self._entry(pr, self.pkg_var).pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(pr, text="Auto Detect", font=F(9, "bold"), bg=BG3, fg=CYAN,
                  relief="flat", cursor="hand2", bd=0, padx=14, pady=6,
                  activebackground=LINE, activeforeground=FG,
                  command=self._detect_pkg).pack(side="right", padx=(8, 0))

        right = tk.Frame(inner, bg=BG0)
        right.grid(row=0, column=1, sticky="nsew")

        self._section(right, "CONNECTION DIAGNOSTICS").pack(fill="x", pady=(0, 8))
        ic = self._card(right, BG2); ic.pack(fill="x", pady=(0, 16))
        self.conn_lbl = tk.Label(ic, textvariable=self.conn_info,
                                 font=F(9), bg=BG2, fg=FG2,
                                 justify="left", anchor="w", wraplength=300,
                                 padx=16, pady=16)
        self.conn_lbl.pack(fill="x")

        tk.Button(right, text="⚡  Test Device Connection", font=F(10, "bold"),
                  bg=ACCENT, fg=WHITE, relief="flat", cursor="hand2",
                  bd=0, padx=20, pady=11, activebackground="#E11D48",
                  activeforeground=WHITE,
                  command=self._test_conn).pack(anchor="w")

    def _refresh_devices(self):
        def do():
            devs = adb_devices()
            def update_ui():
                try:
                    self.dev_list.delete(0, "end")
                    for d in devs: self.dev_list.insert("end", f"  {d}")
                    if devs:
                        self.dev_list.selection_set(0)
                        if not self.serial_var.get().strip():
                            self.serial_var.set(devs[0])
                    else:
                        self.dev_list.insert("end", "  No devices found")
                except Exception: pass
            self.after(0, update_ui)
        threading.Thread(target=do, daemon=True).start()

    def _pick_device(self, _=None):
        sel = self.dev_list.curselection()
        if sel:
            v = self.dev_list.get(sel[0]).strip()
            if v and "No devices" not in v: self.serial_var.set(v)

    def _detect_pkg(self):
        s = self.serial_var.get().strip()
        if not s: messagebox.showwarning("No device", "Select a device first."); return
        self.conn_info.set("Detecting package...")
        def do():
            pkg = ADBDevice(s).find_package()
            def update_ui():
                try:
                    if pkg: self.pkg_var.set(pkg); self.conn_info.set(f"✅  Package found: {pkg}")
                    else: self.conn_info.set("⚠️   TikTok not found on device.")
                except Exception: pass
            self.after(0, update_ui)
        threading.Thread(target=do, daemon=True).start()

    def _test_conn(self):
        s = self.serial_var.get().strip()
        if not s: messagebox.showwarning("No device", "Enter a serial."); return
        self.conn_info.set("Connecting...")
        def do():
            info = ADBDevice(s).info()
            def update_ui():
                try:
                    if info["model"]:
                        self.conn_info.set(
                            f"✅  {info['model']}\nAndroid {info['android']}  ·  {info['w']}×{info['h']}")
                    else:
                        self.conn_info.set("❌  Not responding.\nRun: adb connect 127.0.0.1:5555")
                except Exception: pass
            self.after(0, update_ui)
        threading.Thread(target=do, daemon=True).start()

    # ── Train tab ──────────────────────────────────────────────────────────────
    def _build_train(self, f):
        cols = tk.Frame(f, bg=BG0)
        cols.pack(fill="both", expand=True, padx=24, pady=24)
        cols.columnconfigure(0, weight=1); cols.columnconfigure(1, weight=1)

        left = tk.Frame(cols, bg=BG0)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        tk.Label(left, text="1  Collect & Label Dataset", font=F(12, "bold"),
                 bg=BG0, fg=FG, anchor="w").pack(fill="x", pady=(0, 4))
        tk.Label(left,
            text="Navigate to a stream with a chest visible,\n"
                 "capture it, and draw a box around the element.",
            font=F(9), bg=BG0, fg=FG2, justify="left", anchor="w"
        ).pack(fill="x", pady=(0, 14))

        c1 = self._card(left, BG2); c1.pack(fill="x", pady=(0, 12))
        br = tk.Frame(c1, bg=BG2); br.pack(fill="x", padx=14, pady=14)
        tk.Button(br, text="📸  Capture from Phone", font=F(10, "bold"),
                  bg=ACCENT, fg=WHITE, relief="flat", cursor="hand2", bd=0,
                  padx=16, pady=10, activebackground="#E11D48",
                  command=self._capture_label).pack(side="left")
        tk.Button(br, text="📁  Import Images", font=F(9, "bold"), bg=BG3, fg=CYAN,
                  relief="flat", cursor="hand2", bd=0, padx=14, pady=10,
                  activebackground=LINE, activeforeground=FG,
                  command=self._import_label).pack(side="left", padx=(10, 0))
        self.cap_status = tk.Label(c1, text="", font=FM, bg=BG2,
                                   fg=GREEN, anchor="w", padx=14)
        self.cap_status.pack(fill="x", pady=(0, 10))

        ds = self._card(left, BG2); ds.pack(fill="x", pady=(0, 12))
        self._section(ds, "DATASET SUMMARY", bg=BG2).pack(fill="x", padx=14, pady=(12, 6))
        self.ds_lbl = tk.Label(ds, text=self._ds_text(),
                               font=FN, bg=BG2, fg=CYAN,
                               justify="left", anchor="w")
        self.ds_lbl.pack(fill="x", padx=14, pady=(0, 12))
        br2 = tk.Frame(ds, bg=BG2); br2.pack(fill="x", padx=14, pady=(0, 14))
        tk.Button(br2, text="Open Label Tool", font=F(9, "bold"), bg=BG3, fg=CYAN,
                  relief="flat", cursor="hand2", bd=0, padx=12, pady=7,
                  activebackground=LINE, activeforeground=FG,
                  command=self._open_labeller).pack(side="left")
        tk.Button(br2, text="Open Folder", font=F(9), bg=BG3, fg=FG2,
                  relief="flat", cursor="hand2", bd=0, padx=12, pady=7,
                  activebackground=LINE, activeforeground=FG,
                  command=lambda: os.startfile(DATA_DIR) if os.name == "nt" else None
                  ).pack(side="left", padx=(8, 0))

        right = tk.Frame(cols, bg=BG0)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(right, text="2  Train YOLO Model", font=F(12, "bold"),
                 bg=BG0, fg=FG, anchor="w").pack(fill="x", pady=(0, 4))
        tk.Label(right,
            text="Train YOLO on your labelled images.\nFirst run downloads yolov8n.pt (~6 MB).",
            font=F(9), bg=BG0, fg=FG2, justify="left", anchor="w"
        ).pack(fill="x", pady=(0, 14))

        tc = self._card(right, BG2); tc.pack(fill="x", pady=(0, 14))
        ep_row = tk.Frame(tc, bg=BG2); ep_row.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(ep_row, text="Epochs", font=F(9, "bold"), bg=BG2, fg=FG2).pack(side="left")
        self.ep_lbl = tk.Label(ep_row, text="150", font=FN, bg=BG2, fg=AMBER)
        self.ep_lbl.pack(side="right")
        self.epochs_var.trace_add("write",
            lambda *_: self.ep_lbl.configure(text=str(self.epochs_var.get())))
        tk.Scale(tc, variable=self.epochs_var, from_=10, to=200, resolution=5,
                 orient="horizontal", bg=BG2, fg=FG3, troughcolor=BG3,
                 highlightthickness=0, showvalue=False, sliderlength=14,
                 activebackground=AMBER, bd=0, relief="flat"
                 ).pack(fill="x", padx=14, pady=(0, 4))
        tk.Label(tc, text="  50 for quick test · 150+ for production accuracy.",
                 font=F(8), bg=BG2, fg=FG3, anchor="w"
                 ).pack(fill="x", pady=(0, 12))

        self.train_btn = tk.Button(right, text="🏋  Start Training Model",
            font=F(10, "bold"), bg=ACCENT, fg=WHITE, relief="flat",
            cursor="hand2", bd=0, padx=20, pady=11,
            activebackground="#E11D48", command=self._start_training)
        self.train_btn.pack(anchor="w", pady=(0, 14))

        ms = self._card(right, BG2); ms.pack(fill="x", pady=(0, 12))
        self._section(ms, "ACTIVE MODEL STATUS", bg=BG2).pack(fill="x", padx=14, pady=(12, 6))
        self.train_model_lbl = tk.Label(ms, text=self.detector.model_info(),
                                        font=F(9), bg=BG2,
                                        fg=GREEN if self.detector.is_loaded() else FG3,
                                        justify="left", anchor="w")
        self.train_model_lbl.pack(fill="x", padx=14, pady=(0, 6))
        tk.Button(ms, text="Reload Model Weights", font=F(8, "bold"), bg=BG2, fg=CYAN,
                  relief="flat", cursor="hand2", bd=0, padx=14,
                  activebackground=BG3, activeforeground=FG,
                  command=self._reload_model).pack(anchor="w", pady=(0, 12))

        tk.Frame(f, bg=LINE, height=1).pack(fill="x", padx=24)
        self._section(f, "TRAINING PROCESS LOG").pack(fill="x", padx=24, pady=(12, 6))
        lw2 = tk.Frame(f, bg=BG2, highlightthickness=1, highlightbackground=LINE)
        lw2.pack(fill="x", padx=24, pady=(0, 16))
        self.train_log = tk.Text(lw2, bg=BG2, fg=FG2, font=FM, height=7,
                                 relief="flat", bd=0, wrap="word",
                                 highlightthickness=0, padx=14, pady=10)
        tsb = tk.Scrollbar(lw2, orient="vertical", command=self.train_log.yview,
                           bg=BG2, troughcolor=BG2, relief="flat")
        self.train_log.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y"); self.train_log.pack(fill="x")
        self.train_log.configure(state="disabled")

    def _ds_text(self):
        total, lab, boxes = count_labels()
        return f"{total} images  ·  {lab} labelled  ·  {boxes} boxes"

    def _capture_label(self):
        s = self.serial_var.get().strip()
        if not s: messagebox.showwarning("No device", "Select a device in the Device tab."); return
        self.cap_status.configure(text="Capturing...", fg=AMBER); self.update()
        def do():
            img = ADBDevice(s).screencap()
            if not img:
                self.after(0, lambda: self.cap_status.configure(
                    text="❌  Screencap failed", fg=RED)); return
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(IMAGES_DIR, f"capture_{ts}.png")
            img.save(path)
            self.after(0, self._open_labeller, path)
        threading.Thread(target=do, daemon=True).start()

    def _import_label(self):
        paths = filedialog.askopenfilenames(
            title="Select screenshots",
            filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if not paths: return
        imported = []
        for p in paths:
            ts   = datetime.now().strftime("%H%M%S%f")
            dest = os.path.join(IMAGES_DIR, f"import_{ts}.png")
            try: Image.open(p).convert("RGB").save(dest); imported.append(dest)
            except Exception: pass
        if imported: self._open_labeller(imported[0])

    def _open_labeller(self, start_path=None):
        images = sorted([os.path.join(IMAGES_DIR, f)
                         for f in os.listdir(IMAGES_DIR) if f.lower().endswith(".png")])
        if not images:
            messagebox.showinfo("No images",
                "No images in training_data/images/ yet.\nCapture some first."); return
        idx = images.index(start_path) if start_path in images else 0
        def on_close():
            t = self._ds_text()
            self.ds_lbl.configure(text=t)
            self.cap_status.configure(text=f"✅  {t}", fg=GREEN)
        LabelWindow(self, images, idx, on_close)

    def _start_training(self):
        _, lab, _ = count_labels()
        if lab < 5:
            messagebox.showwarning("Not enough data",
                f"Only {lab} labelled images.\nNeed at least 5 (aim for 30+)."); return
        self.train_btn.configure(state="disabled", text="Training...", bg=FG3)
        self._tlog("─" * 42)

        def done(ok):
            self.train_btn.configure(state="normal", text="🏋  Start Training", bg=ACCENT)
            if ok:
                self.detector.reload()
                info = self.detector.model_info()
                col  = GREEN if self.detector.is_loaded() else FG3
                self.train_model_lbl.configure(text=info, fg=col)
                self.run_model_lbl.configure(text=info, fg=col)
                self._refresh_model_pill()
                self._tlog("✅  Model ready — go to the Run tab.")

        run_training(self.epochs_var.get(),
                     log_fn=lambda m: self.after(0, self._tlog, m),
                     done_fn=lambda ok: self.after(0, done, ok))

    def _reload_model(self):
        self.detector.reload()
        info = self.detector.model_info()
        col  = GREEN if self.detector.is_loaded() else FG3
        self.train_model_lbl.configure(text=info, fg=col)
        self.run_model_lbl.configure(text=info, fg=col)
        self._refresh_model_pill()

    def _tlog(self, msg):
        self.train_log.configure(state="normal")
        self.train_log.insert("end", msg + "\n")
        self.train_log.see("end")
        self.train_log.configure(state="disabled")

    # ── Guide tab ──────────────────────────────────────────────────────────────
    def _build_guide(self, f):
        wrap = tk.Frame(f, bg=BG0); wrap.pack(fill="both", expand=True, padx=20, pady=20)
        txt = tk.Text(wrap, bg=BG0, fg=FG2, font=("Segoe UI", 9), relief="flat", bd=0,
                      wrap="word", highlightthickness=0, padx=28, pady=24, spacing1=2)
        gsb = tk.Scrollbar(wrap, orient="vertical", command=txt.yview,
                           bg=BG0, troughcolor=BG0, relief="flat")
        txt.configure(yscrollcommand=gsb.set)
        gsb.pack(side="right", fill="y"); txt.pack(fill="both", expand=True)

        txt.tag_configure("h1",   font=F(13, "bold"), foreground=FG,   spacing1=22, spacing3=4)
        txt.tag_configure("step", font=F(8, "bold"),  foreground=ACCENT, spacing1=4)
        txt.tag_configure("body", font=("Segoe UI", 9), foreground=FG2, spacing1=2)
        txt.tag_configure("code", font=FM,             foreground=CYAN,  spacing1=2)
        txt.tag_configure("tip",  font=F(8),           foreground=AMBER, spacing1=6)
        txt.tag_configure("rule", font=F(1),           foreground=LINE,  spacing1=8, spacing3=8)

        def h(t):  txt.insert("end", t + "\n",   "h1")
        def s(t):  txt.insert("end", t + "\n",   "step")
        def p(t):  txt.insert("end", t + "\n",   "body")
        def c(t):  txt.insert("end", t + "\n",   "code")
        def tip(t):txt.insert("end", "💡  " + t + "\n", "tip")
        def rule(): txt.insert("end", "─" * 60 + "\n", "rule")

        h("Quick Start")
        rule()
        s("① SETUP")
        c("    pip install Pillow numpy ultralytics")
        p("    Connect phone via USB cable.\n"
          "    Settings → About phone → tap Build number 7×\n"
          "    Settings → Developer options → USB Debugging ON\n"
          "    Tap Allow when the phone prompts you.")

        s("② COLLECT TRAINING DATA")
        p("    Go to the Train tab.\n"
          "    Find a TikTok LIVE stream with a chest visible.\n"
          "    Click Capture from Phone — the labeller opens.\n"
          "    Draw a tight box around the chest, click Save & Next.\n"
          "    Aim for 30+ examples across different streams.")
        tip("Capture at different animation stages for best accuracy.")

        s("③ TRAIN")
        p("    Train tab → Start Training.\n"
          "    First run downloads yolov8n.pt (~6 MB) automatically.\n"
          "    Takes 5–15 min. Watch progress in the output panel.\n"
          "    When done, best.pt is saved to the model/ folder.")

        s("④ SCAN")
        p("    Open TikTok LIVE on your phone.\n"
          "    Run tab → press Start.\n"
          "    All scan frames auto-save to training_data/images/\n"
          "    so you can label and retrain after every session.")

        s("⑤ RETRAIN TO IMPROVE")
        p("    After scanning, Train tab → Open label tool.\n"
          "    New frames from the scan will be there waiting.\n"
          "    Label chests, then hit Start Training again.")
        tip("More labelled data = higher confidence = fewer missed chests.")

        rule()
        h("Paths")
        c(f"    Training data  →  {DATA_DIR}")
        c(f"    Model          →  {MODEL_PATH}")
        c(f"    Results        →  {RESULTS_DIR}")
        c(f"    ADB            →  {ADB_EXE}")
        c(f"    scrcpy         →  {SCRCPY_EXE or 'not found'}")

        txt.configure(state="disabled")

    # ── Actions ────────────────────────────────────────────────────────────────
    def _log(self, msg, tag=None):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n", tag or "")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _open_results(self):
        if os.name == "nt": os.startfile(RESULTS_DIR)

    def _mirror(self):
        s = self.serial_var.get().strip()
        if not s: messagebox.showwarning("No device", "Select a device first."); return
        if not SCRCPY_EXE:
            messagebox.showerror("Not found",
                "scrcpy not found.\nhttps://github.com/Genymobile/scrcpy/releases"); return
        try:
            subprocess.Popen([SCRCPY_EXE, "--serial", s,
                "--window-title", "TikTok Bot  ·  Live View",
                "--always-on-top", "--window-width", "380",
                "--no-audio", "--stay-awake"])
            self._log(f"📺  Mirror: {s}")
        except Exception as e: self._log(f"❌  {e}", "warn")

    def _screenshot(self):
        s = self.serial_var.get().strip()
        if not s: messagebox.showwarning("No device", "Select a device first."); return
        img = ADBDevice(s).screencap()
        if img:
            p = os.path.join(RESULTS_DIR, f"manual_{datetime.now().strftime('%H%M%S')}.png")
            img.save(p); self._log(f"📸  {p}")
        else: self._log("⚠️   Screencap failed.", "warn")

    def _stop_scan(self):
        if self.bot: self.bot.stop(); self._log("⏹   Stop requested...")

    def _on_result(self, r):
        self.results.append(r)
        if r["has_campaign"]:
            def _t(c2):
                return f'{next((c[1] for c in CLASSES if c[0]==c2), "?")} {c2}'
            tags = "  ·  ".join(_t(c2) for c2 in r.get("campaigns", []))
            self._log(f"  {r['index']:>4}  ✅  {tags}", "hit")
        else:
            self._log(f"  {r['index']:>4}  —")

        wc = [x for x in self.results if x["has_campaign"]]
        n  = len(self.results)
        self.stat["n"].set(str(n))
        self.stat["wc"].set(str(len(wc)))
        self.stat["rate"].set(f"{round(len(wc)/n*100, 1)}%" if n else "—")
        try:
            from datetime import datetime as dt
            diff = (dt.fromisoformat(r["scan_time"]) -
                    dt.fromisoformat(self.results[0]["scan_time"])).total_seconds()
            if diff > 0: self.stat["spm"].set(f"{round(n/diff*60, 1)}")
        except Exception: pass

        cc = {}
        for x in wc:
            for c in x["campaigns"]: cc[c] = cc.get(c, 0) + 1
        self.det_list.delete(0, "end")
        for c, cnt in sorted(cc.items(), key=lambda x: -x[1]):
            e = next((cl[1] for cl in CLASSES if cl[0] == c), "")
            l = next((cl[2] for cl in CLASSES if cl[0] == c), c)
            self.det_list.insert("end", f"  {e}  {l}  ×{cnt}")

    def _on_done(self, _):
        self.running = False; self.bot = None
        self.run_btn.configure(text="▶   START", bg=ACCENT, state="normal")
        self._status_pill.configure(text="● DONE", fg=GREEN)

    def _start(self):
        if self.running: return
        serial  = self.serial_var.get().strip()
        package = self.pkg_var.get().strip()
        if not serial:
            messagebox.showwarning("No device", "Go to the Device tab first."); return
        if not PIL_OK:
            messagebox.showerror("Missing", "Run:  pip install Pillow numpy ultralytics"); return

        self.running = True; self.results = []
        self.run_btn.configure(text="⏳  RUNNING", bg=BG3, fg=FG2, state="disabled")
        self._status_pill.configure(text="● SCANNING", fg=CYAN)
        self._log(f"  {'─'*40}")
        self._log(f"  {datetime.now().strftime('%H:%M:%S')}  ·  {serial}")

        cfg = {
            "streams":        int(self.streams_var.get()),
            "mode":           self.mode_var.get(),
            "delay":          float(self.delay_var.get()),
            "conf":           round(self.conf_var.get(), 2),
            "mirror":         self.mirror_var.get(),
            "skip_nav":       self.skip_nav.get(),
            "tap":            self.tap_var.get(),
            "entry_wait":     float(self.entry_wait_var.get()),
        }

        self.bot = Bot(serial, package, cfg,
                       log=lambda m: self.after(0, self._log, m),
                       on_result=lambda r: self.after(0, self._on_result, r),
                       on_done=lambda r: self.after(0, self._on_done, r),
                       detector=self.detector)

        def run():
            try: self.bot.run()
            except Exception as e:
                self.after(0, self._log, f"❌  {e}", "warn")
                self.after(0, self._log, traceback.format_exc(), "warn")
                self.after(0, self._on_done, [])

        threading.Thread(target=run, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try: App().mainloop()
    except Exception: traceback.print_exc(); input("Press Enter...")
