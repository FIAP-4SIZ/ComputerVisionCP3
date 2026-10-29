# Fluxo de desenvolvimento

Na inspeção inicial havia somente `origin/main`, três commits descritivos em inglês e nenhum guia de branches. O fluxo adotado para esta entrega é:

- `feature/video-input`: importação da base necessária e entrada por vídeo.
- `feature/pose-validation`: validação das poses, dependente da funcionalidade de vídeo.
- `feature/per-tracker-validation`: seleção e expiração locais por tracker, dependente da validação de poses.
- `feature/lighting-comparison`: ajustes opcionais de iluminação e comparação do mesmo vídeo, dependente dos trackers independentes.
- `feature/desktop-validation`: smoke de widgets reais e registro das validações de desktop.
- `feature/partial-body-analysis`: observações de enquadramento parcial, dependente da validação desktop.
- `feature/vrchat-fingers`: detecção Hands e flexão por dedo via parâmetros de avatar OSC, dependente da análise parcial.
- `feature/observed-pose-validation`: evidência de imagem para trackers e confirmação geométrica/temporal de mãos.
- `feature/portuguese-ui`: telas em português com rolagem.
- `feature/repository-organization`: documentação, entradas reproduzíveis e revisão no GitHub.
- Commits pequenos, descritivos em inglês; sem push para o repositório de referência.
- `develop` foi criada, por autorização explícita do usuário, a partir de `main`, sem integrar features. Merges de features continuam condicionados a todas as verificações obrigatórias aprovadas. Ausência de infraestrutura não conta como aprovação.
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

Não havia lint nem tipagem configurados no repositório acadêmico ou na aplicação original. A aplicação original possui especificações PyInstaller para Linux e Windows, que devem ser verificadas antes de aprovar sua integração. O experimento `tracking/examples/steamvr_pipe_experiment.py` (antigo `bin/tests/pipetest.py`) é um experimento manual de named pipes para SteamVR, com `assert 0` incondicional, e não uma suíte automatizada aprovada. Testes com hardware e empacotamento Windows exigem ambientes apropriados; qualquer pendência deve ser relatada e bloqueia o merge.

## Dependências entre branches e revisão

As funcionalidades foram desenvolvidas em sequência e ainda não foram integradas. Cada PR deve comparar somente com seu predecessor, usando rascunho enquanto houver testes pendentes. A primeira entrada da cadeia é `feature/video-input` → `develop`; as seguintes usam a feature anterior como base. Depois de integrar uma base com todas as verificações aprovadas, revisar/atualizar a base do PR seguinte. Não executar squash/rebase/force-push que invalide a cadeia sem revisar os commits dependentes.

Main e develop continuam na proposta inicial até a validação obrigatória. Não mudar a branch padrão para uma feature para contornar esse bloqueio. A lista atual de PRs pode ser consultada no GitHub; ausência de teste físico bloqueia a integração mesmo com checks automáticos verdes.

## Organização dos arquivos

Guias em `tracking/docs/guides`, diagnóstico em `tracking/docs/architecture`, relatórios em `tracking/docs/reports` e material original em `tracking/docs/reference`. Código de execução permanece em `tracking/bin` para evitar quebra de imports e empacotamento. O lançador `tracking/run.py` permite executar de qualquer diretório com Python 3.12. Apenas `requirements-study.txt` define as bibliotecas de execução; os outros manifests encaminham para ele.

- `feature/vrchat-desktop-input`: entrada OSC de pulo para VRChat Steam sem headset; dependente da organização. Validação no cliente VRChat permanece obrigatória.

- `feature/desktop-capture-lifecycle`: primeiro quadro validado e ciclo de vida Tk na thread principal; dependente do modo desktop.

- `feature/invalid-tracking-guard`: libera ações sem quadros recentes, bloqueia rearme após perda e valida a publicação de dedos; dependente do ciclo de captura.

- `feature/steamvr-readiness`: diagnóstico somente de leitura e plano de integração corporal/esquelética com HMD virtual; não fornece driver completo.

- `feature/vrchat-documentation-audit`: pesquisa no índice completo oficial, correção das conclusões de compatibilidade e instruções do Selfie Expression; sem alegar nova integração funcional.

- `feature/vrchat-osc-body-hands`: remetente OSC ampliado (trackers corporais opcionais e parâmetros configuráveis dos dedos), dependente da auditoria; validação de IK/Animator no cliente continua obrigatória.

- `feature/camera-rotation-default`: corrige a rotação involuntária de 90° na primeira execução, preservando escolhas salvas; dependente da saída OSC ampliada.

- `feature/steamvr-hand-driver`: driver próprio OpenVR de mãos, protocolo local e expiração no receptor; base para conectar os keypoints MediaPipe ao Skeletal Input, sem identificação falsa de controladores.
