# Wendel Dev — YouTube Downloader

Downloader de vídeos do YouTube com interface animada no terminal. Salva vídeo em **MP4** ou extrai áudio em **MP3 (320 kbps)**.

## Como usar no Windows

1. Instale o [Python 3.10+](https://www.python.org/downloads/) e marque a opção **Add Python to PATH**.
2. Dê dois cliques em `iniciar.bat`.
3. Cole o link do vídeo e escolha MP4 ou MP3.
4. O arquivo ficará na pasta `downloads`.

Na primeira execução, o script cria um ambiente virtual e instala automaticamente as dependências. O FFmpeg também é obtido pela dependência `imageio-ffmpeg`.

O programa funciona sem configuração adicional. Ter o [Node.js](https://nodejs.org/) instalado é opcional, mas pode ajudar o `yt-dlp` a disponibilizar todos os formatos quando o YouTube exige desafios JavaScript.

## Aviso

Use esta ferramenta apenas para baixar conteúdo próprio, licenciado ou cuja autorização de download você possua. Respeite direitos autorais e os termos do serviço aplicáveis.

## Tecnologias

- Python
- yt-dlp
- Rich
- FFmpeg
