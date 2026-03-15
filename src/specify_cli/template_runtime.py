from __future__ import annotations

import json
import os
import posixpath
import shutil
import ssl
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Protocol

import httpx
import truststore
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

DEFAULT_TEMPLATE_REPO_OWNER = "Z-WICK"
DEFAULT_TEMPLATE_REPO_NAME = "spec-kit"

MAX_ZIP_MEMBER_COUNT = 10000
MAX_ZIP_MEMBER_SIZE = 100 * 1024 * 1024
MAX_ZIP_TOTAL_SIZE = 500 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 1000


class TrackerLike(Protocol):
    def add(self, key: str, label: str) -> None: ...
    def start(self, key: str, detail: str = "") -> None: ...
    def complete(self, key: str, detail: str = "") -> None: ...
    def error(self, key: str, detail: str = "") -> None: ...
    def skip(self, key: str, detail: str = "") -> None: ...


def _github_token(cli_token: str | None = None) -> str | None:
    """Return sanitized GitHub token (cli arg takes precedence) or None."""
    return ((cli_token or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()) or None


def _github_auth_headers(cli_token: str | None = None) -> dict[str, str]:
    """Return Authorization header dict only when a non-empty token exists."""
    token = _github_token(cli_token)
    return {"Authorization": f"Bearer {token}"} if token else {}


def _parse_rate_limit_headers(headers: httpx.Headers) -> dict:
    """Extract and parse GitHub rate-limit headers."""
    info: dict[str, object] = {}

    if "X-RateLimit-Limit" in headers:
        info["limit"] = headers.get("X-RateLimit-Limit")
    if "X-RateLimit-Remaining" in headers:
        info["remaining"] = headers.get("X-RateLimit-Remaining")
    if "X-RateLimit-Reset" in headers:
        reset_epoch = int(headers.get("X-RateLimit-Reset", "0"))
        if reset_epoch:
            reset_time = datetime.fromtimestamp(reset_epoch, tz=timezone.utc)
            info["reset_epoch"] = reset_epoch
            info["reset_time"] = reset_time
            info["reset_local"] = reset_time.astimezone()

    if "Retry-After" in headers:
        retry_after = headers.get("Retry-After")
        try:
            info["retry_after_seconds"] = int(retry_after)
        except ValueError:
            info["retry_after"] = retry_after

    return info


def _format_rate_limit_error(status_code: int, headers: httpx.Headers, url: str) -> str:
    """Format a user-friendly error message with rate-limit information."""
    rate_info = _parse_rate_limit_headers(headers)

    lines = [f"GitHub API returned status {status_code} for {url}", ""]

    if rate_info:
        lines.append("[bold]Rate Limit Information:[/bold]")
        if "limit" in rate_info:
            lines.append(f"  • Rate Limit: {rate_info['limit']} requests/hour")
        if "remaining" in rate_info:
            lines.append(f"  • Remaining: {rate_info['remaining']}")
        if "reset_local" in rate_info:
            reset_str = rate_info["reset_local"].strftime("%Y-%m-%d %H:%M:%S %Z")
            lines.append(f"  • Resets at: {reset_str}")
        if "retry_after_seconds" in rate_info:
            lines.append(f"  • Retry after: {rate_info['retry_after_seconds']} seconds")
        lines.append("")

    lines.append("[bold]Troubleshooting Tips:[/bold]")
    lines.append("  • If you're on a shared CI or corporate environment, you may be rate-limited.")
    lines.append("  • Consider using a GitHub token via --github-token or the GH_TOKEN/GITHUB_TOKEN")
    lines.append("    environment variable to increase rate limits.")
    lines.append("  • Authenticated requests have a limit of 5,000/hour vs 60/hour for unauthenticated.")

    return "\n".join(lines)


def merge_json_files(existing_path: Path, new_content: dict, verbose: bool = False) -> dict:
    """Merge new JSON content into existing JSON file."""
    try:
        with open(existing_path, "r", encoding="utf-8") as f:
            existing_content = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return new_content

    def deep_merge(base: dict, update: dict) -> dict:
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    merged = deep_merge(existing_content, new_content)

    if verbose:
        console.print(f"[cyan]Merged JSON file:[/cyan] {existing_path.name}")

    return merged


def handle_vscode_settings(
    sub_item: Path,
    dest_file: Path,
    rel_path: Path,
    verbose: bool = False,
    tracker: TrackerLike | None = None,
) -> None:
    """Handle merging or copying of .vscode/settings.json files."""

    def log(message: str, color: str = "green") -> None:
        if verbose and not tracker:
            console.print(f"[{color}]{message}[/] {rel_path}")

    try:
        with open(sub_item, "r", encoding="utf-8") as f:
            new_settings = json.load(f)

        if dest_file.exists():
            merged = merge_json_files(dest_file, new_settings, verbose=verbose and not tracker)
            with open(dest_file, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=4)
                f.write("\n")
            log("Merged:", "green")
        else:
            shutil.copy2(sub_item, dest_file)
            log("Copied (no existing settings.json):", "blue")

    except Exception as e:
        log(f"Warning: Could not merge, copying instead: {e}", "yellow")
        shutil.copy2(sub_item, dest_file)


def should_preserve_existing_on_reinit(project_relative_path: Path) -> bool:
    """Return True when re-initialization should preserve an existing file."""
    parts = project_relative_path.parts
    if not parts:
        return False

    if parts[0] == "specs":
        return True

    if parts[0] == ".specify":
        if len(parts) >= 2 and parts[1] in {"memory", "extensions"}:
            return True
        if len(parts) >= 2 and parts[1] == ".project":
            return True
        if len(parts) >= 2 and parts[1].startswith("pipeline-state"):
            return True

    return False


def download_template_from_github(
    ai_assistant: str,
    download_dir: Path,
    *,
    script_type: str = "sh",
    verbose: bool = True,
    show_progress: bool = True,
    client: httpx.Client | None = None,
    debug: bool = False,
    github_token: str | None = None,
) -> tuple[Path, dict]:
    if client is None:
        client = httpx.Client(verify=ssl_context)

    if verbose:
        console.print("[cyan]Fetching latest release information...[/cyan]")
    api_url = (
        f"https://api.github.com/repos/{DEFAULT_TEMPLATE_REPO_OWNER}/"
        f"{DEFAULT_TEMPLATE_REPO_NAME}/releases/latest"
    )

    try:
        response = client.get(
            api_url,
            timeout=30,
            follow_redirects=True,
            headers=_github_auth_headers(github_token),
        )
        status = response.status_code
        if status != 200:
            error_msg = _format_rate_limit_error(status, response.headers, api_url)
            if debug:
                error_msg += f"\n\n[dim]Response body (truncated 500):[/dim]\n{response.text[:500]}"
            raise RuntimeError(error_msg)
        try:
            release_data = response.json()
        except ValueError as je:
            raise RuntimeError(
                f"Failed to parse release JSON: {je}\nRaw (truncated 400): {response.text[:400]}"
            ) from je
    except Exception as e:
        console.print("[red]Error fetching release information[/red]")
        console.print(Panel(str(e), title="Fetch Error", border_style="red"))
        raise typer.Exit(1) from e

    assets = release_data.get("assets", [])
    pattern = f"spec-kit-template-{ai_assistant}-{script_type}"
    matching_assets = [
        asset for asset in assets if pattern in asset["name"] and asset["name"].endswith(".zip")
    ]

    asset = matching_assets[0] if matching_assets else None
    if asset is None:
        console.print(
            f"[red]No matching release asset found[/red] for [bold]{ai_assistant}[/bold] "
            f"(expected pattern: [bold]{pattern}[/bold])"
        )
        asset_names = [a.get("name", "?") for a in assets]
        console.print(
            Panel("\n".join(asset_names) or "(no assets)", title="Available Assets", border_style="yellow")
        )
        raise typer.Exit(1)

    download_url = asset["browser_download_url"]
    filename = asset["name"]
    file_size = asset["size"]

    if verbose:
        console.print(f"[cyan]Found template:[/cyan] {filename}")
        console.print(f"[cyan]Size:[/cyan] {file_size:,} bytes")
        console.print(f"[cyan]Release:[/cyan] {release_data['tag_name']}")

    zip_path = download_dir / filename
    if verbose:
        console.print("[cyan]Downloading template...[/cyan]")

    try:
        with client.stream(
            "GET",
            download_url,
            timeout=60,
            follow_redirects=True,
            headers=_github_auth_headers(github_token),
        ) as response:
            if response.status_code != 200:
                error_msg = _format_rate_limit_error(response.status_code, response.headers, download_url)
                if debug:
                    error_msg += f"\n\n[dim]Response body (truncated 400):[/dim]\n{response.text[:400]}"
                raise RuntimeError(error_msg)

            total_size = int(response.headers.get("content-length", 0))
            with open(zip_path, "wb") as f:
                if total_size == 0:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                elif show_progress:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        console=console,
                    ) as progress:
                        task = progress.add_task("Downloading...", total=total_size)
                        downloaded = 0
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress.update(task, completed=downloaded)
                else:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
    except Exception as e:
        console.print("[red]Error downloading template[/red]")
        if zip_path.exists():
            zip_path.unlink()
        console.print(Panel(str(e), title="Download Error", border_style="red"))
        raise typer.Exit(1) from e

    if verbose:
        console.print(f"Downloaded: {filename}")

    metadata = {
        "filename": filename,
        "size": file_size,
        "release": release_data["tag_name"],
        "asset_url": download_url,
    }
    return zip_path, metadata


