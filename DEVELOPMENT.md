# Fluxo de desenvolvimento

Na inspeção inicial havia somente `origin/main`, três commits descritivos em inglês e nenhum guia de branches. O fluxo adotado para esta entrega é:

- `feature/video-input`: importação da base necessária e entrada por vídeo.
- `feature/pose-validation`: validação das poses, dependente da funcionalidade de vídeo.
- `feature/per-tracker-validation`: seleção e expiração locais por tracker, dependente da validação de poses.
- `feature/lighting-comparison`: ajustes opcionais de iluminação e comparação do mesmo vídeo, dependente dos trackers independentes.
- Commits pequenos, descritivos em inglês; sem push para o repositório de referência.
- `develop` só será criada/atualizada e receberá merge quando todas as verificações obrigatórias estiverem aprovadas. Ausência de infraestrutura não conta como aprovação.
- Não editar diretamente `main` ou `develop`; não publicar merges com testes pendentes.

## Origem e arquitetura

O projeto acadêmico continha apenas o README. `tracking/` importa a aplicação MIT de `ju1ce/Mediapipe-VR-Fullbody-Tracking`, commit `789f8acd1525d6a2daad79ae82c4925f1e0cbc8c`, incluindo a licença e as melhorias de medição da etapa anterior. O README acadêmico original foi preservado. `tracking/tests/fixtures/original_mediapipepose.py` preserva o laço original para testes de regressão, sem depender do histórico de outro repositório.

Execute comandos da aplicação a partir de `tracking/`. `bin/` contém GUI, fontes de imagem, transformação da pose e backends. A GUI usa Tkinter; inferência e desenho usam a mesma API `mp.solutions.pose`. A câmera mantém o último quadro; o vídeo deve ser sequencial e nunca usar essa política de descarte.

## Verificações

Com Python 3.12, instale `tracking/requirements-study.txt`. A partir de `tracking/`:

```bash
python -m pip check
python -m unittest discover -s tests -v
python -m compileall -q bin tools tests
```

Não havia lint nem tipagem configurados no repositório acadêmico ou na aplicação original. A aplicação original possui especificações PyInstaller para Linux e Windows, que devem ser verificadas antes de aprovar sua integração. O antigo `bin/tests/pipetest.py` é um experimento manual de named pipes para SteamVR, com `assert 0` incondicional, e não uma suíte automatizada aprovada. Testes com hardware e empacotamento Windows exigem ambientes apropriados; qualquer pendência deve ser relatada e bloqueia o merge.
