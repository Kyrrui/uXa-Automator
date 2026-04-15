"""
uXa Automator — Native Windows/macOS key/mouse automation with a repeatable action queue.

Requirements:
    pip install pynput pillow

Run:
    python auto_input.py
"""

import tkinter as tk
from tkinter import ttk, filedialog
import threading
import time
import uuid
import json
import os
import sys
import random


# ─── Theme ────────────────────────────────────────────────────────────────────

BG = "#0a0a0f"
SURFACE = "#131320"
SURFACE2 = "#1b1b2e"
BORDER = "#2a2a42"
BORDER_HI = "#3d3d5c"
TEXT = "#e0e0f0"
TEXT_DIM = "#6e6e8e"
ACCENT = "#00e5a0"
ACCENT_DIM = "#0d2e24"
DANGER = "#ff4a6a"
DANGER_DIM = "#2e0d14"
WARNING = "#ffb84a"


# ─── App ──────────────────────────────────────────────────────────────────────

class AutoInputApp:
    def __init__(self, root):
        self.root = root
        self.root.title("uXa Automator")

        # Set window icon
        icon_path = os.path.join(
            getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))),
            "uxa-no-background.png"
        )
        if os.path.exists(icon_path):
            try:
                icon_img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon_img)
                self._icon_ref = icon_img  # prevent garbage collection
            except tk.TclError:
                pass
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # State — queue is a list of steps; each step is either a pause or a
        # group of concurrent actions that fire simultaneously.
        # Group step: {"id", "type": "group", "actions": [action, ...]}
        # Pause step: {"id", "type": "pause", "duration": float}
        self.queue = []  # list of step dicts
        self.selected_step_id = None  # currently selected step for "Add to Step"
        self.collapsed_steps = set()  # step IDs that are collapsed
        self.running = False
        self.worker_thread = None
        self.stop_event = threading.Event()

        # ── Styles ────────────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Dim.TLabel", background=BG, foreground=TEXT_DIM, font=("Consolas", 9))
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 16))
        style.configure("Section.TLabel", background=BG, foreground=TEXT_DIM, font=("Consolas", 9, "bold"))
        style.configure("Accent.TLabel", background=BG, foreground=ACCENT, font=("Consolas", 10, "bold"))
        style.configure("Status.TLabel", background=SURFACE2, foreground=TEXT_DIM, font=("Consolas", 9))

        # Main container
        main = ttk.Frame(root, style="TFrame")
        main.pack(padx=24, pady=20)

        # Header
        hdr = ttk.Frame(main, style="TFrame")
        hdr.pack(fill="x", pady=(0, 16))
        # Load logo for header
        logo_path = os.path.join(
            getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))),
            "uxa-no-background.png"
        )
        if os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                logo_img = Image.open(logo_path).resize((36, 36), Image.LANCZOS)
                self._header_logo = ImageTk.PhotoImage(logo_img)
                tk.Label(hdr, image=self._header_logo, bg=BG).pack(side="left", padx=(0, 8))
            except Exception:
                pass
        ttk.Label(hdr, text="uXa Automator", style="Header.TLabel").pack(side="left")

        # ── Add Action Section ────────────────────────────────────────────
        ttk.Label(main, text="ADD ACTION", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

        add_frame = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, bd=0)
        add_frame.pack(fill="x", pady=(0, 12))
        add_inner = tk.Frame(add_frame, bg=SURFACE)
        add_inner.pack(padx=14, pady=14)

        # Row 1: Type selector
        r1 = tk.Frame(add_inner, bg=SURFACE)
        r1.pack(fill="x", pady=(0, 10))

        self.action_type = tk.StringVar(value="key_hold")

        types = [
            ("Hold Key", "key_hold"),
            ("Press Key", "key_press"),
            ("Hold Mouse", "mouse_hold"),
            ("Click Mouse", "mouse_click"),
            ("Pause", "pause"),
        ]

        for i, (label, val) in enumerate(types):
            rb = tk.Radiobutton(
                r1, text=label, variable=self.action_type, value=val,
                bg=SURFACE, fg=TEXT_DIM, selectcolor=SURFACE2,
                activebackground=SURFACE, activeforeground=ACCENT,
                font=("Segoe UI", 9), indicatoron=0,
                padx=10, pady=6, bd=0, relief="flat",
                highlightbackground=BORDER, highlightthickness=1,
                command=self._on_type_change,
            )
            rb.pack(side="left", padx=(0, 4))
            # Style the selected one
            rb.configure(selectcolor=ACCENT_DIM)

        # Row 2: Input config
        r2 = tk.Frame(add_inner, bg=SURFACE)
        r2.pack(fill="x", pady=(0, 10))

        # Key capture
        self.key_frame = tk.Frame(r2, bg=SURFACE)
        self.key_frame.pack(side="left", fill="x", expand=True, padx=(0, 8))

        tk.Label(self.key_frame, text="KEY", bg=SURFACE, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.key_capture_btn = tk.Button(
            self.key_frame, text="Click & press a key", bg=SURFACE2, fg=TEXT_DIM,
            font=("Consolas", 11), bd=0, relief="flat",
            highlightbackground=BORDER, highlightthickness=1,
            activebackground=SURFACE2, activeforeground=ACCENT,
            width=22, pady=8,
        )
        self.key_capture_btn.pack(fill="x")
        self.key_capture_btn.bind("<Button-1>", self._start_key_capture)
        self.captured_key = None
        self.captured_key_name = None

        # Mouse button selector
        self.mouse_frame = tk.Frame(r2, bg=SURFACE)

        tk.Label(self.mouse_frame, text="BUTTON", bg=SURFACE, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.mouse_btn_var = tk.StringVar(value="left")
        mb_frame = tk.Frame(self.mouse_frame, bg=SURFACE)
        mb_frame.pack()
        for btn_name in ["left", "middle", "right"]:
            rb = tk.Radiobutton(
                mb_frame, text=btn_name.title(), variable=self.mouse_btn_var, value=btn_name,
                bg=SURFACE, fg=TEXT_DIM, selectcolor=ACCENT_DIM,
                activebackground=SURFACE, activeforeground=ACCENT,
                font=("Segoe UI", 9), indicatoron=0,
                padx=12, pady=6, bd=0, relief="flat",
                highlightbackground=BORDER, highlightthickness=1,
            )
            rb.pack(side="left", padx=(0, 4))

        # Duration
        self.dur_frame = tk.Frame(r2, bg=SURFACE)
        self.dur_frame.pack(side="left")

        tk.Label(self.dur_frame, text="DURATION (s)", bg=SURFACE, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.duration_var = tk.StringVar(value="5.0")
        dur_entry = tk.Entry(
            self.dur_frame, textvariable=self.duration_var, bg=SURFACE2, fg=TEXT,
            font=("Consolas", 11), bd=0, relief="flat", width=8,
            insertbackground=ACCENT, highlightbackground=BORDER, highlightthickness=1,
        )
        dur_entry.pack(pady=(0, 0))

        # Interval (for press/click modes)
        self.interval_frame = tk.Frame(r2, bg=SURFACE)

        tk.Label(self.interval_frame, text="INTERVAL (ms)", bg=SURFACE, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.interval_var = tk.StringVar(value="100")
        int_entry = tk.Entry(
            self.interval_frame, textvariable=self.interval_var, bg=SURFACE2, fg=TEXT,
            font=("Consolas", 11), bd=0, relief="flat", width=8,
            insertbackground=ACCENT, highlightbackground=BORDER, highlightthickness=1,
        )
        int_entry.pack()

        # Count (optional, for press/click modes — overrides duration)
        self.count_frame = tk.Frame(r2, bg=SURFACE)

        tk.Label(self.count_frame, text="COUNT (optional)", bg=SURFACE, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.count_var = tk.StringVar(value="")
        tk.Entry(
            self.count_frame, textvariable=self.count_var, bg=SURFACE2, fg=TEXT,
            font=("Consolas", 11), bd=0, relief="flat", width=8,
            insertbackground=ACCENT, highlightbackground=BORDER, highlightthickness=1,
        ).pack()

        # Add buttons
        add_btns = tk.Frame(add_inner, bg=SURFACE)
        add_btns.pack(fill="x", pady=(4, 0))

        self.add_btn = tk.Button(
            add_btns, text="＋ Add New Step", bg=ACCENT_DIM, fg=ACCENT,
            font=("Segoe UI Semibold", 10), bd=0, relief="flat", pady=8,
            activebackground=ACCENT, activeforeground=BG,
            highlightbackground=ACCENT, highlightthickness=1,
            command=self._add_new_step,
        )
        self.add_btn.pack(fill="x")

        self.add_to_step_btn = tk.Button(
            add_btns, text="＋ Add to Selected Step (concurrent)", bg=SURFACE2, fg=TEXT_DIM,
            font=("Segoe UI", 9), bd=0, relief="flat", pady=6,
            activebackground=SURFACE2, activeforeground=TEXT_DIM,
            highlightbackground=BORDER, highlightthickness=1,
            command=self._add_to_step, state="disabled",
        )
        self.add_to_step_btn.pack(fill="x", pady=(4, 0))

        self._on_type_change()

        # ── Queue ─────────────────────────────────────────────────────────
        ttk.Label(main, text="ACTION QUEUE", style="Section.TLabel").pack(anchor="w", pady=(4, 6))

        queue_outer = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, bd=0)
        queue_outer.pack(fill="x", pady=(0, 12))

        # Scrollable queue list
        self.queue_canvas = tk.Canvas(queue_outer, bg=SURFACE, highlightthickness=0, height=160, bd=0)
        self.queue_scrollbar = tk.Scrollbar(queue_outer, orient="vertical", command=self.queue_canvas.yview)
        self.queue_list_frame = tk.Frame(self.queue_canvas, bg=SURFACE)

        self.queue_list_frame.bind("<Configure>", lambda e: self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all")))
        self.queue_canvas.create_window((0, 0), window=self.queue_list_frame, anchor="nw", tags="frame")
        self.queue_canvas.configure(yscrollcommand=self.queue_scrollbar.set)
        self.queue_canvas.bind("<Configure>", lambda e: self.queue_canvas.itemconfig("frame", width=e.width))

        self.queue_canvas.pack(side="left", fill="both", expand=True)
        self.queue_scrollbar.pack(side="right", fill="y")

        self.empty_label = tk.Label(
            self.queue_list_frame, text="No actions yet — add one above",
            bg=SURFACE, fg=TEXT_DIM, font=("Consolas", 9), pady=60,
        )
        self.empty_label.pack()

        # Queue buttons row
        qbtn_frame = tk.Frame(main, bg=BG)
        qbtn_frame.pack(fill="x", pady=(0, 12))

        self.clear_btn = tk.Button(
            qbtn_frame, text="Clear All", bg=SURFACE2, fg=TEXT_DIM,
            font=("Segoe UI", 9), bd=0, pady=6, padx=16,
            highlightbackground=BORDER, highlightthickness=1,
            activebackground=DANGER_DIM, activeforeground=DANGER,
            command=self._clear_queue,
        )
        self.clear_btn.pack(side="left")

        tk.Button(
            qbtn_frame, text="Save", bg=SURFACE2, fg=TEXT_DIM,
            font=("Segoe UI", 9), bd=0, pady=6, padx=16,
            highlightbackground=BORDER, highlightthickness=1,
            activebackground=ACCENT_DIM, activeforeground=ACCENT,
            command=self._save_queue,
        ).pack(side="right", padx=(4, 0))

        tk.Button(
            qbtn_frame, text="Load", bg=SURFACE2, fg=TEXT_DIM,
            font=("Segoe UI", 9), bd=0, pady=6, padx=16,
            highlightbackground=BORDER, highlightthickness=1,
            activebackground=ACCENT_DIM, activeforeground=ACCENT,
            command=self._load_queue,
        ).pack(side="right")

        # ── Controls ──────────────────────────────────────────────────────
        ttk.Label(main, text="CONTROLS", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

        ctrl_row1 = tk.Frame(main, bg=BG)
        ctrl_row1.pack(fill="x", pady=(0, 8))

        # Delay
        delay_f = tk.Frame(ctrl_row1, bg=BG)
        delay_f.pack(side="left", padx=(0, 16))
        tk.Label(delay_f, text="START DELAY (s)", bg=BG, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.delay_var = tk.StringVar(value="3")
        tk.Entry(
            delay_f, textvariable=self.delay_var, bg=SURFACE2, fg=TEXT,
            font=("Consolas", 11), bd=0, width=8,
            insertbackground=ACCENT, highlightbackground=BORDER, highlightthickness=1,
        ).pack()

        # Start key
        start_k = tk.Frame(ctrl_row1, bg=BG)
        start_k.pack(side="left", padx=(0, 16))
        tk.Label(start_k, text="START KEY", bg=BG, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.start_key_btn = tk.Button(
            start_k, text="F6", bg=SURFACE2, fg=ACCENT,
            font=("Consolas", 10), bd=0, relief="flat", width=12, pady=4,
            highlightbackground=BORDER, highlightthickness=1,
            activebackground=SURFACE2, activeforeground=ACCENT,
        )
        self.start_key_btn.pack()
        self.start_key_btn.bind("<Button-1>", self._start_start_key_capture)
        self._start_key = None  # pynput Key object, set by _start_global_hotkey

        # Stop key
        stop_f = tk.Frame(ctrl_row1, bg=BG)
        stop_f.pack(side="left", padx=(0, 16))
        tk.Label(stop_f, text="STOP KEY", bg=BG, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.stop_key_btn = tk.Button(
            stop_f, text="Escape", bg=SURFACE2, fg=DANGER,
            font=("Consolas", 10), bd=0, relief="flat", width=12, pady=4,
            highlightbackground=BORDER, highlightthickness=1,
            activebackground=SURFACE2, activeforeground=ACCENT,
        )
        self.stop_key_btn.pack()
        self.stop_key_btn.bind("<Button-1>", self._start_stop_key_capture)
        self._stop_key = None  # pynput Key object, set by _start_global_hotkey

        ctrl_row2 = tk.Frame(main, bg=BG)
        ctrl_row2.pack(fill="x", pady=(0, 6))

        # Repeat
        repeat_f = tk.Frame(ctrl_row2, bg=BG)
        repeat_f.pack(side="left", padx=(0, 16))
        self.repeat_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            repeat_f, text="Loop queue", variable=self.repeat_var,
            bg=BG, fg=TEXT, selectcolor=SURFACE2,
            activebackground=BG, activeforeground=ACCENT,
            font=("Segoe UI", 10),
        ).pack(anchor="w")
        tk.Label(repeat_f, text="Repeat queue when finished",
                 bg=BG, fg=TEXT_DIM, font=("Consolas", 7)).pack(anchor="w")

        # Variance (used by per-step humanize)
        variance_f = tk.Frame(ctrl_row2, bg=BG)
        variance_f.pack(side="left", padx=(0, 16))
        tk.Label(variance_f, text="VARIANCE %", bg=BG, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.variance_var = tk.StringVar(value="15")
        tk.Entry(
            variance_f, textvariable=self.variance_var, bg=SURFACE2, fg=TEXT,
            font=("Consolas", 11), bd=0, width=5,
            insertbackground=ACCENT, highlightbackground=BORDER, highlightthickness=1,
        ).pack(anchor="w")
        tk.Label(variance_f, text="For steps set to Humanized",
                 bg=BG, fg=TEXT_DIM, font=("Consolas", 7)).pack(anchor="w")

        # Start / Stop
        btn_frame = tk.Frame(main, bg=BG)
        btn_frame.pack(fill="x", pady=(8, 8))

        self.start_btn = tk.Button(
            btn_frame, text="▶  Start", bg=ACCENT, fg=BG,
            font=("Segoe UI Semibold", 12), bd=0, pady=10,
            activebackground="#00cc8e", activeforeground=BG,
            command=self._start,
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.stop_btn = tk.Button(
            btn_frame, text="■  Stop", bg=DANGER_DIM, fg=DANGER,
            font=("Segoe UI Semibold", 12), bd=0, pady=10,
            activebackground=DANGER, activeforeground="#fff",
            highlightbackground=DANGER, highlightthickness=1,
            command=self._stop, state="disabled",
        )
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Status bar
        self.status_frame = tk.Frame(main, bg=SURFACE2, highlightbackground=BORDER, highlightthickness=1)
        self.status_frame.pack(fill="x", pady=(8, 0))

        self.status_dot = tk.Canvas(self.status_frame, width=10, height=10, bg=SURFACE2, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(10, 6), pady=10)
        self._draw_dot(TEXT_DIM)

        self.status_label = tk.Label(
            self.status_frame, text="Idle", bg=SURFACE2, fg=TEXT_DIM,
            font=("Consolas", 9),
        )
        self.status_label.pack(side="left", pady=10)

        self.status_counter = tk.Label(
            self.status_frame, text="", bg=SURFACE2, fg=TEXT_DIM,
            font=("Consolas", 9),
        )
        self.status_counter.pack(side="right", padx=10, pady=10)

        # Hotkey hint
        self.hotkey_hint = tk.Label(main, text="F6 = Start  |  Escape = Stop  (works while alt-tabbed)",
                 bg=BG, fg=TEXT_DIM, font=("Consolas", 8))
        self.hotkey_hint.pack(pady=(8, 0))

        # Global escape to stop (works even when alt-tabbed)
        self._start_global_hotkey()

        # Set min size
        self.root.update_idletasks()
        self.root.minsize(520, self.root.winfo_height())

    # ── Global hotkey ─────────────────────────────────────────────────────

    def _start_global_hotkey(self):
        from pynput.keyboard import Listener, Key

        self._stop_key = Key.esc
        self._start_key = Key.f6

        def on_press(key):
            if key == self._stop_key:
                self.root.after(0, self._stop)
            elif key == self._start_key:
                self.root.after(0, self._start)

        self._hotkey_listener = Listener(on_press=on_press)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

    def _keysym_to_pynput(self, keysym):
        """Convert a tkinter keysym to a pynput Key/KeyCode."""
        from pynput.keyboard import Key, KeyCode

        mapping = {
            "Escape": Key.esc, "space": Key.space,
            "Return": Key.enter, "Tab": Key.tab, "BackSpace": Key.backspace,
            "Delete": Key.delete, "Insert": Key.insert,
            "Shift_L": Key.shift_l, "Shift_R": Key.shift_r,
            "Control_L": Key.ctrl_l, "Control_R": Key.ctrl_r,
            "Alt_L": Key.alt_l, "Alt_R": Key.alt_r,
            "Caps_Lock": Key.caps_lock, "Menu": Key.menu,
            "Up": Key.up, "Down": Key.down, "Left": Key.left, "Right": Key.right,
            "Home": Key.home, "End": Key.end,
            "Prior": Key.page_up, "Next": Key.page_down,
        }
        for i in range(1, 13):
            mapping[f"F{i}"] = getattr(Key, f"f{i}")

        if keysym in mapping:
            return mapping[keysym]
        elif len(keysym) == 1:
            return KeyCode.from_char(keysym.lower())
        else:
            try:
                return getattr(Key, keysym.lower())
            except AttributeError:
                return KeyCode.from_char(keysym.lower())

    def _update_hotkey_hint(self):
        start_name = self.start_key_btn.cget("text")
        stop_name = self.stop_key_btn.cget("text")
        self.hotkey_hint.configure(text=f"{start_name} = Start  |  {stop_name} = Stop  (works while alt-tabbed)")

    def _start_start_key_capture(self, event):
        self.start_key_btn.configure(text="Listening...", fg=WARNING)
        self.root.bind("<KeyPress>", self._on_start_key_captured)

    def _on_start_key_captured(self, event):
        self.root.unbind("<KeyPress>")
        self._start_key = self._keysym_to_pynput(event.keysym)
        display = event.keysym.upper() if len(event.keysym) == 1 else event.keysym
        self.start_key_btn.configure(text=display, fg=ACCENT)
        self._update_hotkey_hint()

    def _start_stop_key_capture(self, event):
        self.stop_key_btn.configure(text="Listening...", fg=WARNING)
        self.root.bind("<KeyPress>", self._on_stop_key_captured)

    def _on_stop_key_captured(self, event):
        self.root.unbind("<KeyPress>")
        self._stop_key = self._keysym_to_pynput(event.keysym)
        display = event.keysym.upper() if len(event.keysym) == 1 else event.keysym
        self.stop_key_btn.configure(text=display, fg=DANGER)
        self._update_hotkey_hint()

    # ── Type change visibility ────────────────────────────────────────────

    def _on_type_change(self):
        t = self.action_type.get()
        # Hide all optional frames
        self.key_frame.pack_forget()
        self.mouse_frame.pack_forget()
        self.dur_frame.pack_forget()
        self.interval_frame.pack_forget()
        self.count_frame.pack_forget()

        r2 = self.key_frame.master  # the r2 frame

        if t == "key_hold":
            self.key_frame.pack(in_=r2, side="left", fill="x", expand=True, padx=(0, 8))
            self.dur_frame.pack(in_=r2, side="left")
        elif t == "key_press":
            self.key_frame.pack(in_=r2, side="left", fill="x", expand=True, padx=(0, 8))
            self.dur_frame.pack(in_=r2, side="left", padx=(0, 8))
            self.interval_frame.pack(in_=r2, side="left", padx=(0, 8))
            self.count_frame.pack(in_=r2, side="left")
        elif t == "mouse_hold":
            self.mouse_frame.pack(in_=r2, side="left", fill="x", expand=True, padx=(0, 8))
            self.dur_frame.pack(in_=r2, side="left")
        elif t == "mouse_click":
            self.mouse_frame.pack(in_=r2, side="left", fill="x", expand=True, padx=(0, 8))
            self.dur_frame.pack(in_=r2, side="left", padx=(0, 8))
            self.interval_frame.pack(in_=r2, side="left", padx=(0, 8))
            self.count_frame.pack(in_=r2, side="left")
        elif t == "pause":
            self.dur_frame.pack(in_=r2, side="left")

    # ── Key capture ───────────────────────────────────────────────────────

    def _start_key_capture(self, event):
        self.key_capture_btn.configure(text="Listening...", fg=WARNING)
        self.root.bind("<KeyPress>", self._on_key_captured)

    def _on_key_captured(self, event):
        self.root.unbind("<KeyPress>")
        key_name = event.keysym
        self.captured_key = event.keysym
        self.captured_key_name = event.keysym

        display = key_name.upper() if len(key_name) == 1 else key_name
        self.key_capture_btn.configure(text=display, fg=ACCENT)

    # ── Queue management ──────────────────────────────────────────────────

    def _build_action(self):
        """Build an action dict from current UI inputs. Returns None on error."""
        t = self.action_type.get()
        try:
            dur = float(self.duration_var.get() or 5)
        except ValueError:
            self._set_status("Invalid duration", DANGER, DANGER)
            return None
        try:
            interval = int(float(self.interval_var.get() or 100))
        except ValueError:
            self._set_status("Invalid interval", DANGER, DANGER)
            return None

        if t == "pause":
            return {"id": str(uuid.uuid4())[:8], "type": t, "duration": dur}

        action = {"id": str(uuid.uuid4())[:8], "type": t, "duration": dur}

        # Parse optional count
        count_str = self.count_var.get().strip()
        count = None
        if count_str:
            try:
                count = int(float(count_str))
                if count < 1:
                    count = None
            except ValueError:
                self._set_status("Invalid count", DANGER, DANGER)
                return None

        if t in ("key_hold", "key_press"):
            if not self.captured_key:
                self.key_capture_btn.configure(text="⚠ Set a key first!", fg=DANGER)
                return None
            action["key"] = self.captured_key
            action["key_display"] = self.key_capture_btn.cget("text")
            if t == "key_press":
                action["interval"] = interval
                if count is not None:
                    action["count"] = count
        elif t in ("mouse_hold", "mouse_click"):
            action["button"] = self.mouse_btn_var.get()
            if t == "mouse_click":
                action["interval"] = interval
                if count is not None:
                    action["count"] = count

        return action

    def _add_new_step(self):
        """Always creates a new step in the queue."""
        action = self._build_action()
        if action is None:
            return

        if action["type"] == "pause":
            self.queue.append(action)
        else:
            step = {
                "id": str(uuid.uuid4())[:8],
                "type": "group",
                "actions": [action],
                "humanize": False,
            }
            self.queue.append(step)
            self.selected_step_id = step["id"]

        self._render_queue()

    def _add_to_step(self):
        """Add action to the currently selected step (concurrent)."""
        if not self.selected_step_id:
            self._set_status("Select a step first", WARNING, WARNING)
            return

        action = self._build_action()
        if action is None:
            return

        if action["type"] == "pause":
            self._set_status("Can't add pause to a step — use Add New Step", WARNING, WARNING)
            return

        step = next((s for s in self.queue if s["id"] == self.selected_step_id), None)
        if not step or step["type"] != "group":
            self._set_status("Selected step is not a group", WARNING, WARNING)
            return

        step["actions"].append(action)
        self._render_queue()

    def _select_step(self, step_id):
        """Select a step for concurrent action adding."""
        step = next((s for s in self.queue if s["id"] == step_id), None)
        if not step or step["type"] != "group":
            return
        if self.selected_step_id == step_id:
            self.selected_step_id = None  # toggle off
        else:
            self.selected_step_id = step_id
        self._render_queue()

    def _toggle_collapse(self, step_id):
        """Toggle collapsed state of a step."""
        if step_id in self.collapsed_steps:
            self.collapsed_steps.discard(step_id)
        else:
            self.collapsed_steps.add(step_id)
        self._render_queue()

    def _toggle_humanize(self, step_id):
        """Toggle per-step humanize."""
        step = next((s for s in self.queue if s["id"] == step_id), None)
        if step and step["type"] == "group":
            step["humanize"] = not step.get("humanize", False)
            self._render_queue()

    def _update_add_to_step_btn(self):
        """Enable/disable the Add to Step button based on selection."""
        if self.selected_step_id:
            step = next((s for s in self.queue if s["id"] == self.selected_step_id), None)
            if step and step["type"] == "group":
                self.add_to_step_btn.configure(
                    state="normal", fg=ACCENT, bg=ACCENT_DIM,
                    activebackground=ACCENT, activeforeground=BG,
                    highlightbackground=ACCENT,
                )
                return
        self.add_to_step_btn.configure(
            state="disabled", fg=TEXT_DIM, bg=SURFACE2,
            highlightbackground=BORDER,
        )

    def _remove_action(self, action_id):
        """Remove an individual action from a group, or a whole step."""
        new_queue = []
        for step in self.queue:
            if step["id"] == action_id:
                if self.selected_step_id == action_id:
                    self.selected_step_id = None
                continue
            if step["type"] == "group":
                step["actions"] = [a for a in step["actions"] if a["id"] != action_id]
                if not step["actions"]:
                    if self.selected_step_id == step["id"]:
                        self.selected_step_id = None
                    continue
            new_queue.append(step)
        self.queue = new_queue
        self._render_queue()

    def _move_step(self, step_id, direction):
        idx = next(i for i, s in enumerate(self.queue) if s["id"] == step_id)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.queue):
            self.queue[idx], self.queue[new_idx] = self.queue[new_idx], self.queue[idx]
        self._render_queue()

    def _clear_queue(self):
        self.queue = []
        self.selected_step_id = None
        self._render_queue()

    def _save_queue(self):
        if not self.queue:
            self._set_status("Nothing to save", WARNING, WARNING)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Save Queue",
        )
        if not path:
            return
        with open(path, "w") as f:
            json.dump(self.queue, f, indent=2)
        self._set_status(f"Saved to {path}", ACCENT, ACCENT)

    def _load_queue(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Load Queue",
        )
        if not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("Expected a list")
            self.queue = data
            self.selected_step_id = None
            self._render_queue()
            self._set_status(f"Loaded {len(data)} step(s)", ACCENT, ACCENT)
        except (json.JSONDecodeError, ValueError, KeyError):
            self._set_status("Invalid queue file", DANGER, DANGER)

    def _render_queue(self):
        for w in self.queue_list_frame.winfo_children():
            w.destroy()

        # Validate selection still exists
        if self.selected_step_id:
            if not any(s["id"] == self.selected_step_id for s in self.queue):
                self.selected_step_id = None

        self._update_add_to_step_btn()

        if not self.queue:
            self.empty_label = tk.Label(
                self.queue_list_frame, text="No actions yet — add one above",
                bg=SURFACE, fg=TEXT_DIM, font=("Consolas", 9), pady=60,
            )
            self.empty_label.pack()
            return

        for i, step in enumerate(self.queue):
            selected = step["id"] == self.selected_step_id
            bg = ACCENT_DIM if selected else (SURFACE2 if i % 2 == 0 else SURFACE)
            step_label_fg = WARNING if selected else ACCENT
            border_color = ACCENT if selected else bg

            # Step header row
            header = tk.Frame(self.queue_list_frame, bg=bg, highlightbackground=border_color,
                              highlightthickness=1 if selected else 0)
            header.pack(fill="x", padx=6, pady=(4, 0))

            step_label = tk.Label(header, text=f"Step {i+1}", bg=bg, fg=step_label_fg,
                     font=("Consolas", 9, "bold"), width=7, cursor="hand2")
            step_label.pack(side="left", padx=(6, 0))

            if step["type"] == "pause":
                desc_label = tk.Label(header, text=f"Pause for {step['duration']}s", bg=bg, fg=TEXT,
                         font=("Consolas", 9), anchor="w")
                desc_label.pack(side="left", fill="x", expand=True, padx=6, pady=4)
                tk.Button(header, text="▲", bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, command=lambda sid=step["id"]: self._move_step(sid, -1)).pack(side="left")
                tk.Button(header, text="▼", bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, command=lambda sid=step["id"]: self._move_step(sid, 1)).pack(side="left")
                tk.Button(header, text="✕", bg=bg, fg=DANGER, font=("Consolas", 9, "bold"),
                          bd=0, padx=8, command=lambda sid=step["id"]: self._remove_action(sid)).pack(side="right")
            else:
                # Group step — clickable to select
                collapsed = step["id"] in self.collapsed_steps
                chevron = "▶" if collapsed else "▼"
                collapse_btn = tk.Button(header, text=chevron, bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, cursor="hand2",
                          command=lambda sid=step["id"]: self._toggle_collapse(sid))
                collapse_btn.pack(side="left")

                action_count = len(step["actions"])
                max_dur = max(a["duration"] for a in step["actions"])
                humanized = step.get("humanize", False)
                dur_str = f"~{max_dur}s" if humanized else f"{max_dur}s"
                desc_label = tk.Label(header, text=f"{action_count} input{'s' if action_count != 1 else ''} \u00b7 {dur_str} (concurrent)",
                         bg=bg, fg=TEXT_DIM, font=("Consolas", 8), anchor="w", cursor="hand2")
                desc_label.pack(side="left", fill="x", expand=True, padx=6, pady=4)
                hum_text = "Humanized" if humanized else "Exact"
                hum_fg = ACCENT if humanized else TEXT_DIM
                hum_bg = ACCENT_DIM if humanized else bg
                tk.Button(header, text=hum_text, bg=hum_bg, fg=hum_fg,
                          font=("Consolas", 7, "bold"), bd=0, padx=6, pady=2, cursor="hand2",
                          highlightbackground=ACCENT if humanized else BORDER, highlightthickness=1,
                          command=lambda sid=step["id"]: self._toggle_humanize(sid)).pack(side="left", padx=(0, 4))
                tk.Button(header, text="▲", bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, command=lambda sid=step["id"]: self._move_step(sid, -1)).pack(side="left")
                tk.Button(header, text="▼", bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, command=lambda sid=step["id"]: self._move_step(sid, 1)).pack(side="left")
                tk.Button(header, text="✕", bg=bg, fg=DANGER, font=("Consolas", 9, "bold"),
                          bd=0, padx=8, command=lambda sid=step["id"]: self._remove_action(sid)).pack(side="right")

                # Make header clickable for selection
                for widget in [header, step_label, desc_label]:
                    widget.bind("<Button-1>", lambda e, sid=step["id"]: self._select_step(sid))

                # Individual actions (hidden when collapsed)
                if not collapsed:
                    for action in step["actions"]:
                        arow = tk.Frame(self.queue_list_frame, bg=bg)
                        arow.pack(fill="x", padx=6)

                        tk.Label(arow, text="", bg=bg, width=7).pack(side="left", padx=(6, 0))
                        tk.Label(arow, text=f"  {self._describe_action(action)}", bg=bg, fg=TEXT,
                                 font=("Consolas", 9), anchor="w").pack(side="left", fill="x", expand=True, padx=6, pady=2)
                        tk.Button(arow, text="✕", bg=bg, fg=DANGER, font=("Consolas", 8),
                                  bd=0, padx=8, command=lambda aid=action["id"]: self._remove_action(aid)).pack(side="right")

    def _describe_action(self, a):
        t = a["type"]
        dur = a["duration"]
        if t == "key_hold":
            return f"Hold [{a['key_display']}] for {dur}s"
        elif t == "key_press":
            count = a.get("count")
            if count:
                return f"Press [{a['key_display']}] x{count} @{a['interval']}ms"
            return f"Press [{a['key_display']}] for {dur}s @{a['interval']}ms"
        elif t == "mouse_hold":
            return f"Hold mouse {a['button']} for {dur}s"
        elif t == "mouse_click":
            count = a.get("count")
            if count:
                return f"Click mouse {a['button']} x{count} @{a['interval']}ms"
            return f"Click mouse {a['button']} for {dur}s @{a['interval']}ms"
        return "???"

    # ── Execution ─────────────────────────────────────────────────────────

    def _draw_dot(self, color):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill=color, outline="")

    def _set_status(self, text, color=TEXT_DIM, dot_color=None):
        self.status_label.configure(text=text, fg=color)
        if dot_color:
            self._draw_dot(dot_color)

    def _start(self):
        if not self.queue:
            self._set_status("Queue is empty!", WARNING, WARNING)
            return
        if self.running:
            return

        self.running = True
        self.stop_event.clear()
        self.start_btn.configure(state="disabled", bg=SURFACE2)
        self.stop_btn.configure(state="normal")

        self.worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self.worker_thread.start()

    def _stop(self):
        if not self.running:
            return
        self.stop_event.set()
        self.running = False
        self.start_btn.configure(state="normal", bg=ACCENT)
        self.stop_btn.configure(state="disabled")
        self._set_status("Stopped", TEXT_DIM, TEXT_DIM)
        self.status_counter.configure(text="")

    def _run_worker(self):
        # Lazy import so the app opens even if pynput isn't installed yet
        try:
            from pynput.keyboard import Controller as KBController, Key
            from pynput.mouse import Controller as MouseController, Button
        except ImportError:
            self.root.after(0, lambda: self._set_status("Install pynput: pip install pynput", DANGER, DANGER))
            self.root.after(0, lambda: self._stop_ui())
            return

        kb = KBController()
        mouse = MouseController()

        button_map = {
            "left": Button.left,
            "middle": Button.middle,
            "right": Button.right,
        }

        # Resolve key name to pynput key
        def resolve_key(name):
            # Check if it's a special key
            try:
                return getattr(Key, name.lower())
            except AttributeError:
                pass
            # Single char
            if len(name) == 1:
                return name.lower()
            # Common mappings
            mapping = {
                "space": Key.space, "return": Key.enter, "enter": Key.enter,
                "tab": Key.tab, "escape": Key.esc, "backspace": Key.backspace,
                "shift_l": Key.shift_l, "shift_r": Key.shift_r,
                "control_l": Key.ctrl_l, "control_r": Key.ctrl_r,
                "alt_l": Key.alt_l, "alt_r": Key.alt_r,
                "caps_lock": Key.caps_lock, "delete": Key.delete,
                "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
                "home": Key.home, "end": Key.end,
                "page_up": Key.page_up, "page_down": Key.page_down,
                "insert": Key.insert, "menu": Key.menu,
            }
            # Function keys
            for i in range(1, 13):
                mapping[f"f{i}"] = getattr(Key, f"f{i}")

            return mapping.get(name.lower(), name.lower() if len(name) == 1 else name)

        # Start delay
        try:
            delay = float(self.delay_var.get() or 0)
        except ValueError:
            delay = 0
        if delay > 0:
            start_time = time.time()
            while time.time() - start_time < delay:
                if self.stop_event.is_set():
                    return
                remaining = delay - (time.time() - start_time)
                self.root.after(0, lambda r=remaining: self._set_status(f"Starting in {r:.1f}s", WARNING, WARNING))
                time.sleep(0.1)

        try:
            variance_pct = float(self.variance_var.get() or 20) / 100.0
        except ValueError:
            variance_pct = 0.2

        def jitter(value, humanize):
            """Apply random variance to a timing value if humanize is on."""
            if not humanize:
                return value
            offset = value * variance_pct
            return max(0.001, value + random.uniform(-offset, offset))

        def run_action(action, humanize):
            """Execute a single action (runs in its own thread for concurrency)."""
            t = action["type"]
            dur = action["duration"]

            if t == "key_hold":
                key = resolve_key(action["key"])
                kb.press(key)
                self._interruptible_sleep(jitter(dur, humanize))
                kb.release(key)

            elif t == "key_press":
                key = resolve_key(action["key"])
                interval_s = action["interval"] / 1000.0
                count = action.get("count")
                if count:
                    for _ in range(count):
                        if self.stop_event.is_set():
                            return
                        kb.press(key)
                        kb.release(key)
                        self._interruptible_sleep(jitter(interval_s, humanize))
                else:
                    end_time = time.time() + jitter(dur, humanize)
                    while time.time() < end_time and not self.stop_event.is_set():
                        kb.press(key)
                        kb.release(key)
                        self._interruptible_sleep(jitter(interval_s, humanize))

            elif t == "mouse_hold":
                btn = button_map[action["button"]]
                mouse.press(btn)
                self._interruptible_sleep(jitter(dur, humanize))
                mouse.release(btn)

            elif t == "mouse_click":
                btn = button_map[action["button"]]
                interval_s = action["interval"] / 1000.0
                count = action.get("count")
                if count:
                    for _ in range(count):
                        if self.stop_event.is_set():
                            return
                        mouse.click(btn)
                        self._interruptible_sleep(jitter(interval_s, humanize))
                else:
                    end_time = time.time() + jitter(dur, humanize)
                    while time.time() < end_time and not self.stop_event.is_set():
                        mouse.click(btn)
                        self._interruptible_sleep(jitter(interval_s, humanize))

        loop_count = 0
        while not self.stop_event.is_set():
            loop_count += 1
            for i, step in enumerate(self.queue):
                if self.stop_event.is_set():
                    return

                if step["type"] == "pause":
                    self.root.after(0, lambda idx=i, dur=step["duration"]: (
                        self._set_status(f"[Step {idx+1}/{len(self.queue)}] Pause for {dur}s", ACCENT, ACCENT),
                        self.status_counter.configure(text=f"Loop {loop_count}")
                    ))
                    self._interruptible_sleep(step["duration"])

                elif step["type"] == "group":
                    step_humanize = step.get("humanize", False)
                    descs = ", ".join(self._describe_action(a) for a in step["actions"])
                    self.root.after(0, lambda idx=i, d=descs: (
                        self._set_status(f"[Step {idx+1}/{len(self.queue)}] {d}", ACCENT, ACCENT),
                        self.status_counter.configure(text=f"Loop {loop_count}")
                    ))

                    if len(step["actions"]) == 1:
                        run_action(step["actions"][0], step_humanize)
                    else:
                        threads = []
                        for action in step["actions"]:
                            t = threading.Thread(target=run_action, args=(action, step_humanize), daemon=True)
                            t.start()
                            threads.append(t)
                        for t in threads:
                            t.join()

            if not self.repeat_var.get():
                break

        self.root.after(0, lambda: self._stop())

    def _stop_ui(self):
        self.running = False
        self.start_btn.configure(state="normal", bg=ACCENT)
        self.stop_btn.configure(state="disabled")

    def _interruptible_sleep(self, duration):
        end = time.time() + duration
        while time.time() < end:
            if self.stop_event.is_set():
                return
            time.sleep(min(0.05, end - time.time()))


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    # Center window
    root.update_idletasks()
    app = AutoInputApp(root)
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")
    root.mainloop()