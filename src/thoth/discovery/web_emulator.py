"""Web emulator for recording browser interactions."""
# pragma: no cover

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

from thoth.utilities.schemas import BrowserRecording

# Lazy import to avoid blocking module load (selenium has heavy imports)
if TYPE_CHECKING:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options


class WebEmulatorRecorder:
    """Simple Selenium-based browser recorder."""  # pragma: no cover

    def __init__(self, driver_path: str | None = None) -> None:  # pragma: no cover
        # Import selenium only when actually creating an instance
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(driver_path, options=options)
        self.actions: list[dict[str, Any]] = []
        self.start_url = ''

    def start_recording(self, url: str) -> None:  # pragma: no cover
        """Open the browser for manual interaction."""
        logger.info(f'Starting web emulator at {url}')
        self.start_url = url
        self.driver.get(url)
        logger.info('Interact with the page and close the window when finished')

    def stop_recording(self) -> BrowserRecording:  # pragma: no cover
        """Close the browser and return recording data."""
        try:
            current_url = self.driver.current_url
            cookies = self.driver.get_cookies()
        except Exception:  # pragma: no cover - driver may already be closed
            current_url = ''
            cookies = []
        self.driver.quit()
        logger.info('Web emulator stopped')
        return BrowserRecording(
            start_url=self.start_url,
            end_url=current_url,
            cookies=cookies,
            actions=self.actions,
        )

    def save_recording(
        self, recording: BrowserRecording, path: str | Path
    ) -> None:  # pragma: no cover
        """Save a recording to disk."""
        Path(path).write_text(recording.model_dump_json(indent=2))

    def load_recording(self, path: str | Path) -> BrowserRecording:  # pragma: no cover
        """Load a recording from disk."""
        data = Path(path).read_text()
        return BrowserRecording.model_validate_json(data)


def run_emulator(url: str) -> None:  # pragma: no cover
    """Run the emulator as a simple CLI utility."""
    recorder = WebEmulatorRecorder()
    recorder.start_recording(url)
    input('Press Enter after closing the browser...')
    recording = recorder.stop_recording()
    output = Path('browser_recording.json')
    recorder.save_recording(recording, output)
    logger.info(f'Recording saved to {output}')


if __name__ == '__main__':  # pragma: no cover
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else 'about:blank'
    run_emulator(target)
