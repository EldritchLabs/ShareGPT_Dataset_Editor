import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import json
import os

class ShareGPTEditorV4:
    def __init__(self, root):
        self.tree_map = {} # Maps tree item IDs to dataset indices
        self.root = root
        self.root.title("ShareGPT Dataset Editor - v4")
        self.root.geometry("1000x800")
        
        # Data State
        self.dataset = [] # List of dicts: {"id": int, "conversations": [...]}
        self.current_thread_conversations = [] 
        self.selected_item_index = None # Index in self.dataset
        self.selected_msg_index = None  # Index of the human msg in conversations list
        self.next_id = 1
        
        # UI Setup
        self.setup_styles()
        self.create_main_container()
        self.show_input_mode()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", padding=6, font=("Arial", 10))
        style.configure("Action.TButton", foreground="blue")
        style.configure("Danger.TButton", foreground="red")
        style.configure("Treeview", rowheight=30)

    def create_main_container(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Top Navigation Bar
        self.nav_bar = tk.Frame(self.main_frame, bg="#f0f0f0", pady=5)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X)

        self.toggle_btn = tk.Button(self.nav_bar, text="📂 Switch to Library View", command=self.toggle_view, 
                                    font=("Arial", 10, "bold"), padx=20)
        self.toggle_btn.pack(pady=5)

        # Content Area (Swapped by toggle_view)
        self.content_area = tk.Frame(self.main_frame)
        self.content_area.pack(fill=tk.BOTH, expand=True)

    def clear_content_area(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

    def toggle_view(self):
        if hasattr(self, 'current_mode') and self.current_mode == 'input':
            self.show_library_mode()
        else:
            self.show_input_mode()

    # --- INPUT MODE UI ---
    def show_input_mode(self):
        self.current_mode = 'input'
        self.toggle_btn.config(text="📚 Switch to Library Mode")
        self.clear_content_area()

        container = tk.Frame(self.content_area, padx=20, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Header Info
        header_frame = tk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        display_id = self.dataset[self.selected_item_index]['id'] if self.selected_item_index is not None else self.next_id
        self.id_label = tk.Label(header_frame, text=f"Thread ID: {display_id}", font=("Arial", 14, "bold"))
        self.id_label.pack(side=tk.LEFT)
        
        if self.selected_item_index is not None:
            edit_tag = tk.Label(header_frame, text=" (EDITING EXISTING PAIR)", fg="orange", font=("Arial", 10, "bold"))
            edit_tag.pack(side=tk.LEFT, padx=10)

        # Text Areas
        tk.Label(container, text="Human Prompt:", fg="#2196F3", font=("Arial", 10, "bold")).pack(anchor="w")
        self.human_text = tk.Text(container, height=8, undo=True, font=("Consolas", 11), relief="flat", highlightthickness=1, highlightbackground="#ccc")
        self.human_text.pack(fill=tk.X, pady=(0, 15))

        tk.Label(container, text="GPT Answer:", fg="#4CAF50", font=("Arial", 10, "bold")).pack(anchor="w")
        self.gpt_text = tk.Text(container, height=15, undo=True, font=("Consolas", 11), relief="flat", highlightthickness=1, highlightbackground="#ccc")
        self.gpt_text.pack(fill=tk.BOTH, expand=True)

        # Action Buttons Frame
        btn_frame = tk.Frame(container, pady=20)
        btn_frame.pack(fill=tk.X)

        if self.selected_item_index is not None:
            tk.Button(btn_frame, text="💾 SAVE CHANGES", command=self.save_existing_changes, bg="#4caf50", fg="white", padx=20).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="➕ APPEND NEW PAIR", command=self.append_to_existing_thread, bg="#2196F3", fg="white", padx=20).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="🗑 CLEAR INPUTS", command=self.clear_inputs).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="❌ CANCEL", command=self.cancel_edit, bg="#f44336", fg="white", padx=20).pack(side=tk.LEFT, padx=5)
        else:
            tk.Button(btn_frame, text="➕ ADD NEXT PAIR (SAME THREAD)", command=self.add_next_pair, bg="#e1f5fe").pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="✔ FINISH & NEW ID", command=self.finish_conversation, bg="#c8e6c9").pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="🗑 CLEAR INPUTS", command=self.clear_inputs).pack(side=tk.RIGHT, padx=5)

        # Footer Actions
        footer = tk.Frame(container, pady=10)
        footer.pack(fill=tk.X)
        tk.Button(footer, text="📂 OPEN JSON", command=self.open_file, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(footer, text="💾 EXPORT ALL", command=self.export_all, bg="#4caf50", fg="white", width=15).pack(side=tk.RIGHT, padx=5)

    def clear_inputs(self):
        """Clears text boxes for a fresh start."""
        self.human_text.delete("1.0", tk.END)
        self.gpt_text.delete("1.0", tk.END)
        
    # --- LIBRARY MODE UI ---
    def show_library_mode(self):
        self.current_mode = 'library'
        self.toggle_btn.config(text="📝 Switch to Input Mode")
        self.clear_content_area()

        container = tk.Frame(self.content_area, padx=20, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Search/Filter Bar
        search_frame = tk.Frame(container)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(search_frame, text="Search IDs:", font=("Arial", 10)).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda name, index, mode: self.refresh_treeview())
        tk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # TreeView for Threads and Messages
        columns = ("type", "id", "preview")
        self.tree = ttk.Treeview(container, columns=columns, selectmode='browse')
        self.tree.heading("#0", text="Thread / Message Structure")
        self.tree.column("#0", width=300)
        self.tree.column("type", width=80)
        self.tree.column("id", width=60)
        self.tree.column("preview", width=400)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.refresh_treeview()

    def refresh_treeview(self):
        """Populates the tree with dataset content and builds index map."""
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        search_term = self.search_var.get().lower()
        self.tree_map = {} # Reset mapping
        
        for idx, item in enumerate(self.dataset):
            if search_term and search_term not in str(item['id']): continue
            
            # Insert Thread Node
            thread_node = self.tree.insert("", tk.END, text=f"ID: {item['id']}", values=("THREAD", item['id'], f"{len(item['conversations'])} messages"))
            self.tree_map[thread_node] = idx # Map node to dataset index
            
            for m_idx, msg in enumerate(item['conversations']):
                preview = (msg['value'][:80].replace('\n', ' ') + '...') if len(msg['value']) > 80 else msg['value'].replace('\n', ' ')
                m_node = self.tree.insert(thread_node, tk.END, text=f"{'👤 Human' if msg['from']=='human' else '🤖 GPT'}", 
                                          values=(msg['from'].upper(), "-", preview))
                # Store message info for retrieval using the proper tags attribute
                self.tree.item(m_node, tags=(f"{idx}|{m_idx}",))

    def on_tree_double_click(self, event):
        """Handles selection from library to input mode."""
        try:
            selection = self.tree.selection()
            if not selection: return
            item_id = selection[0]
            
            tags = self.tree.item(item_id, "tags")
            
            if tags: # It's a message node
                idx_str, m_idx_str = tags[0].split('|')
                thread_idx = int(idx_str)
                msg_idx = int(m_idx_str)
                
                # We want to load the pair (Human + GPT). 
                # If they clicked GPT, step back 1 to get the Human prompt.
                if self.dataset[thread_idx]['conversations'][msg_idx]['from'] == 'gpt':
                    msg_idx = max(0, msg_idx - 1)
                    
                self.load_into_editor(thread_idx, msg_idx)
            else:
                # If clicking thread header, select first pair
                self.load_into_editor(self.tree_map[item_id], 0)
        except Exception as e:
            print(f"Selection error: {e}")

    def load_into_editor(self, t_idx, m_idx):
        """Helper to populate text boxes."""
        self.selected_item_index = t_idx
        self.selected_msg_index = m_idx
        
        # MUST show input mode first so the text boxes are created on screen
        self.show_input_mode()
        
        item = self.dataset[t_idx]
        convs = item['conversations']
        
        self.human_text.delete("1.0", tk.END)
        self.gpt_text.delete("1.0", tk.END)
        
        # Load Human
        if m_idx < len(convs):
            self.human_text.insert("1.0", convs[m_idx]['value'])
            
        # Load GPT (the next message)
        if m_idx + 1 < len(convs):
            self.gpt_text.insert("1.0", convs[m_idx + 1]['value'])

    # --- DATA LOGIC & FILE I/O ---
    def add_next_pair(self):
        """Saves current pair to thread list and clears UI for next one."""
        h_val = self.human_text.get("1.0", tk.END).strip()
        g_val = self.gpt_text.get("1.0", tk.END).strip()
        
        if not h_val or not g_val:
            messagebox.showwarning("Empty Input", "Both Human and GPT fields must have content.")
            return
        
        self.current_thread_conversations.append({"from": "human", "value": h_val})
        self.current_thread_conversations.append({"from": "gpt", "value": g_val})
        
        self.clear_inputs()

    def finish_conversation(self):
        # If there's text left in the boxes, add it as a pair before finishing
        h_val = self.human_text.get("1.0", tk.END).strip()
        g_val = self.gpt_text.get("1.0", tk.END).strip()
        if h_val and g_val:
            self.current_thread_conversations.append({"from": "human", "value": h_val})
            self.current_thread_conversations.append({"from": "gpt", "value": g_val})

        if not self.current_thread_conversations:
            messagebox.showwarning("Empty", "No conversation data to save.")
            return

        entry = {"id": self.next_id, "conversations": list(self.current_thread_conversations)}
        self.dataset.append(entry)
        self.next_id += 1
        self.current_thread_conversations = []
        messagebox.showinfo("Success", f"Thread {entry['id']} added.")
        self.show_input_mode()

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Sort and find max ID
                    ids = [int(d['id']) for d in data if str(d.get('id', '')).isdigit()]
                    self.next_id = max(ids) + 1 if ids else 1
                    self.dataset = data
                    self.show_library_mode()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def export_all(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.dataset, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Saved", "Dataset exported successfully!")

    def cancel_edit(self):
        self.selected_item_index = None
        self.selected_msg_index = None
        self.show_input_mode()

    def append_to_existing_thread(self):
        """Appends the current text box contents as a new pair to the selected thread."""
        h_val = self.human_text.get("1.0", tk.END).strip()
        g_val = self.gpt_text.get("1.0", tk.END).strip()
        
        if not h_val or not g_val:
            messagebox.showwarning("Empty Input", "Both Human and GPT fields must have content.")
            return
            
        t_idx = self.selected_item_index
        self.dataset[t_idx]['conversations'].append({"from": "human", "value": h_val})
        self.dataset[t_idx]['conversations'].append({"from": "gpt", "value": g_val})
        
        messagebox.showinfo("Appended", "New pair appended to the end of this thread. Don't forget to Export All when done.")
        self.selected_item_index = None
        self.selected_msg_index = None
        self.show_library_mode()

    def save_existing_changes(self):
        """Commits changes from text boxes back to the dataset."""
        h_val = self.human_text.get("1.0", tk.END).strip()
        g_val = self.gpt_text.get("1.0", tk.END).strip()
        
        t_idx = self.selected_item_index
        m_idx = self.selected_msg_index
        
        convs = self.dataset[t_idx]['conversations']
        
        if m_idx < len(convs):
            convs[m_idx]['value'] = h_val
        if m_idx + 1 < len(convs):
            convs[m_idx + 1]['value'] = g_val
            
        messagebox.showinfo("Saved", "Changes saved to memory. Don't forget to Export All when done.")
        self.selected_item_index = None
        self.selected_msg_index = None
        self.show_library_mode()

if __name__ == "__main__":
    root = tk.Tk()
    app = ShareGPTEditorV4(root)
    root.mainloop()