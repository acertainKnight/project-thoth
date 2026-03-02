import { App, Modal, Platform } from 'obsidian';
import type ThothPlugin from '../../main';
import { ChatRenderer } from '../views/chat-renderer';
import { makeDraggable } from '../utils/draggable';

/**
 * MultiChatModal — Obsidian Modal host for the Thoth chat UI.
 *
 * On desktop this floats as a draggable/resizable popup.
 * On mobile it fills the entire screen.
 *
 * All chat state and rendering is delegated to ChatRenderer.
 * This class handles only Modal lifecycle, positioning, and dragging.
 */
export class MultiChatModal extends Modal {
  plugin: ThothPlugin;
  private renderer: ChatRenderer | null = null;
  private keyboardCleanup: (() => void) | null = null;

  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
  }

  async onOpen(): Promise<void> {
    const { contentEl } = this;
    contentEl.empty();

    this.setupModalPosition();
    this.titleEl.setText('Thoth Chat');

    this.renderer = new ChatRenderer(contentEl, this.plugin, this.app);

    // Wire mobile keyboard handling so ChatRenderer can invoke it
    if ((this.app as any).isMobile) {
      this.renderer.mobileKeyboardSetup = (inputEl, msgs, area) => {
        this.setupMobileKeyboardHandling(inputEl, msgs, area);
      };
    }

    await this.renderer.mount();
    this.makeDraggable();
  }

  onClose(): void {
    if (this.keyboardCleanup) {
      this.keyboardCleanup();
      this.keyboardCleanup = null;
    }
    this.renderer?.unmount();
    this.renderer = null;
    this.contentEl.empty();
  }

  /** Expose the renderer for reading activeSessionId etc. during mode transitions. */
  getRenderer(): ChatRenderer | null {
    return this.renderer;
  }

  // ──────────────────────────────────────────────────────────────────
  // Modal-specific positioning
  // ──────────────────────────────────────────────────────────────────

  setupModalPosition(): void {
    const modalEl = this.modalEl;
    modalEl.addClass('thoth-chat-popup');

    if ((this.app as any).isMobile) {
      modalEl.addClass('thoth-mobile-modal');

      const modalContainer = modalEl.parentElement;
      if (modalContainer && modalContainer.classList.contains('modal-container')) {
        modalContainer.style.position = 'fixed';
        modalContainer.style.top = '0';
        modalContainer.style.left = '0';
        modalContainer.style.right = '0';
        modalContainer.style.bottom = '0';
        modalContainer.style.width = '100vw';
        modalContainer.style.height = '100vh';
        modalContainer.style.maxHeight = '100vh';
        modalContainer.style.overflow = 'hidden';
      }

      modalEl.style.position = 'fixed';
      modalEl.style.top = '0';
      modalEl.style.left = '0';
      modalEl.style.right = '0';
      modalEl.style.bottom = '0';
      modalEl.style.width = '100vw';
      modalEl.style.height = '100vh';
      modalEl.style.maxWidth = '100vw';
      modalEl.style.maxHeight = '100vh';
      modalEl.style.borderRadius = '0';
      modalEl.style.resize = 'none';
      modalEl.style.transform = 'none';
      modalEl.style.zIndex = '1000';
      modalEl.style.overflow = 'hidden';
    } else {
      const backdrop = modalEl.parentElement;
      if (backdrop && backdrop.classList.contains('modal-container')) {
        backdrop.style.backgroundColor = 'transparent';
        backdrop.style.pointerEvents = 'none';
        backdrop.addClass('thoth-transparent-backdrop');
        modalEl.style.pointerEvents = 'auto';
      }

      setTimeout(() => {
        const modalBackdrop = document.querySelector(
          '.modal-container:has(.thoth-chat-popup), .modal-container .thoth-chat-popup'
        )?.parentElement;
        if (modalBackdrop) {
          (modalBackdrop as HTMLElement).style.backgroundColor = 'transparent';
          (modalBackdrop as HTMLElement).style.pointerEvents = 'none';
          modalEl.style.pointerEvents = 'auto';
        }
      }, 100);

      modalEl.style.position = 'fixed';
      modalEl.style.bottom = '20px';
      modalEl.style.right = '20px';
      modalEl.style.top = 'unset';
      modalEl.style.left = 'unset';
      modalEl.style.transform = 'none';
      modalEl.style.width = '450px';
      modalEl.style.height = '600px';
      modalEl.style.maxWidth = '90vw';
      modalEl.style.maxHeight = '80vh';
      modalEl.style.zIndex = '1000';
      modalEl.style.borderRadius = '12px';
      modalEl.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.3)';
      modalEl.style.resize = 'both';
      modalEl.style.overflow = 'hidden';
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Dragging (desktop only)
  // ──────────────────────────────────────────────────────────────────

  makeDraggable(): void {
    if (Platform.isMobile) return;

    const modalEl = this.modalEl;

    // Use the tab navigation bar as the drag handle (top of the chat UI)
    const handle = modalEl.querySelector('.thoth-tab-navigation') as HTMLElement ?? modalEl;
    makeDraggable(modalEl, handle);
  }

  // ──────────────────────────────────────────────────────────────────
  // Mobile keyboard handling
  // ──────────────────────────────────────────────────────────────────

  setupMobileKeyboardHandling(
    inputEl: HTMLTextAreaElement,
    messagesContainer: HTMLElement,
    inputArea: HTMLElement
  ): void {
    const modalContent = this.modalEl;
    const modalContainer = modalContent.parentElement;
    const hasContainer = modalContainer && modalContainer.classList.contains('modal-container');

    let isKeyboardVisible = false;
    let nativeKeyboardHeight: number | null = null;

    const capacitorKeyboard = (window as any).Capacitor?.Plugins?.Keyboard;
    if (capacitorKeyboard) {
      capacitorKeyboard.addListener('keyboardWillShow', (info: any) => {
        nativeKeyboardHeight = info.keyboardHeight;
      });
      capacitorKeyboard.addListener('keyboardWillHide', () => {
        nativeKeyboardHeight = null;
      });
    }

    const checkCSSVariable = (): number | null => {
      const keyboardOffset = getComputedStyle(document.documentElement).getPropertyValue('--keyboard-offset');
      if (keyboardOffset && keyboardOffset !== '0px') return parseInt(keyboardOffset);
      return null;
    };

    const scrollToBottom = (container: HTMLElement) => {
      container.scrollTop = container.scrollHeight;
    };

    const handleInputFocus = () => {
      if (isKeyboardVisible) return;

      setTimeout(() => {
        isKeyboardVisible = true;
        const windowHeight = window.innerHeight;
        let modalHeight: number;

        if (nativeKeyboardHeight !== null) {
          modalHeight = Math.round(windowHeight - nativeKeyboardHeight);
        } else {
          const cssKeyboardOffset = checkCSSVariable();
          if (cssKeyboardOffset !== null) {
            modalHeight = Math.round(windowHeight - cssKeyboardOffset);
          } else {
            const visualViewport = window.visualViewport;
            const vpHeight = visualViewport ? visualViewport.height : windowHeight;
            const inputRect = inputEl.getBoundingClientRect();
            if (inputRect.bottom > vpHeight - 50) {
              modalHeight = Math.max(300, vpHeight);
            } else {
              modalHeight = Math.round(windowHeight - windowHeight * 0.25);
            }
          }
        }

        modalContent.addClass('keyboard-visible');
        if (hasContainer && modalContainer) {
          modalContainer.style.height = `${modalHeight}px`;
          modalContainer.style.maxHeight = `${modalHeight}px`;
        }
        modalContent.style.height = `${modalHeight}px`;
        modalContent.style.maxHeight = `${modalHeight}px`;

        const inputAreaHeight = inputArea.offsetHeight || 80;
        const messagesMaxHeight = modalHeight - inputAreaHeight - 120;
        messagesContainer.style.maxHeight = `${messagesMaxHeight}px`;
        messagesContainer.style.flexShrink = '1';
        messagesContainer.style.overflowY = 'auto';

        scrollToBottom(messagesContainer);
        setTimeout(() => {
          inputEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }, 50);
      }, 150);
    };

    const handleInputBlur = () => {
      if (!isKeyboardVisible) return;

      setTimeout(() => {
        if (document.activeElement === inputEl) return;

        isKeyboardVisible = false;
        modalContent.removeClass('keyboard-visible');
        if (hasContainer && modalContainer) {
          modalContainer.style.height = '100vh';
          modalContainer.style.maxHeight = '100vh';
        }
        modalContent.style.height = '100vh';
        modalContent.style.maxHeight = '100vh';
        messagesContainer.style.maxHeight = '';
        messagesContainer.style.flexShrink = '';
        messagesContainer.style.overflowY = '';
      }, 100);
    };

    inputEl.addEventListener('focus', handleInputFocus);
    inputEl.addEventListener('blur', handleInputBlur);

    this.keyboardCleanup = () => {
      inputEl.removeEventListener('focus', handleInputFocus);
      inputEl.removeEventListener('blur', handleInputBlur);
      if (hasContainer && modalContainer) {
        modalContainer.style.height = '';
        modalContainer.style.maxHeight = '';
      }
      modalContent.style.height = '';
      modalContent.style.maxHeight = '';
      messagesContainer.style.maxHeight = '';
      messagesContainer.style.flexShrink = '';
      messagesContainer.style.overflowY = '';
      modalContent.removeClass('keyboard-visible');
    };
  }
}
