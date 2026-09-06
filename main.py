from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
from rich import box
from dotenv import load_dotenv
from openai import APIConnectionError, InternalServerError, OpenAI, RateLimitError
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from yt_dlp import YoutubeDL


console = Console()
ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
DOWNLOADS = ROOT / "downloads"
TRANSCRIPTS = ROOT / "transcricoes"
ENV_FILE = ROOT / ".env"
SUPPORTED_MEDIA = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".flac"}
YOUTUBE_URL = re.compile(
    r"^https?://(www\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)[^\s]+$",
    re.IGNORECASE,
)
OUTPUT_NAME_LOCK = threading.Lock()


@dataclass
class TranscriptionJob:
    name: str
    stage: str = "Na fila"
    percent: float = 0
    status: str = "waiting"
    started_at: float = 0


class TranscriptionDashboard:
    def __init__(self, sources: list[Path]) -> None:
        self.jobs = {str(path): TranscriptionJob(path.name) for path in sources}
        self.started_at = time.monotonic()
        self.lock = threading.Lock()
        self.live = Live(self, console=console, refresh_per_second=10, transient=False)

    def __rich_console__(self, _console, _options):
        yield self.render()

    def __enter__(self) -> "TranscriptionDashboard":
        self.live.start()
        return self

    def __exit__(self, *_args) -> None:
        self.live.update(self.render(), refresh=True)
        self.live.stop()

    def update(
        self,
        source: Path,
        stage: str,
        percent: float,
        status: str = "running",
    ) -> None:
        with self.lock:
            job = self.jobs[str(source)]
            job.stage = stage
            job.percent = max(0, min(100, percent))
            job.status = status
            if not job.started_at and status == "running":
                job.started_at = time.monotonic()
        self.live.update(self)

    def render(self):
        with self.lock:
            jobs = list(self.jobs.values())
            elapsed = int(time.monotonic() - self.started_at)
            average = sum(job.percent for job in jobs) / max(1, len(jobs))
            done = sum(job.status == "done" for job in jobs)
            failed = sum(job.status == "error" for job in jobs)

            phase = int(time.monotonic() * 8) % 34
            scanner = Text("  WENDEL DEV // NEURAL TRANSCRIPTION ENGINE  ", style="dim green")
            scanner.stylize("bold bright_cyan", phase, min(phase + 5, len(scanner)))
            header = Panel(
                Align.center(scanner),
                title="[bold bright_green]SYSTEM ONLINE[/]",
                subtitle=f"[cyan]{elapsed // 60:02}:{elapsed % 60:02}[/]",
                border_style="bright_green",
                box=box.DOUBLE,
            )

            overall = Progress(
                TextColumn("[bold cyan]PROGRESSO GLOBAL[/]"),
                BarColumn(bar_width=None, complete_style="bright_green", finished_style="bright_cyan"),
                TaskProgressColumn(),
                expand=True,
            )
            overall.add_task("lote", total=100, completed=average)

            table = Table(
                box=box.ROUNDED,
                border_style="green",
                header_style="bold bright_cyan",
                expand=True,
                padding=(0, 1),
            )
            table.add_column("STATUS", width=10, justify="center")
            table.add_column("ARQUIVO", ratio=4, overflow="ellipsis", no_wrap=True)
            table.add_column("ETAPA ATUAL", ratio=3, overflow="ellipsis")
            table.add_column("PROGRESSO", width=12, justify="right")
            icons = {
                "waiting": ("[dim]AGUARDA[/]", "dim"),
                "running": ("[bold yellow]ATIVO[/]", "yellow"),
                "done": ("[bold green]PRONTO[/]", "green"),
                "error": ("[bold red]ERRO[/]", "red"),
            }
            priority = {"running": 0, "error": 1, "waiting": 2, "done": 3}
            visible_jobs = sorted(jobs, key=lambda job: priority[job.status])[:8]
            for job in visible_jobs:
                badge, color = icons[job.status]
                table.add_row(
                    badge,
                    Text(job.name, style="white"),
                    Text(job.stage, style=color),
                    Text(f"{job.percent:6.1f}%", style=f"bold {color}"),
                )
            if len(jobs) > len(visible_jobs):
                table.add_row(
                    "[dim]MAIS[/]",
                    f"[dim]+ {len(jobs) - len(visible_jobs)} arquivos no lote[/]",
                    "[dim]Processamento continua em segundo plano[/]",
                    "[dim]...[/]",
                )

            wave_chars = ".:-=+*#%@#*+=-:"
            offset = int(time.monotonic() * 12) % len(wave_chars)
            wave = (wave_chars[offset:] + wave_chars[:offset]) * 4
            footer = Panel(
                Align.center(Text(wave, style="bold bright_green")),
                title=f"[white]ARQUIVOS {len(jobs)}[/]  [green]PRONTOS {done}[/]  [red]FALHAS {failed}[/]",
                border_style="cyan",
            )
            layout = Table.grid(expand=True)
            layout.add_row(header)
            layout.add_row(overall)
            layout.add_row(table)
            layout.add_row(footer)
            return layout


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
        time.sleep(0.015)
    console.print(
        Panel.fit(
            "[bold cyan]MEDIA DOWNLOADER + AI TRANSCRIBER[/]\n"
            "[dim green]Wendel Dev // secure terminal v2.0[/]",
            border_style="bright_green",
            padding=(1, 5),
        ),
        justify="center",
    )


