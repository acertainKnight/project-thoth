# iOS Shortcuts for Thoth Letta ADE

## Method 1: Simple Home Screen Bookmark (Easiest)

### Steps:
1. **Open Safari** on your iPhone
2. **Navigate to**: `https://lambda-workstation.tail71634c.ts.net/agents/agent-10418b8d-37a5-4923-8f70-69ccc58d66ff`
3. **Tap the Share button** (box with arrow pointing up)
4. **Scroll down** and tap "**Add to Home Screen**"
5. **Name it**: "Thoth Research" (or whatever you like)
6. **Tap "Add"**

**Result**: You'll have an icon on your home screen that opens directly to the orchestrator agent, bypassing any cache issues.

---

## Method 2: iOS Shortcuts App (More Customizable)

This method lets you create a custom icon and more complex behavior.

### Steps:

1. **Open Shortcuts app** (comes with iOS)

2. **Tap "+" to create new shortcut**

3. **Add Action**: Search for "**Open URLs**"

4. **Enter URL**:
   ```
   https://lambda-workstation.tail71634c.ts.net/agents/agent-10418b8d-37a5-4923-8f70-69ccc58d66ff
   ```

5. **Tap the shortcut name** at top and rename to "**Thoth Research**"

6. **Tap the icon** next to the name to customize:
   - Choose a **color**
   - Choose an **icon** (try: brain, book, magnifying glass, document)
   - Or tap "**Choose Photo**" to use a custom image

7. **Tap "Done"**

8. **Tap the three dots (⋯)** on your shortcut

9. **Tap the Share icon**, then "**Add to Home Screen**"

10. **Tap "Add"**

**Result**: Custom icon on home screen that opens Letta ADE directly.

---

## Method 3: Advanced - Multiple Agent Shortcuts

Create separate shortcuts for each specialist agent:

### Thoth Orchestrator (Main)
```
Name: Thoth Main
Icon: Brain icon, blue color
URL: https://lambda-workstation.tail71634c.ts.net/agents/agent-10418b8d-37a5-4923-8f70-69ccc58d66ff
```

### Discovery Scout
```
Name: Discovery Scout
Icon: Magnifying glass, green color
URL: https://lambda-workstation.tail71634c.ts.net/agents/agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64
```

### Citation Analyzer
```
Name: Citation Analyzer
Icon: Link icon, purple color
URL: https://lambda-workstation.tail71634c.ts.net/agents/agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5
```

### Analysis Expert
```
Name: Analysis Expert
Icon: Document icon, orange color
URL: https://lambda-workstation.tail71634c.ts.net/agents/agent-8a4183a6-fffc-4082-b40b-aab29727a3ab
```

---

## Method 4: Advanced - Menu Selector

Create ONE shortcut that asks which agent to open:

### Steps:

1. **Open Shortcuts app**

2. **Create new shortcut**

3. **Add "Choose from Menu" action**

4. **Configure menu**:
   - Rename "One" to "🧠 Orchestrator"
   - Rename "Two" to "🔍 Discovery Scout"
   - Tap "Add New Item" for more options
   - Add "📊 Citation Analyzer"
   - Add "📝 Analysis Expert"

5. **For each menu item**, add "**Open URLs**" action with the respective URL:

   **Orchestrator**:
   ```
   https://lambda-workstation.tail71634c.ts.net/agents/agent-10418b8d-37a5-4923-8f70-69ccc58d66ff
   ```

   **Discovery Scout**:
   ```
   https://lambda-workstation.tail71634c.ts.net/agents/agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64
   ```

   **Citation Analyzer**:
   ```
   https://lambda-workstation.tail71634c.ts.net/agents/agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5
   ```

   **Analysis Expert**:
   ```
   https://lambda-workstation.tail71634c.ts.net/agents/agent-8a4183a6-fffc-4082-b40b-aab29727a3ab
   ```

6. **Name**: "Thoth Agents"

7. **Add to Home Screen**

**Result**: Tap the icon, get a menu to choose which agent to talk to.

---

## Custom Icon Images (Optional)

If you want a truly custom app-like experience:

### Create Custom Icons:

1. **Use an app like Canva or Icon Generator**
2. **Create 1024x1024 PNG images** with your design
3. **Save to Photos**
4. **In Shortcuts**: Choose Photo → Select your custom icon

### Suggested Designs:
- **Thoth symbol** (Egyptian god of knowledge - ibis bird)
- **Brain with circuit board**
- **Stack of books**
- **Magnifying glass over papers**

---

## Pro Tips:

### Tip 1: Create a Folder
Put all Thoth shortcuts in a home screen folder named "Research" for organization.

### Tip 2: Widget Support
iOS 14+ supports widgets. You can add Shortcuts to your widget screen for even faster access.

### Tip 3: Siri Integration
Name your shortcuts descriptively, then you can say:
- "Hey Siri, open Thoth Research"
- "Hey Siri, run Discovery Scout"

### Tip 4: Back Button
When you open via shortcut, Safari will show a "← Back to [Your App]" button at top, making it feel app-like.

---

## Troubleshooting:

**Shortcut opens but shows error?**
- Check Tailscale is connected (green dot in Tailscale app)
- Make sure server is running: `docker ps | grep letta`

**Want to update URL?**
- Open Shortcuts app → Edit shortcut → Change URL

**Lost agent IDs?**
- Run on server: `curl http://localhost:8283/v1/agents | jq '.[] | {name, id}'`

---

## Quick Start Recommendation:

**For simplest setup**:
1. Open Safari
2. Go to: `https://lambda-workstation.tail71634c.ts.net/agents/agent-10418b8d-37a5-4923-8f70-69ccc58d66ff`
3. Share → Add to Home Screen
4. Name it "Thoth"
5. Done!

You now have a one-tap access to your research assistant that looks and feels like a native app! 🎉