def _ensure_within_destination(path: Path, destination: Path) -> None:
    """Ensure a target path stays within the destination root."""
    destination_resolved = destination.resolve()
    resolved_path = path.resolve(strict=False)
    if resolved_path != destination_resolved and destination_resolved not in resolved_path.parents:
        raise ValueError(f"Path escapes destination: {path}")


def _ensure_no_symlink_components(path: Path, destination: Path) -> None:
    """Reject any existing symlink component between destination and path."""
    destination_resolved = destination.resolve()
    target_parent = path if path == destination_resolved else path.parent

    try:
        relative_parent = target_parent.relative_to(destination_resolved)
    except ValueError as e:
        raise ValueError(f"Path escapes destination: {path}") from e

    current = destination_resolved
    for part in relative_parent.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError(f"Path contains symlink component: {current}")


def _validate_zip_members(zip_ref: zipfile.ZipFile, destination: Path) -> None:
    """Validate ZIP members before extraction to prevent path traversal."""
    destination_resolved = destination.resolve()
    members = zip_ref.infolist()

    if len(members) > MAX_ZIP_MEMBER_COUNT:
        raise ValueError(f"ZIP archive has too many entries: {len(members)}")

    total_uncompressed_size = 0
    for member in members:
        member_name = member.filename
        if not member_name:
            raise ValueError("ZIP archive contains an empty member name")

        if member.file_size > MAX_ZIP_MEMBER_SIZE:
            raise ValueError(f"ZIP archive member is too large: {member_name}")

        total_uncompressed_size += member.file_size
        if total_uncompressed_size > MAX_ZIP_TOTAL_SIZE:
            raise ValueError("ZIP archive expands beyond the allowed size limit")

        compressed_size = max(member.compress_size, 1)
        if member.file_size > 0 and member.file_size / compressed_size > MAX_ZIP_COMPRESSION_RATIO:
            raise ValueError(f"ZIP archive member has suspicious compression ratio: {member_name}")

        normalized_name = posixpath.normpath(member_name)
        member_path = PurePosixPath(normalized_name)
        if member_path.is_absolute():
            raise ValueError(f"ZIP archive contains absolute path: {member_name}")
        if any(part == ".." for part in member_path.parts):
            raise ValueError(f"ZIP archive contains unsafe path: {member_name}")
        if stat.S_ISLNK(member.external_attr >> 16):
            raise ValueError(f"ZIP archive contains symlink entry: {member_name}")

        resolved_target = (destination_resolved / Path(*member_path.parts)).resolve()
        if resolved_target != destination_resolved and destination_resolved not in resolved_target.parents:
            raise ValueError(f"ZIP archive path escapes destination: {member_name}")


