import os
import sys
import time
import shutil
import json
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import pandas as pd

# Optional drag & drop support for Windows
try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False

DEFAULT_PATH = os.path.join(os.getcwd(), "dataset_cache", "unified_dataset.parquet")


def fast_snippet(val) -> tuple:
    """
    BLAZING FAST: Extracts a short 100-character preview and estimated character count
    WITHOUT running heavy JSON serialization or scanning 18k-token nested arrays.
    Returns: (preview_string, total_length)
    """
    if val is None:
        return ("", 0)

    # 1. If it's a list/numpy array (conversations/messages)
    if isinstance(val, (list, np.ndarray)):
        if len(val) == 0:
            return ("[]", 0)
        first_item = val[0]
        # If it's a ShareGPT/ChatML dict
        if isinstance(first_item, dict):
            speaker = first_item.get("from") or first_item.get("role") or "?"
            content = first_item.get("value") or first_item.get("content") or ""
            content_snippet = str(content).replace("\n", " ")[:90]
            preview = f"[{speaker.upper()}]: {content_snippet}..."
        else:
            preview = str(first_item).replace("\n", " ")[:90] + "..."
        # Rough fast size estimate without traversing
        approx_len = len(val) * 200
        return (preview, approx_len)

    # 2. If it's already a string or numeric
    if isinstance(val, str):
        preview = val.replace("\n", " ").strip()
        preview = (preview[:100] + "...") if len(preview) > 100 else preview
        return (preview, len(val))

    s = str(val)
    return (s[:100], len(s))


def full_serialize(val) -> str:
    """Only called ONCE when you click a specific row to edit it."""
    if val is None:
        return ""
    if isinstance(val, np.ndarray):
        val = val.tolist()
    if isinstance(val, (list, dict)):
        try:
            return json.dumps(val, ensure_ascii=False, indent=2)
        except Exception:
            return str(val)
    if isinstance(val, float) and pd.isna(val):
        return ""
    return str(val)


def full_deserialize(text_str: str, original_template):
    """Parses edited text back to original column structure."""
    text_str = text_str.strip()
    if isinstance(original_template, (list, np.ndarray)):
        try:
            parsed = json.loads(text_str)
            if isinstance(parsed, list):
                if isinstance(original_template, np.ndarray):
                    return np.array(parsed, dtype=object)
                return parsed
        except Exception:
            pass
    elif isinstance(original_template, dict):
        try:
            parsed = json.loads(text_str)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return text_str


def parse_to_qa(val) -> tuple:
    """Extracts (question, answer) from raw string, ShareGPT, or ChatML structures."""
    if val is None:
        return ("", "")
    
    # 1. If it's a conversation list/array
    if isinstance(val, (list, np.ndarray)):
        turns = val.tolist() if isinstance(val, np.ndarray) else val
        q_parts, a_parts = [], []
        for turn in turns:
            if isinstance(turn, dict):
                role = str(turn.get("from") or turn.get("role") or "").lower()
                content = str(turn.get("value") or turn.get("content") or "")
                if role in ("human", "user"):
                    q_parts.append(content)
                elif role in ("gpt", "assistant", "bot"):
                    a_parts.append(content)
        return ("\n\n".join(q_parts), "\n\n".join(a_parts))
    
    text = str(val).strip()
    
    # 2. Try JSON parse if it's a stringified JSON list
    if (text.startswith("[") and text.endswith("]")) or (text.startswith("{") and text.endswith("}")):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parse_to_qa(parsed)
        except Exception:
            pass
            
    # 3. Llama-3 Header Format
    if "<|start_header_id|>" in text:
        parts = text.split("<|start_header_id|>")
        q_parts, a_parts = [], []
        for p in parts:
            if p.startswith("user<|end_header_id|>"):
                body = p.split("<|end_header_id|>")[-1].split("<|eot_id|>")[0].strip()
                q_parts.append(body)
            elif p.startswith("assistant<|end_header_id|>"):
                body = p.split("<|end_header_id|>")[-1].split("<|eot_id|>")[0].strip()
                a_parts.append(body)
        if q_parts or a_parts:
            return ("\n\n".join(q_parts), "\n\n".join(a_parts))

    # 4. Fallback: Entire text to Question, Answer empty
    return (text, "")


