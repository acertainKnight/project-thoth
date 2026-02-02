"""
Service management commands for Thoth.

Provides start, stop, restart, and status commands for Docker-based services.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger


def get_project_root() -> Path:
    """
    Find the project root directory.
    
    Returns:
        Path to project root
    """
    # Try config file first
    config_file = Path.home() / ".config" / "thoth" / "cli.conf"
    if config_file.exists():
        with open(config_file) as f:
            for line in f:
                if line.startswith("THOTH_PROJECT_ROOT="):
                    path = line.split("=", 1)[1].strip().strip('"')
                    return Path(path)
    
    # Try to find from current directory
    current = Path.cwd()
    while current != current.parent:
        if (current / "docker-compose.yml").exists():
            return current
        current = current.parent
    
    # Fallback to common location
    fallback = Path.home() / "thoth"
    if fallback.exists():
        return fallback
    
    logger.error("Could not find Thoth project root")
    print("❌ Could not find Thoth installation")
    print("   Run 'thoth setup' to install Thoth")
    sys.exit(1)


def get_letta_mode() -> str:
    """
    Get current Letta mode from settings.
    
    Returns:
        'cloud' or 'self-hosted'
    """
    settings_file = Path.home() / ".config" / "thoth" / "settings.json"
    if not settings_file.exists():
        return "self-hosted"  # Default
    
    try:
        with open(settings_file) as f:
            settings = json.load(f)
            return settings.get("letta", {}).get("mode", "self-hosted")
    except Exception:
        return "self-hosted"


def run_docker_compose(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """
    Run docker compose command.
    
    Args:
        args: Command arguments
        cwd: Working directory
        check: Raise on error
        
    Returns:
        Completed process
    """
    cmd = ["docker", "compose"] + args
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check
    )


def handle_start(args) -> int:
    """
    Start Thoth services.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    print("🚀 Starting Thoth services...")
    
    project_root = get_project_root()
    letta_mode = get_letta_mode()
    
    try:
        # Start Letta if self-hosted
        if letta_mode == "self-hosted":
            print("  Starting Letta (self-hosted mode)...")
            result = run_docker_compose(
                ["-f", "docker-compose.letta.yml", "up", "-d"],
                cwd=project_root,
                check=False
            )
            if result.returncode != 0:
                logger.warning(f"Letta start had issues: {result.stderr}")
                print("  ⚠️  Letta may need manual start")
            else:
                print("  ✅ Letta started")
            
            # Wait for Letta to be ready
            time.sleep(3)
        
        # Start Thoth services
        print("  Starting Thoth services...")
        result = run_docker_compose(["up", "-d"], cwd=project_root)
        
        print("\n✅ Thoth is running!")
        if letta_mode == "cloud":
            print("   Letta: Cloud (api.letta.com)")
        else:
            print("   Letta: http://localhost:8283")
        print("   API: http://localhost:8000")
        print("   MCP: http://localhost:8001")
        print("\n💡 Tip: Use 'thoth stop' to free RAM when not in use")
        
        return 0
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start services: {e.stderr}")
        print(f"\n❌ Failed to start services: {e.stderr}")
        print("   Check 'docker ps' to see running containers")
        return 1


def handle_stop(args) -> int:
    """
    Stop Thoth services.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    print("🛑 Stopping Thoth services...")
    
    project_root = get_project_root()
    letta_mode = get_letta_mode()
    
    try:
        # Stop Thoth services
        run_docker_compose(["stop"], cwd=project_root)
        print("✅ Thoth stopped (RAM freed)")
        
        # Ask about Letta if self-hosted
        if letta_mode == "self-hosted":
            print("\n💡 Letta containers still running (shared across projects)")
            if not args.get("quiet", False):
                response = input("   Stop Letta too? (y/N): ")
                if response.lower() in ["y", "yes"]:
                    run_docker_compose(
                        ["-f", "docker-compose.letta.yml", "stop"],
                        cwd=project_root
                    )
                    print("   ✅ Letta stopped")
        
        return 0
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop services: {e.stderr}")
        print(f"\n❌ Failed to stop services: {e.stderr}")
        return 1


def handle_restart(args) -> int:
    """
    Restart Thoth services.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    print("🔄 Restarting Thoth services...")
    
    # Stop first
    stop_args = {"quiet": True}
    if handle_stop(stop_args) != 0:
        return 1
    
    print("   Waiting...")
    time.sleep(2)
    
    # Start again
    return handle_start(args)


def handle_status(args) -> int:
    """
    Show service status.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    project_root = get_project_root()
    letta_mode = get_letta_mode()
    
    print("📊 Thoth Service Status:\n")
    
    # Show Thoth services
    result = run_docker_compose(["ps"], cwd=project_root, check=False)
    print(result.stdout)
    
    # Show Letta if self-hosted
    if letta_mode == "self-hosted":
        print("\n📊 Letta Service Status:\n")
        result = run_docker_compose(
            ["-f", "docker-compose.letta.yml", "ps"],
            cwd=project_root,
            check=False
        )
        print(result.stdout)
    else:
        print("Letta: Cloud mode (api.letta.com)")
    
    return 0


def handle_logs(args) -> int:
    """
    Show service logs.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    project_root = get_project_root()
    
    # Build docker compose logs command
    cmd = ["logs"]
    if args.get("follow", False):
        cmd.append("-f")
    if args.get("tail"):
        cmd.extend(["--tail", str(args["tail"])])
    if args.get("service"):
        cmd.append(args["service"])
    
    try:
        subprocess.run(
            ["docker", "compose"] + cmd,
            cwd=project_root,
            check=True
        )
        return 0
    except subprocess.CalledProcessError:
        return 1


def configure_subparser(subparsers) -> None:
    """
    Configure service management subcommand.
    
    Args:
        subparsers: Subparser object from argparse
    """
    parser = subparsers.add_parser(
        "service",
        help="Manage Thoth services (start/stop/status)",
        description="Manage Thoth Docker services"
    )
    
    service_subparsers = parser.add_subparsers(dest="service_command", help="Service command")
    
    # Start command
    start_parser = service_subparsers.add_parser("start", help="Start Thoth services")
    start_parser.set_defaults(func=handle_start)
    
    # Stop command
    stop_parser = service_subparsers.add_parser("stop", help="Stop Thoth services")
    stop_parser.add_argument("--quiet", "-q", action="store_true", help="Don't ask about Letta")
    stop_parser.set_defaults(func=handle_stop)
    
    # Restart command
    restart_parser = service_subparsers.add_parser("restart", help="Restart Thoth services")
    restart_parser.set_defaults(func=handle_restart)
    
    # Status command
    status_parser = service_subparsers.add_parser("status", help="Show service status")
    status_parser.set_defaults(func=handle_status)
    
    # Logs command
    logs_parser = service_subparsers.add_parser("logs", help="View service logs")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output")
    logs_parser.add_argument("--tail", type=int, help="Number of lines to show from end")
    logs_parser.add_argument("service", nargs="?", help="Specific service name")
    logs_parser.set_defaults(func=handle_logs)
