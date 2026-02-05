# Obsidian Modal Container - Keyboard Fix

## The Real Problem ✅

**You were right!** The issue was related to how Obsidian wraps plugin modals.

### Obsidian's Modal Structure

When you create a modal in Obsidian, it doesn't just create the modal element. It wraps it:

```
.modal-container (Obsidian's wrapper)
  └── .modal (your plugin modal)
        └── .modal-content
              └── your UI elements
```

### What Was Blocking the Fix

**We were only adjusting the modal**, not the container:

```typescript
// Before (not working):
modalContent.style.height = `${viewportHeight}px`;  // ✅ Modal adjusted
// But container still at 100vh! ❌
```

**The container was set to `100vh` and never changed**, so:
1. Keyboard appears
2. Visual viewport shrinks (e.g., 844px → 400px)
3. We adjusted modal height to 400px
4. But container stayed at 844px
5. Result: Container extended under keyboard, blocking the view

### The Fix

Now we adjust **both** the container and the modal:

```typescript
// Get Obsidian's modal container
const modalContainer = this.modalEl.parentElement;

// When keyboard shows:
if (modalContainer) {
  modalContainer.style.height = `${viewportHeight}px`;  // ✅ Container
  modalContainer.style.maxHeight = `${viewportHeight}px`;
}
this.modalEl.style.height = `${viewportHeight}px`;  // ✅ Modal
this.modalEl.style.maxHeight = `${viewportHeight}px`;
```

## Deployment

```bash
cd /home/nick-hallmark/Documents/python/project-thoth
make deploy-plugin
```

**Files deployed**: 
- main.js (206KB) - Updated Feb 2, 19:46
- manifest.json
- styles.css (50KB)

## What to Watch in Debug Panel

The debug box will now show:

```
🚀 Keyboard Handler Active
Window: 844px
Mobile: true
✅ Viewport API available
✅ Found modal container          ← NEW! Should see this
Initial VP: 844px
✅ Listeners attached
```

When you focus the input:
```
🎯 Input focused
Checking keyboard...
Window resize #1
Input top: 750, bottom: 800      ← Shows input position
Container: 400px                  ← NEW! Container adjusted
Modal: 400px                      ← Modal adjusted
Messages height: 280px
⌨️ KEYBOARD SHOWN!
```

## Enhanced Detection Methods

The fix now uses **multiple detection methods** because viewport events don't always fire reliably:

### Method 1: Visual Viewport API
```typescript
visualViewport.addEventListener('resize', handleViewportResize);
```
- iOS 13+, Android Chrome 61+
- Most accurate when it works

### Method 2: Window Resize (Backup)
```typescript
window.addEventListener('resize', handleWindowResize);
```
- Fires when viewport size changes
- More reliable on some devices

### Method 3: Input Position Tracking
```typescript
// Check if input is near/below viewport bottom
if (inputRect.bottom > vpHeight - 50) {
  // Manually trigger keyboard handling
}
```
- Checks multiple times (100ms, 300ms, 500ms, 800ms)
- Catches cases where events don't fire
- Most aggressive detection

### Method 4: Debounced Checks
```typescript
setTimeout(checkKeyboard, 50); // Debounce
```
- Prevents excessive recalculations
- Smooths out rapid events

## Why This Fix Should Work

1. **Adjusts Obsidian's container** - no longer blocked by wrapper
2. **Multiple detection methods** - catches keyboard even if viewport events don't fire
3. **Position-based detection** - monitors input position as fallback
4. **Forced layout reflows** - ensures browser applies changes immediately
5. **Aggressive checking** - polls at 100ms, 300ms, 500ms, 800ms after focus

## Testing Checklist

Test on your iPhone (iOS 26):

- [ ] Open chat modal
- [ ] Check debug box shows "✅ Found modal container"
- [ ] Tap input field
- [ ] Debug should show:
  - "🎯 Input focused"
  - "Container: [height]px" ← **This is new!**
  - "Modal: [height]px"
  - "⌨️ KEYBOARD SHOWN!" or "FORCED: Cont+Modal=[height]px"
- [ ] Input field should be visible above keyboard
- [ ] You should be able to see what you're typing
- [ ] Messages should scroll properly

## If It Still Doesn't Work

Check the debug panel for these clues:

**If you see**:
```
⚠️ No modal container
```
Then Obsidian's structure changed. We'll need to investigate further.

**If you see**:
```
✅ Found modal container
Container: 400px
Modal: 400px
```
But input is still hidden, then we may need to adjust the positioning logic.

**If viewport height never changes** (stays at 844px):
```
VP: 844px, KB: 0px
```
Then the position-based detection should kick in:
```
⚠️ Input near/below viewport!
FORCED: Cont+Modal=544px
```

## Code Locations

**File**: `obsidian-plugin/thoth-obsidian/src/modals/multi-chat-modal.ts`

**Key sections**:
- Lines ~360-370: Get modal container
- Lines ~385-400: Adjust container + modal height when keyboard shows
- Lines ~420-430: Restore container + modal height when keyboard hides
- Lines ~450-485: Position-based detection fallback
- Lines ~520-535: Cleanup function

## Why Obsidian's Structure Matters

Obsidian plugins run inside Obsidian's modal system, which:
- Controls positioning and z-index
- Manages backdrop/overlay
- Handles animations
- Wraps content in containers

**Key lesson**: When working with Obsidian modals on mobile, you must consider the entire hierarchy, not just your plugin's modal element.

## Status

✅ **Container fix deployed** - Feb 2, 19:46  
✅ **Multi-method detection active**  
✅ **Position-based fallback enabled**  
🧪 **Ready for testing on iOS 26**

---

**Next**: Test on your iPhone and check if the debug panel shows the container being adjusted!
