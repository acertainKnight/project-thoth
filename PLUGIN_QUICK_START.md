# 🚀 Plugin Deployment - Quick Start

## One Command to Rule Them All

```bash
cd /home/nick-hallmark/Documents/python/project-thoth
make deploy-plugin
```

That's it! This command:
- ✅ Builds the plugin
- ✅ Deploys all files (main.js, manifest.json, styles.css)
- ✅ Clears Obsidian cache
- ✅ Sets up vault integration

---

## After Deployment

1. **Close Obsidian completely** (don't just reload with Ctrl+R)
2. **Reopen Obsidian**
3. **Enable plugin**: Settings → Community Plugins → Enable "Thoth"

---

## Mobile Testing

### On Desktop
```bash
make deploy-plugin
```

### On Mobile (with Obsidian Sync)
1. Wait for sync to complete (or force sync in mobile app)
2. Restart Obsidian mobile app
3. Settings → Community Plugins → Enable "Thoth"
4. Test: Open chat, tap input field, keyboard should not cover input

### Mobile Keyboard Test Checklist
- [ ] Keyboard appears when tapping input
- [ ] Input field stays visible above keyboard
- [ ] Can see what you're typing
- [ ] Messages scroll properly
- [ ] Send button is accessible
- [ ] Smooth transition when keyboard appears/disappears

---

## Common Commands

```bash
# Deploy plugin (main command)
make deploy-plugin

# Watch mode (auto-rebuild on code changes)
make plugin-dev

# Start Thoth services
make dev

# Check service health
make health

# View all commands
make help
```

---

## Troubleshooting

### Plugin not loading?
```bash
# Verify files are deployed
ls -lh /home/nick-hallmark/Documents/thoth/.obsidian/plugins/thoth-obsidian/

# Should see:
# main.js (200KB)
# manifest.json (459B)
# styles.css (50KB)
```

### Changes not appearing?
```bash
# Redeploy and force restart
make deploy-plugin
pkill obsidian && obsidian
```

### Mobile keyboard still covering input?
```bash
# Verify styles.css includes keyboard fix
grep -c "keyboard-visible" /home/nick-hallmark/Documents/thoth/.obsidian/plugins/thoth-obsidian/styles.css
# Should output: 3 or more
```

---

## File Locations

**Source**: `obsidian-plugin/thoth-obsidian/`
- `src/` - TypeScript source code
- `styles.css` - UI styles (2531 lines)
- `manifest.json` - Plugin metadata

**Deployed**: `/home/nick-hallmark/Documents/thoth/.obsidian/plugins/thoth-obsidian/`
- `main.js` - Compiled plugin
- `manifest.json` - Plugin metadata
- `styles.css` - UI styles
- `data.json` - Plugin settings

---

## Development Workflow

### Edit → Build → Test

```bash
# 1. Edit source files
vim obsidian-plugin/thoth-obsidian/src/modals/multi-chat-modal.ts

# 2. Build and deploy
make deploy-plugin

# 3. Restart Obsidian
pkill obsidian && obsidian

# 4. Test changes
```

### Watch Mode

Terminal 1:
```bash
make plugin-dev  # Auto-rebuilds on changes
```

Terminal 2:
```bash
# After changes detected, deploy:
make deploy-plugin
# Then restart Obsidian
```

---

## Status: ✅ Working

- ✅ `make deploy-plugin` is the functional command
- ✅ All files deploy correctly (including styles.css)
- ✅ Mobile keyboard management CSS is included
- ✅ Cache clearing works
- ✅ Vault integration works

---

## Need Help?

- Full guide: `docs/PLUGIN_DEPLOYMENT_FIXED.md`
- Mobile keyboard fix: `docs/MOBILE_KEYBOARD_FIX.md`
- Mobile usage: `docs/MOBILE_USAGE.md`
- Obsidian setup: `docs/OBSIDIAN_REMOTE_SETUP.md`
