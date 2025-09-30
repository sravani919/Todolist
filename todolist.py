"""
Tkinter To‑Do — Professional UI v3 (Unique & Impressive)
Run in VS Code: python main.py
No external dependencies. Data persists to todo_db.json.

What’s new (polish + uniqueness):
- Theme toggle (Light/Dark) with cohesive colors
- Color‑coded rows (foreground + soft background tints)
- Status icons: ○ To Do, ▸ In Progress, ✓ Done (can turn off by changing SHOW_ICONS=False)
- Overdue badge with warning icon (⚠) and red highlight
- Keyboard shortcuts: Ctrl/Cmd+N (new task), Ctrl/Cmd+S (save), Delete (delete selected)
- Focus Mode window for Pomodoro (large countdown)
- Streak counter (consecutive days with at least one task completed)
- Mini analytics (task counts by priority + completion rate)
- NEW: Interactive Analytics window with charts (stacked status vs priority, overall priority pie, due-time buckets)
"""

import json
import uuid
import time
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

DB_PATH = Path("todo_db.json")
PRIORITIES = ["High", "Medium", "Low"]
STATUS = ["To Do", "In Progress", "Done"]
SHOW_ICONS = True  # set to False to remove icons from titles/meta

# --- Visual mappings (Light theme defaults) ---
LIGHT = {
    "bg": "#fafbfc",
    "fg": "#111111",
    "card": "#ffffff",
    "tree_bg": "#ffffff",
    "tree_alt": "#f7f7f9",
}
DARK = {
    "bg": "#0f1115",
    "fg": "#e6e6e6",
    "card": "#151922",
    "tree_bg": "#151922",
    "tree_alt": "#10141b",
}

PRIORITY_COLORS = {
    "High": "#d32f2f",     # red
    "Medium": "#f57c00",   # orange
    "Low": "#388e3c",      # green
}
STATUS_COLORS = {
    "To Do": "#424242",        # gray/dark
    "In Progress": "#1976d2",  # blue
    "Done": "#2e7d32",         # green
}
OVERDUE_COLOR = "#c62828"         # deep red

# Soft background tints for rows
ROW_BG = {
    "done": "#e8f5e9",      # green tint
    "prog": "#e3f2fd",      # blue tint
    "overdue": "#ffebee",   # red tint
    "todo": "#f5f5f5",      # light gray
}

PRIORITY_ICONS = {"High": "▲", "Medium": "●", "Low": "■"}
STATUS_ICONS = {"To Do": "○", "In Progress": "▸", "Done": "✓"}
WARN_ICON = "⚠"

@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    due: Optional[str] = None
    priority: str = "Medium"
    tags: List[str] = field(default_factory=list)
    status: str = "To Do"
    completed_at: Optional[str] = None

    @property
    def is_overdue(self) -> bool:
        if not self.due or self.status == "Done":
            return False
        try:
            d = datetime.fromisoformat(self.due).date()
            return d < date.today()
        except Exception:
            return False

# ---------------- Persistence ----------------

def load_db():
    if DB_PATH.exists():
        try:
            return json.loads(DB_PATH.read_text())
        except Exception:
            return {"tasks": []}
    return {"tasks": []}


def save_db(db):
    DB_PATH.write_text(json.dumps(db, indent=2))

# ---------------- Quick Add Parser ----------------

def quick_parse(raw: str):
    tokens = raw.split()
    title_parts, tags, prio, due_iso = [], [], None, None

    def due_from_word(w: str):
        today = date.today()
        if w == "today":
            return datetime.combine(today, datetime.min.time()).isoformat()
        if w == "tomorrow":
            d = today + timedelta(days=1)
            return datetime.combine(d, datetime.min.time()).isoformat()
        if w in ("nextweek", "next-week"):
            d = today + timedelta(days=7)
            return datetime.combine(d, datetime.min.time()).isoformat()
        return None

    i = 0
    while i < len(tokens):
        t = tokens[i]
        low = t.lower()
        if low.startswith("#") and len(t) > 1:
            tags.append(low[1:])
        elif low.startswith("!"):
            v = low[1:]
            prio = "High" if v.startswith("h") else ("Low" if v.startswith("l") else "Medium")
        elif low == "next" and i + 1 < len(tokens) and tokens[i+1].lower() == "week":
            due_iso = due_from_word("nextweek")
            i += 1
        else:
            due_iso = due_iso or due_from_word(low)
            title_parts.append(t)
        i += 1

    title = " ".join(title_parts).strip()
    return title, tags, prio, due_iso

