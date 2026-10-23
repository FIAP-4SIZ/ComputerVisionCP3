# Análise por câmera ou arquivo

## Escopo e critérios

A aplicação desktop mantém OpenCV, `mp.solutions.pose` e o pipeline de transformação/saída do projeto original. A interface oferece câmera e seleção local de arquivo (não um servidor de uploads). O objetivo é analisar vídeos sem exigir câmera ou headset. O backend **Somente análise** desenha os landmarks sem enviar trackers; SteamVR e OSC continuam selecionáveis.

Critérios: quadros na ordem, timestamps monotônicos, nenhuma perda intencional de quadros de arquivo, memória independente da duração do vídeo, controles de pausa/retomada/reinício/cancelamento, EOF sem travamento, erros reportados e recursos liberados. A câmera continua usando o quadro mais recente, adequado ao tempo real.

## Executar

Na raiz de `ComputerVisionCP3`:

```bash
python -m venv .venv
# Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r tracking/requirements-study.txt
cd tracking
python bin/mediapipepose.py
```

Escolha **Arquivo de vídeo → Selecionar vídeo...**. A seleção configura **Somente análise** por padrão; troque o backend se precisar transmitir à VR. **Save and Continue** inicia a reprodução/análise. A janela mostra vídeo, esqueleto quando detectado, métricas e estado/quadro/percentual/tempo do arquivo. A GUI fornece pausa, retomar, reiniciar e cancelar. Após fim ou cancelamento, reiniciar reabre o mesmo arquivo e limpa os históricos do MediaPipe e do backend OSC. Para escolher outro arquivo, encerre e abra o aplicativo.

Formatos aceitos: MP4, AVI, MOV, MKV, WEBM, M4V, MPG, MPEG, sujeitos aos codecs disponíveis no OpenCV. Extensão aceita não garante que o conteúdo seja decodificável. Arquivo inexistente, codec indisponível, FPS inválido, arquivo vazio e quadro corrompido são tratados como erros. Sem pessoa detectada, o quadro é exibido com aviso e nenhum tracker é inventado.

## Decisões de implementação

- `bin/video_source.py`: máquina de estados ready/running/paused/completed/cancelled/error. Usa leitura síncrona de um quadro por vez e mantém no máximo um quadro pendente para o agendamento. Não usa a thread da câmera, que descartaria frames.
- Timestamps vêm de `CAP_PROP_POS_MSEC`. Se forem inválidos, repetidos ou regressivos, estima-se o próximo tempo pelo índice/FPS, assegurando crescimento. FPS inválido bloqueia o arquivo, evitando inventar velocidade de reprodução. Arquivos de taxa variável dependem dos timestamps disponibilizados pelo decodificador.
- O relógio monotônico agenda a reprodução; atraso de inferência deixa a reprodução mais lenta, mas não elimina frames. Pausa congela a posição e desloca a referência do relógio ao retomar.
- `params.frame_timestamp_ms` e `params.frame_index` associam a pose ao quadro do arquivo. Não se altera o protocolo dos backends VR. A API legada `Pose.process` não recebe timestamp externo; sua filtragem interna usa o comportamento da própria biblioteca. O timestamp do arquivo permanece disponível na aplicação, sem fingir que a API o recebeu.
- `mediapipepose.py` escolhe apenas a fonte: cor, tamanho, detector, conversão geométrica, desenho e backend são compartilhados. `finally` libera fonte/detector/backend/janelas, inclusive na falha.
- `helpers.CameraStream.close` encerra a thread com espera limitada e libera a câmera. Drivers que bloqueiam indefinidamente uma chamada nativa ainda dependem do comportamento do dispositivo.
- `DummyBackend.updatepose` agora retorna sucesso, permitindo visualizar uma pose sem infraestrutura VR; antes ele pulava o desenho quando havia detecção.
- As specs PyInstaller agora resolvem o código/modelos no ambiente ativo, incluem templates e bibliotecas Tcl/Tk quando o Python standalone as mantém fora do sistema.

O decoder nem sempre distingue fim normal de arquivo truncado. Quando o número de quadros é conhecido e a leitura termina antes dele, o aplicativo reporta truncamento; metadados incorretos podem gerar esse aviso. Arquivos sem contagem conhecida mostram progresso por quadro/tempo, sem percentual fictício.

## Testar e integrar

```bash
cd tracking
python -m unittest discover -s tests -v
python -m pip check
python -m compileall -q bin tests tools
git diff --check
python -m pip install pyinstaller
pyinstaller --noconfirm bin/mediapipepose_linux.spec
./dist/mediapipepose/mediapipepose --check-runtime
```

No Windows use `bin/mediapipepose.spec` e `dist/mediapipepose/mediapipepose.exe --check-runtime`. `.github/workflows/quality.yml`, na raiz do repositório, configura ambas as plataformas. O workflow antigo dentro de `tracking/.github/` é referência histórica, não é executado pelo GitHub.

Testes incluem mocks do decodificador e GUI, arquivo AVI gerado e decodificado de verdade e o laço principal com inferência MediaPipe real. A fixture sintética da regressão verifica poses detectadas; os vídeos gerados verificam ausência de pessoa. Eles não comprovam precisão corporal nem validação física em SteamVR/VRChat. O ensaio com vídeo corporal real deve ser relatado separadamente, sem tratar mocks como medições de precisão.

Esta feature só pode ser integrada quando os testes e os builds/smokes Linux e Windows estiverem aprovados. Desktop real, webcam e VR permanecem testes manuais pendentes se não houver equipamento; não declarar integração aprovada nessas condições. Nenhuma atualização de `main` está autorizada por este fluxo.
