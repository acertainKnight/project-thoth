import { Notice } from 'obsidian';
import type ThothPlugin from '../../main';

interface GitHubRelease {
  tag_name: string;
  name: string;
  prerelease: boolean;
}

export class UpdateChecker {
  private plugin: ThothPlugin;
  private readonly GITHUB_REPO = 'acertainKnight/project-thoth';
  private readonly CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000; // 24 hours

  constructor(plugin: ThothPlugin) {
    this.plugin = plugin;
  }

  /**
   * Schedule an update check with a delay after plugin load.
   * Respects user settings and throttles checks to once per 24 hours.
   */
  scheduleCheck(): void {
    // Wait 10 seconds after plugin load before checking
    setTimeout(() => {
      this.checkForUpdate().catch(err => {
        console.error('[Thoth Update Checker] Check failed:', err);
      });
    }, 10000);
  }

  /**
   * Check for updates from GitHub releases.
   *
   * Args:
   *     force: If true, bypasses the 24-hour throttle.
   *
   * Returns:
   *     Promise that resolves when check is complete.
   */
  async checkForUpdate(force: boolean = false): Promise<void> {
    const settings = this.plugin.settings;

    // Skip if updates are disabled
    if (!settings.checkForUpdates) {
      console.log('[Thoth Update Checker] Updates disabled in settings');
      return;
    }

    // Skip if not on stable channel
    if (settings.releaseChannel !== 'stable') {
      console.log(`[Thoth Update Checker] Skipping check for ${settings.releaseChannel} channel`);
      return;
    }

    // Check throttle (skip if checked recently, unless forced)
    const now = Date.now();
    const timeSinceLastCheck = now - settings.lastUpdateCheck;
    if (!force && timeSinceLastCheck < this.CHECK_INTERVAL_MS) {
      const hoursUntilNext = Math.ceil((this.CHECK_INTERVAL_MS - timeSinceLastCheck) / (60 * 60 * 1000));
      console.log(`[Thoth Update Checker] Throttled. Next check in ~${hoursUntilNext} hours`);
      return;
    }

    try {
      const latestRelease = await this.fetchLatestRelease();

      // Update last check timestamp
      settings.lastUpdateCheck = now;
      await this.plugin.saveSettings();

      if (!latestRelease) {
        console.log('[Thoth Update Checker] No releases found');
        return;
      }

      const remoteVersion = this.normalizeVersion(latestRelease.tag_name);
      const localVersion = this.normalizeVersion(this.plugin.manifest.version);

      console.log(`[Thoth Update Checker] Local: ${localVersion}, Remote: ${remoteVersion}`);

      // Check if user already dismissed this version
      if (settings.dismissedVersion === remoteVersion) {
        console.log(`[Thoth Update Checker] Version ${remoteVersion} already dismissed`);
        return;
      }

      // Compare versions
      if (this.isNewerVersion(remoteVersion, localVersion)) {
        this.showUpdateNotice(remoteVersion);
      } else {
        console.log('[Thoth Update Checker] Already on latest version');
      }
    } catch (error) {
      console.error('[Thoth Update Checker] Error checking for updates:', error);
    }
  }

  /**
   * Fetch the latest release from GitHub API.
   *
   * Returns:
   *     Promise resolving to the latest release, or null if none found.
   */
  private async fetchLatestRelease(): Promise<GitHubRelease | null> {
    const url = `https://api.github.com/repos/${this.GITHUB_REPO}/releases/latest`;

    const response = await fetch(url, {
      headers: {
        'Accept': 'application/vnd.github.v3+json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error(`GitHub API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Normalize a version string by stripping 'v' prefix and prerelease suffixes.
   *
   * Args:
   *     version: Version string like 'v1.2.3' or '1.2.3-alpha'
   *
   * Returns:
   *     Normalized version like '1.2.3'
   *
   * Example:
   *     >>> normalizeVersion('v1.2.3')
   *     '1.2.3'
   *     >>> normalizeVersion('1.0.0-alpha')
   *     '1.0.0'
   */
  private normalizeVersion(version: string): string {
    let normalized = version.replace(/^v/, '');
    normalized = normalized.split('-')[0];
    normalized = normalized.split('+')[0];
    return normalized;
  }

  /**
   * Compare two semver version strings.
   *
   * Args:
   *     remote: Remote version string (e.g., '1.2.3')
   *     local: Local version string (e.g., '1.0.0')
   *
   * Returns:
   *     True if remote is newer than local, false otherwise.
   *
   * Example:
   *     >>> isNewerVersion('1.2.3', '1.2.0')
   *     True
   *     >>> isNewerVersion('1.0.0', '1.0.0')
   *     False
   */
  private isNewerVersion(remote: string, local: string): boolean {
    const remoteParts = remote.split('.').map(n => parseInt(n, 10));
    const localParts = local.split('.').map(n => parseInt(n, 10));

    for (let i = 0; i < 3; i++) {
      const r = remoteParts[i] || 0;
      const l = localParts[i] || 0;

      if (r > l) return true;
      if (r < l) return false;
    }

    return false;
  }

  /**
   * Display an update notification to the user.
   *
   * Args:
   *     version: The new version available.
   */
  private showUpdateNotice(version: string): void {
    const currentVersion = this.normalizeVersion(this.plugin.manifest.version);
    const message = `Thoth v${version} is available (you have v${currentVersion}). Run the install script to update.`;

    const notice = new Notice(message, 30000); // Show for 30 seconds

    // Add dismiss button functionality
    const noticeEl = (notice as any).noticeEl;
    if (noticeEl) {
      const dismissBtn = noticeEl.createEl('button', {
        text: 'Dismiss',
        cls: 'thoth-update-dismiss-btn'
      });

      dismissBtn.style.marginLeft = '10px';
      dismissBtn.style.padding = '2px 8px';
      dismissBtn.style.cursor = 'pointer';

      dismissBtn.onclick = async () => {
        this.plugin.settings.dismissedVersion = version;
        await this.plugin.saveSettings();
        notice.hide();
      };
    }

    console.log(`[Thoth Update Checker] Update available: ${version}`);
  }
}
