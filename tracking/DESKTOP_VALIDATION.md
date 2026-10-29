# Validação de desktop e equipamento

## Estado atual

A branch `develop` foi criada e publicada a partir da `main`, no commit `3732575`. Isso cria a base de integração; não integra as features nem substitui testes. Os branches de implementação permanecem separados.

Foi disponibilizado Xvfb localmente, usando pacotes Debian verificados pelo APT, sem alterar dependências do projeto. Em display virtual de 1920×1200, o teste abriu widgets Tk reais e acionou seus callbacks. Foram verificados configuração inicial, seleção do backend de análise, pausa/retomada, reinício/cancelamento, iluminação manual, rejeição de valor inválido e restauração do original. A janela OpenCV real abriu e mostrou a composição lado a lado. Não foram usados mocks de widgets; o provedor de configuração e a interação humana foram automatizados. Arquivos de parâmetros são isolados em diretório temporário.

Resultado: controles aprovados, janela OpenCV aprovada e layout requisitado de 624×915 dentro do display de 1920×1200. Isso é validação de componentes reais em Linux virtual, não de toda a aplicação em Windows nem de ergonomia em qualquer resolução/DPI.

A suíte foi executada novamente: **109 testes aprovados, sem falhas ou skips**. `pip check`, compilação e execução do binário Linux com `--check-runtime` também passaram. A API de Actions continua retornando `Forbidden`; os resultados remotos não foram confirmados.

| Pendência anterior | Situação |
|---|---|
| Criar `develop` | Criada/publicada, sem merge de features |
| Widgets reais da GUI | Tk e OpenCV aprovados em display virtual Linux |
| GUI Windows / aplicação com câmera | Aguardando execução no computador do usuário |
| Testes e build Windows | Aguardando resultados locais ou acesso à CI |
| Webcam física | Não conectada à nuvem; usuário informou disponibilidade no Windows |
| SteamVR/VRChat/headset | Não disponíveis no equipamento informado; pendentes |

## Executar no Windows

Primeiro verifique `py -3.12 --version`. Se essa versão não estiver instalada, instale Python 3.12 pelo distribuidor oficial e repita a verificação antes de criar o ambiente. Python 3.14 não atende à combinação de dependências fixada neste projeto: no teste informado pelo usuário, `mediapipe==0.10.21` não possuía distribuição compatível e a instalação foi interrompida.

Os oito erros de importação reportados nessa tentativa decorreram da ausência das dependências, não de oito testes funcionais executados. `pip check` sem conflitos em um ambiente vazio não confirma instalação completa. PyInstaller/executável ausentes também são consequência dessa instalação interrompida. Não atualizar MediaPipe automaticamente para contornar a falha, pois isso muda a API usada pela aplicação.

Para preservar um ambiente `.venv` criado com outra versão, use um novo `.venv312` e seus executáveis explicitamente. Pare depois da instalação até confirmar que ela terminou com sucesso. O Python 3.14 global pode permanecer instalado.

Use Python 3.12 e Git. Se já clonou o projeto para os testes, preserve suas alterações e atualize para `feature/desktop-validation` com `git fetch origin` e `git switch feature/desktop-validation`. Não use reset/force para apagar alterações locais. Caso contrário, clone em uma pasta nova:

```powershell
git clone --branch feature/desktop-validation https://github.com/FIAP-4SIZ/ComputerVisionCP3.git ComputerVisionCP3-validacao
cd ComputerVisionCP3-validacao
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tracking\requirements-study.txt pyinstaller
cd tracking
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe -m pip check
..\.venv\Scripts\python.exe tools\validate_desktop.py
..\.venv\Scripts\pyinstaller.exe --noconfirm bin\mediapipepose.spec
.\dist\mediapipepose\mediapipepose.exe --check-runtime
.\dist\mediapipepose\mediapipepose.exe
```

Não é necessário alterar a política de execução do PowerShell: os comandos usam diretamente os executáveis do ambiente virtual. Se qualquer etapa falhar, pare nela e informe o comando e erro exatos. O resumo esperado da suíte é `Ran 109 tests` e `OK`; mensagens negativas de câmera/arquivo também podem ser emitidas por cenários de erro controlados nos testes. Para o smoke, procure os resultados `controls`, `opencv_window` e `fits_screen` no JSON final. O smoke abre e fecha janelas automaticamente; ele não acessa a webcam nem o headset.

## Checklist manual da câmera e interface

1. Escolha câmera `0` e backend **Somente análise**. Confirme que abre e que a imagem continua atualizando. Se houver erro, registre-o antes de mudar código; confira também permissão de câmera do Windows e uso por outro aplicativo.
2. Ajuste a rotação para 0 graus, se necessário, e enquadre o corpo inteiro. Confirme landmarks e estados dos trackers com iluminação original.
3. Pause e retome. Confirme que o rastreamento para/retorna sem travamento.
4. Ative lado a lado. Confira original preservado à esquerda e entrada analisada à direita. Compare manual/equalização e restaure o original; não avalie precisão só pela aparência.
5. Oculte um pé. Registre se os demais trackers válidos continuam e se o estado do pé muda. Reenquadre-o e confira recuperação.
6. Execute também um vídeo: confirme progresso, pausa/retomada, reinício, cancelamento e fim sem travar.
7. Encerre e abra a aplicação novamente: a câmera precisa voltar a abrir. Registre eventuais erros de fechamento, layout cortado ou comportamento diferente no executável.

Informe Windows/Python utilizados, resumo dos testes, build/smoke e resultados de cada item acima. Não envie credenciais. Logs de erro são mais úteis do que apenas dizer que não funcionou.

## VR e integração

O teste de envio UDP local e os comandos SteamVR já são cobertos automaticamente, mas não comprovam recepção ou movimento do avatar. Para concluir a validação física, ainda será necessário headset/driver SteamVR ou VRChat OSC configurado: calibrar, verificar identidade/orientação dos trackers, oclusão de um pé, recuperação, pausas e encerramento. Registre se o receptor retém poses antigas; a expiração local não garante desativação remota.

Criar `develop` não resolve essas pendências. **Nenhuma feature foi integrada; aprovação continua bloqueada pelos testes externos que faltam.** Este documento registra execução, não transforma testes não realizados em aprovados.

## Repetir o smoke no Linux

Com um display gráfico disponível ou um Xvfb iniciado:

```bash
cd tracking
DISPLAY=:97 python tools/validate_desktop.py
```

O display `:97` é o utilizado nesta sessão; use o display efetivamente disponível em sua máquina. A ferramenta restaura o diretório de trabalho e não modifica seus arquivos de parâmetros.