def build_from_qa(q_text: str, a_text: str, template) -> str:
    """Converts Q and A back into the appropriate target format string."""
    q_clean = q_text.strip()
    a_clean = a_text.strip()
    
    # If the column is natively a list/array (ShareGPT)
    if isinstance(template, (list, np.ndarray)):
        convs = [
            {"from": "human", "value": q_clean},
            {"from": "gpt", "value": a_clean}
        ]
        return json.dumps(convs, ensure_ascii=False, indent=2)
    
    raw_template_str = str(template) if template is not None else ""
    
    # If template is Llama 3 header tokens
    if "<|start_header_id|>" in raw_template_str:
        return f"<|start_header_id|>user<|end_header_id|>\n\n{q_clean}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{a_clean}<|eot_id|>"
    
    # If template is stringified JSON
    if raw_template_str.strip().startswith("[") and "value" in raw_template_str:
        convs = [
            {"from": "human", "value": q_clean},
            {"from": "gpt", "value": a_clean}
        ]
        return json.dumps(convs, ensure_ascii=False, indent=2)

    # Standard ShareGPT text default
    convs = [
        {"from": "human", "value": q_clean},
        {"from": "gpt", "value": a_clean}
    ]
    return json.dumps(convs, ensure_ascii=False, indent=2)


class FastParquetEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("PMPF High-Speed Parquet Editor")
        self.root.geometry("1150x820")
        self.root.minsize(850, 600)

        self.df = pd.DataFrame()
        self.current_file = ""
        self.target_col = ""
        self.selected_index = None

        self.setup_ui()
        self.setup_drag_and_drop()

        initial_file = None
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            initial_file = sys.argv[1]
        elif os.path.exists(DEFAULT_PATH):
            initial_file = DEFAULT_PATH

        if initial_file:
            self.root.after(50, lambda: self.load_parquet(initial_file))

    def setup_ui(self):
        toolbar = tk.Frame(self.root, bg="#eceff1", pady=8, padx=10)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="📂 Open Parquet", font=("Arial", 9, "bold"), command=self.open_file_dialog).pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="💾 Save Overwrite (With Backup)", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=self.save_overwrite).pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="💾 Save As...", bg="#455a64", fg="white", font=("Arial", 9), command=self.save_as_dialog).pack(side=tk.LEFT, padx=4)

        dnd_text = " [Drag & Drop Ready]" if HAS_WINDND else ""
        self.status_label = tk.Label(toolbar, text="No file loaded" + dnd_text, bg="#eceff1", fg="#37474f", font=("Arial", 9))
        self.status_label.pack(side=tk.RIGHT, padx=10)

        filter_bar = tk.Frame(self.root, bg="#f5f5f5", pady=5, padx=10)
        filter_bar.pack(side=tk.TOP, fill=tk.X)

        tk.Label(filter_bar, text="Target Column:", bg="#f5f5f5", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.col_combo = ttk.Combobox(filter_bar, state="readonly", width=18)
        self.col_combo.pack(side=tk.LEFT, padx=6)
        self.col_combo.bind("<<ComboboxSelected>>", self.on_column_changed)

        tk.Label(filter_bar, text="🔍 Quick Filter:", bg="#f5f5f5", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(12, 0))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self.refresh_table())
        tk.Entry(filter_bar, textvariable=self.search_var, font=("Consolas", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tree_frame = tk.LabelFrame(self.main_container, text=" Dataset Entries ", padx=5, pady=5)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        columns = ("row_idx", "preview", "char_len")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("row_idx", text="Index")
        self.tree.heading("preview", text="Content Preview")
        self.tree.heading("char_len", text="Length Est.")

        self.tree.column("row_idx", width=65, minwidth=50, anchor="center")
        self.tree.column("preview", width=840, minwidth=400)
        self.tree.column("char_len", width=95, minwidth=60, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)

        editor_frame = tk.LabelFrame(self.main_container, text=" Fast Content Editor ", padx=5, pady=5)
        editor_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(5, 0))

        meta_header = tk.Frame(editor_frame)
        meta_header.pack(fill=tk.X, pady=(0, 4))

        self.editor_title = tk.Label(meta_header, text="Select an entry above or type to create a new row", font=("Arial", 9, "bold"), fg="#1565c0")
        self.editor_title.pack(side=tk.LEFT)

        self.char_counter = tk.Label(meta_header, text="Chars: 0", font=("Arial", 9), fg="#616161")
        self.char_counter.pack(side=tk.RIGHT)

        # Single Window (Raw / ShareGPT) Container
        self.raw_frame = tk.Frame(editor_frame)
        self.text_editor = tk.Text(self.raw_frame, wrap="word", undo=True, height=11, font=("Consolas", 10), relief="groove", bd=1)
        self.text_editor.pack(fill=tk.BOTH, expand=True)
        self.text_editor.bind("<KeyRelease>", lambda _: self.update_char_count())
        self.raw_frame.pack(fill=tk.BOTH, expand=True)

        # Dual Window (Question / Answer) Container
        self.qa_frame = tk.Frame(editor_frame)
        
        q_box_frame = tk.Frame(self.qa_frame)
        q_box_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        tk.Label(q_box_frame, text="👤 Human / Question:", font=("Arial", 9, "bold"), fg="#1976d2").pack(anchor="w")
        self.q_editor = tk.Text(q_box_frame, wrap="word", undo=True, height=11, font=("Consolas", 10), relief="groove", bd=1)
        self.q_editor.pack(fill=tk.BOTH, expand=True)
        self.q_editor.bind("<KeyRelease>", lambda _: self.update_char_count())

        a_box_frame = tk.Frame(self.qa_frame)
        a_box_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))
        tk.Label(a_box_frame, text="🤖 Assistant / Answer (Paste LLM here):", font=("Arial", 9, "bold"), fg="#2e7d32").pack(anchor="w")
        self.a_editor = tk.Text(a_box_frame, wrap="word", undo=True, height=11, font=("Consolas", 10), relief="groove", bd=1)
        self.a_editor.pack(fill=tk.BOTH, expand=True)
        self.a_editor.bind("<KeyRelease>", lambda _: self.update_char_count())

        btn_bar = tk.Frame(editor_frame, pady=6)
        btn_bar.pack(fill=tk.X)

        tk.Button(btn_bar, text="💾 Update Selected", bg="#1976d2", fg="white", font=("Arial", 9, "bold"), padx=10, command=self.update_entry).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_bar, text="➕ Add as New Row", bg="#00796b", fg="white", font=("Arial", 9, "bold"), padx=10, command=self.add_entry).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_bar, text="🗑 Delete Selected", bg="#d32f2f", fg="white", font=("Arial", 9), padx=10, command=self.delete_entry).pack(side=tk.LEFT, padx=3)

        # Mode Toggle Checkbox
        self.split_view_var = tk.BooleanVar(value=False)
        self.chk_view = tk.Checkbutton(
            btn_bar, text="Split Q&A Mode", font=("Arial", 9, "bold"),
            variable=self.split_view_var, command=self.toggle_editor_view
        )
        self.chk_view.pack(side=tk.LEFT, padx=(12, 4))

        tk.Button(btn_bar, text="🧹 Clear Text Box", font=("Arial", 9), command=self.clear_box).pack(side=tk.RIGHT, padx=3)

    def setup_drag_and_drop(self):
        if HAS_WINDND:
            try:
                windnd.hook_dropfiles(self.root, func=self.on_file_drop)
            except Exception as e:
                print(f"Drag & Drop hook warning: {e}")

    def on_file_drop(self, files):
        if not files: return
        f = files[0]
        if isinstance(f, bytes): f = f.decode(sys.getfilesystemencoding(), errors="ignore")
        if f.lower().endswith(".parquet"):
            self.load_parquet(f)
        else:
            messagebox.showwarning("Invalid File", f"Must be a .parquet file:\n{f}")

    def open_file_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("Parquet Files", "*.parquet"), ("All Files", "*.*")])
        if path:
            self.load_parquet(path)

    def load_parquet(self, path):
        try:
            t0 = time.time()
            print(f"Reading parquet: {path}")
            df = pd.read_parquet(path)
            if df.empty:
                messagebox.showwarning("Empty Parquet", "Parquet file contains 0 rows.")
                return

            self.df = df
            self.current_file = os.path.abspath(path)

            cols = list(self.df.columns)
            self.col_combo["values"] = cols

            if "text" in cols: self.target_col = "text"
            elif "conversations" in cols: self.target_col = "conversations"
            elif "messages" in cols: self.target_col = "messages"
            else: self.target_col = cols[0]

            self.col_combo.set(self.target_col)
            self.clear_box()
            self.refresh_table()

            elapsed = round(time.time() - t0, 3)
            print(f"Loaded {len(df)} rows in {elapsed}s")
            self.status_label.config(text=f"Loaded: {os.path.basename(path)} | Rows: {len(self.df)} ({elapsed}s)")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load Parquet:\n{e}")

    def on_column_changed(self, _):
        self.target_col = self.col_combo.get()
        self.clear_box()
        self.refresh_table()

    def refresh_table(self):
        # Detach/clear quickly
        for i in self.tree.get_children():
            self.tree.delete(i)

        if self.df.empty or not self.target_col or self.target_col not in self.df.columns:
            return

        query = self.search_var.get().lower()

        # HIGH SPEED POPULATION LOOP
        series = self.df[self.target_col]
        for idx in self.df.index:
            raw_val = series.iat[idx]
            preview, char_len = fast_snippet(raw_val)

            if query and query not in preview.lower():
                continue

            self.tree.insert("", tk.END, values=(idx, preview, char_len))

    def toggle_editor_view(self):
        """Swaps between 1-window raw ShareGPT/JSON and 2-window Markdown Q&A."""
        template = None
        if self.selected_index is not None:
            template = self.df.at[self.selected_index, self.target_col]
        elif not self.df.empty and self.target_col in self.df.columns:
            template = self.df[self.target_col].dropna().iloc[0] if not self.df[self.target_col].dropna().empty else ""

        if self.split_view_var.get():
            # Switching TO Split Q&A mode: convert current text_editor content into Q & A
            current_raw = self.text_editor.get("1.0", tk.END).strip()
            q, a = parse_to_qa(current_raw)
            self.q_editor.delete("1.0", tk.END)
            self.q_editor.insert("1.0", q)
            self.a_editor.delete("1.0", tk.END)
            self.a_editor.insert("1.0", a)

            self.raw_frame.pack_forget()
            self.qa_frame.pack(fill=tk.BOTH, expand=True)
        else:
            # Switching BACK to 1-window mode: autoconvert Q & A back into raw ShareGPT format
            q = self.q_editor.get("1.0", tk.END).strip()
            a = self.a_editor.get("1.0", tk.END).strip()
            combined_raw = build_from_qa(q, a, template)

            self.text_editor.delete("1.0", tk.END)
            self.text_editor.insert("1.0", combined_raw)

            self.qa_frame.pack_forget()
            self.raw_frame.pack(fill=tk.BOTH, expand=True)

        self.update_char_count()

    def get_current_editor_text(self, template) -> str:
        """Gets consolidated string regardless of active editor mode."""
        if self.split_view_var.get():
            q = self.q_editor.get("1.0", tk.END).strip()
            a = self.a_editor.get("1.0", tk.END).strip()
            return build_from_qa(q, a, template)
        return self.text_editor.get("1.0", tk.END).strip()

    def update_char_count(self):
        if self.split_view_var.get():
            q_len = len(self.q_editor.get("1.0", tk.END).strip())
            a_len = len(self.a_editor.get("1.0", tk.END).strip())
            self.char_counter.config(text=f"Q: {q_len} | A: {a_len} | Total: {q_len + a_len}")
        else:
            total_len = len(self.text_editor.get("1.0", tk.END).strip())
            self.char_counter.config(text=f"Chars: {total_len}")

    def on_row_selected(self, _):
        sel = self.tree.selection()
        if not sel: return

        row_idx = int(self.tree.item(sel[0], "values")[0])
        self.selected_index = row_idx

        raw_val = self.df.at[row_idx, self.target_col]
        full_text = full_serialize(raw_val)

        # Populate single view
        self.text_editor.delete("1.0", tk.END)
        self.text_editor.insert("1.0", full_text)

        # Populate split view
        q, a = parse_to_qa(raw_val)
        self.q_editor.delete("1.0", tk.END)
        self.q_editor.insert("1.0", q)
        self.a_editor.delete("1.0", tk.END)
        self.a_editor.insert("1.0", a)

        self.editor_title.config(text=f"Editing Row #{row_idx} (Column: '{self.target_col}')", fg="#e65100")
        self.update_char_count()

    def update_entry(self):
        if self.selected_index is None:
            messagebox.showwarning("Selection Error", "Select a row from the table first.")
            return

        template = self.df.at[self.selected_index, self.target_col]
        new_text = self.get_current_editor_text(template)
        parsed_val = full_deserialize(new_text, template)

        self.df.at[self.selected_index, self.target_col] = parsed_val
        self.refresh_table()
        messagebox.showinfo("Updated", f"Row #{self.selected_index} updated in memory!\nClick 'Save Overwrite' to commit to disk.")

    def add_entry(self):
        template = self.df[self.target_col].dropna().iloc[0] if not self.df[self.target_col].dropna().empty else ""
        new_text = self.get_current_editor_text(template)

        if not new_text.strip():
            messagebox.showwarning("Empty", "Cannot insert an empty entry.")
            return

        parsed_val = full_deserialize(new_text, template)

        new_row = {col: None for col in self.df.columns}
        new_row[self.target_col] = parsed_val

        self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
        self.selected_index = len(self.df) - 1

        self.refresh_table()
        self.status_label.config(text=f"Loaded: {os.path.basename(self.current_file)} | Rows: {len(self.df)}")
        messagebox.showinfo("Added", f"New row added as ID #{self.selected_index}!")

    def delete_entry(self):
        if self.selected_index is None:
            messagebox.showwarning("Selection Error", "Select a row from the table to delete.")
            return

        if messagebox.askyesno("Confirm Delete", f"Delete row #{self.selected_index}?"):
            self.df.drop(index=self.selected_index, inplace=True)
            self.df.reset_index(drop=True, inplace=True)
            self.clear_box()
            self.refresh_table()
            self.status_label.config(text=f"Loaded: {os.path.basename(self.current_file)} | Rows: {len(self.df)}")
            messagebox.showinfo("Deleted", "Row deleted from memory.")

    def save_overwrite(self):
        if self.df.empty or not self.current_file:
            messagebox.showwarning("Warning", "No active parquet dataset loaded.")
            return

        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup_file = f"{self.current_file}.backup_{ts}"
            shutil.copy2(self.current_file, backup_file)

            self.df.reset_index(drop=True, inplace=True)
            self.df.to_parquet(self.current_file, index=False)
            messagebox.showinfo("Saved", f"Parquet saved successfully!\nSafety backup:\n{os.path.basename(backup_file)}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Could not overwrite file:\n{e}")

    def save_as_dialog(self):
        if self.df.empty:
            messagebox.showwarning("Warning", "No dataset to save.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".parquet", filetypes=[("Parquet Files", "*.parquet")])
        if path:
            try:
                self.df.reset_index(drop=True, inplace=True)
                self.df.to_parquet(path, index=False)
                self.current_file = path
                self.status_label.config(text=f"Loaded: {os.path.basename(path)} | Rows: {len(self.df)}")
                messagebox.showinfo("Saved", f"Saved to:\n{os.path.basename(path)}")
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", f"Save Failed:\n{e}")

    def clear_box(self):
        self.selected_index = None
        self.text_editor.delete("1.0", tk.END)
        self.q_editor.delete("1.0", tk.END)
        self.a_editor.delete("1.0", tk.END)
        self.editor_title.config(text="Select an entry above or type to create a new row", fg="#1565c0")
        self.update_char_count()


def main():
    try:
        root = tk.Tk()
        app = FastParquetEditor(root)
        root.mainloop()
    except Exception as e:
        print("\nFATAL ERROR:")
        traceback.print_exc()
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()