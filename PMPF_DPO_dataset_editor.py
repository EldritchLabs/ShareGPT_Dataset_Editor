import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import json
import os

DEFAULT_SAVE_PATH = os.path.join(os.getcwd(), "dataset_cache", "dpo_dataset.json")

class DPOEditorV1:
    def __init__(self, root):
        self.root = root
        self.root.title("DPO Preference Dataset Editor - v1")
        self.root.geometry("1100x850")
        
        # Data State: List of dicts: {"id": int, "system": str, "prompt": str, "chosen": str, "rejected": str}
        self.dataset = [] 
        self.selected_item_index = None
        self.next_id = 1
        
        self.setup_styles()
        self.create_main_container()
        self.show_input_mode()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", padding=5, font=("Arial", 10))
        style.configure("Treeview", rowheight=28)

    def create_main_container(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.nav_bar = tk.Frame(self.main_frame, bg="#e0e0e0", pady=6)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X)

        self.toggle_btn = tk.Button(
            self.nav_bar, text="📂 Switch to Library View", 
            command=self.toggle_view, font=("Arial", 10, "bold"), padx=15
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=10)

        self.counter_label = tk.Label(self.nav_bar, text="Pairs: 0", font=("Arial", 10, "bold"), bg="#e0e0e0")
        self.counter_label.pack(side=tk.RIGHT, padx=15)

        self.content_area = tk.Frame(self.main_frame)
        self.content_area.pack(fill=tk.BOTH, expand=True)

    def update_counter(self):
        self.counter_label.config(text=f"Total DPO Pairs: {len(self.dataset)}")

    def clear_content_area(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

    def toggle_view(self):
        if hasattr(self, 'current_mode') and self.current_mode == 'input':
            self.show_library_mode()
        else:
            self.show_input_mode()

    # --- INPUT / EDIT VIEW ---
    def show_input_mode(self):
        self.current_mode = 'input'
        self.toggle_btn.config(text="📚 Switch to Library Mode")
        self.clear_content_area()

        container = tk.Frame(self.content_area, padx=15, pady=8)
        container.pack(fill=tk.BOTH, expand=True)

        # Header Info
        header = tk.Frame(container)
        header.pack(fill=tk.X, pady=(0, 5))
        display_id = self.dataset[self.selected_item_index]['id'] if self.selected_item_index is not None else self.next_id
        tk.Label(header, text=f"DPO Pair ID: {display_id}", font=("Arial", 13, "bold")).pack(side=tk.LEFT)
        
        if self.selected_item_index is not None:
            tk.Label(header, text=" [EDITING RECORD]", fg="orange", font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=10)

        # 1. System Prompt (Optional)
        tk.Label(container, text="System Prompt (Optional Persona Context):", font=("Arial", 9, "bold"), fg="#555").pack(anchor="w")
        self.sys_text = tk.Text(container, height=2, font=("Consolas", 10), relief="groove", bd=1)
        self.sys_text.pack(fill=tk.X, pady=(0, 6))

        # 2. Prompt (Question)
        tk.Label(container, text="User Prompt / Question (Trigger):", font=("Arial", 9, "bold"), fg="#1976D2").pack(anchor="w")
        self.prompt_text = tk.Text(container, height=3, font=("Consolas", 10), relief="groove", bd=1)
        self.prompt_text.pack(fill=tk.X, pady=(0, 6))

        # Split pane for Chosen vs Rejected
        answers_frame = tk.Frame(container)
        answers_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        # Left: Chosen (Positive)
        left_frame = tk.Frame(answers_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        tk.Label(left_frame, text="✅ CHOSEN RESPONSE (Target Author Style):", font=("Arial", 9, "bold"), fg="#2E7D32").pack(anchor="w")
        self.chosen_text = tk.Text(left_frame, font=("Consolas", 10), relief="groove", bd=1, undo=True)
        self.chosen_text.pack(fill=tk.BOTH, expand=True)

        # Right: Rejected (Negative)
        right_frame = tk.Frame(answers_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        tk.Label(right_frame, text="❌ REJECTED RESPONSE (SFT Temp-0 Mistake to Unlearn):", font=("Arial", 9, "bold"), fg="#C62828").pack(anchor="w")
        self.rejected_text = tk.Text(right_frame, font=("Consolas", 10), relief="groove", bd=1, undo=True)
        self.rejected_text.pack(fill=tk.BOTH, expand=True)

        # Button Bar
        btn_frame = tk.Frame(container, pady=10)
        btn_frame.pack(fill=tk.X)

        if self.selected_item_index is not None:
            tk.Button(btn_frame, text="💾 SAVE CHANGES", bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), padx=15, command=self.save_edit).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="❌ CANCEL", bg="#e53935", fg="white", padx=10, command=self.cancel_edit).pack(side=tk.LEFT, padx=5)
        else:
            tk.Button(btn_frame, text="➕ ADD TO DATASET", bg="#2196F3", fg="white", font=("Arial", 9, "bold"), padx=15, command=self.add_pair).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="🗑 CLEAR FIELDS", padx=10, command=self.clear_fields).pack(side=tk.LEFT, padx=5)

        # Bottom Bar: Open / Export
        footer = tk.Frame(container, pady=5)
        footer.pack(fill=tk.X)
        tk.Button(footer, text="📂 LOAD JSON", width=14, command=self.open_file).pack(side=tk.LEFT, padx=5)
        tk.Button(footer, text="💾 EXPORT JSON", width=18, bg="#388E3C", fg="white", font=("Arial", 9, "bold"), command=self.export_all).pack(side=tk.RIGHT, padx=5)

    def clear_fields(self):
        self.prompt_text.delete("1.0", tk.END)
        self.chosen_text.delete("1.0", tk.END)
        self.rejected_text.delete("1.0", tk.END)

    def add_pair(self):
        p = self.prompt_text.get("1.0", tk.END).strip()
        c = self.chosen_text.get("1.0", tk.END).strip()
        r = self.rejected_text.get("1.0", tk.END).strip()
        s = self.sys_text.get("1.0", tk.END).strip()

        if not p or not c or not r:
            messagebox.showwarning("Missing Data", "Prompt, Chosen, and Rejected fields are all required!")
            return

        entry = {"id": self.next_id, "system": s, "prompt": p, "chosen": c, "rejected": r}
        self.dataset.append(entry)
        self.next_id += 1
        self.update_counter()
        self.clear_fields()
        messagebox.showinfo("Saved", f"Pair #{entry['id']} appended to DPO dataset!")

    def save_edit(self):
        idx = self.selected_item_index
        self.dataset[idx]["system"] = self.sys_text.get("1.0", tk.END).strip()
        self.dataset[idx]["prompt"] = self.prompt_text.get("1.0", tk.END).strip()
        self.dataset[idx]["chosen"] = self.chosen_text.get("1.0", tk.END).strip()
        self.dataset[idx]["rejected"] = self.rejected_text.get("1.0", tk.END).strip()
        
        self.selected_item_index = None
        self.show_library_mode()

    def cancel_edit(self):
        self.selected_item_index = None
        self.show_input_mode()

    # --- LIBRARY / VIEWER MODE ---
    def show_library_mode(self):
        self.current_mode = 'library'
        self.toggle_btn.config(text="📝 Switch to Input Mode")
        self.clear_content_area()

        container = tk.Frame(self.content_area, padx=15, pady=8)
        container.pack(fill=tk.BOTH, expand=True)

        # Search bar
        search_frame = tk.Frame(container)
        search_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(search_frame, text="Filter Prompt/Chosen:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self.refresh_tree())
        tk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Treeview
        columns = ("id", "prompt", "chosen", "rejected")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("id", text="ID")
        self.tree.heading("prompt", text="Prompt")
        self.tree.heading("chosen", text="Chosen (Good)")
        self.tree.heading("rejected", text="Rejected (Bad)")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("prompt", width=300)
        self.tree.column("chosen", width=350)
        self.tree.column("rejected", width=350)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_double_click)

        sb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)

        self.refresh_tree()

    def refresh_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        query = self.search_var.get().lower()
        for idx, item in enumerate(self.dataset):
            p_snippet = item['prompt'].replace('\n', ' ')
            c_snippet = item['chosen'].replace('\n', ' ')
            r_snippet = item['rejected'].replace('\n', ' ')

            if query and (query not in p_snippet.lower() and query not in c_snippet.lower()):
                continue

            self.tree.insert("", tk.END, values=(item['id'], p_snippet, c_snippet, r_snippet), tags=(str(idx),))

    def on_double_click(self, event):
        sel = self.tree.selection()
        if not sel: return
        item_tag = self.tree.item(sel[0], "tags")[0]
        idx = int(item_tag)

        self.selected_item_index = idx
        self.show_input_mode()

        data = self.dataset[idx]
        self.sys_text.insert("1.0", data.get("system", ""))
        self.prompt_text.insert("1.0", data.get("prompt", ""))
        self.chosen_text.insert("1.0", data.get("chosen", ""))
        self.rejected_text.insert("1.0", data.get("rejected", ""))

    # --- FILE I/O ---
    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.dataset = json.load(f)
                ids = [int(x["id"]) for x in self.dataset if "id" in x and str(x["id"]).isdigit()]
                self.next_id = max(ids) + 1 if ids else 1
                self.update_counter()
                self.show_library_mode()
                messagebox.showinfo("Loaded", f"Loaded {len(self.dataset)} items.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load JSON:\n{e}")

    def export_all(self):
        os.makedirs(os.path.dirname(DEFAULT_SAVE_PATH), exist_ok=True)
        path = filedialog.asksaveasfilename(
            initialdir=os.path.dirname(DEFAULT_SAVE_PATH),
            initialfile=os.path.basename(DEFAULT_SAVE_PATH),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.dataset, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Exported", f"Successfully saved {len(self.dataset)} preference pairs!")

if __name__ == "__main__":
    root = tk.Tk()
    app = DPOEditorV1(root)
    root.mainloop()