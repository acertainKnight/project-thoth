import { Notice } from 'obsidian';
import type ThothPlugin from '../../main';

interface GitHubAsset {
  name: string;
  browser_download_url: string;
}

interface GitHubRelease {
  tag_name: string;
  assets: GitHubAsset[];
}

/**
 * Downloads and installs plugin update files from a GitHub release into the
 * current Obsidian vault's plugin directory.
 *
 * Only usable on desktop — mobile Obsidian cannot write arbitrary files.
 */
export class PluginInstaller {
  private readonly plugin: ThothPlugin;
  private readonly GITHUB_REPO = 'acertainKnight/project-thoth';
  private readonly PLUGIN_ID = 'thoth-obsidian';
  private readonly PLUGIN_FILES = ['main.js', 'manifest.json', 'styles.css'];

  constructor(plugin: ThothPlugin) {
    this.plugin = plugin;
  }

  /**
   * Resolve the absolute path to this plugin's folder inside the vault.
   *
   * Returns:
   *     Absolute filesystem path, e.g.
   *     "/home/user/vault/.obsidian/plugins/thoth-obsidian"
   */
  getPluginDir(): string {
    const basePath = (this.plugin.app.vault.adapter as any).basePath as string;
    return `${basePath}/.obsidian/plugins/${this.PLUGIN_ID}`;
  }

  /**
   * Fetch the GitHub release for the given version and download the three
   * plugin files (main.js, manifest.json, styles.css) from its assets.
   *
   * Args:
   *     version: Normalised semver string (without 'v' prefix).
   *     onProgress: Optional callback invoked with status messages.
   *
   * Returns:
   *     Map of filename → file content string.
   *
   * Throws:
   *     Error if the release or any required asset cannot be fetched.
   */
  async fetchReleaseAssets(
    version: string,
    onProgress?: (msg: string) => void,
  ): Promise<Map<string, string>> {
    const tag = `v${version}`;
    const releaseUrl = `https://api.github.com/repos/${this.GITHUB_REPO}/releases/tags/${tag}`;

    onProgress?.(`Fetching release ${tag}…`);

    const releaseResponse = await fetch(releaseUrl, {
      headers: { Accept: 'application/vnd.github.v3+json' },
    });

    if (!releaseResponse.ok) {
      throw new Error(`Could not fetch release ${tag}: HTTP ${releaseResponse.status}`);
    }

    const release: GitHubRelease = await releaseResponse.json();
    const assetMap = new Map<string, string>(
      release.assets.map(a => [a.name, a.browser_download_url]),
    );

    const result = new Map<string, string>();

    for (const filename of this.PLUGIN_FILES) {
      const downloadUrl = assetMap.get(filename);
      if (!downloadUrl) {
        throw new Error(
          `Release ${tag} is missing required asset: ${filename}. ` +
          'This release may not include pre-built plugin files.',
        );
      }

      onProgress?.(`Downloading ${filename}…`);
      const fileResponse = await fetch(downloadUrl);
      if (!fileResponse.ok) {
        throw new Error(`Failed to download ${filename}: HTTP ${fileResponse.status}`);
      }

      result.set(filename, await fileResponse.text());
    }

    return result;
  }

  /**
   * Download and install a plugin release into the vault plugin directory.
   *
   * After writing files this method attempts a hot-reload by disabling and
   * re-enabling the plugin via the internal Obsidian API. If that fails (e.g.
   * on older Obsidian builds), a Notice with manual reload instructions is
   * shown instead.
   *
   * Args:
   *     version: Normalised semver string (without 'v' prefix).
   *     onProgress: Optional callback for granular status updates.
   *
   * Throws:
   *     Error if downloading or writing files fails.
   */
  async install(version: string, onProgress?: (msg: string) => void): Promise<void> {
    const files = await this.fetchReleaseAssets(version, onProgress);

    const pluginDir = this.getPluginDir();
    const fs: typeof import('fs') = require('fs');
    const path: typeof import('path') = require('path');

    // Ensure the plugin directory exists
    if (!fs.existsSync(pluginDir)) {
      fs.mkdirSync(pluginDir, { recursive: true });
    }

    onProgress?.('Writing files…');
    for (const [filename, content] of files) {
      fs.writeFileSync(path.join(pluginDir, filename), content, 'utf-8');
    }

    onProgress?.('Done!');

    // Attempt hot-reload via internal Obsidian API
    const reloadInstruction =
      "Plugin updated to v" + version + "! " +
      "To apply: Settings → Community Plugins → find 'Thoth Research Assistant' → toggle off then on. " +
      "Or restart Obsidian.";

    try {
      const plugins = (this.plugin.app as any).plugins;
      if (plugins?.disablePlugin && plugins?.enablePlugin) {
        await plugins.disablePlugin(this.PLUGIN_ID);
        await plugins.enablePlugin(this.PLUGIN_ID);
        new Notice(`Plugin updated to v${version}! Hot-reload applied.`, 10000);
        return;
      }
    } catch (e) {
      console.warn('[PluginInstaller] Hot-reload failed, showing manual instructions:', e);
    }

    new Notice(reloadInstruction, 30000);
  }
}
