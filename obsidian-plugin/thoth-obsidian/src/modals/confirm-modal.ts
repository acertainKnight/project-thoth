import { App, Modal } from 'obsidian';

export class ConfirmModal extends Modal {
  private message: string;
  private resolve: (value: boolean) => void;

  constructor(app: App, message: string, resolve: (value: boolean) => void) {
    super(app);
    this.message = message;
    this.resolve = resolve;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    contentEl.createEl('h3', { text: 'Confirmation' });
    contentEl.createEl('p', { text: this.message });

    const buttonContainer = contentEl.createEl('div');
    buttonContainer.style.cssText = 'display: flex; justify-content: flex-end; gap: 10px; margin-top: 15px;';

    const cancelButton = buttonContainer.createEl('button', { text: 'Cancel' });
    cancelButton.style.cssText = 'padding: 8px 16px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
    cancelButton.onclick = () => {
      this.resolve(false);
      this.close();
    };

    const confirmButton = buttonContainer.createEl('button', { text: 'Confirm' });
    confirmButton.style.cssText = 'padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px;';
    confirmButton.onclick = () => {
      this.resolve(true);
      this.close();
    };
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}
