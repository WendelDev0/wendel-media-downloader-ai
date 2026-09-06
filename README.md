# Wendel Dev — Media Downloader + AI Transcriber

Ferramenta para baixar vídeos do YouTube em **MP4**, extrair **MP3** e transcrever áudio/vídeo com a API da OpenAI. No Windows continua existindo o terminal local. Na VPS, o Aegis Panel sobe a **mesa web**.

## Recursos

- Download MP4 ou MP3 pelo link do YouTube.
- Seleção de arquivo local por janela do Windows.
- Fluxo de baixar e transcrever automaticamente.
- Transcrição com `gpt-4o-mini-transcribe`.
- Tradução opcional para português do Brasil.
- Divisão automática de arquivos longos em partes.
- Geração de texto `.txt` e legenda `.srt`.
- Geração opcional de um título e uma descrição fiéis ao conteúdo transcrito.
- Seleção de quantos áudios e vídeos você quiser em um único lote.
- Até quatro transcrições simultâneas, com falhas isoladas e novas tentativas automáticas.
- Nomes automáticos baseados no tema central de cada conteúdo.
- Dashboard animado premium com progresso global, etapa por arquivo, cronômetro e status ao vivo.
- Uma pasta própria para cada transcrição, nomeada conforme o tema central.
- Chave da API protegida no arquivo local `.env`, ignorado pelo Git.

## Como usar

1. Instale o [Python 3.10+](https://www.python.org/downloads/) e marque **Add Python to PATH**.
2. Crie uma chave em [OpenAI API Keys](https://platform.openai.com/api-keys).
3. Dê dois cliques em `iniciar.bat`.
4. Escolha baixar, transcrever um arquivo local ou fazer os dois.
5. Na primeira transcrição, cole a chave quando o programa pedir. A digitação fica oculta.
6. Após transcrever, confirme a criação automática do título e da descrição do criativo.

Downloads ficam em `downloads`. Cada trabalho recebe uma pasta em `transcricoes/Nome do Tema/`, contendo o texto, a legenda e o arquivo de título e descrição quando ele for gerado.

## Hospedar no Aegis Panel

O painel precisa de um processo HTTP. Este repositório já tem `Dockerfile`, `aegis.toml` e `/health`.

1. Envie o código para o GitHub (sem o arquivo `.env`).
2. No Aegis, crie um app com origem **git** e este repositório.
3. Porta interna: **8000**.
4. Variáveis de ambiente:
   - `OPENAI_API_KEY` — obrigatória para transcrever
   - `APP_PASSWORD` — senha da mesa no navegador
   - `APP_SECRET` — opcional, assina o cookie de sessão
   - `WENDEL_MODE=web`
5. Volume persistente em `downloads` e `transcricoes`, se o painel pedir.
6. Aponte o domínio. O Caddy cuida do HTTPS.

Se o container não tiver teclado, `python main.py` também sobe a web sozinho. Não use mais um app com `customtkinter`/Tk no Aegis: a imagem Linux não tem `libtk8.6.so` e o fallback de `input()` quebra com `EOFError`.

Para testar local: `iniciar-web.bat` ou `python -m uvicorn app:app --host 127.0.0.1 --port 8000`.

## Gerar aplicativo executável

1. Execute `iniciar.bat` pelo menos uma vez.
2. Dê dois cliques em `build_exe.bat`.
3. Aguarde a compilação terminar.
4. Compartilhe o arquivo `dist/WendelDev-AI-Windows.zip`.

Quem receber deve extrair o ZIP inteiro e abrir `WendelDev-AI.exe`. Não é necessário instalar Python. Downloads, transcrições e a configuração local da API ficam ao lado do executável.

Cada usuário precisa informar sua própria `OPENAI_API_KEY`. Nunca distribua seu arquivo `.env` dentro do ZIP.

Também é possível usar a opção `04` para gerar um título e uma descrição a partir de uma transcrição `.txt` já existente.

Use a opção `05` para selecionar vários arquivos. Você pode escolher de 1 a 4 processamentos simultâneos; todos os resultados recebem nomes temáticos e ficam na pasta `transcricoes`.

## Skill incluída

O repositório inclui a skill `skills/generate-creative-metadata`, que padroniza a geração de título e descrição a partir de transcrições. Ela pode ser reutilizada por agentes compatíveis com skills do Codex.

## Segurança

Nunca publique sua chave. O programa pode salvá-la em `.env`, que está listado no `.gitignore`. O arquivo `.env.example` contém apenas um exemplo sem credencial real.

## NeonDB

O NeonDB não é necessário para baixar ou transcrever. Uma versão futura poderá usá-lo para armazenar histórico, títulos e caminhos dos resultados sem guardar a chave da OpenAI.

## Aviso

Use apenas para conteúdo próprio, licenciado ou autorizado. Respeite direitos autorais e os termos dos serviços aplicáveis.
