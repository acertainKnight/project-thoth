import { App, Modal } from 'obsidian';

export class InputModal extends Modal {
  private promptText: string;
  private resolve: (value: string | null) => void;
  private inputEl: HTMLInputElement;

  constructor(app: App, promptText: string, resolve: (value: string | null) => void) {
    super(app);
    this.promptText = promptText;
    this.resolve = resolve;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    contentEl.createEl('h3', { text: this.promptText });

    this.inputEl = contentEl.createEl('input', { type: 'text' });
    this.inputEl.style.cssText = 'width: 100%; padding: 8px; margin: 10px 0; border: 1px solid var(--background-modifier-border); border-radius: 4px;';
    this.inputEl.focus();

    const buttonContainer = contentEl.createEl('div');
    buttonContainer.style.cssText = 'display: flex; justify-content: flex-end; gap: 10px; margin-top: 15px;';

    const cancelButton = buttonContainer.createEl('button', { text: 'Cancel' });
    cancelButton.style.cssText = 'padding: 8px 16px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
    cancelButton.onclick = () => {
      this.resolve(null);
      this.close();
    };

    const okButton = buttonContainer.createEl('button', { text: 'OK' });
    okButton.style.cssText = 'padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px;';
    okButton.onclick = () => {
      this.resolve(this.inputEl.value.trim() || null);
      this.close();
    };

    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        this.resolve(this.inputEl.value.trim() || null);
        this.close();
      } else if (e.key === 'Escape') {
        this.resolve(null);
        this.close();
      }
    });
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}
