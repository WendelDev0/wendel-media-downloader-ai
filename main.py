from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.text import Text
from yt_dlp import YoutubeDL


console = Console()
DOWNLOADS = Path(__file__).resolve().parent / "downloads"
YOUTUBE_URL = re.compile(
    r"^https?://(www\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)[^\s]+$",
    re.IGNORECASE,
)


def intro() -> None:
    console.clear()
    art = r"""
██╗    ██╗███████╗███╗   ██╗██████╗ ███████╗██╗         ██████╗ ███████╗██╗   ██╗
██║    ██║██╔════╝████╗  ██║██╔══██╗██╔════╝██║         ██╔══██╗██╔════╝██║   ██║
██║ █╗ ██║█████╗  ██╔██╗ ██║██║  ██║█████╗  ██║         ██║  ██║█████╗  ██║   ██║
██║███╗██║██╔══╝  ██║╚██╗██║██║  ██║██╔══╝  ██║         ██║  ██║██╔══╝  ╚██╗ ██╔╝
╚███╔███╔╝███████╗██║ ╚████║██████╔╝███████╗███████╗    ██████╔╝███████╗ ╚████╔╝
 ╚══╝╚══╝ ╚══════╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚══════╝    ╚═════╝ ╚══════╝  ╚═══╝
"""
    for line in art.splitlines():
        console.print(Align.center(Text(line, style="bold bright_green")))
        time.sleep(0.025)
    console.print(
        Panel.fit(
            "[bold cyan]YOUTUBE MEDIA DOWNLOADER[/]\n[dim green]secure terminal initialized // v1.0[/]",
            border_style="bright_green",
            padding=(1, 5),
        ),
        justify="center",
    )
    with Progress(
        SpinnerColumn(style="green"), TextColumn("[green]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Carregando módulos...", total=None)
        time.sleep(0.7)
        progress.update(task, description="Sistema pronto.")
        time.sleep(0.35)


def progress_hook(data: dict) -> None:
    if data.get("status") == "downloading":
        downloaded = data.get("downloaded_bytes", 0)
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        percent = (downloaded / total * 100) if total else 0
        speed = data.get("_speed_str", "--")
        eta = data.get("_eta_str", "--")
        console.print(
            f"\r[bright_green]▓[/] [cyan]{percent:5.1f}%[/]  "
            f"[dim]velocidade {speed} • ETA {eta}[/]",
            end="",
        )
    elif data.get("status") == "finished":
        console.print("\n[bold green]✓ Download concluído. Processando arquivo...[/]")


def choose_format() -> str:
    console.print("\n[bold green][01][/] MP4  [dim]vídeo[/]")
    console.print("[bold magenta][02][/] MP3  [dim]somente áudio[/]")
    while True:
        choice = Prompt.ask("\n[cyan]Selecione o formato[/]", choices=["1", "2", "01", "02"])
        if choice in {"1", "01"}:
            return "mp4"
        if choice in {"2", "02"}:
            return "mp3"


def download(url: str, media_format: str) -> None:
    DOWNLOADS.mkdir(exist_ok=True)
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    common = {
        "outtmpl": str(DOWNLOADS / "%(title).180B [%(id)s].%(ext)s"),
        "ffmpeg_location": ffmpeg_path,
        "progress_hooks": [progress_hook],
        "noplaylist": True,
        "windowsfilenames": True,
        "quiet": True,
        "no_warnings": True,
    }
    if node_path := shutil.which("node"):
        common["js_runtimes"] = {"node": {"path": node_path}}

    if media_format == "mp4":
        options = {
            **common,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }
    else:
        options = {
            **common,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ],
        }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "arquivo")
    console.print(
        Panel(
            f"[bold bright_green]✓ MISSÃO CONCLUÍDA[/]\n\n"
            f"[white]{title}[/]\n[dim]Formato: {media_format.upper()}\nPasta: {DOWNLOADS}[/]",
            border_style="green",
        )
    )


def main() -> None:
    try:
        intro()
        while True:
            url = Prompt.ask("\n[bold cyan]Cole o link do vídeo do YouTube[/]").strip()
            if YOUTUBE_URL.match(url):
                break
            console.print("[bold red]✗ Link inválido. Cole uma URL válida do YouTube.[/]")
        media_format = choose_format()
        console.print(f"\n[green]>[/] Iniciando captura em [bold]{media_format.upper()}[/]...")
        download(url, media_format)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operação cancelada pelo usuário.[/]")
    except Exception as exc:
        console.print(Panel(f"[bold red]Falha no download[/]\n{exc}", border_style="red"))
        sys.exit(1)


if __name__ == "__main__":
    main()
