"""
Docker installer for automated Docker and Docker Compose setup.

Platform-specific installation on Linux and macOS.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from loguru import logger


class DockerInstaller:
    """Platform-specific Docker installer."""

    @staticmethod
    def detect_platform() -> str:
        """
        Detect the current platform.

        Returns:
            Platform name: 'linux', 'macos', or 'windows'
        """
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        elif system == "linux":
            return "linux"
        elif system == "windows":
            return "windows"
        else:
            return "unknown"

    @staticmethod
    def detect_linux_distro() -> str | None:
        """
        Detect Linux distribution.

        Returns:
            Distro name: 'ubuntu', 'debian', 'fedora', 'arch', or None
        """
        try:
            # Try /etc/os-release first (standard)
            os_release = Path("/etc/os-release")
            if os_release.exists():
                content = os_release.read_text()
                if "ubuntu" in content.lower():
                    return "ubuntu"
                elif "debian" in content.lower():
                    return "debian"
                elif "fedora" in content.lower():
                    return "fedora"
                elif "arch" in content.lower():
                    return "arch"

            # Try lsb_release command
            result = subprocess.run(
                ["lsb_release", "-is"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                distro = result.stdout.strip().lower()
                return distro

        except Exception as e:
            logger.debug(f"Could not detect Linux distro: {e}")

        return None

    @staticmethod
    def has_homebrew() -> bool:
        """
        Check if Homebrew is installed (macOS).

        Returns:
            True if brew command is available
        """
        return shutil.which("brew") is not None

    @staticmethod
    def install_docker_linux() -> tuple[bool, str]:
        """
        Install Docker on Linux using native package managers.

        Returns:
            Tuple of (success, message)
        """
        distro = DockerInstaller.detect_linux_distro()

        if distro in ("ubuntu", "debian"):
            return DockerInstaller._install_docker_debian()
        elif distro == "fedora":
            return DockerInstaller._install_docker_fedora()
        elif distro == "arch":
            return DockerInstaller._install_docker_arch()
        else:
            return (
                False,
                f"Unsupported Linux distro: {distro}. Please install Docker manually.",
            )

    @staticmethod
    def _install_docker_debian() -> tuple[bool, str]:
        """
        Install Docker on Debian/Ubuntu.

        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info("Installing Docker on Debian/Ubuntu...")

            # Update package index
            subprocess.run(
                ["sudo", "apt-get", "update"],
                check=True,
                timeout=120,
            )

            # Install prerequisites
            subprocess.run(
                [
                    "sudo",
                    "apt-get",
                    "install",
                    "-y",
                    "ca-certificates",
                    "curl",
                    "gnupg",
                ],
                check=True,
                timeout=120,
            )

            # Add Docker's official GPG key
            subprocess.run(
                [
                    "sudo",
                    "install",
                    "-m",
                    "0755",
                    "-d",
                    "/etc/apt/keyrings",
                ],
                check=True,
                timeout=30,
            )

            # Add Docker repository
            subprocess.run(
                [
                    "bash",
                    "-c",
                    'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | '
                    'sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg',
                ],
                check=True,
                timeout=60,
            )

            # Install Docker Engine
            subprocess.run(
                ["sudo", "apt-get", "update"],
                check=True,
                timeout=120,
            )
            subprocess.run(
                [
                    "sudo",
                    "apt-get",
                    "install",
                    "-y",
                    "docker-ce",
                    "docker-ce-cli",
                    "containerd.io",
                    "docker-buildx-plugin",
                    "docker-compose-plugin",
                ],
                check=True,
                timeout=300,
            )

            logger.info("Docker installed successfully on Debian/Ubuntu")
            return (True, "Docker installed successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Docker on Debian/Ubuntu: {e}")
            return (False, f"Installation failed: {e}")
        except subprocess.TimeoutExpired:
            return (False, "Installation timed out")

    @staticmethod
    def _install_docker_fedora() -> tuple[bool, str]:
        """
        Install Docker on Fedora.

        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info("Installing Docker on Fedora...")

            # Install Docker using dnf
            subprocess.run(
                ["sudo", "dnf", "-y", "install", "dnf-plugins-core"],
                check=True,
                timeout=120,
            )

            subprocess.run(
                [
                    "sudo",
                    "dnf",
                    "config-manager",
                    "--add-repo",
                    "https://download.docker.com/linux/fedora/docker-ce.repo",
                ],
                check=True,
                timeout=60,
            )

            subprocess.run(
                [
                    "sudo",
                    "dnf",
                    "install",
                    "-y",
                    "docker-ce",
                    "docker-ce-cli",
                    "containerd.io",
                    "docker-compose-plugin",
                ],
                check=True,
                timeout=300,
            )

            logger.info("Docker installed successfully on Fedora")
            return (True, "Docker installed successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Docker on Fedora: {e}")
            return (False, f"Installation failed: {e}")
        except subprocess.TimeoutExpired:
            return (False, "Installation timed out")

    @staticmethod
    def _install_docker_arch() -> tuple[bool, str]:
        """
        Install Docker on Arch Linux.

        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info("Installing Docker on Arch Linux...")

            # Install Docker using pacman
            subprocess.run(
                ["sudo", "pacman", "-Syu", "--noconfirm"],
                check=True,
                timeout=120,
            )

            subprocess.run(
                ["sudo", "pacman", "-S", "--noconfirm", "docker", "docker-compose"],
                check=True,
                timeout=300,
            )

            logger.info("Docker installed successfully on Arch Linux")
            return (True, "Docker installed successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Docker on Arch Linux: {e}")
            return (False, f"Installation failed: {e}")
        except subprocess.TimeoutExpired:
            return (False, "Installation timed out")

    @staticmethod
    def install_docker_macos() -> tuple[bool, str]:
        """
        Install Docker on macOS using Homebrew.

        Returns:
            Tuple of (success, message)
        """
        if not DockerInstaller.has_homebrew():
            return (
                False,
                "Homebrew not found. Install from https://brew.sh first.",
            )

        try:
            logger.info("Installing Docker on macOS via Homebrew...")

            # Install Docker Desktop
            subprocess.run(
                ["brew", "install", "--cask", "docker"],
                check=True,
                timeout=600,
            )

            logger.info("Docker installed successfully on macOS")
            return (
                True,
                "Docker Desktop installed. Please launch Docker.app to start the daemon.",
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Docker on macOS: {e}")
            return (False, f"Installation failed: {e}")
        except subprocess.TimeoutExpired:
            return (False, "Installation timed out")

    @staticmethod
    def start_docker_daemon() -> tuple[bool, str]:
        """
        Start Docker daemon if not running.

        Returns:
            Tuple of (success, message)
        """
        plat = DockerInstaller.detect_platform()

        try:
            # Check if daemon is already running
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )

            if result.returncode == 0:
                return (True, "Docker daemon is already running")

            # Try to start daemon
            if plat == "linux":
                subprocess.run(
                    ["sudo", "systemctl", "start", "docker"],
                    check=True,
                    timeout=30,
                )
                subprocess.run(
                    ["sudo", "systemctl", "enable", "docker"],
                    check=True,
                    timeout=30,
                )
                return (True, "Docker daemon started successfully")

            elif plat == "macos":
                return (
                    False,
                    "Please launch Docker Desktop manually from Applications",
                )

            else:
                return (False, f"Cannot auto-start Docker on {plat}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Docker daemon: {e}")
            return (False, f"Failed to start daemon: {e}")
        except subprocess.TimeoutExpired:
            return (False, "Daemon start timed out")

    @staticmethod
    def add_user_to_docker_group() -> tuple[bool, str]:
        """
        Add current user to docker group (Linux only).

        Returns:
            Tuple of (success, message)
        """
        plat = DockerInstaller.detect_platform()

        if plat != "linux":
            return (True, "Not needed on this platform")

        try:
            import getpass

            username = getpass.getuser()

            subprocess.run(
                ["sudo", "usermod", "-aG", "docker", username],
                check=True,
                timeout=30,
            )

            return (
                True,
                f"Added {username} to docker group. Please log out and back in.",
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add user to docker group: {e}")
            return (False, f"Failed: {e}")
        except subprocess.TimeoutExpired:
            return (False, "Operation timed out")

    @staticmethod
    def install_docker() -> tuple[bool, str]:
        """
        Install Docker on the current platform.

        Returns:
            Tuple of (success, message)
        """
        plat = DockerInstaller.detect_platform()

        logger.info(f"Installing Docker on {plat}...")

        if plat == "linux":
            success, msg = DockerInstaller.install_docker_linux()
            if success:
                # Add user to docker group
                DockerInstaller.add_user_to_docker_group()
                # Start daemon
                DockerInstaller.start_docker_daemon()
            return (success, msg)

        elif plat == "macos":
            return DockerInstaller.install_docker_macos()

        elif plat == "windows":
            return (
                False,
                "Automatic Docker installation not supported on Windows.\n"
                "Please download from: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe",
            )

        else:
            return (False, f"Unsupported platform: {plat}")

    @staticmethod
    def get_install_url() -> str:
        """
        Get Docker download URL for current platform.

        Returns:
            Download URL string
        """
        plat = DockerInstaller.detect_platform()

        if plat == "linux":
            return "https://docs.docker.com/engine/install/"
        elif plat == "macos":
            return "https://docs.docker.com/desktop/install/mac-install/"
        elif plat == "windows":
            return "https://docs.docker.com/desktop/install/windows-install/"
        else:
            return "https://docs.docker.com/get-docker/"
