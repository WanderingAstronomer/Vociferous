"""Minimal Tkinter UI for ChatterBug (stub implementation).

Start/Stop UI that runs recording and ASR in background threads and updates UI
via `root.after()`.
"""
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import queue

import audio
import asr
import storage


def _worker(root, text_widget, status_var, stop_event, level_queue, level_var, level_bar):
    status_var.set("Recording...")
    wav_bytes, dur = audio.record(stop_event=stop_event, level_queue=level_queue)
    status_var.set("Transcribing...")
    txt, meta = asr.transcribe_wav(wav_bytes, language_hint="en")
    storage.append_transcript(txt, {**meta, "dur_s": dur})

    def ui_update():
        text_widget.delete("1.0", tk.END)
        text_widget.insert(tk.END, txt)
        root.clipboard_clear()
        root.clipboard_append(txt)
        status_var.set("Idle")
        level_var.set(0.0)
        level_bar["value"] = 0

    root.after(0, ui_update)


def run_ui():
    root = tk.Tk()
    root.title("ChatterBug (MVP stub)")
    root.geometry("1024x640")
    root.minsize(720, 480)

    status_var = tk.StringVar(value="Idle")
    model_status_var = tk.StringVar(value="Checking models…")
    level_var = tk.DoubleVar(value=0.0)

    outer = ttk.Frame(root, padding=8)
    outer.pack(fill="both", expand=True)

    top = ttk.Frame(outer)
    top.pack(fill="x", pady=(0, 8))

    model_label = ttk.Label(top, textvariable=model_status_var, width=28)
    model_label.pack(side="left", padx=(0, 8))

    status_label = ttk.Label(top, textvariable=status_var)
    status_label.pack(side="left")

    text_widget = ScrolledText(outer, height=10, wrap="word")
    text_widget.pack(fill="both", expand=True)

    btn_frame = ttk.Frame(outer)
    btn_frame.pack(fill="x", pady=8)
    start_btn = ttk.Button(btn_frame, text="Start")
    stop_btn = ttk.Button(btn_frame, text="Stop")
    start_btn.pack(side="left", padx=4)
    stop_btn.pack(side="left", padx=4)

    meter_frame = ttk.Frame(outer)
    meter_frame.pack(fill="x", pady=(0, 8))
    ttk.Label(meter_frame, text="Mic level").pack(side="left", padx=(0, 6))
    level_bar = ttk.Progressbar(meter_frame, orient="horizontal", mode="determinate", maximum=0.2, variable=level_var)
    level_bar.pack(side="left", fill="x", expand=True)

    stop_event = None
    worker_thread = None
    level_queue: queue.SimpleQueue[float] = queue.SimpleQueue()

    def on_start():
        nonlocal stop_event, worker_thread, level_queue
        if worker_thread and worker_thread.is_alive():
            return
        # reset meter queue
        level_queue = queue.SimpleQueue()
        stop_event = threading.Event()
        worker_thread = threading.Thread(
            target=_worker,
            args=(root, text_widget, status_var, stop_event, level_queue, level_var, level_bar),
            daemon=True,
        )
        worker_thread.start()
        status_var.set("Recording…")

    def on_stop():
        nonlocal stop_event
        if stop_event:
            stop_event.set()

    start_btn.config(command=on_start)
    stop_btn.config(command=on_stop)

    def poll_levels():
        # Update mic level bar while recording
        updated = False
        while True:
            try:
                rms = level_queue.get_nowait()
                level_var.set(rms)
                level_bar["value"] = rms
                updated = True
            except Exception:
                break
        if updated:
            # Clamp visually
            if level_bar["value"] > level_bar["maximum"]:
                level_bar["value"] = level_bar["maximum"]
        root.after(50, poll_levels)

    poll_levels()

    def poll_models():
        ok, details = asr.check_engine_availability()
        if ok:
            model_status_var.set("Models: ready")
            model_label.config(foreground="green4")
        else:
            model_status_var.set("Models: missing")
            model_label.config(foreground="red3")
        # Optionally show the first detail in tooltip? Keep simple: append count
        root.after(10_000, poll_models)

    poll_models()

    root.mainloop()
