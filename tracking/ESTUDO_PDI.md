# Diagnóstico e primeira melhoria — PDI aplicado ao rastreamento VR

## Escopo e fontes

Esta entrega implementa somente a primeira melhoria do plano. Não implementa ainda filtros de imagem, novas suavizações ou rejeição de landmarks.

Foi analisado o projeto `ju1ce/Mediapipe-VR-Fullbody-Tracking`, commit `789f8acd1525d6a2daad79ae82c4925f1e0cbc8c`. Ele foi clonado em `/workspace/Mediapipe-VR-Fullbody-Tracking`; o repositório acadêmico `ComputerVisionCP3`, que continha apenas README, permanece intacto.

Referências:

- [Projeto original](https://github.com/ju1ce/Mediapipe-VR-Fullbody-Tracking/tree/789f8acd1525d6a2daad79ae82c4925f1e0cbc8c).
- [Aula indicada](https://arnaldojr.github.io/cognitivecomputing/aulas/PDI/lab17/mediapipe.html): respondeu HTTP 403 neste ambiente. Consultei o [notebook correspondente no repositório do professor](https://github.com/arnaldojr/cognitivecomputing/blob/b3937428887da4d38a8eb7c760ccbd1969558d0e/material/aulas/PDI/lab17/mediapipe.ipynb) e `mediapipe-multperson.py` no mesmo diretório, obtidos via Git. Não assumi que o HTML inacessível estivesse idêntico ao notebook.
- Código da biblioteca instalada: `mediapipe/python/solutions/pose.py`, versão 0.10.21. Sua implementação limpa o campo `presence` dos resultados; ele não deve ser usado como confiança disponível nesta API.

## 1. Funcionamento atual

```text
init_gui.py → parameters.py → escolha/conexão do backend
                                ↓
helpers.CameraStream: VideoCapture.read() em thread
                                ↓
mediapipepose.py: cópia → rotação/espelho → limite de tamanho → BGR para RGB
                                ↓
mp.solutions.pose.Pose.process(): landmarks da imagem e landmarks world
                                ↓
helpers.mediapipeTo3dpose(): 33 landmarks → esqueleto interno de 29 pontos
                                ↓
inversão de X/Y → rotações Z/X/Y → cálculo das orientações
                                ↓
backends.py: escala + alinhamento → SteamVR ou VRChat OSC
                                ↓
RGB para BGR → desenho do esqueleto → janela OpenCV
```

`init_gui.py` abre Tkinter e salva parâmetros iniciais em `params.p`. `parameters.py` guarda opções de execução e salva ajustes em `saved_params.json`. Execute sempre na mesma pasta para reutilizar esses arquivos. `inference_gui.py` fornece calibração, pausa, espelhamento e suavização. `webui.py` usa Flask para operar parte desses controles remotamente.

A câmera pode ser um índice USB ou uma URL. Há uma thread de captura e um laço de inferência; o projeto usa o quadro mais recente, descartando intermediários quando a câmera é mais rápida. Isso evita acumular uma fila, mas FPS de processamento não equivale necessariamente à taxa da câmera.

O detector é `mp.solutions.pose.Pose`, com `model_complexity` configurável, detecção mínima 0,5, rastreamento mínimo configurável e `smooth_landmarks=True` por padrão. A inferência acompanha uma pessoa, não várias. O padrão é modelo 1, limite de imagem de 640 pixels e captura solicitada de 640×480. A resolução efetiva depende da câmera.

### Coordenadas e keypoints

| Representação | Significado | Uso no projeto |
|---|---|---|
| `pose_landmarks.x/y` | Coordenadas normalizadas pela largura/altura; podem sair do enquadramento | Desenhar sobre a imagem |
| Pixels | `u = x × largura`, `v = y × altura` | Visualização em OpenCV |
| `pose_landmarks.z` | Profundidade relativa estimada, com origem nos quadris; não é distância medida em metros | Não é a entrada dos trackers |
| `pose_world_landmarks` | Coordenadas 3D estimadas em metros, origem no centro dos quadris | Construir o esqueleto interno |
| Coordenadas VR | Esqueleto após inversões de eixos, rotações, escala e translação | Comunicação com os backends |

Exemplo: em imagem de 640×480, `x=0,25`, `y=0,5` corresponde a `(160,240)` pixels. `x` e `y` são proporções, enquanto largura e altura são dimensões da imagem. Se a imagem for redimensionada, use suas novas dimensões para desenhar.

No MediaPipe: ombros 11/12, quadris 23/24, joelhos 25/26, tornozelos 27/28, calcanhares 29/30 e pontas dos pés 31/32. Em cada par, o primeiro índice é o lado esquerdo da pessoa, não necessariamente o lado esquerdo da tela. O espelhamento afeta essa interpretação visual.

O esqueleto interno usa tornozelo direito em 0, direito/ esquerdo dos quadris em 2/3, tornozelo esquerdo em 5, origem pélvica em 6 e média dos ombros em 7. Algumas orientações têm comentários de lateralidade ambíguos; não foram trocadas sem um ensaio de orientação com hardware.

`visibility` estima se o ponto está visível, sem representar erro espacial garantido. A função `mediapipeTo3dpose` copia apenas XYZ e descarta essa informação. `min_tracking_confidence` é um limiar do rastreamento da pose, não um filtro individual de cada tornozelo. O modelo pode prever pontos ocultos: existir um número não significa que o pé foi observado.

**Uma câmera monocular não mede a profundidade real.** As coordenadas world resultam da estimativa do modelo. Oclusões, perspectiva, corpo cortado e ambiguidade entre frente e costas continuam presentes.

### Calibração e comunicação

`InferenceWindow.autocalibrate` usa a média dos tornozelos para corrigir inclinações em Z e X. Com SteamVR, compara a orientação dos pés com a do headset para ajustar Y e estima escala usando altura do headset e extensão vertical do esqueleto. Também há controles manuais.

O backend SteamVR consulta a pose do HMD e transforma o deslocamento HMD→pescoço pela orientação do headset. Alinha o ponto médio dos ombros ao pescoço calculado. Envia posições e quaternions pelo protocolo textual do driver ApriltagTrackers: named pipe no Windows ou socket Unix no Linux. O driver e o SteamVR não fazem parte deste checkout.

O backend OSC usa uma referência fixa para a cabeça, aplica escala e deslocamento, inverte Z e converte quaternions para ângulos de Euler antes de transmitir bundles UDP para `/tracking/trackers/{id}/position` e `/rotation`. IP/porta padrão: 127.0.0.1:9000. Não possui o mesmo retorno da pose do HMD; calibração automática de Y/escala não equivale à do SteamVR. Preview completo e envio de mãos não estão implementados nesse backend.

### Suavização já existente

Há filtragem temporal no próprio MediaPipe. SteamVR recebe `smoothing` e `additional_smoothing`, cuja execução está no driver externo; este repositório não permite auditar sua fórmula. OSC ignora a janela de suavização do driver e já implementa:

`posição_filtrada = s × posição_anterior + (1 − s) × posição_atual`.

`s` é o peso do histórico. Por exemplo, histórico 1,0 m, posição nova 1,2 m e `s=0,7` dão `0,7×1,0 + 0,3×1,2 = 1,06 m`. Um `s` maior reduz variações e aumenta atraso. A suavização depende da taxa de atualização; o valor 1 congela a posição. O histórico OSC começa em zeros e as rotações não recebem a mesma filtragem explícita. Não foi adicionado um segundo filtro.

## 2. Problemas confirmados e prioridades

| Prioridade | Evidência no original | Consequência e proposta |
|---|---|---|
| 1 | “Inference time” inclui conversão geométrica/backend, mas FPS exclui espera, captura e exibição | Medir separadamente e usar o ciclo completo. Implementado nesta etapa |
| 1 | `CameraStream.update` publica o retorno de `read()` antes de conferir sucesso; imagem e sinal de disponibilidade são compartilhados sem sincronização | Pode tentar copiar `None` ou perder a relação entre quadro e metadados. Implementado nesta etapa |
| 2 | XYZ são aceitos sem finitude, visibilidade ou validade geométrica; normalização de vetores pode dividir por zero | Validar pontos usados por cada tracker e rejeitar orientações degeneradas antes de transmitir |
| 2 | Quando a pose inteira desaparece não há atualização; quando só o pé some, a pose prevista ainda pode ser enviada | Definir retenção curta, expiração e indicação visual por tracker; testar recuperação sem saltos |
| 3 | Brilho/contraste dependem da câmera e da sala, sem comparação controlada | Ensaiar pré-processamento opcional e desligado por padrão |
| 4 | Suavização OSC inicia em zero, não tem validação de intervalo na GUI e difere do driver | Estudar o filtro existente e medir compromisso jitter/atraso antes de adicionar outro |

Outras limitações verificadas: dependências sem versões fixas; `bin/requirements.txt` omite python-osc; README sugere Python 3.9, CI fixa 3.10.8; `DummyBackend.updatepose` retorna `None` e faz o laço pular a visualização quando há pose. A captura não tem encerramento coordenado na saída normal e a calibração acessa dados compartilhados com a inferência. Esses itens não foram corrigidos em bloco nesta primeira etapa.

**O que já está correto:** BGR→RGB antes da inferência; retorno para BGR na exibição; limite de resolução mantendo proporção; esqueleto desenhado; backends separados; parâmetros de modelo e filtros existentes. Preservados.

## 3. Plano de quatro melhorias

1. **Medições e captura válida (implementada):** estabelecer uma base verificável antes de tentar melhorar qualidade ou velocidade.
2. **Validação de landmarks (próxima):** preservar `visibility`, checar XYZ finitos e vetores usados nas rotações; indicar quais pontos falham. Escolher prazo máximo de retenção e política por tracker, evitando congelamento indefinido. Não rejeitar grandes movimentos apenas porque são rápidos.
3. **Pré-processamento opcional:** experimentar uma técnica por vez no mesmo vídeo, guardando a imagem original. Comparar iluminação normal, escura e contraluz. Somente adotar quando houver benefício medido para o caso de uso.
4. **Avaliação da suavização atual:** corrigir inicialização/validar parâmetros quando os testes justificarem, comparar perfis ajustáveis e usar média móvel apenas como alternativa experimental, sem empilhar filtros automaticamente.

### Técnicas de PDI que podem ou não ajudar

| Técnica | Quando investigar | Quando pode prejudicar / custo |
|---|---|---|
| Brilho e contraste (`clip(aI+b,0,255)`) | Imagem escura com informação ainda recuperável | Saturação apaga detalhes; não recupera informação perdida; percorre todos os pixels |
| Equalização da luminância em YCrCb | Faixa de intensidade comprimida | Pode amplificar ruído e variar entre quadros; não equalizar R/G/B separadamente, pois altera cores; conversões + histograma |
| Convolução Gaussiana 3×3 | Ruído visível em baixa luz | Borra bordas/pés e mãos pequenos; custo por pixel e vizinhança |
| Redimensionamento, por exemplo 640→480 | CPU limitada | Pode perder pés pequenos e detalhes; o projeto já faz resize, portanto ajustar o limite existente e medir |
| Contornos/morfologia | Experimento separado de máscara/segmentação | Uma silhueta binária não substitui a imagem RGB esperada pela rede; não aplicar automaticamente |
| Pontos de interesse/fluxo óptico | Experimento futuro de movimento entre quadros | Características de textura não são necessariamente articulações; há deriva e oclusões; não substituem landmarks sem avaliação |

Na fórmula de brilho, `I` é a intensidade original, `a` controla contraste, `b` soma brilho e `clip` limita a 0…255. Com `I=80`, `a=1,2`, `b=10`, sai 106. Esta fórmula é uma proposta, não uma alteração já aplicada.

## 4. Primeira melhoria: explicação dos arquivos completos

Todos os arquivos estão disponíveis integralmente no checkout e no pacote de entrega; não há trechos omitidos necessários para executar.

| Arquivo | Alteração e razão |
|---|---|
| `bin/helpers.py` | Cronometra `cap.read()` com `perf_counter`; só publica capturas válidas; `Lock` agrupa imagem, tempo e timestamp; `read_latest()` fornece cópia e consome a disponibilidade sob o mesmo lock |
| `bin/frame_metrics.py` | Novo módulo pequeno: `deque(maxlen=60)` armazena janela limitada; `add()` registra segundos e `summary()` calcula médias e converte para milissegundos |
| `bin/mediapipepose.py` | Usa `read_latest`, separa tempo de pose e transformação/envio, mede ciclo completo e desenha duas linhas de métricas; mostra ausência da pose inteira |
| `requirements-study.txt` | Instalação opcional reproduzível para Python 3.12, mantendo a API antiga e uma única distribuição OpenCV |
| `tests/test_first_improvement.py` | Oito testes de métricas, captura, laço principal e equivalência ao original; usa unittest, sem dependência de testes nova |
| `tools/benchmark_pose.py` | Ensaio offline nos mesmos pixels com/sem métricas; não exige webcam nem janelas |
| `ESTUDO_PDI.md` | Diagnóstico, justificativas, testes, limites e apresentação |

**Por que isso ajuda:** a leitura falha deixa de ser entregue como imagem, e cada medição fica associada ao quadro correto. O cronômetro monotônico `perf_counter` mede durações sem depender de mudanças no relógio do sistema. O lock protege somente a entrega do quadro, não toda a inferência. Não foi alterado o modelo, o pré-processamento, a calibração, o protocolo ou a fórmula dos trackers.

**Métricas na tela:**

- `captura`: duração da chamada OpenCV `read`, incluindo espera do driver/decodificação. Não mede exposição nem latência física total.
- `idade`: tempo entre o fim desse `read` e sua retirada para processamento. Não inclui buffers internos da câmera.
- `pose`: somente `pose.process`.
- `trackers`: conversão geométrica, rotações e chamada ao backend. Em OSC, mede envio local, não recebimento/renderização no VRChat.
- `ciclo`: intervalo entre quadros concluídos, incluindo espera por quadro, pré-processamento, inferência, visualização e eventos. A janela mostra a amostra anterior porque o ciclo atual termina depois de `waitKey`.
- `FPS`: número de ciclos dividido pela soma de suas durações na janela. Com 60 ciclos de média 0,04 segundo, `FPS=60/(60×0,04)=25`. Não é a média dos FPS instantâneos.

Captura e inferência acontecem em paralelo: **não some as médias de captura, idade, pose e trackers para deduzir o ciclo**. Pausa não entra no ciclo do rastreamento. O caminho preexistente de backend que retorna falso continua descartado da amostragem; o backend Dummy deve ser corrigido separadamente antes de usá-lo para avaliar FPS com pose.

**Conceitos da aula:** representação da imagem como matriz, cópia para preservar dados, vídeo quadro a quadro, conversão de cor, keypoints e análise quantitativa de processamento. Esta etapa prepara a avaliação de PDI; não acrescenta um filtro de imagem nem promete aumentar precisão.

## 5. Instalação e execução

O original não fixa a versão histórica de MediaPipe. Nesta máquina foi validado **Python 3.12.14, MediaPipe 0.10.21, OpenCV contrib 4.11.0.86 e NumPy 1.26.4**. A API `mp.solutions.pose` existe nessa combinação. O ambiente anterior com MediaPipe 1.1.1 usa outra API e não deve executar este projeto. A aula atual usa Tasks; isso não obriga migrar este código.

Em uma máquina com desktop, câmera e Python 3.12:

```bash
cd Mediapipe-VR-Fullbody-Tracking
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell, em vez da linha acima:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements-study.txt
python -m pip check
python -m unittest discover -s tests -v
python bin/mediapipepose.py
```

No Linux, Tkinter e bibliotecas de exibição OpenCV precisam estar presentes. Instale os pacotes correspondentes da distribuição, por exemplo `python3-tk`, `libgl1` e `libglib2.0-0` no Debian, se faltarem. Não instale `opencv-python` junto com `opencv-contrib-python`: ambos fornecem `cv2`. O arquivo de estudo substitui a instalação pelas listas antigas; não exige instalar PyInstaller para desenvolver.

Na máquina desta tarefa, o ambiente já está em `/workspace/.venvs/mediapipe-vr-legacy`. Para testes sem GUI:

```bash
cd /workspace/Mediapipe-VR-Fullbody-Tracking
source /workspace/.venvs/mediapipe-vr-legacy/bin/activate
export MPLCONFIGDIR=/workspace/.cache/matplotlib
export XDG_CACHE_HOME=/workspace/.cache
python -m unittest discover -s tests -v
```

Na interface, escolha câmera `0` ou sua URL, selecione o backend, enquadre o corpo inteiro e mantenha parâmetros iguais para comparações. SteamVR exige o driver original e headset; para OSC, configure IP/porta e ative OSC no VRChat. A interface e os protocolos permanecem os do original. Ative **Log frametimes to console** para acompanhar as médias; ESC encerra o programa como antes. Não use o backend Dummy para avaliação nesta versão.

## 6. Testes e resultados

### Automatizados e comparação do código original

`python -m unittest discover -s tests -v`: **8 testes aprovados**, com hardware e GUI substituídos nos testes do laço. O teste de equivalência lê o commit original local e compara entradas do backend no mesmo cenário sintético: **29 posições e 3 quaternions exatamente iguais**. Não prova equivalência de todas as poses nem estabilidade em VR. Esse teste é explicitamente pulado se o commit não estiver disponível, sem contabilizá-lo como aprovado.

Também foi executado `Pose.process` real em imagem preta de 640×480: retorno sem pose, como esperado. Isso verifica carregamento/inferência da biblioteca, não precisão.

| Situação | Original | Primeira melhoria |
|---|---|---|
| Cálculo do FPS | Inverso de inferência + transformação/envio | Ciclos concluídos por tempo total, média de até 60 amostras |
| Falha de `read` | Publica sinal e imagem antes de validar | Não publica `None` nem imagem vazia; libera a captura na falha |
| Entrega entre threads | Sem lock | Imagem e metadados entregues sob o mesmo lock |
| Pose válida da fixture | Entrada original do backend | Exatamente as mesmas posições e orientações |
| Ausência de pose | Sem envio ao backend | Mesmo comportamento e aviso visual |
| BGR/RGB e pixels do detector | Conversão existente | Preservados |

Exemplo **didático, não medição de câmera**: se pose leva 10 ms, trackers 5 ms e o ciclo completo 40 ms, o cálculo antigo anuncia cerca de 66,7 FPS (`1/0,015`), enquanto o novo apresenta 25 FPS (`1/0,04`).

### Benchmark real de vídeo, sem câmera/headset

Foi usado `Jeff.mp4` do material do professor no commit citado, primeiros 60 quadros, reduzidos de 1280×720 para 640×360. O vídeo mostra principalmente tronco e cabeça; não serve para comprovar rastreamento de pés. Cinco chamadas de aquecimento por execução, modelo 1, limiares 0,5, suavização ligada; as duas execuções recebem os mesmos pixels e têm detector próprio. A ordem é sem métricas, depois com métricas.

```bash
python tools/benchmark_pose.py caminho/Jeff.mp4 --frames 60
```

| Medição desta execução | Sem métricas | Com métricas |
|---|---:|---:|
| Inferência média | 42,26 ms | 49,71 ms |
| Ciclo offline RGB + inferência (+ métricas) | 42,69 ms | 52,30 ms |
| Vazão offline | 23,43 quadros/s | 19,12 quadros/s |
| Quadros com pose retornada | 60/60 | 60/60 |

Decodificação média do arquivo: 2,76 ms, realizada antes dos dois ensaios. Custo isolado de adicionar/resumir a janela: aproximadamente **30,33 µs** por chamada em 10.000 repetições. Esse microbenchmark exclui desenho, lock, logging e concorrência. Não representa todo o custo da modificação.

A execução com métricas foi mais lenta, inclusive dentro da inferência não modificada. Uma execução sequencial nesta máquina compartilhada não permite atribuir a diferença toda à instrumentação. Uma rodada exploratória anterior teve tempos menores; portanto não há evidência de ganho de desempenho nem estimativa confiável de regressão em uso real. O objetivo aqui foi corrigir a medição e a entrega dos quadros. **Esses valores não são FPS de câmera, não executam a aplicação VR completa e não medem precisão.**

## 7. Próximas comparações com equipamento

Grave e conserve o vídeo original. Fixe câmera, resolução, modelo, calibração, roupa, fundo e parâmetros de suavização. Compare uma alteração por vez no mesmo arquivo, repita as condições e relate média e dispersão, sem usar o FPS nominal do arquivo como taxa de processamento.

| Condição | Medida recomendada | Estado nesta entrega |
|---|---|---|
| Pessoa parada, corpo inteiro | Desvio padrão XYZ por landmark, taxa de baixa visibilidade | Não medido |
| Movimento lento e rápido | Atraso e acompanhamento, com referência temporal visível | Não medido |
| Pé oculto e reaparecendo | Tempo de perda/recuperação e salto na retomada | Não medido |
| Iluminação normal/escura/contraluz | Mesmos quadros com/sem uma técnica de PDI, visibilidade e custo | Não medido |
| SteamVR/VRChat em funcionamento | Captura, pose, trackers e ciclos completos; inspeção da orientação | Não medido |

Visibilidade alta não é prova de coordenada correta. Para afirmar melhoria de precisão, será necessária uma referência conhecida de posição ou movimento. Sem ela, podemos comparar estabilidade, latência e perdas, explicitando que são medidas diferentes de precisão.

Sem webcam, display e headset nesta nuvem, não foram verificados captura ao vivo, janela real, calibração física, recepção OSC em VRChat ou driver SteamVR. Testes usam mocks somente onde explicitado. Não foram aplicados filtros de imagem, tampouco feita uma migração de API ou treinamento de rede neural.

## 8. Resumo para apresentação acadêmica

“Primeiro analisei o sistema e identifiquei que ele já convertia corretamente BGR para RGB e já possuía suavização. Encontrei uma falha na entrega de quadros inválidos e um indicador de FPS que não incluía o ciclo completo. Corrigi a publicação dos quadros e separei os tempos de captura, inferência e atualização dos trackers. Usei conceitos de matrizes de imagem, vídeo quadro a quadro e avaliação quantitativa. Os testes mostraram que a transformação da pose foi preservada no cenário comparado. Ainda não afirmo maior precisão: a próxima etapa é validar visibilidade e oclusões, e depois testar ajustes de iluminação com os mesmos vídeos.”
