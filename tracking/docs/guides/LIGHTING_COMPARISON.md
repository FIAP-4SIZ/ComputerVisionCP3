# Ajustes opcionais de iluminação e comparação

## Diagnóstico, escopo e fluxo

A aplicação já convertia BGR para RGB e limitava a resolução antes do MediaPipe. Essas etapas foram preservadas. A próxima melhoria prevista era comparar ajustes de iluminação, sem presumir que todos ajudariam e sem alterar o vídeo original.

Branch: `feature/lighting-comparison`, baseada em `feature/per-tracker-validation`, no repositório `FIAP-4SIZ/ComputerVisionCP3`. A funcionalidade oferece três modos exclusivos: original, brilho/contraste manual e equalização da luminância. O padrão continua **original, ajustes desligados**. Não foram adicionados filtros de ruído, CLAHE, redes neurais, modelos ou dependências.

```text
Câmera ou arquivo → orientação/tamanho comuns → original BGR preservado
                                                ├→ comparação visual: painel esquerdo
                                                └→ ajuste escolhido → BGR/RGB → MediaPipe
                                                                      → trackers/desenho
                                                                      → painel direito
```

O arquivo de entrada nunca é aberto para escrita. Na aplicação, a imagem anterior ao ajuste fica separada do resultado; o desenho dos landmarks não a modifica. “Original” na tela significa o quadro após a orientação e o redimensionamento comuns, antes de qualquer ajuste de iluminação.

## Usar na aplicação

Com Python 3.12 e o ambiente virtual ativo:

```bash
python -m pip install -r tracking/requirements-study.txt
cd tracking
python bin/mediapipepose.py
```

Selecione câmera ou arquivo como antes. Na janela de execução:

1. Em **Iluminacao opcional**, escolha **Original**, **Brilho e contraste** ou **Equalizar luminancia**.
2. No modo manual, configure contraste de 0,1 a 3 e brilho de −100 a 100. Esses valores são ignorados nos outros modos; não há empilhamento automático.
3. Marque **Lado a lado** e pressione **Aplicar iluminacao**. O painel esquerdo preserva o original; somente o direito recebe o ajuste, os landmarks e as métricas.
4. Use **Restaurar original** para voltar ao modo desligado e aos parâmetros neutros.

Nos campos numéricos, use ponto decimal, como `1.2`.

**A comparação visual não executa o detector duas vezes.** “Original (sem inferencia)” não significa que a detecção falhou à esquerda: aquele painel serve apenas para comparar pixels. Para comparar detecções quantitativamente, utilize a ferramenta offline abaixo.

As mudanças se aplicam aos próximos quadros. Em vídeo pausado/encerrado, o último quadro mantém seu ajuste e rótulo de origem; retome ou reinicie para analisar com a configuração nova. Na pausa de câmera, a imagem pode ser comparada sem executar novas inferências, preservando a pausa do rastreamento.

Quando o ajuste efetivo muda, o detector, os históricos locais dos trackers e a janela de métricas são reiniciados para não misturar resultados de entradas diferentes. Apenas ativar/desativar a visualização lado a lado não reinicia o modelo. O histórico interno do driver SteamVR não é controlado por esta opção. O prazo de expiração e os demais controles continuam funcionando.

O tempo **PDI** aparece no cabeçalho da comparação e no log quando **Log frametimes to console** estiver ativo. O custo de compor a visualização entra no ciclo completo/FPS da aplicação. A comparação dobra a largura da imagem exibida e adiciona cópias de tamanho limitado à resolução escolhida.

## Conceitos de PDI e justificativas

### Brilho e contraste manual

É aplicada a fórmula `saida = clip(arredondar(a × I + b), 0, 255)` separadamente a cada canal BGR. `I` é a intensidade original, `a` é o contraste e `b` soma brilho. Com `I=80`, `a=1,2` e `b=20`, a saída é 116. Com `I=220`, sai 284 antes do limite, portanto o valor final é 255 e parte da informação se perde.

Os cálculos usam ponto flutuante antes de limitar/voltar para uint8, evitando overflow. Não se usa valor absoluto: uma intensidade 20 com brilho −50 deve virar 0, e não 30. O custo percorre os pixels e aloca matrizes temporárias do tamanho do quadro.

Pode ajudar quando há informação recuperável em uma imagem escura ou com pouco contraste. Pode prejudicar uma imagem já clara, saturar cores e amplificar ruído. Não recupera detalhes que a câmera já perdeu em regiões pretas/brancas.

### Equalização de histograma

