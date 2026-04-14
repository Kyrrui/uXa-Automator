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

        # Add button
        self.add_btn = tk.Button(
            add_inner, text="＋ Add to Queue", bg=ACCENT_DIM, fg=ACCENT,
            font=("Segoe UI Semibold", 10), bd=0, relief="flat", pady=8,
            activebackground=ACCENT, activeforeground=BG,
            highlightbackground=ACCENT, highlightthickness=1,
            command=self._add_action,
        )
        self.add_btn.pack(fill="x", pady=(4, 0))

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

        ctrl_frame = tk.Frame(main, bg=BG)
        ctrl_frame.pack(fill="x", pady=(0, 6))

        # Delay
        delay_f = tk.Frame(ctrl_frame, bg=BG)
        delay_f.pack(side="left", padx=(0, 16))
        tk.Label(delay_f, text="START DELAY (s)", bg=BG, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.delay_var = tk.StringVar(value="3")
        tk.Entry(
            delay_f, textvariable=self.delay_var, bg=SURFACE2, fg=TEXT,
            font=("Consolas", 11), bd=0, width=8,
            insertbackground=ACCENT, highlightbackground=BORDER, highlightthickness=1,
        ).pack()

        # Stop key
        stop_f = tk.Frame(ctrl_frame, bg=BG)
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

        # Repeat
        self.repeat_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            ctrl_frame, text="Loop queue", variable=self.repeat_var,
            bg=BG, fg=TEXT, selectcolor=SURFACE2,
            activebackground=BG, activeforeground=ACCENT,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(0, 16))

        # Humanize
        self.humanize_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ctrl_frame, text="Humanize", variable=self.humanize_var,
            bg=BG, fg=TEXT, selectcolor=SURFACE2,
            activebackground=BG, activeforeground=ACCENT,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(0, 8))

        variance_f = tk.Frame(ctrl_frame, bg=BG)
        variance_f.pack(side="left", padx=(0, 16))
        tk.Label(variance_f, text="VARIANCE %", bg=BG, fg=TEXT_DIM, font=("Consolas", 8, "bold")).pack(anchor="w")
        self.variance_var = tk.StringVar(value="20")
        tk.Entry(
            variance_f, textvariable=self.variance_var, bg=SURFACE2, fg=TEXT,
            font=("Consolas", 11), bd=0, width=5,
            insertbackground=ACCENT, highlightbackground=BORDER, highlightthickness=1,
        ).pack()

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
        self.hotkey_hint = tk.Label(main, text="Tip: Press Escape at any time to emergency-stop",
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

        def on_press(key):
            if key == self._stop_key:
                self.root.after(0, self._stop)

        self._hotkey_listener = Listener(on_press=on_press)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

    def _start_stop_key_capture(self, event):
        self.stop_key_btn.configure(text="Listening...", fg=WARNING)
        self.root.bind("<KeyPress>", self._on_stop_key_captured)

    def _on_stop_key_captured(self, event):
        from pynput.keyboard import Key

        self.root.unbind("<KeyPress>")
        keysym = event.keysym

        # Map tkinter keysym to pynput Key
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
            self._stop_key = mapping[keysym]
        elif len(keysym) == 1:
            from pynput.keyboard import KeyCode
            self._stop_key = KeyCode.from_char(keysym.lower())
        else:
            # Try pynput Key attribute as fallback
            try:
                self._stop_key = getattr(Key, keysym.lower())
            except AttributeError:
                from pynput.keyboard import KeyCode
                self._stop_key = KeyCode.from_char(keysym.lower())

        display = keysym.upper() if len(keysym) == 1 else keysym
        self.stop_key_btn.configure(text=display, fg=DANGER)
        self.hotkey_hint.configure(text=f"Tip: Press {display} at any time to emergency-stop")

    # ── Type change visibility ────────────────────────────────────────────

    def _on_type_change(self):
        t = self.action_type.get()
        # Hide all optional frames
        self.key_frame.pack_forget()
        self.mouse_frame.pack_forget()
        self.dur_frame.pack_forget()
        self.interval_frame.pack_forget()

        r2 = self.key_frame.master  # the r2 frame

        if t == "key_hold":
            self.key_frame.pack(in_=r2, side="left", fill="x", expand=True, padx=(0, 8))
            self.dur_frame.pack(in_=r2, side="left")
        elif t == "key_press":
            self.key_frame.pack(in_=r2, side="left", fill="x", expand=True, padx=(0, 8))
            self.dur_frame.pack(in_=r2, side="left", padx=(0, 8))
            self.interval_frame.pack(in_=r2, side="left")
        elif t == "mouse_hold":
            self.mouse_frame.pack(in_=r2, side="left", fill="x", expand=True, padx=(0, 8))
            self.dur_frame.pack(in_=r2, side="left")
        elif t == "mouse_click":
            self.mouse_frame.pack(in_=r2, side="left", fill="x", expand=True, padx=(0, 8))
            self.dur_frame.pack(in_=r2, side="left", padx=(0, 8))
            self.interval_frame.pack(in_=r2, side="left")
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

    def _add_action(self):
        t = self.action_type.get()
        try:
            dur = float(self.duration_var.get() or 5)
        except ValueError:
            self._set_status("Invalid duration", DANGER, DANGER)
            return
        try:
            interval = int(float(self.interval_var.get() or 100))
        except ValueError:
            self._set_status("Invalid interval", DANGER, DANGER)
            return

        if t == "pause":
            # Pause always creates a new step
            self.queue.append({
                "id": str(uuid.uuid4())[:8],
                "type": "pause",
                "duration": dur,
            })
        else:
            # Build the action dict
            action = {
                "id": str(uuid.uuid4())[:8],
                "type": t,
                "duration": dur,
            }

            if t in ("key_hold", "key_press"):
                if not self.captured_key:
                    self.key_capture_btn.configure(text="⚠ Set a key first!", fg=DANGER)
                    return
                action["key"] = self.captured_key
                action["key_display"] = self.key_capture_btn.cget("text")
                if t == "key_press":
                    action["interval"] = interval
            elif t in ("mouse_hold", "mouse_click"):
                action["button"] = self.mouse_btn_var.get()
                if t == "mouse_click":
                    action["interval"] = interval

            # Add to existing group step, or create a new one
            if self.queue and self.queue[-1]["type"] == "group":
                self.queue[-1]["actions"].append(action)
            else:
                self.queue.append({
                    "id": str(uuid.uuid4())[:8],
                    "type": "group",
                    "actions": [action],
                })

        self._render_queue()

    def _remove_action(self, action_id):
        """Remove an individual action from a group, or a whole step."""
        new_queue = []
        for step in self.queue:
            if step["id"] == action_id:
                continue  # remove entire step (pause or group)
            if step["type"] == "group":
                step["actions"] = [a for a in step["actions"] if a["id"] != action_id]
                if not step["actions"]:
                    continue  # drop empty groups
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
            self._render_queue()
            self._set_status(f"Loaded {len(data)} step(s)", ACCENT, ACCENT)
        except (json.JSONDecodeError, ValueError, KeyError):
            self._set_status("Invalid queue file", DANGER, DANGER)

    def _render_queue(self):
        for w in self.queue_list_frame.winfo_children():
            w.destroy()

        if not self.queue:
            self.empty_label = tk.Label(
                self.queue_list_frame, text="No actions yet — add one above",
                bg=SURFACE, fg=TEXT_DIM, font=("Consolas", 9), pady=60,
            )
            self.empty_label.pack()
            return

        for i, step in enumerate(self.queue):
            bg = SURFACE2 if i % 2 == 0 else SURFACE

            # Step header row
            header = tk.Frame(self.queue_list_frame, bg=bg)
            header.pack(fill="x", padx=6, pady=(4, 0))

            tk.Label(header, text=f"Step {i+1}", bg=bg, fg=ACCENT,
                     font=("Consolas", 9, "bold"), width=7).pack(side="left", padx=(6, 0))

            if step["type"] == "pause":
                tk.Label(header, text=f"Pause for {step['duration']}s", bg=bg, fg=TEXT,
                         font=("Consolas", 9), anchor="w").pack(side="left", fill="x", expand=True, padx=6, pady=4)
                # Step controls
                tk.Button(header, text="▲", bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, command=lambda sid=step["id"]: self._move_step(sid, -1)).pack(side="left")
                tk.Button(header, text="▼", bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, command=lambda sid=step["id"]: self._move_step(sid, 1)).pack(side="left")
                tk.Button(header, text="✕", bg=bg, fg=DANGER, font=("Consolas", 9, "bold"),
                          bd=0, padx=8, command=lambda sid=step["id"]: self._remove_action(sid)).pack(side="right")
            else:
                # Group step — show step controls on header
                action_count = len(step["actions"])
                tk.Label(header, text=f"{action_count} input{'s' if action_count != 1 else ''} (concurrent)",
                         bg=bg, fg=TEXT_DIM, font=("Consolas", 8), anchor="w"
                         ).pack(side="left", fill="x", expand=True, padx=6, pady=4)
                tk.Button(header, text="▲", bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, command=lambda sid=step["id"]: self._move_step(sid, -1)).pack(side="left")
                tk.Button(header, text="▼", bg=bg, fg=TEXT_DIM, font=("Consolas", 8),
                          bd=0, padx=4, command=lambda sid=step["id"]: self._move_step(sid, 1)).pack(side="left")
                tk.Button(header, text="✕", bg=bg, fg=DANGER, font=("Consolas", 9, "bold"),
                          bd=0, padx=8, command=lambda sid=step["id"]: self._remove_action(sid)).pack(side="right")

                # Individual actions within the group
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
            return f"Press [{a['key_display']}] for {dur}s @{a['interval']}ms"
        elif t == "mouse_hold":
            return f"Hold mouse {a['button']} for {dur}s"
        elif t == "mouse_click":
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

        humanize = self.humanize_var.get()
        try:
            variance_pct = float(self.variance_var.get() or 20) / 100.0
        except ValueError:
            variance_pct = 0.2

        def jitter(value):
            """Apply random variance to a timing value if humanize is on."""
            if not humanize:
                return value
            offset = value * variance_pct
            return max(0.001, value + random.uniform(-offset, offset))

        def run_action(action):
            """Execute a single action (runs in its own thread for concurrency)."""
            t = action["type"]
            dur = action["duration"]

            if t == "key_hold":
                key = resolve_key(action["key"])
                kb.press(key)
                self._interruptible_sleep(jitter(dur))
                kb.release(key)

            elif t == "key_press":
                key = resolve_key(action["key"])
                interval_s = action["interval"] / 1000.0
                end_time = time.time() + jitter(dur)
                while time.time() < end_time and not self.stop_event.is_set():
                    kb.press(key)
                    kb.release(key)
                    self._interruptible_sleep(jitter(interval_s))

            elif t == "mouse_hold":
                btn = button_map[action["button"]]
                mouse.press(btn)
                self._interruptible_sleep(jitter(dur))
                mouse.release(btn)

            elif t == "mouse_click":
                btn = button_map[action["button"]]
                interval_s = action["interval"] / 1000.0
                end_time = time.time() + jitter(dur)
                while time.time() < end_time and not self.stop_event.is_set():
                    mouse.click(btn)
                    self._interruptible_sleep(jitter(interval_s))

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
                    self._interruptible_sleep(jitter(step["duration"]))

                elif step["type"] == "group":
                    descs = ", ".join(self._describe_action(a) for a in step["actions"])
                    self.root.after(0, lambda idx=i, d=descs: (
                        self._set_status(f"[Step {idx+1}/{len(self.queue)}] {d}", ACCENT, ACCENT),
                        self.status_counter.configure(text=f"Loop {loop_count}")
                    ))

                    if len(step["actions"]) == 1:
                        run_action(step["actions"][0])
                    else:
                        threads = []
                        for action in step["actions"]:
                            t = threading.Thread(target=run_action, args=(action,), daemon=True)
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