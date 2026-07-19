# Wendel Dev — Media Downloader + AI Transcriber

Ferramenta animada para Windows que baixa vídeos do YouTube em **MP4**, extrai **MP3** e transcreve arquivos de áudio/vídeo com a API da OpenAI.

## Recursos

- Download MP4 ou MP3 pelo link do YouTube.
- Seleção de arquivo local por janela do Windows.
- Fluxo de baixar e transcrever automaticamente.
- Transcrição com `gpt-4o-mini-transcribe`.
- Tradução opcional para português do Brasil.
- Divisão automática de arquivos longos em partes.
- Geração de texto `.txt` e legenda `.srt`.
- Chave da API protegida no arquivo local `.env`, ignorado pelo Git.

## Como usar

1. Instale o [Python 3.10+](https://www.python.org/downloads/) e marque **Add Python to PATH**.
2. Crie uma chave em [OpenAI API Keys](https://platform.openai.com/api-keys).
3. Dê dois cliques em `iniciar.bat`.
4. Escolha baixar, transcrever um arquivo local ou fazer os dois.
5. Na primeira transcrição, cole a chave quando o programa pedir. A digitação fica oculta.

Downloads ficam em `downloads`. Textos e legendas ficam em `transcricoes`.

## Segurança

Nunca publique sua chave. O programa pode salvá-la em `.env`, que está listado no `.gitignore`. O arquivo `.env.example` contém apenas um exemplo sem credencial real.

## NeonDB

O NeonDB não é necessário para baixar ou transcrever. Uma versão futura poderá usá-lo para armazenar histórico, títulos e caminhos dos resultados sem guardar a chave da OpenAI.

## Aviso

Use apenas para conteúdo próprio, licenciado ou autorizado. Respeite direitos autorais e os termos dos serviços aplicáveis.
