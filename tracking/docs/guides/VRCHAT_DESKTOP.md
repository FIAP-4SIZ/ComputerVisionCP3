# VRChat Steam no Windows, sem headset

Este modo controla uma ação do jogo: levantar os dois braços envia um pulo por OSC. Não precisa Unity, avatar próprio ou headset. Não transforma a webcam em full body tracking nem anima automaticamente cada dedo. O mundo precisa permitir pulo. A tecla Espaço deve funcionar no mesmo mundo antes do teste.

## 1. Abrir o VRChat

1. Inicie VRChat pela Steam em **modo desktop / não VR**. Não abra SteamVR.
2. Entre em um mundo onde seja possível pular e confirme o pulo com Espaço.
3. Abra o menu de ação (normalmente tecla R no desktop), procure **Options → OSC → Enabled** e ative OSC. Os nomes/posição podem variar conforme o idioma e a versão do cliente.
4. Feche menus e o campo de chat antes de testar. Mantenha inicialmente as configurações padrão de OSC: entrada UDP na porta 9000. Se personalizou a porta, use a mesma no aplicativo.

## 2. Testar comunicação sem câmera

Com a aplicação de rastreamento fechada, execute de `tracking/`, no ambiente Python 3.12 já instalado:

```cmd
..\.venv\Scripts\python.exe tools\vrchat_desktop_check.py --send
```

Se seu ambiente é `.venv312`, substitua `.venv`. O comando envia `/input/Jump` com **inteiros** 0, 1 e 0; segura por 150 ms e libera inclusive se interrompido. Observe o personagem: ele deve pular. A mensagem “enviado” não confirma recepção UDP.

Se não pular: confira se Espaço funciona, OSC está ativado, VRChat está aberto e se IP/porta coincidem. No mesmo computador use **127.0.0.1:9000**; não use endereço da webcam nem a porta de saída 9001. Confira permissões do aplicativo no Firewall do Windows sem desativar o firewall. Se sua versão oferece depuração/monitor OSC, confira a chegada de `/input/Jump`. Não avance ao MediaPipe até este teste funcionar.

## 3. Conectar movimentos da câmera

Execute `python run.py` usando o Python do ambiente, ou o executável reconstruído a partir deste branch:

1. Entrada **Câmera ao vivo**, câmera **0**.
2. Destino **VRChat desktop (pulo)**, IP **127.0.0.1**, porta **9000**.
3. Deixe **Rastrear dedos** desligado neste primeiro teste; não precisa de calibração VR.
4. **Salvar e continuar**. Posicione ombros, cotovelos e pulsos dentro da imagem. Pernas/quadris podem ficar fora.
5. Levante os dois pulsos acima dos ombros por pelo menos três quadros. O aplicativo envia um pulo. Abaixe os dois braços antes de repetir.
6. Confira pausa/retomada, perda dos pontos e encerramento: liberam o botão. A câmera precisa continuar processando para temporizar o pulso; falhas de rede/encerramento forçado não garantem entrega da liberação. Em problemas, pressione e solte Espaço e feche o emissor.

O aplicativo pode continuar vendo a câmera enquanto VRChat é usado; não mantenha dois emissores disputando o mesmo comando. Vídeos também passam pelo mesmo detector e podem disparar pulos: só selecione este destino quando quiser controlar o jogo.

## O que cada destino faz

| Destino | Uso |
|---|---|
| Somente análise | Visualizar sem enviar comandos |
| VRChat desktop (pulo) | Comando de jogo sem headset ou avatar editável |
| VRChat OSC | Trackers corporais e parâmetros customizados de dedos; não equivale a controle corporal desktop |
| SteamVR | Driver/headset; não é necessário neste cenário |

Os dez parâmetros `MP_Left_*`/`MP_Right_*` dos dedos não são entradas universais do jogo. Precisam de um avatar configurado no Unity. Não espere que funcionem num avatar público qualquer. Para futuramente configurar dedos de um avatar próprio, use o guia VRCHAT_FINGERS: animações humanoides de dedos pertencem à camada **Gesture**, com máscaras e controle de tracking apropriados, preservando o controller existente; não apenas criar nomes de parâmetros no menu.

## Implementação e evidências

`bin/desktop_osc.py` verifica pontos observados 11–16, confirma três quadros e só rearma depois de abaixar os braços. O limiar de elevação é 0,08 da altura normalizada; o de retorno 0,02 cria histerese. A 30 FPS, três quadros acrescentam cerca de 67 ms de confirmação. Não há medição de profundidade nem exigência de pernas. `bin/mediapipepose.py` usa o mesmo fluxo de câmera/vídeo e libera em pausas/saída. A interface mantém os destinos anteriores.

Testes cobrem confirmação, pulso único, rearme, pontos ausentes/fora do quadro, pausa, integração com laço da câmera e pacotes UDP reais. **O VRChat não está instalado na nuvem: pulo observado no cliente ainda precisa ser confirmado pelo usuário.** Nenhum merge para develop até as verificações obrigatórias. Não há alegação de precisão.

Referência oficial do comando e seu tipo: [OSC Input](https://github.com/vrchat-community/osc/blob/main/docs/Input.md). Referência das camadas de animação: [Playable Layers](https://github.com/vrchat-community/creator-docs/blob/main/Docs/docs/avatars/playable-layers.md). Consultadas pelo repositório oficial; o site de documentação retornou HTTP 403 nesta sessão.


Validação da entrega: 164 testes locais (8 novos), pip check, compilação, GUI real em Xvfb 1280×720 e build/runtime Linux aprovados. A primeira CI Windows identificou um caractere de seta incompatível com console CP1252 na prévia do teste; substituído por `->`, com teste de regressão nessa codificação. Conferir a CI do commit final no PR #11. Não considerar essa correção como comprovação do pulo no cliente.

## Câmera falhou / Tcl_AsyncDelete no Windows

O erro relatado pelo usuário revelou captura sem quadro e uso da interface Tk numa thread secundária. A correção está em `feature/desktop-capture-lifecycle`: valida o primeiro quadro antes de abrir GUI/MediaPipe, tenta aquecimento limitado e DirectShow no mesmo ID no Windows, e mantém todo Tk na thread principal com encerramento coordenado. Calibração solicitada pela interface web agora é agendada para a thread principal.

Feche outras instâncias do aplicativo, OBS, navegador ou programa que esteja usando a webcam. No Windows, confira Configurações → Privacidade e segurança → Câmera → acesso para aplicativos da área de trabalho. Atualize para o branch da correção e execute de tracking:

```cmd
..\.venv\Scripts\python.exe tools\check_camera.py --camera 0
```

A ferramenta deve receber dez quadros e liberar a câmera. Se falhar e houver outro dispositivo, repita explicitamente com `--camera 1`; não há varredura automática de webcams. Ela usa a resolução padrão do dispositivo para separar problemas de captura de uma resolução configurada. Se passar, abra `run.py` e escolha a mesma câmera. Um driver pode bloquear chamadas nativas; retries limitados não eliminam toda falha de hardware.

Validação local da correção: 172 testes, incluindo inicialização sem quadro, fallback Windows no mesmo ID, aquecimento, liberação, impedimento de Tk em thread secundária, erros antes da GUI/modelo e encerramento do laço. Repetir CI Linux/Windows e captura real no equipamento do usuário antes de aprovar integração.
