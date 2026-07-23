# ShareGPT Dataset Editor v4

A simple python-based GUI for editing ShareGPT formatted JSON datasets.

**New:** v4 adds an "APPEND NEW PAIR" button and a "CLEAR INPUTS" button to the edit screen. When you select an existing thread, you can now clear text boxes, type a new Human/GPT exchange, and append it directly to the end of that specific thread.

![screen3](https://cdn-uploads.huggingface.co/production/uploads/68e840caa318194c44ec2a04/BzoSjynHHQTa0gXIa3vC7.png)

![screen1](https://cdn-uploads.huggingface.co/production/uploads/68e840caa318194c44ec2a04/ghEv1EIQgKn1X11hLhvCz.png)

![screen2](https://cdn-uploads.huggingface.co/production/uploads/68e840caa318194c44ec2a04/M2okVgkvt8-ZJeM4JwQU3.png)

---

A simple, lightweight Python-based GUI for creating and editing ShareGPT-formatted JSON datasets. Designed to eliminate the tedious manual formatting of brackets, quotes, and line breaks in text editors, this tool streamlines the process of building high-quality conversational datasets for LLM fine-tuning.

More features coming with future versions such as merging, conversions, and slop/quality audits.

## 🌟 Current Features

The application operates using a dual-view system:

### 1. Input Mode (Creation & Editing)
* **Clean Interface:** Dedicated text boxes for "Human Prompt" and "GPT Answer".
* **Thread Building:** Easily string together multiple Q&A pairs under a single Conversation ID. Click "Add Next Pair" to continue a conversation, or "Finish & New ID" to wrap it up and start a new one.
* **Auto-Formatting:** Never worry about JSON syntax again. The tool automatically handles escaping quotes (`\"`) and converting literal line breaks into `\n` characters when saving.
* **Direct Editing:** When an existing pair is loaded from the Library, you can edit the text directly and click "Save Changes" to update the dataset in memory.

### 2. Library Mode (Dataset Management)
* **Visual Dashboard:** A scrollable, expandable tree-view of your entire dataset.
* **Thread Inspection:** Expand any Conversation ID to see a preview of all Human and GPT messages within that thread.
* **Quick Search:** Filter through massive datasets instantly by searching for specific Thread IDs.
* **One-Click Loading:** Double-click any message in the tree to instantly load that specific Q&A pair back into Input Mode for editing.

### 3. File I/O
* **Smart Import:** Click "Open JSON" to load pre-existing ShareGPT datasets. The tool automatically calculates the next available ID so you can seamlessly resume your work.
* **Export All:** Save your entire session (both imported data and newly created threads) to a clean, perfectly formatted `.json` file ready for fine-tuning.

## 🚀 How to Use

1. **Run the script:** Execute `python dataset_editor_v3.py` in your terminal.
2. **To create a new dataset:** Simply paste your first prompt and answer into the boxes. Click **Finish & New ID** for a single-turn conversation, or **Add Next Pair** to build a multi-turn thread.
3. **To edit an existing dataset:** Click **Open JSON** at the bottom, select your file, and use the **Library View** to browse. Double-click any message to edit it, then click **Save Changes**.
4. **To save your work:** Click **Export All** to generate your final `.json` file.

## 📋 Requirements
* Python 3.x
* `tkinter` (Included in standard Python installations)
