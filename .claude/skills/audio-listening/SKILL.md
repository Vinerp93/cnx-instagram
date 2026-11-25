---
name: audio-listening
description: "Ouve" o áudio dos Reels e de outros arquivos de vídeo ou áudio do projeto. Transcreve a fala com timestamps (faster-whisper, local, pt-BR) e mede duração, volume (LUFS/pico) e trechos de silêncio. Use quando pedirem para ouvir, transcrever, legendar (.srt), revisar o áudio de um vídeo, comparar o que é falado com a legenda.txt, ou checar se o áudio de um post está ok antes de publicar.
---

# Ouvir áudio (Reels e vídeos)

Claude não ouve arquivos diretamente. Esta skill converte o áudio em texto e números que dá para ler.

## Preparação (uma vez por sessão)

```bash
which ffmpeg ffprobe            # precisam existir
python3 -c "import faster_whisper" 2>/dev/null || pip install -q faster-whisper
```

Na primeira transcrição o modelo é baixado do Hugging Face (`small` tem cerca de 460 MB). Se a rede bloquear, rode com `--no-transcript` para ter só as métricas.

## Uso

```bash
S=.claude/skills/audio-listening/scripts/listen.py
python3 $S pecas/2026-11-25-1800-reels-responder-rapido/video.mp4   # um arquivo
python3 $S pecas                                                     # todos os vídeos
python3 $S pecas --no-transcript                                     # só métricas, rápido
python3 $S <arquivo> --out <pasta>   # grava <post>.transcricao.md e <post>.srt
```

Opções: `--model tiny|base|small|medium|large-v3` (padrão `small`; `base` é mais rápido e erra mais), `--lang pt`.

O relatório traz, por arquivo:
- duração, volume integrado (LUFS) e pico (dBTP);
- trechos de silêncio acima de 0,6s;
- tempo de fala, número de palavras e palavras por minuto;
- transcrição com timestamps `[mm:ss.s]`.

## Como ler o resultado

- **Volume:** no Reels, mire em cerca de −14 LUFS e pico abaixo de −1 dBTP. Pico acima de −1 dBTP tende a distorcer depois da compressão do Instagram.
- **Silêncio longo:** o LUFS ignora o silêncio, então um vídeo quase todo mudo ainda pode mostrar um "volume ok". O script avisa quando mais de 50% do vídeo está em silêncio. Nesses casos, confira com o usuário se é proposital.
- **Sem fala detectada:** o áudio é só música ou efeitos. Não invente uma transcrição.
- **Legenda vs. fala:** quando houver fala, compare com a `legenda.txt` da mesma pasta e aponte o que for diferente (números, datas, nomes, promessas).
- Whisper erra nomes próprios e termos técnicos (Meta Ads, CNX, API de Conversões). Marque trechos duvidosos em vez de "corrigir" por conta própria.

## Não faça

- Não grave transcrições dentro de `pecas/` sem que peçam: a pasta é publicada. Use o scratchpad ou a pasta indicada em `--out`.
- Não altere os arquivos de vídeo.