def _normalize_project_relative_parts(raw_path: str) -> tuple[str, ...]:
    """Normalize a user-provided project-relative path into safe path parts."""
    relative_path = Path(raw_path)
    if relative_path.is_absolute():
        raise ValueError(f"Path must be relative to the project: {raw_path}")

    parts = tuple(part for part in relative_path.parts if part not in ("", "."))
    if not parts:
        raise ValueError(f"Path must not be empty: {raw_path}")
    if any(part == ".." for part in parts):
        raise ValueError(f"Path must not escape the project: {raw_path}")
    return parts


def _resolve_project_relative_path(raw_path: str, project_path: Path) -> Path:
    """Resolve a user-provided relative path and keep it inside the project."""
    parts = _normalize_project_relative_parts(raw_path)
    target_path = (project_path / Path(*parts)).resolve(strict=False)
    _ensure_within_destination(target_path, project_path)
    _ensure_no_symlink_components(target_path, project_path)
    return target_path


def _supports_secure_directory_move() -> bool:
    """Return whether the platform supports the strict dir_fd-based move path."""
    required_features = (
        hasattr(os, "rename")
        and hasattr(os, "mkdir")
        and hasattr(os, "open")
        and hasattr(os, "O_NOFOLLOW")
        and hasattr(os, "O_DIRECTORY")
    )
    if not required_features:
        return False

    dir_fd_support = getattr(os, "supports_dir_fd", ())
    return os.rename in dir_fd_support and os.open in dir_fd_support and os.mkdir in dir_fd_support


