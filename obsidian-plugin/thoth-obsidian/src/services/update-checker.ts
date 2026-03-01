import { Notice } from 'obsidian';
import type ThothPlugin from '../../main';

interface GitHubRelease {
  tag_name: string;
  name: string;
  prerelease: boolean;
}

export interface ServerVersionInfo {
  server_version: string;
  min_plugin_version: string;
}

export interface CompatibilityStatus {
  serverVersion: string;
  /** Minimum plugin version the server supports. */
  minPluginVersion: string;
  /** Minimum server version the installed plugin requires. */
  minServerVersion: string;
  /** Installed plugin version satisfies server's minimum. */
  pluginCompatible: boolean;
  /** Running server version satisfies the installed plugin's minimum. */
  serverCompatible: boolean;
  /** Both directions are satisfied. */
  ok: boolean;
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
        // When in remote mode also surface a compatibility warning in the notice
        let compatNote = '';
        if (this.plugin.settings.remoteMode) {
          const compat = await this.checkCompatibility().catch(() => null);
          if (compat && !compat.ok) {
            compatNote = ' Verify compatibility with your server before installing.';
          }
        }
        this.showUpdateNotice(remoteVersion, compatNote);
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
   *     extraNote: Optional sentence appended to the notice (e.g. compatibility warning).
   */
  private showUpdateNotice(version: string, extraNote: string = ''): void {
    const currentVersion = this.normalizeVersion(this.plugin.manifest.version);
    const installInstruction = this.plugin.settings.remoteMode
      ? 'Open plugin settings → Plugin Updates to install.'
      : 'Run the install script to update.';
    const message = `Thoth v${version} is available (you have v${currentVersion}). ${installInstruction}${extraNote}`;

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

  // ─── Public helpers used by the Plugin Updates settings UI ───────────────

  /**
   * Fetch version and compatibility info from the connected remote server.
   *
   * Returns:
   *     ServerVersionInfo on success, null if the server is unreachable or
   *     not running a version that exposes /version.
   */
  async fetchServerVersion(): Promise<ServerVersionInfo | null> {
    const base = this.plugin.settings.remoteEndpointUrl.replace(/\/$/, '');
    try {
      const response = await this.plugin.authFetch(`${base}/version`);
      if (!response.ok) return null;
      return await response.json() as ServerVersionInfo;
    } catch {
      return null;
    }
  }

  /**
   * Fetch the manifest.json from a specific GitHub release tag to read its
   * minServerVersion field (and any other metadata the candidate build declares).
   *
   * Args:
   *     version: Normalised version string (without 'v' prefix).
   *
   * Returns:
   *     Parsed manifest object or null on failure.
   */
  async fetchGitHubManifest(version: string): Promise<{ minServerVersion?: string } | null> {
    const tag = `v${version}`;
    const url = `https://raw.githubusercontent.com/${this.GITHUB_REPO}/${tag}/obsidian-plugin/thoth-obsidian/manifest.json`;
    try {
      const response = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!response.ok) return null;
      return await response.json();
    } catch {
      return null;
    }
  }

  /**
   * Check whether the installed plugin and the remote server are mutually compatible.
   *
   * Returns:
   *     CompatibilityStatus or null if the server could not be reached.
   */
  async checkCompatibility(): Promise<CompatibilityStatus | null> {
    const serverInfo = await this.fetchServerVersion();
    if (!serverInfo) return null;

    const installedPluginVersion = this.normalizeVersion(this.plugin.manifest.version);
    const minServerVersion = (this.plugin.manifest as any).minServerVersion ?? '0.0.0';

    const pluginCompatible = !this.isNewerVersion(
      this.normalizeVersion(serverInfo.min_plugin_version),
      installedPluginVersion,
    );
    const serverCompatible = !this.isNewerVersion(
      this.normalizeVersion(minServerVersion),
      this.normalizeVersion(serverInfo.server_version),
    );

    return {
      serverVersion: serverInfo.server_version,
      minPluginVersion: serverInfo.min_plugin_version,
      minServerVersion,
      pluginCompatible,
      serverCompatible,
      ok: pluginCompatible && serverCompatible,
    };
  }

  /**
   * Public wrapper around fetchLatestRelease for use by the settings UI.
   *
   * Returns:
   *     The latest GitHub release, or null if none found.
   */
  async getLatestRelease(): Promise<GitHubRelease | null> {
    return this.fetchLatestRelease();
  }
}
