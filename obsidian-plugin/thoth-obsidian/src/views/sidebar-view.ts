import { ItemView, WorkspaceLeaf } from 'obsidian';
import type ThothPlugin from '../../main';
import { ChatRenderer } from './chat-renderer';

export const THOTH_VIEW_TYPE = 'thoth-chat-sidebar';

/**
 * Native Obsidian sidebar panel for Thoth Chat.
 * Registered via Plugin.registerView() so Obsidian treats it like any
 * other first-class pane (Backlinks, Outline, etc.).
 */
export class ThothSidebarView extends ItemView {
  plugin: ThothPlugin;
  private renderer: ChatRenderer | null = null;

  constructor(leaf: WorkspaceLeaf, plugin: ThothPlugin) {
    super(leaf);
    this.plugin = plugin;
  }

  getViewType(): string {
    return THOTH_VIEW_TYPE;
  }

  getDisplayText(): string {
    return 'Thoth Chat';
  }

  getIcon(): string {
    return 'message-circle';
  }

  async onOpen(): Promise<void> {
    const container = this.contentEl;
    container.empty();
    container.addClass('thoth-sidebar-view');

    this.renderer = new ChatRenderer(container, this.plugin, this.app);

    // Add mode buttons: undock to floating panel
    this.renderer.modeButtons = [
      {
        label: '⇱',
        title: 'Undock to floating panel',
        onClick: () => this.undockToFloating()
      }
    ];

    await this.renderer.mount();

    // Track that the sidebar is now open
    this.plugin.settings.chatDisplayMode = 'sidebar';
    await this.plugin.saveSettings();
  }

  async onClose(): Promise<void> {
    this.renderer?.unmount();
    this.renderer = null;
    this.contentEl.empty();

    // Only update mode if sidebar was the active mode (don't override if
    // the user triggered close as part of a transition to floating/minimized)
    if (this.plugin.settings.chatDisplayMode === 'sidebar') {
      this.plugin.settings.chatDisplayMode = 'closed';
      await this.plugin.saveSettings();
    }
  }

  /** Expose the renderer so ThothPlugin can read/write state during mode transitions. */
  getRenderer(): ChatRenderer | null {
    return this.renderer;
  }

  /** Transition: close sidebar and open as floating panel, preserving session state. */
  private async undockToFloating(): Promise<void> {
    // Save state before closing
    this.plugin.settings.chatDisplayMode = 'floating';
    await this.plugin.saveSettings();

    // Close the sidebar leaf and open floating
    this.leaf.detach();
    await this.plugin.createFloatingChatPanel();
  }
}
