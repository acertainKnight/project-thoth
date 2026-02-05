#!/bin/bash
# Force reload Obsidian plugin by clearing cache

set -e

echo "🔄 Force reloading Obsidian plugin..."
echo ""

# Step 1: Rebuild
echo "1️⃣  Building plugin..."
cd /home/nick-hallmark/Documents/python/project-thoth/obsidian-plugin/thoth-obsidian
npm run build

# Step 2: Deploy
echo ""
echo "2️⃣  Deploying to Obsidian..."
cp dist/main.js /home/nick-hallmark/Documents/thoth/.obsidian/plugins/thoth-obsidian/main.js
cp manifest.json /home/nick-hallmark/Documents/thoth/.obsidian/plugins/thoth-obsidian/manifest.json
cp styles.css /home/nick-hallmark/Documents/thoth/.obsidian/plugins/thoth-obsidian/styles.css

# Step 3: Clear Obsidian cache
echo ""
echo "3️⃣  Clearing Obsidian cache..."
rm -rf /home/nick-hallmark/.config/obsidian/Cache/* 2>/dev/null || true
rm -rf /home/nick-hallmark/.config/obsidian/Code\ Cache/* 2>/dev/null || true
rm -rf /home/nick-hallmark/.config/obsidian/GPUCache/* 2>/dev/null || true

echo ""
echo "✅ Plugin redeployed and cache cleared!"
echo ""
echo "📱 Now close and reopen Obsidian completely for changes to take effect"
echo "   (Don't just reload with Ctrl+R, actually close the app and reopen it)"