def progress_hook(data: dict) -> None:
    if data.get("status") == "downloading":
        downloaded = data.get("downloaded_bytes", 0)
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        percent = (downloaded / total * 100) if total else 0
        console.print(
            f"\r[bright_green]▓[/] [cyan]{percent:5.1f}%[/]  "
            f"[dim]{data.get('_speed_str', '--')} • ETA {data.get('_eta_str', '--')}[/]",
            end="",
        )
    elif data.get("status") == "finished":
        console.print("\n[bold green]✓ Download concluído. Processando arquivo...[/]")


def choose_format() -> str:
    console.print("\n[bold green][01][/] MP4  [dim]vídeo[/]")
    console.print("[bold magenta][02][/] MP3  [dim]somente áudio[/]")
    choice = Prompt.ask("\n[cyan]Selecione o formato[/]", choices=["1", "2", "01", "02"])
    return "mp4" if choice in {"1", "01"} else "mp3"


def ask_youtube_url() -> str:
    while True:
        url = Prompt.ask("\n[bold cyan]Cole o link do vídeo do YouTube[/]").strip()
        if YOUTUBE_URL.match(url):
            return url
        console.print("[bold red]✗ Link inválido. Cole uma URL válida do YouTube.[/]")


def download(url: str, media_format: str, on_progress=None) -> Path:
    DOWNLOADS.mkdir(exist_ok=True)
    before = set(DOWNLOADS.iterdir())
    common = {
        "outtmpl": str(DOWNLOADS / "%(title).180B [%(id)s].%(ext)s"),
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "progress_hooks": [on_progress or progress_hook],
        "noplaylist": True,
        "windowsfilenames": sys.platform == "win32",
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
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
        }

    with YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)

    created = [path for path in DOWNLOADS.iterdir() if path not in before and path.is_file()]
    if not created:
        raise RuntimeError("Não foi possível localizar o arquivo baixado.")
    return max(created, key=lambda path: path.stat().st_mtime)


def select_local_media() -> Path:
    selected = ""
    try:
        from tkinter import Tk, filedialog

        window = Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title="Selecione um áudio ou vídeo",
            filetypes=[("Áudio e vídeo", "*.mp3 *.mp4 *.mpeg *.mpga *.m4a *.wav *.webm *.ogg *.flac")],
        )
        window.destroy()
    except Exception:
        pass
    if not selected:
        selected = Prompt.ask("[cyan]Digite o caminho completo do arquivo[/]").strip(' "')
    path = Path(selected).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_MEDIA:
        raise ValueError("Arquivo inexistente ou formato não suportado.")
    return path


def select_local_media_batch() -> list[Path]:
    selected: tuple[str, ...] = ()
    try:
        from tkinter import Tk, filedialog

        window = Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        selected = filedialog.askopenfilenames(
            title="Selecione todos os áudios e vídeos",
            filetypes=[("Áudio e vídeo", "*.mp3 *.mp4 *.mpeg *.mpga *.m4a *.wav *.webm *.ogg *.flac")],
        )
        window.destroy()
    except Exception:
        pass
    if not selected:
        typed = Prompt.ask(
            "[cyan]Digite os caminhos completos separados por ponto e vírgula[/]"
        )
        selected = tuple(item.strip(' "') for item in typed.split(";") if item.strip())
    paths = [Path(item).expanduser().resolve() for item in selected]
    invalid = [path for path in paths if not path.is_file() or path.suffix.lower() not in SUPPORTED_MEDIA]
    if not paths:
        raise ValueError("Nenhum arquivo foi selecionado.")
    if invalid:
        raise ValueError(f"Arquivo inválido ou não suportado: {invalid[0]}")
    return paths


