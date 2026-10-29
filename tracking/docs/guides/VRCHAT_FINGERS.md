# Mãos e dedos para avatar VRChat

## Escopo e uso

Ative **Rastrear dedos (OSC requer avatar configurado)** na configuração inicial. A opção é independente de `DEV: Spawn trackers for hands`, que continua significando trackers rígidos do SteamVR. Desligada por padrão, não cria outro detector nem muda o envio corporal. Sem dependências novas: usa `mp.solutions.hands.Hands` do MediaPipe 0.10.21 já instalado.

Para observar só peito/mãos, use **Somente análise**, câmera 0, sem calibrar. Mãos também podem ser detectadas quando Pose não retorna corpo algum. Para controlar o avatar, selecione **VRChat OSC**, endereço/porta do receptor (padrão 127.0.0.1:9000). O envio corporal existente continua ativo se sua validação permitir. Nem quadris nem pernas ocultas são obtidos a partir das mãos. Não há implementação de esqueleto SteamVR nesta feature.

O detector extrai 21 pontos por mão, desenha conexões e mostra cinco flexões de 0 (aberto) a 1 (flexionado). T/I/M/R/L significam polegar, indicador, médio, anelar e mínimo. Essa é uma medida de flexão por dedo, não controle separado de cada articulação ou abertura lateral dos dedos. Uma webcam deve ver os dedos com resolução suficiente: mãos atrás do corpo, fora do quadro ou pequenas não são rastreadas de forma confiável.

## Contrato OSC do avatar

São parâmetros **customizados**, não comandos nativos que controlem automaticamente qualquer avatar. Configure-os no avatar/Animator e confirme seu mapeamento no OSC do VRChat:

| Nome do parâmetro | Tipo | Uso |
|---|---|---|
| `MP_Left_Thumb`, `MP_Right_Thumb` | Float | Flexão do polegar |
| `MP_Left_Index`, `MP_Right_Index` | Float | Indicador |
| `MP_Left_Middle`, `MP_Right_Middle` | Float | Médio |
| `MP_Left_Ring`, `MP_Right_Ring` | Float | Anelar |
| `MP_Left_Little`, `MP_Right_Little` | Float | Mínimo |
| `MP_Left_Tracked`, `MP_Right_Tracked` | Bool | Autoriza aplicação das flexões da mão |

Cada endereço é `/avatar/parameters/` seguido do nome. Exemplo: `/avatar/parameters/MP_Left_Index`, Float 0.7. Crie uma animação aberta e outra fechada por dedo e use seu Float em uma Blend Tree; aplique a camada da mão somente quando seu `Tracked` for verdadeiro. Ajuste máscaras/pesos para não conflitar com gestos dos controles. Recomenda-se validar primeiro com parâmetros locais; sincronizar para outros usuários exige configuração do avatar e orçamento de parâmetros. Ative OSC no VRChat. Mudanças de avatar podem exigir conferir/regenerar a configuração OSC correspondente.

Se perder a detecção, pausar, cancelar, terminar vídeo, reiniciar ou encerrar normalmente, o aplicativo envia `Tracked=false`; não reutiliza a última medição como se fosse atual. Não força os cinco dedos a abrirem: o avatar deve usar a flag para retornar ao seu comportamento padrão. UDP não garante entrega; fechamento forçado ou perda de rede podem impedir a mensagem final. Não foi comprovada recepção/animação em um avatar real nesta nuvem.

## Código e conceitos

- `bin/finger_tracking.py`: detector injetado para testes, validação de 21 pontos finitos, flexão por dedo, desenho e bundles OSC. `HandFrame` preserva os pontos de imagem para análise; os ângulos usam os landmarks espaciais estimados de Hands. Eles não são medições reais de profundidade.
- `bin/mediapipepose.py`: uma inferência Hands opcional por quadro, com o mesmo timestamp da câmera/vídeo; pausa, reinício, encerramento e descarte. Sem histórico de vídeo em memória. O tempo `pose` exibido inclui Pose + Hands + envio dos dedos quando ativados; compare FPS com a opção desligada/ligada no mesmo vídeo.
- `bin/init_gui.py`, `bin/parameters.py`: opção inicial persistida em `params.p`, preservando arquivos antigos sem essa chave.
- Testes em `tests/test_finger_tracking.py` e ferramenta de widgets reais `tools/validate_desktop.py`.