def _safe_move_directory_into_project(source_dir: Path, raw_target_path: str, project_path: Path) -> Path:
    """Move a directory into the project using the strongest safe mechanism available."""
    target_parts = _normalize_project_relative_parts(raw_target_path)
    target_path = project_path / Path(*target_parts)

    _ensure_within_destination(source_dir, project_path)
    _ensure_no_symlink_components(source_dir, project_path)
    if source_dir.is_symlink():
        raise ValueError(f"Source path must not be a symlink: {source_dir}")

    if not _supports_secure_directory_move():
        raise ValueError(
            "Secure directory move is not supported on this platform for --ai generic with --ai-commands-dir"
        )

    open_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

    root_fd = os.open(str(project_path.resolve()), open_flags)
    current_fd = root_fd
    source_parent_fd = None
    source_dir_fd = None
    try:
        for part in target_parts[:-1]:
            try:
                os.mkdir(part, dir_fd=current_fd)
            except FileExistsError:
                pass

            next_fd = os.open(part, open_flags, dir_fd=current_fd)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd

        leaf_name = target_parts[-1]
        try:
            os.lstat(leaf_name, dir_fd=current_fd)
            raise ValueError(f"Target path already exists: {target_path}")
        except FileNotFoundError:
            pass

        source_parent_fd = os.open(str(source_dir.parent.resolve()), open_flags)
        source_dir_fd = os.open(source_dir.name, open_flags, dir_fd=source_parent_fd)
        os.close(source_dir_fd)
        source_dir_fd = None
        os.rename(source_dir.name, leaf_name, src_dir_fd=source_parent_fd, dst_dir_fd=current_fd)
    finally:
        if source_dir_fd is not None:
            os.close(source_dir_fd)
        if source_parent_fd is not None:
            os.close(source_parent_fd)
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)

    resolved_target = target_path.resolve(strict=False)
    _ensure_within_destination(resolved_target, project_path)
    _ensure_no_symlink_components(resolved_target, project_path)
    return resolved_target