def get_openai_client(*, interactive: bool = True) -> OpenAI:
    load_dotenv(ENV_FILE)
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        if not interactive:
            raise ValueError("OPENAI_API_KEY não configurada. Defina no painel ou no arquivo .env.")
        console.print("\n[yellow]A chave será digitada de forma oculta e nunca aparecerá no terminal.[/]")
        key = Prompt.ask("[cyan]OPENAI_API_KEY[/]", password=True).strip()
        if not key.startswith("sk-"):
            raise ValueError("A chave da OpenAI parece inválida.")
        if Confirm.ask("Salvar a chave neste computador para os próximos usos?", default=True):
            ENV_FILE.write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
    return OpenAI(api_key=key)


def split_media(source: Path, target_dir: Path) -> list[Path]:
    output_pattern = target_dir / "parte_%03d.mp3"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        "-f", "segment", "-segment_time", "1200", "-reset_timestamps", "1",
        str(output_pattern),
    ]
    subprocess.run(command, check=True)
    parts = sorted(target_dir.glob("parte_*.mp3"))
    if not parts:
        raise RuntimeError("Não foi possível preparar o áudio para transcrição.")
    return parts


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def translate_ptbr(client: OpenAI, text: str) -> str:
    response = call_with_retry(
        client.responses.create,
        model="gpt-5-mini",
        instructions=(
            "Traduza o texto para português brasileiro natural e fiel. Preserve nomes, marcas, "
            "números e parágrafos. Retorne somente a tradução, sem comentários."
        ),
        input=text,
    )
    return response.output_text.strip()


def call_with_retry(function, **kwargs):
    for attempt in range(4):
        try:
            if attempt and hasattr(kwargs.get("file"), "seek"):
                kwargs["file"].seek(0)
            return function(**kwargs)
        except (RateLimitError, APIConnectionError, InternalServerError):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Falha inesperada ao chamar a API.")


def safe_theme_name(client: OpenAI, transcript: str) -> str:
    response = call_with_retry(
        client.responses.create,
        model="gpt-5.6-luna",
        reasoning={"effort": "none"},
        max_output_tokens=40,
        instructions=(
            "Identifique o tema central da transcrição e responda somente com um título curto "
            "em português do Brasil, entre 3 e 7 palavras. Não use aspas, pontuação final, "
            "prefixos, emojis ou explicações."
        ),
        input=transcript[:12_000],
    )
    name = response.output_text.strip().strip('"\'')
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" .")[:90].strip()
    return name or "Transcrição sem tema identificado"


def unique_output_paths(theme: str) -> tuple[Path, Path]:
    with OUTPUT_NAME_LOCK:
        suffix = 1
        while True:
            label = theme if suffix == 1 else f"{theme} ({suffix})"
            folder = TRANSCRIPTS / label
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=False)
                txt = folder / f"{label}.txt"
                srt = folder / f"{label}.srt"
                txt.touch(exist_ok=False)
                srt.touch(exist_ok=False)
                return txt, srt
            suffix += 1


def generate_creative_metadata(client: OpenAI, transcript_path: Path) -> Path:
    transcript = transcript_path.read_text(encoding="utf-8")
    instructions = """
Crie metadados em português do Brasil para um criativo de vídeo usando somente a transcrição.
Não invente produto, preço, prova, resultado, promessa, link, hashtag ou chamada para ação que
não esteja sustentada pelo conteúdo. Entregue exatamente duas seções em Markdown:

# Título
Um único título claro, específico e atraente, sem clickbait enganoso, com no máximo 100 caracteres.

# Descrição
Uma descrição fiel e natural, entre 2 e 4 parágrafos, explicando o tema, os pontos principais e
o valor do conteúdo. Não acrescente estratégia de campanha, público, segmentação ou testes.
""".strip()

    with console.status("[green]Criando título e descrição do criativo...[/]"):
        response = call_with_retry(
            client.responses.create,
            model="gpt-5.6-luna",
            reasoning={"effort": "none"},
            instructions=instructions,
            input=transcript,
        )
    output = transcript_path.parent / f"{transcript_path.stem}-titulo-e-descricao.md"
    output.write_text(response.output_text.strip() + "\n", encoding="utf-8")
    return output