# ---------------- Utilities ----------------

def consecutive_day_streak(dates: List[date]) -> int:
    if not dates:
        return 0
    uniq = sorted(set(dates))
    streak = 0
    today = date.today()
    # Count back from today
    day = today
    while day in uniq:
        streak += 1
        day = day - timedelta(days=1)
    return streak

# ---------------- App ----------------

class ToDoApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        master.title("Sravani To-Do (Tkinter)")
        master.geometry("1180x740")
        master.minsize(980, 620)
        self.pack(fill="both", expand=True)

        self.db = load_db()
        self.theme_name = "Light"
        self._ensure_theme()
        self._build_ui()
        self._bind_shortcuts()
        self.refresh_all()

        self.timer_running = False
        self.timer_end = 0
        self.timer_task_id = None
        self.focus_win: Optional[tk.Toplevel] = None
        self.after(250, self._tick)

    # ------------- Theme -------------
    def _ensure_theme(self):
        style = ttk.Style()
        try:
            if style.theme_use() == "classic":
                style.theme_use("default")
        except Exception:
            pass
        self._apply_theme(LIGHT)

    def _apply_theme(self, palette):
        style = ttk.Style()
        style.configure("TFrame", background=palette["bg"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["fg"]) 
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), background=palette["bg"], foreground=palette["fg"]) 
        style.configure("H.TLabel", font=("Segoe UI", 12, "bold"), background=palette["bg"], foreground=palette["fg"]) 
        style.configure("Primary.TButton", padding=6)
        style.configure("Accent.TButton", padding=6)
        style.configure("Treeview", background=palette["tree_bg"], fieldbackground=palette["tree_bg"], foreground=palette["fg"]) 
        style.map("Treeview", background=[("selected", "#9ec9ff")])

    def _toggle_theme(self):
        self.theme_name = "Dark" if self.theme_name == "Light" else "Light"
        self._apply_theme(DARK if self.theme_name == "Dark" else LIGHT)

    # ------------- UI -------------
    def _build_ui(self):
        # Top bar
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(10, 6), padx=14)

        ttk.Label(top, text="Sravani To-Do", style="Title.TLabel").pack(side="left")

        self.search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.search_var, width=30).pack(side="left", padx=(14, 6))
        ttk.Button(top, text="Search", command=self.refresh_all).pack(side="left")

        ttk.Label(top, text="Priority:").pack(side="left", padx=(14, 4))
        self.prio_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=self.prio_var, values=["All"] + PRIORITIES, width=8, state="readonly").pack(side="left")

        ttk.Label(top, text="Tag:").pack(side="left", padx=(14, 4))
        self.tag_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.tag_var, width=14).pack(side="left")

        ttk.Label(top, text="View:").pack(side="left", padx=(14, 4))
        self.view_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=self.view_var, values=["Today", "Upcoming", "All", "Completed"], width=11, state="readonly").pack(side="left")

        ttk.Button(top, text="Reset Filters", command=self._reset_filters).pack(side="left", padx=(10,0))
        ttk.Button(top, text="Toggle Theme", command=self._toggle_theme).pack(side="right")
        ttk.Button(top, text="Open Analytics", command=self._open_analytics).pack(side="right", padx=(10,0))

        # Quick add
        qa = ttk.Frame(self)
        qa.pack(fill="x", padx=14, pady=(0, 10))
        ttk.Label(qa, text="Quick-Add:").pack(side="left")
        self.qa_var = tk.StringVar()
        ttk.Entry(qa, textvariable=self.qa_var, width=60).pack(side="left", padx=6)
        ttk.Button(qa, text="Add", style="Primary.TButton", command=self._quick_add).pack(side="left")
        ttk.Label(qa, text="e.g., 'Write report tomorrow #school !high'", foreground="#888").pack(side="left", padx=8)

        # Add/Edit row
        form = ttk.LabelFrame(self, text="Add / Edit Task")
        form.pack(fill="x", padx=14, pady=(0, 12))

        self.title_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        self.due_var = tk.StringVar()  # YYYY-MM-DD
        self.status_var = tk.StringVar(value="To Do")
        self.editing_id: Optional[str] = None

        ttk.Label(form, text="Title *").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        title_entry = ttk.Entry(form, textvariable=self.title_var, width=40)
        title_entry.grid(row=0, column=1, sticky="w", padx=8)
        self._title_entry = title_entry

        ttk.Label(form, text="Description").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(form, textvariable=self.desc_var, width=60).grid(row=1, column=1, sticky="w", padx=8)

        ttk.Label(form, text="Due (YYYY-MM-DD)").grid(row=0, column=2, sticky="w", padx=8)
        ttk.Entry(form, textvariable=self.due_var, width=15).grid(row=0, column=3, sticky="w", padx=8)

        ttk.Label(form, text="Priority").grid(row=0, column=4, sticky="w", padx=8)
        self.prio_sel = ttk.Combobox(form, values=PRIORITIES, state="readonly", width=10)
        self.prio_sel.set("Medium")
        self.prio_sel.grid(row=0, column=5, sticky="w", padx=8)

        ttk.Label(form, text="Tags (comma)").grid(row=1, column=2, sticky="w", padx=8)
        self.tags_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.tags_var, width=20).grid(row=1, column=3, sticky="w", padx=8)

        ttk.Label(form, text="Status").grid(row=1, column=4, sticky="w", padx=8)
        self.status_sel = ttk.Combobox(form, values=STATUS, state="readonly", width=12)
        self.status_sel.set("To Do")
        self.status_sel.grid(row=1, column=5, sticky="w", padx=8)

        ttk.Button(form, text="Save", command=self._save).grid(row=0, column=6, padx=10)
        ttk.Button(form, text="Cancel", command=self._cancel_edit).grid(row=1, column=6, padx=10)

        # Main board
        board = ttk.Frame(self)
        board.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        self.columns = {}
        for i, status in enumerate(STATUS):
            col = ttk.Frame(board)
            col.grid(row=0, column=i, sticky="nsew", padx=6)
            board.columnconfigure(i, weight=1)

            ttk.Label(col, text=status, style="H.TLabel").pack(anchor="w", pady=(0, 6))
            tree = ttk.Treeview(col, columns=("title", "meta"), show="headings", selectmode="browse", height=14)
            tree.heading("title", text="Title")
            tree.heading("meta", text="Meta")
            tree.column("title", width=250)
            tree.column("meta", width=280)
            tree.pack(fill="both", expand=True)

            self._register_tree_tags(tree)

            btns = ttk.Frame(col)
            btns.pack(fill="x", pady=6)
            ttk.Button(btns, text="Edit", command=lambda s=status: self._edit_selected(s)).pack(side="left")
            ttk.Button(btns, text="Delete", command=lambda s=status: self._delete_selected(s)).pack(side="left", padx=6)
            ttk.Button(btns, text="Move", command=lambda s=status: self._move_selected(s)).pack(side="left")
            ttk.Button(btns, text="Start Pomodoro", command=lambda s=status: self._pomodoro_selected(s)).pack(side="left", padx=6)

            self.columns[status] = tree

        # Bottom bar
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=14, pady=(6, 12))
        self.progress_lbl = ttk.Label(bottom, text="Progress: 0/0 done")
        self.progress_lbl.pack(side="left")

        self.analytics_lbl = ttk.Label(bottom, text=" | Analytics: - ")
        self.analytics_lbl.pack(side="left", padx=10)

        self.streak_lbl = ttk.Label(bottom, text=" | Streak: 0 days")
        self.streak_lbl.pack(side="left")

        self.timer_lbl = ttk.Label(bottom, text="Timer: idle")
        self.timer_lbl.pack(side="right")

    # ------------- Helpers -------------
    def _register_tree_tags(self, tree: ttk.Treeview):
        # priority colors (text)
        tree.tag_configure("prio-high", foreground=PRIORITY_COLORS["High"])  # red
        tree.tag_configure("prio-med", foreground=PRIORITY_COLORS["Medium"])  # orange
        tree.tag_configure("prio-low", foreground=PRIORITY_COLORS["Low"])  # green
        # status colors (text)
        tree.tag_configure("status-todo", foreground=STATUS_COLORS["To Do"])  # gray
        tree.tag_configure("status-prog", foreground=STATUS_COLORS["In Progress"])  # blue
        tree.tag_configure("status-done", foreground=STATUS_COLORS["Done"])  # green
        # background tints
        tree.tag_configure("bg-done", background=ROW_BG["done"]) 
        tree.tag_configure("bg-prog", background=ROW_BG["prog"]) 
        tree.tag_configure("bg-overdue", background=ROW_BG["overdue"]) 
        tree.tag_configure("bg-todo", background=ROW_BG["todo"]) 
        # overdue text
        tree.tag_configure("overdue", foreground=OVERDUE_COLOR)

    def _reset_filters(self):
        self.search_var.set("")
        self.prio_var.set("All")
        self.tag_var.set("")
        self.view_var.set("All")
        self.refresh_all()

    def tasks(self) -> List[Task]:
        return [Task(**o) for o in self.db.get("tasks", [])]

    def upsert(self, t: Task):
        arr = self.tasks()
        found = False
        for i, x in enumerate(arr):
            if x.id == t.id:
                arr[i] = t
                found = True
                break
        if not found:
            arr.append(t)
        self.db["tasks"] = [asdict(x) for x in arr]
        save_db(self.db)

    def _filter(self, items: List[Task]) -> List[Task]:
        q = self.search_var.get().strip().lower()
        pr = self.prio_var.get()
        tag = self.tag_var.get().strip().lower()
        view = self.view_var.get()
        today = date.today()
        horizon = today + timedelta(days=7)

        def meta_match(t: Task) -> bool:
            ok = True
            if q:
                ok = q in t.title.lower() or q in t.description.lower()
            if ok and pr != "All":
                ok = t.priority == pr
            if ok and tag:
                ok = any(tag in tg for tg in t.tags)
            if ok and view == "Today":
                ok = t.status != "Done" and t.due and datetime.fromisoformat(t.due).date() <= today
            elif ok and view == "Upcoming":
                ok = t.status != "Done" and t.due and today < datetime.fromisoformat(t.due).date() <= horizon
            elif ok and view == "Completed":
                ok = t.status == "Done"
            return ok

        return [t for t in items if meta_match(t)]

    def _decorate_title(self, t: Task) -> str:
        if SHOW_ICONS:
            return f"{STATUS_ICONS.get(t.status, '')} {t.title}".strip()
        return t.title

    def _meta_line(self, t: Task) -> str:
        due = t.due.split("T")[0] if t.due else "-"
        pr = t.priority
        pr_icon = PRIORITY_ICONS.get(pr, "") if SHOW_ICONS else ""
        parts = []
        if t.is_overdue:
            parts.append(f"{WARN_ICON} OVERDUE" if SHOW_ICONS else "OVERDUE")
        if SHOW_ICONS and pr_icon:
            parts.append(f"{pr_icon} {pr}")
        else:
            parts.append(pr)
        parts.append(f"Due {due}")
        parts.append(f"#{','.join(t.tags) if t.tags else '-'}")
        return " | ".join(parts)

    def _insert_row(self, tree: ttk.Treeview, t: Task):
        title = self._decorate_title(t)
        meta = self._meta_line(t)

        tags = []
        # priority text color
        if t.priority == "High":
            tags.append("prio-high")
        elif t.priority == "Medium":
            tags.append("prio-med")
        else:
            tags.append("prio-low")
        # status text color
        if t.status == "Done":
            tags.append("status-done")
        elif t.status == "In Progress":
            tags.append("status-prog")
        else:
            tags.append("status-todo")
        # background tint
        if t.status == "Done":
            tags.append("bg-done")
        elif t.status == "In Progress":
            tags.append("bg-prog")
        else:
            tags.append("bg-todo")
        if t.is_overdue:
            tags.append("overdue")
            tags.append("bg-overdue")

        tree.insert("", "end", values=(title, meta), tags=tuple(tags))

    def refresh_all(self):
        # clear
        for tree in self.columns.values():
            for iid in tree.get_children():
                tree.delete(iid)

        # insert
        items = self._filter(self.tasks())
        done = 0
        pr_counts = {"High": 0, "Medium": 0, "Low": 0}
        for t in items:
            if t.status == "Done":
                done += 1
            pr_counts[t.priority] = pr_counts.get(t.priority, 0) + 1
            tree = self.columns.get(t.status)
            if not tree:
                continue
            self._insert_row(tree, t)

        total = len(self.tasks())
        completion_rate = f"{(done/total*100):.0f}%" if total else "0%"
        self.progress_lbl.config(text=f"Progress: {done}/{total} done")
        self.analytics_lbl.config(text=f" | Analytics: High {pr_counts['High']}, Med {pr_counts['Medium']}, Low {pr_counts['Low']} | Completion {completion_rate}")

        # streak
        done_days = []
        for t in self.tasks():
            if t.status == "Done" and t.completed_at:
                try:
                    done_days.append(datetime.fromisoformat(t.completed_at).date())
                except Exception:
                    pass
        self.streak_lbl.config(text=f" | Streak: {consecutive_day_streak(done_days)} days")

    # ------------- Selection helpers -------------
    def _selected_task(self, status_name: str) -> Optional[Task]:
        tree = self.columns[status_name]
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", f"Select a task in '{status_name}'.")
            return None
        values = tree.item(sel[0], "values")
        title = str(values[0])
        # normalized title without status icon prefix
        if SHOW_ICONS:
            for icon in STATUS_ICONS.values():
                pref = icon + " "
                if title.startswith(pref):
                    title = title[len(pref):]
                    break
        # search
        for t in self._filter(self.tasks()):
            if t.title == title and t.status == status_name:
                return t
        for t in self.tasks():
            if t.title == title and t.status == status_name:
                return t
        return None

    def _any_selection(self) -> Optional[Tuple[str, Task]]:
        for s in STATUS:
            tree = self.columns[s]
            if tree.selection():
                t = self._selected_task(s)
                if t:
                    return s, t
        return None

    # ------------- Actions -------------
    def _quick_add(self):
        raw = self.qa_var.get().strip()
        if not raw:
            return
        title, tags, prio, due = quick_parse(raw)
        if not title:
            messagebox.showwarning("Quick-Add", "Please include a title in your text.")
            return
        t = Task(id=str(uuid.uuid4()), title=title, tags=tags or [], priority=prio or "Medium", due=due)
        self.upsert(t)
        self.qa_var.set("")
        self.refresh_all()

    def _save(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("Validation", "Title is required.")
            return
        desc = self.desc_var.get().strip()
        due_txt = self.due_var.get().strip()
        due_iso = None
        if due_txt:
            try:
                y, m, d = [int(x) for x in due_txt.split("-")]
                due_iso = datetime(y, m, d).isoformat()
            except Exception:
                messagebox.showerror("Date", "Use YYYY-MM-DD format for Due date.")
                return
        pr = self.prio_sel.get()
        tags = [t.strip().lower() for t in self.tags_var.get().split(',') if t.strip()]
        stt = self.status_sel.get()

        if self.editing_id:
            tid = self.editing_id
        else:
            tid = str(uuid.uuid4())
        completed_at = datetime.now().isoformat() if stt == "Done" else None
        task = Task(id=tid, title=title, description=desc, due=due_iso, priority=pr, tags=tags, status=stt, completed_at=completed_at)
        self.upsert(task)
        self._clear_form()
        self.refresh_all()

    def _clear_form(self):
        self.editing_id = None
        self.title_var.set("")
        self.desc_var.set("")
        self.due_var.set("")
        self.prio_sel.set("Medium")
        self.tags_var.set("")
        self.status_sel.set("To Do")

    def _cancel_edit(self):
        self._clear_form()

    def _edit_selected(self, status_name: str):
        t = self._selected_task(status_name)
        if not t:
            return
        self.editing_id = t.id
        self.title_var.set(t.title)
        self.desc_var.set(t.description)
        self.due_var.set(t.due.split('T')[0] if t.due else "")
        self.prio_sel.set(t.priority)
        self.tags_var.set(",".join(t.tags))
        self.status_sel.set(t.status)
        self._title_entry.focus_set()

    def _delete_selected(self, status_name: str):
        t = self._selected_task(status_name)
        if not t:
            return
        if messagebox.askyesno("Delete", f"Delete '{t.title}'?"):
            remaining = [asdict(x) for x in self.tasks() if x.id != t.id]
            self.db["tasks"] = remaining
            save_db(self.db)
            self.refresh_all()

    def _move_selected(self, status_name: str):
        t = self._selected_task(status_name)
        if not t:
            return
        idx = STATUS.index(t.status)
        new_status = STATUS[min(idx + 1, len(STATUS)-1)]
        t.status = new_status
        if new_status == "Done":
            t.completed_at = datetime.now().isoformat()
        self.upsert(t)
        self.refresh_all()

    def _pomodoro_selected(self, status_name: str):
        t = self._selected_task(status_name)
        if not t:
            return
        minutes = simpledialog.askinteger("Pomodoro", "Minutes (default 25):", minvalue=5, maxvalue=120)
        if not minutes:
            minutes = 25
        self.timer_running = True
        self.timer_end = time.time() + minutes * 60
        self.timer_task_id = t.id
        if t.status == "To Do":
            t.status = "In Progress"
            self.upsert(t)
        self._open_focus_mode(minutes, t.title)
        self.refresh_all()

    # ------------- Focus Mode -------------
    def _open_focus_mode(self, minutes: int, title: str):
        if self.focus_win and tk.Toplevel.winfo_exists(self.focus_win):
            try:
                self.focus_win.destroy()
            except Exception:
                pass
        win = tk.Toplevel(self)
        win.title("Focus Mode")
        win.geometry("520x280")
        win.configure(bg="#101418")
        lbl_title = tk.Label(win, text=title, font=("Segoe UI", 14, "bold"), fg="#9ec9ff", bg="#101418")
        lbl_title.pack(pady=(24, 8))
        self.focus_time_lbl = tk.Label(win, text="", font=("Consolas", 48, "bold"), fg="#ffffff", bg="#101418")
        self.focus_time_lbl.pack(pady=8)
        tk.Label(win, text="Stay focused. We'll notify here when done.", fg="#c9cbd1", bg="#101418").pack(pady=(0, 16))
        self.focus_win = win

    # ------------- Timer -------------
    def _tick(self):
        if self.timer_running:
            remaining = int(self.timer_end - time.time())
            if remaining <= 0:
                self.timer_running = False
                self.timer_lbl.config(text="Timer: complete. Please take a short break.")
                if self.focus_win and tk.Toplevel.winfo_exists(self.focus_win):
                    self.focus_time_lbl.config(text="00:00")
                    messagebox.showinfo("Pomodoro", "Focus session complete!")
            else:
                m, s = divmod(remaining, 60)
                task = next((t for t in self.tasks() if t.id == self.timer_task_id), None)
                focus = f" ({task.title})" if task else ""
                self.timer_lbl.config(text=f"Timer:{focus} {m:02d}:{s:02d}")
                if self.focus_win and tk.Toplevel.winfo_exists(self.focus_win):
                    self.focus_time_lbl.config(text=f"{m:02d}:{s:02d}")
        self.after(500, self._tick)

    # ------------- Analytics (Charts) -------------
    def _summaries(self):
        items = self.tasks()
        # Status x Priority matrix
        status_idx = {s:i for i,s in enumerate(STATUS)}
        pr_idx = {p:i for i,p in enumerate(PRIORITIES)}
        mat = [[0]*len(PRIORITIES) for _ in STATUS]
        pr_totals = {p:0 for p in PRIORITIES}
        # due buckets
        buckets = {"Overdue":0, "Today":0, "Next 7 days":0, "Later":0, "No due":0}
        today = date.today()
        for t in items:
            mat[status_idx[t.status]][pr_idx[t.priority]] += 1
            pr_totals[t.priority] += 1
            if t.due:
                try:
                    d = datetime.fromisoformat(t.due).date()
                    if d < today:
                        buckets["Overdue"] += 1
                    elif d == today:
                        buckets["Today"] += 1
                    elif d <= today + timedelta(days=7):
                        buckets["Next 7 days"] += 1
                    else:
                        buckets["Later"] += 1
                except Exception:
                    buckets["No due"] += 1
            else:
                buckets["No due"] += 1
        return mat, pr_totals, buckets

    def _open_analytics(self):
        win = tk.Toplevel(self)
        win.title("Analytics")
        win.geometry("900x560")
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True)

        # Tab 1: Status vs Priority (stacked bar)
        tab1 = ttk.Frame(nb); nb.add(tab1, text="Status × Priority")
        fig1 = Figure(figsize=(7.6,4.8), dpi=100)
        ax1 = fig1.add_subplot(111)
        mat, pr_totals, buckets = self._summaries()
        x = list(range(len(STATUS)))
        bars = []
        bottom = [0]*len(STATUS)
        labels = PRIORITIES
        colors = [PRIORITY_COLORS[p] for p in PRIORITIES]
        for j,p in enumerate(PRIORITIES):
            vals = [mat[i][j] for i in range(len(STATUS))]
            b = ax1.bar(x, vals, bottom=bottom, label=p, color=colors[j])
            bottom = [bottom[i]+vals[i] for i in range(len(STATUS))]
            bars.append(b)
        ax1.set_xticks(x, STATUS)
        ax1.set_ylabel("Tasks")
        ax1.set_title("Tasks by Status (stacked by Priority)")
        ax1.legend()
        canvas1 = FigureCanvasTkAgg(fig1, master=tab1)
        canvas1.draw(); canvas1.get_tk_widget().pack(fill="both", expand=True)

        # Tab 2: Priority distribution (pie)
        tab2 = ttk.Frame(nb); nb.add(tab2, text="Priority Distribution")
        fig2 = Figure(figsize=(7.6,4.8), dpi=100)
        ax2 = fig2.add_subplot(111)
        sizes = [pr_totals[p] for p in PRIORITIES]
        ax2.pie(sizes, labels=PRIORITIES, autopct=lambda p: f"{p:.0f}%" if p>0 else "", startangle=90, colors=[PRIORITY_COLORS[p] for p in PRIORITIES])
        ax2.set_title("Overall Priority Mix")
        canvas2 = FigureCanvasTkAgg(fig2, master=tab2)
        canvas2.draw(); canvas2.get_tk_widget().pack(fill="both", expand=True)

        # Tab 3: Due buckets (bar)
        tab3 = ttk.Frame(nb); nb.add(tab3, text="Due Timeline")
        fig3 = Figure(figsize=(7.6,4.8), dpi=100)
        ax3 = fig3.add_subplot(111)
        labels = list(buckets.keys())
        vals = [buckets[k] for k in labels]
        ax3.bar(labels, vals)
        ax3.set_ylabel("Tasks")
        ax3.set_title("Due date buckets")
        for i,v in enumerate(vals):
            ax3.text(i, v + 0.05, str(v), ha='center', va='bottom')
        canvas3 = FigureCanvasTkAgg(fig3, master=tab3)
        canvas3.draw(); canvas3.get_tk_widget().pack(fill="both", expand=True)

    # ------------- Shortcuts -------------
    def _bind_shortcuts(self):
        # new task
        self.bind_all("<Control-n>", lambda e: self._title_entry.focus_set())
        self.bind_all("<Command-n>", lambda e: self._title_entry.focus_set())  # mac
        # save
        self.bind_all("<Control-s>", lambda e: self._save())
        self.bind_all("<Command-s>", lambda e: self._save())  # mac
        # delete selected from any column
        def delete_any(_e=None):
            sel = self._any_selection()
            if not sel:
                return
            status, t = sel
            if messagebox.askyesno("Delete", f"Delete '{t.title}'?"):
                remaining = [asdict(x) for x in self.tasks() if x.id != t.id]
                self.db["tasks"] = remaining
                save_db(self.db)
                self.refresh_all()
        self.bind_all("<Delete>", delete_any)

# ---------------- main ----------------

if __name__ == "__main__":
    root = tk.Tk()
    app = ToDoApp(root)
    root.mainloop()