def download_and_extract_template(
    project_path: Path,
    ai_assistant: str,
    script_type: str,
    is_current_dir: bool = False,
    *,
    verbose: bool = True,
    tracker: TrackerLike | None = None,
    client: httpx.Client | None = None,
    debug: bool = False,
    github_token: str | None = None,
) -> Path:
    """Download the latest release and extract it to create a new project."""
    current_dir = Path.cwd()

    if tracker:
        tracker.start("fetch", "contacting GitHub API")
    try:
        zip_path, meta = download_template_from_github(
            ai_assistant,
            current_dir,
            script_type=script_type,
            verbose=verbose and tracker is None,
            show_progress=tracker is None,
            client=client,
            debug=debug,
            github_token=github_token,
        )
        if tracker:
            tracker.complete("fetch", f"release {meta['release']} ({meta['size']:,} bytes)")
            tracker.add("download", "Download template")
            tracker.complete("download", meta["filename"])
    except Exception as e:
        if tracker:
            tracker.error("fetch", str(e))
        elif verbose:
            console.print(f"[red]Error downloading template:[/red] {e}")
        raise

    if tracker:
        tracker.add("extract", "Extract template")
        tracker.start("extract")
    elif verbose:
        console.print("Extracting template...")

    extract_detail: str | None = None
    try:
        if not is_current_dir:
            project_path.mkdir(parents=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_contents = zip_ref.namelist()
            if tracker:
                tracker.start("zip-list")
                tracker.complete("zip-list", f"{len(zip_contents)} entries")
            elif verbose:
                console.print(f"[cyan]ZIP contains {len(zip_contents)} items[/cyan]")

            if is_current_dir:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    _validate_zip_members(zip_ref, temp_path)
                    zip_ref.extractall(temp_path)

                    preserved_paths: list[str] = []
                    extracted_items = list(temp_path.iterdir())
                    if tracker:
                        tracker.start("extracted-summary")
                        tracker.complete("extracted-summary", f"temp {len(extracted_items)} items")
                    elif verbose:
                        console.print(f"[cyan]Extracted {len(extracted_items)} items to temp location[/cyan]")

                    source_dir = temp_path
                    if len(extracted_items) == 1 and extracted_items[0].is_dir():
                        source_dir = extracted_items[0]
                        if tracker:
                            tracker.add("flatten", "Flatten nested directory")
                            tracker.complete("flatten")
                        elif verbose:
                            console.print("[cyan]Found nested directory structure[/cyan]")

                    for item in source_dir.iterdir():
                        dest_path = project_path / item.name
                        _ensure_within_destination(dest_path, project_path)
                        if item.is_dir():
                            if dest_path.exists():
                                if verbose and not tracker:
                                    console.print(f"[yellow]Merging directory:[/yellow] {item.name}")
                                for sub_item in item.rglob("*"):
                                    if sub_item.is_file():
                                        rel_path = sub_item.relative_to(item)
                                        dest_file = dest_path / rel_path
                                        _ensure_within_destination(dest_file.parent, project_path)
                                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                                        _ensure_within_destination(dest_file, project_path)
                                        project_rel = dest_file.relative_to(project_path)

                                        if dest_file.exists() and should_preserve_existing_on_reinit(project_rel):
                                            preserved_paths.append(str(project_rel))
                                            continue

                                        if (
                                            dest_file.name == "settings.json"
                                            and dest_file.parent.name == ".vscode"
                                        ):
                                            handle_vscode_settings(
                                                sub_item,
                                                dest_file,
                                                rel_path,
                                                verbose,
                                                tracker,
                                            )
                                        else:
                                            shutil.copy2(sub_item, dest_file)
                            else:
                                shutil.copytree(item, dest_path)
                        else:
                            project_rel = dest_path.relative_to(project_path)
                            if dest_path.exists() and should_preserve_existing_on_reinit(project_rel):
                                preserved_paths.append(str(project_rel))
                                continue
                            if dest_path.exists() and verbose and not tracker:
                                console.print(f"[yellow]Overwriting file:[/yellow] {item.name}")
                            _ensure_within_destination(dest_path, project_path)
                            shutil.copy2(item, dest_path)
                    if verbose and not tracker:
                        if preserved_paths:
                            preview = ", ".join(preserved_paths[:5])
                            more = f" (+{len(preserved_paths) - 5} more)" if len(preserved_paths) > 5 else ""
                            console.print(f"[yellow]Preserved existing files:[/yellow] {preview}{more}")
                        console.print("[cyan]Template files merged into current directory[/cyan]")
                    extract_detail = (
                        f"merged, preserved {len(preserved_paths)} existing files"
                        if preserved_paths
                        else "merged"
                    )
            else:
                _validate_zip_members(zip_ref, project_path)
                zip_ref.extractall(project_path)

                extracted_items = list(project_path.iterdir())
                if tracker:
                    tracker.start("extracted-summary")
                    tracker.complete("extracted-summary", f"{len(extracted_items)} top-level items")
                elif verbose:
                    console.print(f"[cyan]Extracted {len(extracted_items)} items to {project_path}:[/cyan]")
                    for item in extracted_items:
                        console.print(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")

                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    nested_dir = extracted_items[0]
                    temp_move_dir = project_path.parent / f"{project_path.name}_temp"

                    shutil.move(str(nested_dir), str(temp_move_dir))
                    project_path.rmdir()
                    shutil.move(str(temp_move_dir), str(project_path))
                    if tracker:
                        tracker.add("flatten", "Flatten nested directory")
                        tracker.complete("flatten")
                    elif verbose:
                        console.print("[cyan]Flattened nested directory structure[/cyan]")

    except Exception as e:
        if tracker:
            tracker.error("extract", str(e))
        elif verbose:
            console.print(f"[red]Error extracting template:[/red] {e}")
            if debug:
                console.print(Panel(str(e), title="Extraction Error", border_style="red"))

        if not is_current_dir and project_path.exists():
            shutil.rmtree(project_path)
        raise typer.Exit(1) from e
    else:
        if tracker:
            tracker.complete("extract", extract_detail or "")
    finally:
        if tracker:
            tracker.add("cleanup", "Remove temporary archive")

        if zip_path.exists():
            zip_path.unlink()
            if tracker:
                tracker.complete("cleanup")
            elif verbose:
                console.print(f"Cleaned up: {zip_path.name}")

    return project_path


def ensure_executable_scripts(project_path: Path, tracker: TrackerLike | None = None) -> None:
    """Ensure POSIX .sh scripts under .specify/scripts have execute bits."""
    if os.name == "nt":
        return
    scripts_root = project_path / ".specify" / "scripts"
    if not scripts_root.is_dir():
        return
    failures: list[str] = []
    updated = 0
    for script in scripts_root.rglob("*.sh"):
        try:
            if script.is_symlink() or not script.is_file():
                continue
            try:
                with script.open("rb") as f:
                    if f.read(2) != b"#!":
                        continue
            except Exception:
                continue
            mode = script.stat().st_mode
            if mode & 0o111:
                continue
            new_mode = mode
            if mode & 0o400:
                new_mode |= 0o100
            if mode & 0o040:
                new_mode |= 0o010
            if mode & 0o004:
                new_mode |= 0o001
            if not (new_mode & 0o100):
                new_mode |= 0o100
            os.chmod(script, new_mode)
            updated += 1
        except Exception as e:
            failures.append(f"{script.relative_to(scripts_root)}: {e}")
    if tracker:
        detail = f"{updated} updated" + (f", {len(failures)} failed" if failures else "")
        tracker.add("chmod", "Set script permissions recursively")
        (tracker.error if failures else tracker.complete)("chmod", detail)
    else:
        if updated:
            console.print(f"[cyan]Updated execute permissions on {updated} script(s) recursively[/cyan]")
        if failures:
            console.print("[yellow]Some scripts could not be updated:[/yellow]")
            for failure in failures:
                console.print(f"  - {failure}")


def ensure_constitution_from_template(project_path: Path, tracker: TrackerLike | None = None) -> None:
    """Copy constitution template to memory if it doesn't exist."""
    memory_constitution = project_path / ".specify" / "memory" / "constitution.md"
    template_constitution = project_path / ".specify" / "templates" / "constitution-template.md"

    if memory_constitution.exists():
        if tracker:
            tracker.add("constitution", "Constitution setup")
            tracker.skip("constitution", "existing file preserved")
        return

    if not template_constitution.exists():
        if tracker:
            tracker.add("constitution", "Constitution setup")
            tracker.error("constitution", "template not found")
        return

    try:
        memory_constitution.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_constitution, memory_constitution)
        if tracker:
            tracker.add("constitution", "Constitution setup")
            tracker.complete("constitution", "copied from template")
        else:
            console.print("[cyan]Initialized constitution from template[/cyan]")
    except Exception as e:
        if tracker:
            tracker.add("constitution", "Constitution setup")
            tracker.error("constitution", str(e))
        else:
            console.print(f"[yellow]Warning: Could not initialize constitution: {e}[/yellow]")