def approximate_cues(text: str, start: float, duration: float = 1200) -> list[tuple[float, float, str]]:
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    if not sentences:
        return []
    total_chars = sum(len(item) for item in sentences)
    position = start
    cues = []
    for sentence in sentences:
        span = max(2.0, duration * len(sentence) / total_chars)
        cues.append((position, position + span, sentence))
        position += span
    return cues


def transcribe(
    source: Path,
    translate: bool,
    client: OpenAI | None = None,
    dashboard: TranscriptionDashboard | None = None,
) -> tuple[Path, Path]:
    client = client or get_openai_client()
    TRANSCRIPTS.mkdir(exist_ok=True)
    all_text: list[str] = []
    cues: list[tuple[float, float, str]] = []

    if dashboard:
        dashboard.update(source, "Preparando áudio", 3)
    with tempfile.TemporaryDirectory(prefix="wendel_transcribe_") as temp:
        parts = split_media(source, Path(temp))
        if dashboard:
            dashboard.update(source, f"Áudio dividido em {len(parts)} partes", 8)
        for index, part in enumerate(parts, start=1):
            if dashboard:
                dashboard.update(
                    source,
                    f"IA ouvindo • parte {index}/{len(parts)}",
                    8 + (index - 1) / len(parts) * 72,
                )
            else:
                console.print(f"[green]>[/] Transcrevendo parte {index}/{len(parts)}...")
            with part.open("rb") as audio:
                result = call_with_retry(
                    client.audio.transcriptions.create,
                    model="gpt-4o-mini-transcribe",
                    file=audio,
                    response_format="json",
                    prompt="Transcrição fiel, com pontuação correta. Preserve nomes e termos técnicos.",
                )
            original = result.text.strip()
            if dashboard and translate:
                dashboard.update(
                    source,
                    f"Traduzindo • parte {index}/{len(parts)}",
                    8 + (index - 0.35) / len(parts) * 72,
                )
            final_text = translate_ptbr(client, original) if translate else original
            all_text.append(final_text)

            offset = (index - 1) * 1200
            cues.extend(approximate_cues(final_text, offset))
            if dashboard:
                dashboard.update(
                    source,
                    f"Parte {index}/{len(parts)} concluída",
                    8 + index / len(parts) * 72,
                )

    complete_text = "\n\n".join(all_text)
    if dashboard:
        dashboard.update(source, "Identificando tema central", 88)
    theme = safe_theme_name(client, complete_text)
    if dashboard:
        dashboard.update(source, f"Organizando • {theme}", 94)
    text_path, srt_path = unique_output_paths(theme)
    text_path.write_text(complete_text + "\n", encoding="utf-8")
    srt_lines: list[str] = []
    for number, (start, end, text) in enumerate(cues, start=1):
        srt_lines.extend([str(number), f"{srt_time(start)} --> {srt_time(end)}", text, ""])
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    if dashboard:
        dashboard.update(source, theme, 100, "done")
    return text_path, srt_path


def ask_concurrency() -> int:
    while True:
        value = Prompt.ask(
            "[cyan]Quantos arquivos processar simultaneamente?[/]",
            choices=["1", "2", "3", "4"],
            default="2",
        )
        return int(value)


def transcribe_batch(sources: list[Path], translate: bool, workers: int) -> tuple[list[tuple[Path, Path]], list[tuple[Path, str]]]:
    client = get_openai_client()
    completed: list[tuple[Path, Path]] = []
    failed: list[tuple[Path, str]] = []
    with TranscriptionDashboard(sources) as dashboard:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="transcricao") as executor:
            futures = {
                executor.submit(transcribe, source, translate, client, dashboard): source
                for source in sources
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    txt, srt = future.result()
                    completed.append((txt, srt))
                except Exception as exc:
                    failed.append((source, str(exc)))
                    dashboard.update(source, str(exc)[:80], 100, "error")
    return completed, failed


def show_menu() -> str:
    console.print("\n[bold green][01][/] Baixar do YouTube")
    console.print("[bold cyan][02][/] Transcrever arquivo local com IA")
    console.print("[bold magenta][03][/] Baixar do YouTube e transcrever")
    console.print("[bold yellow][04][/] Criar título e descrição a partir de uma transcrição")
    console.print("[bold bright_blue][05][/] Transcrever vários arquivos ao mesmo tempo")
    return Prompt.ask(
        "\n[cyan]Escolha uma missão[/]",
        choices=["1", "2", "3", "4", "5", "01", "02", "03", "04", "05"],
    )


def select_transcript() -> Path:
    selected = ""
    try:
        from tkinter import Tk, filedialog

        window = Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title="Selecione uma transcrição",
            initialdir=TRANSCRIPTS,
            filetypes=[("Transcrição em texto", "*.txt")],
        )
        window.destroy()
    except Exception:
        pass
    if not selected:
        selected = Prompt.ask("[cyan]Digite o caminho completo da transcrição .txt[/]").strip(' "')
    path = Path(selected).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".txt":
        raise ValueError("Selecione um arquivo de transcrição .txt válido.")
    return path


