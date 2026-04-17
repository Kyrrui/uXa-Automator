<p align="center">
  <img src="uxa-no-background.png" alt="uXa Automator" width="180">
</p>

<h1 align="center">uXa Automator</h1>

<p align="center">
  A lightweight key & mouse automation tool with a step-based queue, per-step humanization, and global hotkeys.
</p>

<p align="center">
  <a href="https://github.com/Kyrrui/uXa-Automator/releases/latest">Download for Windows</a>
</p>

---

## Features

- **Step-based queue** -- group multiple inputs into a single step that runs them concurrently, then sequence steps with pauses
- **Per-step humanize** -- toggle randomized timing on individual steps to avoid bot detection while keeping precision where you need it
- **Optional press/click count** -- guarantee an exact number of inputs instead of relying on duration
- **Global hotkeys** -- start (F6) and stop (Escape) work even when alt-tabbed into another window
- **Save & load presets** -- export your queue as JSON and reload it anytime
- **Collapsible steps** -- keep long queues tidy
- **Pop-out queue view** -- enlarge the queue in a separate window for easier review
- **Looping** -- repeat the queue with a configurable start delay

## Quick Start

### Download (no install required)

Grab the latest `.exe` from [Releases](https://github.com/Kyrrui/uXa-Automator/releases/latest) and run it directly.

### Run from source

```bash
pip install pynput pillow
python auto_input.py
```

## Usage

1. **Select an action type** -- Hold Key, Press Key, Hold Mouse, Click Mouse, or Pause
2. **Configure it** -- set the key/button, duration, interval, and optional count
3. **Add New Step** -- creates a new step in the queue
4. **Add to Selected Step** -- click a step to select it, then add more actions to run concurrently within that step
5. **Toggle Humanize** -- click "Exact"/"Humanized" on any step to randomize its timing
6. **Set Variance %** -- controls how much humanized steps vary (default 15%, realistic human range is 10-20%)
7. **Press Start or F6** -- queue begins after the start delay
8. **Press Stop or Escape** -- emergency stop from any window

## Building

Build a standalone executable:

```bash
pip install pyinstaller pillow
python build.py
```

- **Windows**: produces `dist/uXa Automator.exe`
- **macOS**: produces `dist/uXa Automator.app` and `dist/uXa Automator.dmg` (must be built on macOS)

## License

MIT