Para cada dedo usamos quatro pontos consecutivos: três segmentos. Normalizamos os segmentos e calculamos duas mudanças de direção usando produto escalar e `acos`. Flexão = min(1, (a+b)/180°), sendo a e b os dois ângulos. Exemplo: 45° + 45° resulta em 0,5; dois ângulos de 0° resultam em 0. Não é um modelo biomecânico: polegar e diferentes tamanhos de mão exigem ajuste do avatar. Segmentos coincidentes e valores inválidos rejeitam a mão inteira naquele quadro. Não se adicionou suavização que esconda movimentos sem primeiro medir jitter e atraso.

Hands recebe imagem selfie, como espera a API de handedness. Quando a imagem do usuário não está espelhada, somente a entrada de Hands é espelhada e as coordenadas são devolvidas ao plano original para desenhar. Verifique esquerda/direita com cada mão isoladamente na sua webcam, pois alguns drivers já espelham a imagem. A pontuação mostrada internamente é de classificação esquerda/direita, não confiança individual de cada ponto. Hands não fornece `visibility` por ponto como Pose.

## Testes e resultados

A partir de `tracking/`, com ambiente Python 3.12 instalado:

```cmd
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe -m pip check
..\.venv\Scripts\python.exe tools\validate_desktop.py
..\.venv\Scripts\pyinstaller.exe --noconfirm bin\mediapipepose.spec
.\dist\mediapipepose\mediapipepose.exe --check-runtime
.\dist\mediapipepose\mediapipepose.exe
```

Escolha o executável do ambiente que você realmente criou; se foi `.venv312`, substitua `.venv`. O `--check-runtime` agora precisa informar Pose **e Hands**.

Validação Linux: **134 testes aprovados, zero skips** (16 novos sobre os 118 da análise parcial), UDP local real, inferência Hands real em quadros vazios, vídeo AVI sequencial com timestamps, build PyInstaller e smoke do executável. Widgets Tk/OpenCV reais aprovados em Xvfb 1920×1200, incluindo a nova opção inicial. Lint/tipagem não estão configurados. A versão Windows anterior passou em 109 testes; isso não aprova automaticamente esta versão.

Ensaio positivo adicional: imagem pública de referência `https://storage.googleapis.com/mediapipe-assets/right_hands.jpg`, SHA-256 `4b5134daa4cb60465535239535f9f74c2842aba3aa5fd30bf04ef5678f93d87f`. Arquivo baixado só para teste, não incorporado ao repositório. Inferência real retornou uma mão direita, 21 pontos, score 0,978; flexões aproximadas 0,099 / 0,376 / 0,256 / 0,133 / 0,118. Isso confirma funcionamento do caminho positivo, não acurácia ou estabilidade em webcam. Não há referência anotada dos ângulos nem comparação de precisão.

Checklist físico: mão esquerda isolada, direita isolada, ambas, abrir/fechar cada dedo, mover devagar/rápido, esconder uma mão, sair do quadro, pausar/retomar, reiniciar vídeo e encerrar. Confirme que só os parâmetros correspondentes mudam e que o avatar deixa de aplicar flexões quando `Tracked=false`. Compare FPS no mesmo vídeo com dedos desligados/ligados. Peito sem mãos visíveis permite apenas análise da parte corporal observada, não controle dos dedos.

## Limitações e apresentação

Novos testes/build Windows, câmera física, iluminação real e integração com avatar permanecem pendentes; merge para develop bloqueado. Não houve troca de API do Pose, nem remoção de funções existentes. Enquadramento parcial é análise de pontos visíveis; calibração de escala/posição corporal em VR continua exigindo informações suficientes do corpo.

Para apresentar: “Mantive Pose para o corpo e usei Hands, da mesma biblioteca, para obter 21 pontos independentes por mão. Calculei mudanças de direção entre segmentos para converter cada dedo em um valor de flexão. Enviei esses valores por OSC para parâmetros de um avatar, distinguindo perda de detecção de uma mão aberta. Testes automatizados validam cálculos e comunicação; o movimento efetivo do avatar exige teste no VRChat.”

Próxima melhoria: calibrar abertura/fechamento por usuário e medir jitter/latência com vídeos anotados, após validar o contrato OSC no avatar. Controle de abdução ou de cada articulação requer um contrato adicional e animações correspondentes.