A imagem é convertida de BGR para YCrCb. `Y` representa luminância; `Cr` e `Cb` carregam informação de cor. `equalizeHist` altera apenas Y, depois a imagem volta para BGR. Os canais B/G/R não são equalizados independentemente. Há arredondamento e possível clipping nas conversões; não se promete preservação matemática exata das cores.

Pode ampliar uma faixa de luminância comprimida. Também pode amplificar ruído, exagerar contrastes e variar entre quadros, causando cintilação. Uma imagem constante continua sem detalhes: equalizar não cria informação. O custo inclui conversões de cor, histograma e transformação dos pixels.

Nenhuma das duas técnicas resolve corpo fora do enquadramento, oclusão ou ambiguidade de profundidade monocular. Não há justificativa para aplicar ambas automaticamente ou trocar a API `mp.solutions.pose` neste experimento.

## Comparar o mesmo vídeo de forma controlada

Da pasta `tracking/`:

```bash
python tools/compare_lighting.py caminho/video.mp4 --frames 60 --contrast 1.2 --brightness 20 --output relatorio-novo.json
```

A ferramenta executa original, manual e equalização em passes separados, cada um com detector novo, recebendo os mesmos quadros na mesma ordem e os mesmos timestamps. O valor manual 1,2/+20 é apenas um candidato experimental, não uma recomendação automática. `--frames 0` processa o arquivo inteiro; o padrão é um prefixo de 120 quadros. `--max-size` tem padrão 640.

O relatório contém:

- SHA-256 do arquivo antes/depois e impressão digital dos quadros/timestamps decodificados. Se o arquivo mudar ou os passes receberem entradas diferentes, o ensaio falha.
- Configuração de cada caso, versão/API do MediaPipe, limite de quadros, tamanho e intervalo temporal analisado.
- Tempo médio de decodificação, PDI, inferência e ciclo offline aproximado; taxa de retorno de pose, visibilidade média de ombros/quadris/joelhos/tornozelos e quantidade de quadros com cada tracker válido.
- Luminância média e frações de pixels que possuem **algum canal** em 0 ou 255. Isso não é sinônimo de pixels totalmente pretos/brancos nem de uma medida automática de qualidade.

O FPS offline é estimado pela soma da decodificação e do processamento por quadro, incluindo redimensionamento, ajuste, BGR/RGB e validação. Exclui criação do modelo, hashes, estatísticas, escrita do relatório e exibição. A primeira inferência de cada caso está incluída; não há aquecimento omitindo quadros. Os hashes exigem duas leituras completas do arquivo, mesmo quando se analisa só um prefixo, mas não carregam o vídeo inteiro em memória.

O decoder trabalha sem espera de reprodução no ensaio, mas não descarta quadros. Na interface, o agendamento temporal original continua habilitado. O relatório indica se o EOF foi alcançado; analisar um prefixo não valida o restante do arquivo. A memória de agregação é constante: não se acumulam vídeos ou listas de landmarks.

A ferramenta não transmite para SteamVR/OSC e usa parâmetros explícitos: modelo 1, suavização MediaPipe ativa, limiares 0,5, sem rotação/espelho e com validação de visibilidade 0,5. Para confrontar a interface com o relatório, use os mesmos parâmetros e orientação de 0 graus. O vídeo original, codec, resolução e timestamps ficam preservados. A saída deve ser um JSON novo: entrada, arquivos já existentes ou diretórios inválidos são recusados; nunca são sobrescritos.

## Resultado medido, sem inferir precisão

