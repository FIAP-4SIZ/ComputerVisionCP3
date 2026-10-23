# Próxima melhoria prioritária: validar poses antes de enviar trackers

## Por que esta melhoria

O diagnóstico em `ESTUDO_PDI.md` já identificava a ausência de verificação de visibilidade e coordenadas, além de normalizações que podem dividir por zero. Não foi escolhida uma feature arbitrária: após adicionar vídeo, o mesmo problema passa a ocorrer também em gravações com pés fora do quadro e oclusões. A prioridade é confiabilidade, antes de tentar melhorar precisão com filtros de imagem.

Branch: `feature/pose-validation`, dependente de `feature/video-input`. Nenhuma alteração em `main` ou `develop`. A integração continua bloqueada enquanto houver verificações obrigatórias pendentes.

## Escopo e conceitos da aula

- A API continua sendo `mp.solutions.pose`, sem novo modelo nem nova dependência.
- `pose_validation.prepare_pose` recebe os 33 landmarks world; exige coordenadas XYZ finitas e visibilidade suficiente nos pontos necessários. Depois aplica exatamente o mapeamento/inversões/rotações existente.
- Exige ombros 11/12, quadris 23/24, joelhos 25/26 e tornozelos 27/28. Rotação experimental dos pés também exige 29…32; mãos exigem 15…20; preview completo exige os outros pontos usados pelo esqueleto.
- O limiar padrão é 0,5. A GUI permite ajustá-lo em 0…1 e salva o valor nos parâmetros de execução. Entrada inválida preserva o valor anterior e apresenta feedback. Limiar zero desliga a restrição por visibilidade, mas não aceita campo ausente nem coordenadas inválidas.
- `np.errstate` transforma divisões inválidas e overflow na orientação em rejeição explícita. Quaternions devem ter quatro componentes finitos e norma aproximadamente unitária.
- Poses rejeitadas continuam visíveis para diagnóstico, com aviso e valor de visibilidade quando insuficiente, mas não geram novas atualizações. Em poses válidas, a imagem mostra a visibilidade dos dois tornozelos. Dados de calibração anteriores são removidos quando a pose se torna inválida, some, ou o vídeo termina/é cancelado. A calibração também verifica a existência de pose válida antes de consultar o headset.

Isso aplica análise de keypoints, visibilidade, coordenadas e geometria estudadas em visão computacional. Um valor 0,5 de visibilidade não significa erro menor que 50% nem garante posição correta. Coordenadas world continuam sendo estimativas monoculares, não medições de profundidade.

## Suavização preservada e histórico OSC

Não foi adicionado filtro. O OSC conserva `s × anterior + (1 − s) × atual` após a primeira pose válida. A primeira pose passa a iniciar o histórico com sua própria posição, em vez de misturá-la com um corpo fictício na origem. Reiniciar vídeo limpa o histórico.

Exemplo: posição anterior 1 m, atual 2 m, peso `s=0,7` resulta em 1,3 m. Na primeira amostra, sem anterior válido, usa-se a posição atual. Dados rejeitados não são enviados nem modificam esse histórico. Pesos fora de 0…1 ou não finitos são rejeitados.

Os backends validam os dados e o alinhamento antes de emitir mensagens. SteamVR rejeita respostas do headset não numéricas/não finitas; OSC e SteamVR rejeitam escala/deslocamento inválidos. Nenhum limite arbitrário de velocidade foi acrescentado: movimentos rápidos não são rejeitados somente por sua amplitude.

## Arquivos afetados

| Arquivo | Responsabilidade |
|---|---|
| `bin/pose_validation.py` | Validação e transformação compartilhada pela câmera e pelo vídeo |
| `bin/mediapipepose.py` | Mostra estado da pose, só envia dados aprovados e remove calibração obsoleta |
| `bin/backends.py` | Defesa adicional nos dados enviados e inicialização/histórico OSC |
| `bin/parameters.py` | Limiar validado e persistido |
| `bin/inference_gui.py` | Campo de visibilidade, feedback e proteção da calibração |
| `tests/test_pose_validation.py` | Sucesso, erros, limites, oclusões, degeneração, histórico e respostas HMD |
| `tests/test_first_improvement.py` | Fixture ganha visibilidade explícita; comparação geométrica original é preservada |

## Testes e resultados

```bash
cd tracking
python -m unittest discover -s tests -v
python -m pip check
python -m compileall -q bin tests tools
```

Foram executados **48 testes, todos aprovados, sem skips**. Incluem os 29 testes da feature de vídeo e 19 novos testes da validação. Os testes de integração geram e decodificam AVI real e executam MediaPipe real; as interações gráficas e o equipamento VR são substituídos somente onde documentado. Mensagens OSC são serializadas e decodificadas nos testes; o formato dos comandos SteamVR também é verificado, com o driver substituído por mock.

A regressão de transformação compara o laço original preservado na fixture com o atual: mesmos landmarks válidos produzem exatamente as mesmas 29 posições e três quaternions de entrada do backend. O ajuste intencional da primeira amostra OSC tem testes próprios e não é apresentado como equivalência ao comportamento anterior.

Ensaio adicional com `Jeff.mp4` do material da aula, commit `b3937428887da4d38a8eb7c760ccbd1969558d0e`: primeiros 30 quadros, 640×360, modelo 1. MediaPipe retornou pose em 30/30; com visibilidade mínima 0,5, 0/30 foram aprovados para trackers. Os timestamps foram estritamente crescentes. O vídeo mostra tronco/cabeça e não enquadra os pés: o resultado demonstra rejeição conservadora de dados insuficientes, não aumento de precisão nem estabilidade validada em VR. O vídeo não é incluído como novo asset do projeto.

## Como avaliar em aula

Use gravação de corpo inteiro, sempre o mesmo arquivo e os mesmos parâmetros. Oculte um tornozelo, acompanhe o aviso e confirme que o backend não recebe nova pose durante a rejeição. Ao reaparecer, uma pose válida volta a ser enviada. Compare limiares 0,3/0,5/0,7, perdas, tempo por quadro e latência aparente. Não confunda maior taxa de rejeição com maior precisão.

Resumo: “Usei os níveis de visibilidade dos keypoints para decidir quando uma pose possui informação suficiente. Também validei coordenadas e orientações antes de transmitir. Mantive a suavização existente e evitei que dados inválidos contaminassem seu histórico. O método é simples e explicável, mas não resolve a ambiguidade de profundidade de uma única câmera.”

## Limitações e próximos passos

- A política inicial rejeita a pose inteira se um ponto necessário falhar. Isso pode suspender o quadril mesmo quando só um pé está oculto. A evolução recomendada é validar/expirar cada tracker separadamente, com testes físicos antes de definir uma política de retenção.
- Não se reenvia uma pose antiga como se fosse nova. O estado visual retido pelo receptor OSC depende do VRChat; esta mudança não implementa protocolo de expiração nem promete desativação imediata do avatar. O driver SteamVR mantém suas regras existentes.
- O filtro OSC mantém o histórico válido ao longo de uma oclusão. O atraso na recuperação depende do peso de suavização; reinício explícito limpa esse histórico. Não há interpolação de pontos ausentes nem previsão de movimentos.
- Nem todo erro espacial causa baixa visibilidade. Uma pose confiante ainda pode estar incorreta; não há ground truth de posição nos testes executados.
- Continuam pendentes Windows, GUI real, câmera física e SteamVR/VRChat em equipamento. Ver `VALIDATION_REPORT.md`: código e testes locais não aprovam automaticamente a integração.
