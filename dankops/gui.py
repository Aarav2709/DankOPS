from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .config import AppConfig, CommandProfile, load_config, save_config


class ConfigGui:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = load_config(config_path)
        self.root = tk.Tk()
        self.root.title("DankOPS Setup")
        self.root.geometry("980x720")
        self.fields: dict[str, tk.Variable] = {}
        self.command_vars: dict[str, dict[str, tk.Variable]] = {}
        self._build()

    def _build(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        general = ttk.Frame(notebook)
        scheduler = ttk.Frame(notebook)
        commands = ttk.Frame(notebook)

        notebook.add(general, text="General")
        notebook.add(scheduler, text="Scheduler")
        notebook.add(commands, text="Commands")

        self._build_general(general)
        self._build_scheduler(scheduler)
        self._build_commands(commands)

        footer = ttk.Frame(self.root)
        footer.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(footer, text="Save", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Reload", command=self._reload).pack(side=tk.RIGHT, padx=(0, 8))

    def _add_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.Variable) -> None:
        ttk.Label(parent, text=label, width=30).grid(row=row, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(parent, textvariable=variable, width=50).grid(row=row, column=1, padx=8, pady=6, sticky="ew")

    def _build_general(self, frame: ttk.Frame) -> None:
        frame.columnconfigure(1, weight=1)
        self.fields["bot_token"] = tk.StringVar(value=self.config.bot_token)
        self.fields["owner_user_id"] = tk.StringVar(value=str(self.config.owner_user_id))
        self.fields["target_channel_id"] = tk.StringVar(value=str(self.config.target_channel_id))
        self.fields["status_channel_id"] = tk.StringVar(value=str(self.config.status_channel_id))
        self.fields["presence"] = tk.StringVar(value=self.config.presence)
        self.fields["auto_start"] = tk.BooleanVar(value=self.config.auto_start)
        self._add_row(frame, 0, "Bot Token", self.fields["bot_token"])
        self._add_row(frame, 1, "Owner User ID", self.fields["owner_user_id"])
        self._add_row(frame, 2, "Target Channel ID", self.fields["target_channel_id"])
        self._add_row(frame, 3, "Status Channel ID", self.fields["status_channel_id"])
        self._add_row(frame, 4, "Presence online|idle|dnd|invisible", self.fields["presence"])
        ttk.Checkbutton(frame, text="Auto Start Scheduler", variable=self.fields["auto_start"]).grid(row=5, column=1, sticky="w", padx=8, pady=6)

    def _build_scheduler(self, frame: ttk.Frame) -> None:
        frame.columnconfigure(1, weight=1)
        self.fields["break_mode"] = tk.BooleanVar(value=self.config.break_mode)
        self.fields["break_after_min_minutes"] = tk.StringVar(value=str(self.config.break_after_min_minutes))
        self.fields["break_after_max_minutes"] = tk.StringVar(value=str(self.config.break_after_max_minutes))
        self.fields["break_duration_min_minutes"] = tk.StringVar(value=str(self.config.break_duration_min_minutes))
        self.fields["break_duration_max_minutes"] = tk.StringVar(value=str(self.config.break_duration_max_minutes))
        self.fields["command_interval_min_seconds"] = tk.StringVar(value=str(self.config.command_interval.min_seconds))
        self.fields["command_interval_max_seconds"] = tk.StringVar(value=str(self.config.command_interval.max_seconds))

        ttk.Checkbutton(frame, text="Enable Break Mode", variable=self.fields["break_mode"]).grid(row=0, column=1, sticky="w", padx=8, pady=6)
        self._add_row(frame, 1, "Break After Min Minutes", self.fields["break_after_min_minutes"])
        self._add_row(frame, 2, "Break After Max Minutes", self.fields["break_after_max_minutes"])
        self._add_row(frame, 3, "Break Duration Min Minutes", self.fields["break_duration_min_minutes"])
        self._add_row(frame, 4, "Break Duration Max Minutes", self.fields["break_duration_max_minutes"])
        self._add_row(frame, 5, "Command Interval Min Seconds", self.fields["command_interval_min_seconds"])
        self._add_row(frame, 6, "Command Interval Max Seconds", self.fields["command_interval_max_seconds"])

    def _build_commands(self, frame: ttk.Frame) -> None:
        columns = ("key", "enabled", "message", "min_delay", "max_delay")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=20)
        for col, text, width in [
            ("key", "Key", 120),
            ("enabled", "Enabled", 80),
            ("message", "Message", 360),
            ("min_delay", "Min Delay", 120),
            ("max_delay", "Max Delay", 120),
        ]:
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        editor = ttk.LabelFrame(frame, text="Edit Command")
        editor.pack(fill=tk.X, padx=8, pady=(0, 8))
        editor.columnconfigure(1, weight=1)

        selected = tk.StringVar(value="")
        enabled = tk.BooleanVar(value=False)
        command = tk.StringVar(value="")
        min_delay = tk.StringVar(value="30")
        max_delay = tk.StringVar(value="45")

        ttk.Label(editor, text="Key", width=18).grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(editor, textvariable=selected, width=24).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        ttk.Checkbutton(editor, text="Enabled", variable=enabled).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        ttk.Label(editor, text="Message", width=18).grid(row=1, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(editor, textvariable=command).grid(row=1, column=1, columnspan=2, padx=8, pady=6, sticky="ew")
        ttk.Label(editor, text="Min Delay", width=18).grid(row=2, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(editor, textvariable=min_delay, width=14).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        ttk.Label(editor, text="Max Delay", width=18).grid(row=2, column=2, padx=8, pady=6, sticky="w")
        ttk.Entry(editor, textvariable=max_delay, width=14).grid(row=2, column=3, padx=8, pady=6, sticky="w")

        def refresh_tree() -> None:
            for item in tree.get_children():
                tree.delete(item)
            for key, profile in sorted(self.config.commands.items()):
                tree.insert("", tk.END, iid=key, values=(key, str(profile.enabled), profile.command, profile.min_delay, profile.max_delay))

        def load_selected(_event: object | None = None) -> None:
            focus = tree.focus()
            if not focus:
                return
            profile = self.config.commands.get(focus)
            if profile is None:
                return
            selected.set(focus)
            enabled.set(profile.enabled)
            command.set(profile.command)
            min_delay.set(str(profile.min_delay))
            max_delay.set(str(profile.max_delay))

        def upsert() -> None:
            key = selected.get().strip()
            if not key:
                messagebox.showerror("Error", "Key is required")
                return
            try:
                profile = CommandProfile(
                    enabled=bool(enabled.get()),
                    command=command.get().strip(),
                    min_delay=float(min_delay.get().strip()),
                    max_delay=float(max_delay.get().strip()),
                )
            except ValueError:
                messagebox.showerror("Error", "Delays must be numeric")
                return
            self.config.commands[key] = profile
            refresh_tree()
            tree.focus(key)
            tree.selection_set(key)

        def remove() -> None:
            key = selected.get().strip()
            if not key:
                return
            if key in self.config.commands:
                del self.config.commands[key]
                selected.set("")
                command.set("")
                min_delay.set("30")
                max_delay.set("45")
                enabled.set(False)
                refresh_tree()

        ttk.Button(editor, text="Save Command", command=upsert).grid(row=3, column=1, padx=8, pady=8, sticky="w")
        ttk.Button(editor, text="Delete Command", command=remove).grid(row=3, column=2, padx=8, pady=8, sticky="w")
        tree.bind("<<TreeviewSelect>>", load_selected)
        refresh_tree()

    def _coerce_int(self, key: str) -> int:
        text = str(self.fields[key].get()).strip()
        if not text:
            return 0
        return int(text)

    def _coerce_float(self, key: str) -> float:
        return float(str(self.fields[key].get()).strip())

    def _reload(self) -> None:
        self.config = load_config(self.config_path)
        self.root.destroy()
        ConfigGui(self.config_path).run()

    def _save(self) -> None:
        try:
            cfg = AppConfig(
                bot_token=str(self.fields["bot_token"].get()).strip(),
                owner_user_id=self._coerce_int("owner_user_id"),
                target_channel_id=self._coerce_int("target_channel_id"),
                status_channel_id=self._coerce_int("status_channel_id"),
                presence=str(self.fields["presence"].get()).strip().lower(),
                auto_start=bool(self.fields["auto_start"].get()),
                break_mode=bool(self.fields["break_mode"].get()),
                break_after_min_minutes=self._coerce_float("break_after_min_minutes"),
                break_after_max_minutes=self._coerce_float("break_after_max_minutes"),
                break_duration_min_minutes=self._coerce_float("break_duration_min_minutes"),
                break_duration_max_minutes=self._coerce_float("break_duration_max_minutes"),
                commands=self.config.commands,
            )
            cfg.command_interval.min_seconds = self._coerce_float("command_interval_min_seconds")
            cfg.command_interval.max_seconds = self._coerce_float("command_interval_max_seconds")
        except ValueError:
            messagebox.showerror("Error", "Numeric fields contain invalid values")
            return
        save_config(self.config_path, cfg)
        self.config = cfg
        messagebox.showinfo("Saved", f"Configuration saved to {self.config_path}")

    def run(self) -> None:
        self.root.mainloop()


def run_setup_gui(config_path: Path) -> None:
    ConfigGui(config_path).run()
