from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import imageio_ffmpeg
from dotenv import load_dotenv
from openai import OpenAI
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.text import Text
from yt_dlp import YoutubeDL


console = Console()
ROOT = Path(__file__).resolve().parent
DOWNLOADS = ROOT / "downloads"
TRANSCRIPTS = ROOT / "transcricoes"
ENV_FILE = ROOT / ".env"
SUPPORTED_MEDIA = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".flac"}
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


def download(url: str, media_format: str) -> Path:
    DOWNLOADS.mkdir(exist_ok=True)
    before = set(DOWNLOADS.iterdir())
    common = {
        "outtmpl": str(DOWNLOADS / "%(title).180B [%(id)s].%(ext)s"),
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
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


def get_openai_client() -> OpenAI:
    load_dotenv(ENV_FILE)
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
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
    response = client.responses.create(
        model="gpt-5-mini",
        instructions=(
            "Traduza o texto para português brasileiro natural e fiel. Preserve nomes, marcas, "
            "números e parágrafos. Retorne somente a tradução, sem comentários."
        ),
        input=text,
    )
    return response.output_text.strip()


def generate_paid_traffic_assets(client: OpenAI, transcript_path: Path) -> Path:
    console.print("\n[bold cyan]CONFIGURAÇÃO DA ESTRATÉGIA DE TRÁFEGO PAGO[/]")
    offer = Prompt.ask("[cyan]Qual produto, serviço ou oferta será anunciada?[/]")
    audience = Prompt.ask(
        "[cyan]Qual é o público-alvo?[/]",
        default="Identificar a partir da transcrição",
    )
    objective = Prompt.ask(
        "[cyan]Objetivo principal[/]",
        choices=["vendas", "leads", "mensagens", "visualizações", "reconhecimento"],
        default="vendas",
    )
    platform = Prompt.ask(
        "[cyan]Plataforma[/]",
        choices=["meta", "google", "tiktok", "multicanal"],
        default="meta",
    )
    transcript = transcript_path.read_text(encoding="utf-8")
    instructions = """
Atue como estrategista sênior de performance e copywriter brasileiro. Transforme a
transcrição fornecida em um pacote executável de tráfego pago, em Markdown e português do
Brasil. Baseie afirmações no conteúdo; não invente provas, números, garantias, depoimentos ou
atributos da oferta. Diferencie fatos da transcrição de hipóteses estratégicas.

Entregue obrigatoriamente:
1. resumo estratégico e promessa central;
2. avatar, dores, desejos, objeções e nível de consciência;
3. 10 títulos de vídeo e 10 headlines de anúncio;
4. descrição completa do vídeo com CTA e palavras-chave;
5. 7 ganchos para os primeiros 3 segundos;
6. 5 ângulos criativos, cada um com conceito visual e roteiro de 30 a 60 segundos;
7. 5 textos principais para anúncios, em versões curta e longa;
8. CTAs e ideias de thumbnail sem clickbait enganoso;
9. estrutura de campanha por público frio, morno e remarketing;
10. hipóteses de segmentação, exclusões e posicionamentos;
11. plano de testes A/B priorizado com variável, hipótese e critério de decisão;
12. métricas para acompanhar em cada etapa do funil;
13. alertas de conformidade e trechos que exigem validação humana.

Use títulos claros, listas práticas e blocos prontos para copiar. Não prometa resultados.
""".strip()
    request = f"""
OFERTA: {offer}
PÚBLICO: {audience}
OBJETIVO: {objective}
PLATAFORMA: {platform}

TRANSCRIÇÃO:
{transcript}
""".strip()

    with console.status("[green]Criando estratégia, copies e criativos com IA...[/]"):
        response = client.responses.create(
            model="gpt-5.6-luna",
            reasoning={"effort": "low"},
            instructions=instructions,
            input=request,
        )
    output = TRANSCRIPTS / f"{transcript_path.stem}-trafego-pago.md"
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


def transcribe(source: Path, translate: bool) -> tuple[Path, Path]:
    client = get_openai_client()
    TRANSCRIPTS.mkdir(exist_ok=True)
    text_path = TRANSCRIPTS / f"{source.stem}.txt"
    srt_path = TRANSCRIPTS / f"{source.stem}.srt"
    all_text: list[str] = []
    cues: list[tuple[float, float, str]] = []

    with tempfile.TemporaryDirectory(prefix="wendel_transcribe_") as temp:
        parts = split_media(source, Path(temp))
        for index, part in enumerate(parts, start=1):
            console.print(f"[green]>[/] Transcrevendo parte {index}/{len(parts)}...")
            with part.open("rb") as audio:
                result = client.audio.transcriptions.create(
                    model="gpt-4o-mini-transcribe",
                    file=audio,
                    response_format="json",
                    prompt="Transcrição fiel, com pontuação correta. Preserve nomes e termos técnicos.",
                )
            original = result.text.strip()
            final_text = translate_ptbr(client, original) if translate else original
            all_text.append(final_text)

            offset = (index - 1) * 1200
            cues.extend(approximate_cues(final_text, offset))

    text_path.write_text("\n\n".join(all_text) + "\n", encoding="utf-8")
    srt_lines: list[str] = []
    for number, (start, end, text) in enumerate(cues, start=1):
        srt_lines.extend([str(number), f"{srt_time(start)} --> {srt_time(end)}", text, ""])
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return text_path, srt_path


def show_menu() -> str:
    console.print("\n[bold green][01][/] Baixar do YouTube")
    console.print("[bold cyan][02][/] Transcrever arquivo local com IA")
    console.print("[bold magenta][03][/] Baixar do YouTube e transcrever")
    console.print("[bold yellow][04][/] Criar estratégia de tráfego a partir de uma transcrição")
    return Prompt.ask(
        "\n[cyan]Escolha uma missão[/]",
        choices=["1", "2", "3", "4", "01", "02", "03", "04"],
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
            txt, srt = transcribe(media, translate)
            transcript_path = txt
            console.print(Panel(
                f"[bold bright_green]✓ TRANSCRIÇÃO CONCLUÍDA[/]\n\n[white]{txt}[/]\n[white]{srt}[/]",
                border_style="green",
            ))
            if Confirm.ask("Deseja criar agora o pacote completo para tráfego pago?", default=True):
                strategy = generate_paid_traffic_assets(get_openai_client(), transcript_path)
                console.print(Panel(
                    f"[bold bright_green]✓ ESTRATÉGIA CONCLUÍDA[/]\n\n[white]{strategy}[/]",
                    border_style="green",
                ))
        if choice == "4":
            transcript_path = select_transcript()
            strategy = generate_paid_traffic_assets(get_openai_client(), transcript_path)
            console.print(Panel(
                f"[bold bright_green]✓ ESTRATÉGIA CONCLUÍDA[/]\n\n[white]{strategy}[/]",
                border_style="green",
            ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Operação cancelada pelo usuário.[/]")
    except Exception as exc:
        console.print(Panel(f"[bold red]Falha na operação[/]\n{exc}", border_style="red"))
        sys.exit(1)


if __name__ == "__main__":
    main()
