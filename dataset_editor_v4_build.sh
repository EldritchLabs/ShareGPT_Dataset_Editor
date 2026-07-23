#!/bin/bash
set -e

echo "Installing .NET 8 SDK..."
wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
dpkg -i packages-microsoft-prod.deb
rm packages-microsoft-prod.deb
apt-get update
apt-get install -y dotnet-sdk-8.0

echo "Creating project directory..."
mkdir -p ShareGPTEditor
cd ShareGPTEditor

echo "Writing ShareGPTEditor.csproj..."
cat << 'EOF' > ShareGPTEditor.csproj
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType>
    <TargetFramework>net8.0-windows</TargetFramework>
    <UseWindowsForms>true</UseWindowsForms>
    <ImplicitUsings>disable</ImplicitUsings>
    <Nullable>disable</Nullable>
    <EnableWindowsTargeting>true</EnableWindowsTargeting>
  </PropertyGroup>
</Project>
EOF

echo "Writing Program.cs..."
cat << 'EOF' > Program.cs
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Windows.Forms;

namespace ShareGPTEditor
{
    public class Conversation
    {
        [JsonPropertyName("from")] public string From { get; set; }
        [JsonPropertyName("value")] public string Value { get; set; }
    }

    public class DatasetThread
    {
        [JsonPropertyName("id")] public JsonElement Id { get; set; }
        [JsonPropertyName("conversations")] public List<Conversation> Conversations { get; set; } = new List<Conversation>();
    }

    public class ShareGPTEditorV4 : Form
    {
        private List<DatasetThread> dataset = new List<DatasetThread>();
        private List<Conversation> currentThreadConversations = new List<Conversation>();
        private int? selectedItemIndex = null;
        private int? selectedMsgIndex = null;
        private int nextId = 1;
        private string currentMode = "input";

        private Panel navBar, contentArea;
        private Button toggleBtn;
        private Label idLabel, editTag;
        private TextBox humanText, gptText, searchBox;
        private TreeView treeView;
        private Dictionary<TreeNode, int> treeMap = new Dictionary<TreeNode, int>();

        public ShareGPTEditorV4()
        {
            this.Text = "ShareGPT Dataset Editor - v4";
            this.Size = new Size(1000, 850);
            this.MinimumSize = new Size(800, 700);
            this.StartPosition = FormStartPosition.CenterScreen;
            CreateMainContainer();
            ShowInputMode();
        }

        private void CreateMainContainer()
        {
            navBar = new Panel { Dock = DockStyle.Top, Height = 60, BackColor = Color.FromArgb(240, 240, 240) };
            this.Controls.Add(navBar);
            toggleBtn = new Button { Text = "📂 Switch to Library View", Font = new Font("Arial", 10, FontStyle.Bold), Width = 250, Height = 40, Location = new Point(20, 10) };
            toggleBtn.Click += (s, e) => ToggleView();
            navBar.Controls.Add(toggleBtn);
            contentArea = new Panel { Dock = DockStyle.Fill, Padding = new Padding(20) };
            this.Controls.Add(contentArea);
            contentArea.BringToFront();
        }

        private void ToggleView() { if (currentMode == "input") ShowLibraryMode(); else ShowInputMode(); }