Foi utilizado [Jeff.mp4 do material da aula](https://github.com/arnaldojr/cognitivecomputing/blob/b3937428887da4d38a8eb7c760ccbd1969558d0e/material/aulas/PDI/lab17/Jeff.mp4), commit `b3937428887da4d38a8eb7c760ccbd1969558d0e`, primeiros 60 quadros, reduzidos de 1280×720 para 640×360. O vídeo enquadra principalmente tronco e cabeça; não serve como ground truth para pés ou rastreadores VR. O arquivo não foi adicionado ao projeto.

O [relatório integral](../../evaluation/lighting_jeff_60.json) registra a execução em CPU compartilhada, com Python 3.12, MediaPipe 0.10.21, OpenCV 4.11.0 e NumPy 1.26.4. Os três passes receberam os mesmos quadros e timestamps. O SHA-256 do arquivo permaneceu `22bafdcee9c7851e15610f59fad0da0ba8e19aba7438bcaa84ff87ea78f29d88`.

| Medição | Original | Manual 1,2/+20 | Equalização Y |
|---|---:|---:|---:|
| PDI médio | 0,38 ms | 2,68 ms | 1,37 ms |
| Inferência média | 41,09 ms | 43,76 ms | 39,01 ms |
| Ciclo offline médio | 45,76 ms | 51,20 ms | 44,58 ms |
| FPS offline aproximado | 21,85 | 19,53 | 22,43 |
| Quadros com pose retornada | 60/60 | 60/60 | 60/60 |
| Visibilidade média relevante | 0,2516 | 0,2522 | 0,2518 |
| Quadros com trackers válidos, por tracker | 0 | 0 | 0 |
| Luminância média | 151,22 | 191,76 | 130,23 |
| Pixels com algum canal em 255 | 1,48% | 50,68% | 4,96% |

O ganho manual saturou muitos canais nesta cena já clara. A equalização mudou a distribuição de intensidades, sem melhorar a quantidade de trackers válidos. As pequenas diferenças de visibilidade não comprovam maior precisão. A taxa de retorno de pose permaneceu 60/60, mas isso não torna os pontos previstos dos pés corretos ou visíveis.

É uma execução sequencial por caso, em ordem fixa; variação de CPU, conteúdo ajustado e comportamento do detector podem afetar os tempos. O FPS ligeiramente maior com equalização nesta rodada não demonstra ganho consistente de desempenho. Não foram medidos precisão espacial, jitter físico ou latência no headset. Repita com vídeos de corpo inteiro, iluminação normal/escura/contraluz e parâmetros fixos; não generalize esta amostra para qualquer ambiente.

## Código e testes

| Arquivo | Alteração necessária |
|---|---|
| `bin/lighting.py` | Configuração imutável, transformação BGR, resize compartilhado e comparação sem desenhar no original |
| `bin/parameters.py` | Validação/persistência atômica, padrão desligado e compatibilidade com configurações antigas |
| `bin/inference_gui.py` | Seleção exclusiva de modo, valores manuais, lado a lado e restauração do original |
| `bin/mediapipepose.py` | Aplica o ajuste antes de BGR/RGB, uma inferência por quadro, reset de históricos quando a entrada muda e preview com rótulos coerentes |
| `bin/video_source.py` | Leitura sequencial sem espera opcional, somente para o ensaio; comportamento padrão da aplicação preservado |
| `tools/compare_lighting.py` | Comparação offline, hashes, métricas agregadas e proteção da entrada/saída |
| `tests/test_lighting.py` | Fórmula, clipping, cores, identidade, equalização, imutabilidade, GUI e pipeline da câmera |
| `tests/test_lighting_comparison.py` | Vídeo real gerado, detectores isolados, hashes, sequência temporal, falhas, recursos, CLI e MediaPipe real |
| `tests/test_pose_validation.py` | Persistência e carregamento das opções, inclusive configurações antigas/inválidas |

```bash
python -m unittest discover -s tests -v
python -m pip check
python -m compileall -q bin tests tools
git diff --check
pyinstaller --noconfirm bin/mediapipepose_linux.spec
./dist/mediapipepose/mediapipepose --check-runtime
```

**109 testes aprovados, zero falhas e zero skips**, incluindo os 83 anteriores e 26 novos. Build e smoke Linux com inferência real aprovados; dependências, sintaxe e diff aprovados. Os testes usam mocks para interações gráficas e saídas físicas, explicitamente diferenciados das integrações com arquivos/OpenCV/MediaPipe reais. Não havia lint ou tipagem configurados.

## Limitações, integração e apresentação

Não há câmera, display configurado ou Xvfb nesta máquina. Windows, GUI real e SteamVR/VRChat permanecem pendentes. A API do GitHub retornou `Forbidden` ao consultar Actions; publicar o branch não comprova aprovação da CI. **Nenhum merge para `develop` ou `main`; integração não aprovada.** O experimento manual de named pipes dependente de hardware não foi contabilizado como aprovado.

O lado a lado ajuda a avaliar iluminação/enquadramento, mas não compara duas inferências simultâneas. Ajustes podem prejudicar a imagem, e a recuperação dos históricos depois de trocar o modo pode causar transição de rastreamento. Pausar e mudar opções não altera retroativamente resultados já calculados. O arquivo original sempre permanece separado dos resultados.

Para apresentar: “Comparei técnicas de PDI que já estudamos: ganho e deslocamento de intensidades e equalização de histograma da luminância. Mantive os mesmos quadros, a conversão BGR/RGB e o modelo para isolar a alteração. Verifiquei que o ajuste pode saturar cores e não garante melhor detecção. Por isso as opções começam desligadas e devem ser avaliadas com medidas e com o vídeo original preservado.”

Depois das pendências de integração, a próxima prioridade é obter vídeos de corpo inteiro nas condições de iluminação relevantes e repetir a comparação com referência anotada. Só depois se deve decidir quais ajustes ajudam; filtros de ruído ou técnicas adicionais precisam de justificativa própria.
