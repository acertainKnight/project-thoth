/**
 * Shared drag-and-drop utility for Thoth UI panels.
 *
 * Attaches mouse event listeners so `element` can be dragged by `handle`.
 * Call the returned cleanup function to remove the listeners.
 *
 * Args:
 *     element: The element to move.
 *     handle: The element the user must click/drag on to initiate movement.
 *             Defaults to `element` itself.
 *
 * Returns:
 *     A cleanup function that removes all attached listeners.
 *
 * Example:
 *     >>> const cleanup = makeDraggable(floatingPanel, titleBar);
 *     >>> // later:
 *     >>> cleanup();
 */
export function makeDraggable(element: HTMLElement, handle: HTMLElement = element): () => void {
  let isDragging = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  const onMouseDown = (e: MouseEvent) => {
    if ((e.target as HTMLElement).closest('button, input, textarea, select')) return;

    isDragging = true;
    const rect = element.getBoundingClientRect();
    startX = e.clientX;
    startY = e.clientY;
    startLeft = rect.left;
    startTop = rect.top;

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    e.preventDefault();
  };

  const onMouseMove = (e: MouseEvent) => {
    if (!isDragging) return;

    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    const maxLeft = window.innerWidth - element.offsetWidth;
    const maxTop = window.innerHeight - element.offsetHeight;

    element.style.left = `${Math.max(0, Math.min(maxLeft, startLeft + dx))}px`;
    element.style.top = `${Math.max(0, Math.min(maxTop, startTop + dy))}px`;
    element.style.right = 'unset';
    element.style.bottom = 'unset';
  };

  const onMouseUp = () => {
    isDragging = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  };

  handle.addEventListener('mousedown', onMouseDown);

  return () => {
    handle.removeEventListener('mousedown', onMouseDown);
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  };
}