        private void ShowInputMode()
        {
            currentMode = "input";
            toggleBtn.Text = "📚 Switch to Library Mode";
            contentArea.Controls.Clear();

            Panel headerFrame = new Panel { Dock = DockStyle.Top, Height = 40 };
            int displayId = selectedItemIndex.HasValue ? GetIntId(dataset[selectedItemIndex.Value].Id) : nextId;
            idLabel = new Label { Text = $"Thread ID: {displayId}", Font = new Font("Arial", 14, FontStyle.Bold), AutoSize = true, Location = new Point(0, 0) };
            headerFrame.Controls.Add(idLabel);
            if (selectedItemIndex.HasValue)
            {
                editTag = new Label { Text = " (EDITING EXISTING PAIR)", ForeColor = Color.DarkOrange, Font = new Font("Arial", 10, FontStyle.Bold), AutoSize = true, Location = new Point(idLabel.Right + 10, 4) };
                headerFrame.Controls.Add(editTag);
            }
            contentArea.Controls.Add(headerFrame);

            // BOTTOM FOOTER (Open and Export)
            Panel footer = new Panel { Dock = DockStyle.Bottom, Height = 50 };
            Button openBtn = new Button { Text = "📂 OPEN JSON", Width = 150, Height = 35, Location = new Point(0, 10) };
            openBtn.Click += (s, e) => OpenFile();
            Button exportBtn = new Button { Text = "💾 EXPORT ALL", BackColor = Color.ForestGreen, ForeColor = Color.White, Width = 150, Height = 35, Anchor = AnchorStyles.Right };
            exportBtn.Location = new Point(footer.Width - 150, 10);
            exportBtn.Click += (s, e) => ExportAll();
            footer.Controls.Add(openBtn); footer.Controls.Add(exportBtn);
            contentArea.Controls.Add(footer);

            // ACTION BUTTONS (Add, Finish, Clear)
            Panel btnFrame = new Panel { Dock = DockStyle.Bottom, Height = 60 };
            if (selectedItemIndex.HasValue)
            {
                Button saveBtn = new Button { Text = "💾 SAVE CHANGES", BackColor = Color.ForestGreen, ForeColor = Color.White, Width = 150, Height = 40, Location = new Point(0, 10) };
                saveBtn.Click += (s, e) => SaveExistingChanges();
                Button appendBtn = new Button { Text = "➕ APPEND NEW PAIR", BackColor = Color.DodgerBlue, ForeColor = Color.White, Width = 160, Height = 40, Location = new Point(160, 10) };
                appendBtn.Click += (s, e) => AppendToExistingThread();
                Button clearBtn = new Button { Text = "🗑 CLEAR INPUTS", Width = 130, Height = 40, Location = new Point(330, 10) };
                clearBtn.Click += (s, e) => { humanText.Clear(); gptText.Clear(); };
                Button cancelBtn = new Button { Text = "❌ CANCEL", BackColor = Color.Firebrick, ForeColor = Color.White, Width = 100, Height = 40, Location = new Point(470, 10) };
                cancelBtn.Click += (s, e) => { selectedItemIndex = null; selectedMsgIndex = null; ShowInputMode(); };
                btnFrame.Controls.Add(saveBtn); btnFrame.Controls.Add(appendBtn); btnFrame.Controls.Add(clearBtn); btnFrame.Controls.Add(cancelBtn);
            }
            else
            {
                Button addBtn = new Button { Text = "➕ ADD NEXT PAIR (SAME THREAD)", BackColor = Color.FromArgb(225, 245, 254), Width = 250, Height = 40, Location = new Point(0, 10) };
                addBtn.Click += (s, e) => AddNextPair();
                Button finishBtn = new Button { Text = "✔ FINISH & NEW ID", BackColor = Color.FromArgb(200, 230, 201), Width = 200, Height = 40, Location = new Point(260, 10) };
                finishBtn.Click += (s, e) => FinishConversation();
                Button clearBtn = new Button { Text = "🗑 CLEAR INPUTS", Width = 150, Height = 40, Anchor = AnchorStyles.Right };
                clearBtn.Location = new Point(btnFrame.Width - 150, 10);
                clearBtn.Click += (s, e) => { humanText.Clear(); gptText.Clear(); };
                btnFrame.Controls.Add(finishBtn); btnFrame.Controls.Add(addBtn); btnFrame.Controls.Add(clearBtn);
            }
            contentArea.Controls.Add(btnFrame);

            // TEXT AREAS
            TableLayoutPanel grid = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 4, ColumnCount = 1 };
            grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 25F));
            grid.RowStyles.Add(new RowStyle(SizeType.Percent, 30F));
            grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 25F));
            grid.RowStyles.Add(new RowStyle(SizeType.Percent, 70F));

            Label humanLabel = new Label { Text = "Human Prompt:", ForeColor = Color.DodgerBlue, Font = new Font("Arial", 10, FontStyle.Bold), Dock = DockStyle.Fill };
            humanText = new TextBox { Multiline = true, ScrollBars = ScrollBars.Vertical, Font = new Font("Consolas", 11), Dock = DockStyle.Fill };
            Label gptLabel = new Label { Text = "GPT Answer:", ForeColor = Color.ForestGreen, Font = new Font("Arial", 10, FontStyle.Bold), Dock = DockStyle.Fill };
            gptText = new TextBox { Multiline = true, ScrollBars = ScrollBars.Vertical, Font = new Font("Consolas", 11), Dock = DockStyle.Fill };

            grid.Controls.Add(humanLabel, 0, 0);
            grid.Controls.Add(humanText, 0, 1);
            grid.Controls.Add(gptLabel, 0, 2);
            grid.Controls.Add(gptText, 0, 3);
            contentArea.Controls.Add(grid);
            grid.BringToFront();
        }

        private void ShowLibraryMode()
        {
            currentMode = "library";
            toggleBtn.Text = "📝 Switch to Input Mode";
            contentArea.Controls.Clear();

            Panel searchFrame = new Panel { Dock = DockStyle.Top, Height = 40 };
            Label searchLabel = new Label { Text = "Search IDs:", Font = new Font("Arial", 10), AutoSize = true, Location = new Point(0, 10) };
            searchBox = new TextBox { Location = new Point(80, 8), Width = 300 };
            searchBox.TextChanged += (s, e) => RefreshTreeView();
            searchFrame.Controls.Add(searchLabel); searchFrame.Controls.Add(searchBox);
            contentArea.Controls.Add(searchFrame);

            treeView = new TreeView { Dock = DockStyle.Fill, Font = new Font("Arial", 10), FullRowSelect = true };
            treeView.DoubleClick += OnTreeDoubleClick;
            contentArea.Controls.Add(treeView);
            treeView.BringToFront();
            RefreshTreeView();
        }

        private void RefreshTreeView()
        {
            treeView.Nodes.Clear(); treeMap.Clear();
            string searchTerm = searchBox.Text.ToLower();
            for (int i = 0; i < dataset.Count; i++)
            {
                var item = dataset[i];
                if (!string.IsNullOrEmpty(searchTerm) && !item.Id.ToString().Contains(searchTerm)) continue;
                TreeNode threadNode = new TreeNode($"ID: {item.Id} ({item.Conversations.Count} messages)");
                treeMap[threadNode] = i;
                for (int m = 0; m < item.Conversations.Count; m++)
                {
                    var msg = item.Conversations[m];
                    string preview = msg.Value.Replace("\n", " ");
                    if (preview.Length > 80) preview = preview.Substring(0, 80) + "...";
                    TreeNode mNode = new TreeNode($"{(msg.From == "human" ? "👤 Human" : "🤖 GPT")} - {preview}") { Tag = $"{i}|{m}" };
                    threadNode.Nodes.Add(mNode);
                }
                treeView.Nodes.Add(threadNode);
            }
        }

        private void OnTreeDoubleClick(object sender, EventArgs e)
        {
            if (treeView.SelectedNode == null) return;
            if (treeView.SelectedNode.Tag != null)
            {
                string[] parts = treeView.SelectedNode.Tag.ToString().Split('|');
                int tIdx = int.Parse(parts[0]), mIdx = int.Parse(parts[1]);
                if (dataset[tIdx].Conversations[mIdx].From == "gpt") mIdx = Math.Max(0, mIdx - 1);
                LoadIntoEditor(tIdx, mIdx);
            }
            else if (treeMap.ContainsKey(treeView.SelectedNode)) LoadIntoEditor(treeMap[treeView.SelectedNode], 0);
        }

        private void LoadIntoEditor(int tIdx, int mIdx)
        {
            selectedItemIndex = tIdx; selectedMsgIndex = mIdx;
            ShowInputMode();
            var convs = dataset[tIdx].Conversations;
            if (mIdx < convs.Count) humanText.Text = convs[mIdx].Value;
            if (mIdx + 1 < convs.Count) gptText.Text = convs[mIdx + 1].Value;
        }

        private void AddNextPair()
        {
            if (string.IsNullOrEmpty(humanText.Text.Trim()) || string.IsNullOrEmpty(gptText.Text.Trim())) { MessageBox.Show("Both fields must have content."); return; }
            currentThreadConversations.Add(new Conversation { From = "human", Value = humanText.Text.Trim() });
            currentThreadConversations.Add(new Conversation { From = "gpt", Value = gptText.Text.Trim() });
            humanText.Clear(); gptText.Clear();
        }

        private void FinishConversation()
        {
            if (!string.IsNullOrEmpty(humanText.Text.Trim()) && !string.IsNullOrEmpty(gptText.Text.Trim()))
            {
                currentThreadConversations.Add(new Conversation { From = "human", Value = humanText.Text.Trim() });
                currentThreadConversations.Add(new Conversation { From = "gpt", Value = gptText.Text.Trim() });
            }
            if (currentThreadConversations.Count == 0) { MessageBox.Show("No data to save."); return; }
            dataset.Add(new DatasetThread { Id = JsonSerializer.Deserialize<JsonElement>(nextId.ToString()), Conversations = new List<Conversation>(currentThreadConversations) });
            nextId++; currentThreadConversations.Clear();
            MessageBox.Show("Thread added."); ShowInputMode();
        }

        private void OpenFile()
        {
            using (OpenFileDialog ofd = new OpenFileDialog { Filter = "JSON files (*.json)|*.json" })
            {
                if (ofd.ShowDialog() == DialogResult.OK)
                {
                    try
                    {
                        dataset = JsonSerializer.Deserialize<List<DatasetThread>>(File.ReadAllText(ofd.FileName));
                        int maxId = 0;
                        foreach (var d in dataset) { int id = GetIntId(d.Id); if (id > maxId) maxId = id; }
                        nextId = maxId + 1; ShowLibraryMode();
                    }
                    catch (Exception ex) { MessageBox.Show($"Error: {ex.Message}"); }
                }
            }
        }

        private void ExportAll()
        {
            using (SaveFileDialog sfd = new SaveFileDialog { Filter = "JSON files (*.json)|*.json", DefaultExt = "json" })
            {
                if (sfd.ShowDialog() == DialogResult.OK)
                {
                    File.WriteAllText(sfd.FileName, JsonSerializer.Serialize(dataset, new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping }));
                    MessageBox.Show("Exported successfully!");
                }
            }
        }

        private void AppendToExistingThread()
        {
            if (string.IsNullOrEmpty(humanText.Text.Trim()) || string.IsNullOrEmpty(gptText.Text.Trim())) { MessageBox.Show("Both fields must have content."); return; }
            dataset[selectedItemIndex.Value].Conversations.Add(new Conversation { From = "human", Value = humanText.Text.Trim() });
            dataset[selectedItemIndex.Value].Conversations.Add(new Conversation { From = "gpt", Value = gptText.Text.Trim() });
            MessageBox.Show("New pair appended to the end of this thread.");
            selectedItemIndex = null; selectedMsgIndex = null; ShowLibraryMode();
        }

        private void SaveExistingChanges()
        {
            var convs = dataset[selectedItemIndex.Value].Conversations;
            if (selectedMsgIndex.Value < convs.Count) convs[selectedMsgIndex.Value].Value = humanText.Text.Trim();
            if (selectedMsgIndex.Value + 1 < convs.Count) convs[selectedMsgIndex.Value + 1].Value = gptText.Text.Trim();
            MessageBox.Show("Changes saved."); selectedItemIndex = null; selectedMsgIndex = null; ShowLibraryMode();
        }

        private int GetIntId(JsonElement element)
        {
            if (element.ValueKind == JsonValueKind.Number && element.TryGetInt32(out int id)) return id;
            if (element.ValueKind == JsonValueKind.String && int.TryParse(element.GetString(), out int parsedId)) return parsedId;
            return 0;
        }

        [STAThread] static void Main() { Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); Application.Run(new ShareGPTEditorV4()); }
    }
}
EOF

echo "Compiling Compressed Version..."
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true

echo "Done! Your EXE is located at: $(pwd)/bin/Release/net8.0-windows/win-x64/publish/ShareGPTEditor.exe"