def main() -> None:
    try:
        intro()
        choice = show_menu().lstrip("0")
        media: Path | None = None
        if choice in {"1", "3"}:
            url = ask_youtube_url()
            media_format = "mp4" if choice == "1" else "mp3"
            if choice == "1":
                media_format = choose_format()
            media = download(url, media_format)
            console.print(f"[bold green]✓ Arquivo salvo:[/] {media}")
        if choice == "2":
            media = select_local_media()
        transcript_path: Path | None = None
        if choice in {"2", "3"} and media:
            translate = Confirm.ask("Traduzir o resultado para português do Brasil?", default=True)
            dashboard = TranscriptionDashboard([media])
            with dashboard:
                try:
                    txt, srt = transcribe(media, translate, dashboard=dashboard)
                except Exception as exc:
                    dashboard.update(media, str(exc)[:80], 100, "error")
                    raise
            transcript_path = txt
            console.print(Panel(
                f"[bold bright_green]✓ TRANSCRIÇÃO CONCLUÍDA[/]\n\n[white]{txt}[/]\n[white]{srt}[/]",
                border_style="green",
            ))
            if Confirm.ask("Deseja criar agora o título e a descrição do criativo?", default=True):
                metadata = generate_creative_metadata(get_openai_client(), transcript_path)
                console.print(Panel(
                    f"[bold bright_green]✓ TÍTULO E DESCRIÇÃO CONCLUÍDOS[/]\n\n[white]{metadata}[/]",
                    border_style="green",
                ))
        if choice == "4":
            transcript_path = select_transcript()
            metadata = generate_creative_metadata(get_openai_client(), transcript_path)
            console.print(Panel(
                f"[bold bright_green]✓ TÍTULO E DESCRIÇÃO CONCLUÍDOS[/]\n\n[white]{metadata}[/]",
                border_style="green",
            ))
        if choice == "5":
            sources = select_local_media_batch()
            console.print(f"[green]✓ {len(sources)} arquivos selecionados.[/]")
            translate = Confirm.ask("Traduzir os resultados para português do Brasil?", default=True)
            workers = ask_concurrency()
            completed, failed = transcribe_batch(sources, translate, workers)
            summary = f"[bold green]Concluídos: {len(completed)}[/]\n[bold red]Falhas: {len(failed)}[/]"
            if completed:
                summary += f"\n\n[dim]Pasta: {TRANSCRIPTS}[/]"
            console.print(Panel(summary, title="LOTE FINALIZADO", border_style="bright_blue"))
    except KeyboardInterrupt:
        console.print("\n[yellow]Operação cancelada pelo usuário.[/]")
    except Exception as exc:
        console.print(Panel(f"[bold red]Falha na operação[/]\n{exc}", border_style="red"))
        sys.exit(1)


def should_start_web() -> bool:
    mode = os.getenv("WENDEL_MODE", "").strip().lower()
    if mode == "cli":
        return False
    if mode == "web":
        return True
    if os.getenv("PORT"):
        return True
    return not sys.stdin.isatty()


def listen_port() -> int:
    raw = os.getenv("PORT") or "8000"
    try:
        port = int(raw)
    except ValueError:
        port = 8000
    return port if 1 <= port <= 65535 else 8000


def run_web() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=listen_port())


# Aegis detecta FastAPI aqui e sobe com `uvicorn main:app` na porta do painel.
from app import app


if __name__ == "__main__":
    if should_start_web():
        run_web()
    else:
        main()
