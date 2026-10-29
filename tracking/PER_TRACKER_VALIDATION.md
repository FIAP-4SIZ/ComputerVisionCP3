# Validação independente dos trackers

> A etapa seguinte de comparação opcional de iluminação está documentada em `LIGHTING_COMPARISON.md`. Os 83 testes e resultados abaixo registram a etapa dos trackers independentes.

## Problema e escopo

Esta é a próxima melhoria definida em `POSE_VALIDATION.md`: a validação anterior rejeitava a pose inteira quando um tornozelo falhava. Agora quadril, pés e mãos são avaliados por suas dependências, usando os mesmos landmarks world do MediaPipe e o mesmo alinhamento do projeto. Nenhuma rede, dependência ou filtro novo foi adicionado.

Branch: `feature/per-tracker-validation`, baseada em `feature/pose-validation`, no repositório `FIAP-4SIZ/ComputerVisionCP3`. Integração com `develop` continua bloqueada pelos testes externos pendentes. O esqueleto completo de preview mantém a validação conservadora anterior.

## Como funciona

`prepare_trackers` primeiro tenta o caminho completo já existente. Quando ele falha, valida os grupos separadamente. O quadro resultante contém posições, orientações, máscara de validade, motivos de rejeição e, somente quando possível, os dados completos para calibração.

| Tracker | Dependências principais |
|---|---|
| Quadril | Ombros 11/12 e quadris 23/24 |
| Pé direito | Âncora comum + joelho 26 e tornozelo 28 |
| Pé esquerdo | Âncora comum + joelho 25 e tornozelo 27 |
| Rotação experimental dos pés | Também exige calcanhar e ponta do respectivo pé: 30/32 ou 29/31 |
| Mão esquerda | Âncora comum + pontos 15/17/19 |
| Mão direita | Âncora comum + pontos 16/18/20 |

A âncora comum exige ombros e quadris válidos: sem ela, não há alinhamento confiável ao pescoço. Coordenadas não finitas, visibilidade ausente/insuficiente e orientações degeneradas continuam rejeitadas. Na perna esquerda reta, o fallback original usa o outro tornozelo; nesse caso ele também precisa ser válido. Essa dependência não foi ocultada nem substituída por uma rotação inventada.

Os cálculos de orientação foram extraídos para `tracker_math.py`. As funções antigas em `helpers.py` continuam disponíveis e chamam as mesmas operações. As referências numéricas congeladas do commit `968bbf1` verificam quadril, pernas, pés, mãos e os fallbacks das pernas retas.

Na representação interna, slots inutilizáveis podem receber preenchimento neutro para permitir o mapeamento da matriz. Eles **não são medições**: a máscara é obrigatória no caminho parcial e impede seu envio. A calibração automática nunca usa esses slots. Os testes verificam os endereços e dados efetivamente serializados, não apenas a máscara.

## Perda, expiração e recuperação

Há quatro estados locais por tracker:

- `sem dados`: nenhuma medição válida foi recebida.
- `ok`: o quadro atual permite atualizar o tracker.
- `ausente`: houve perda; o histórico local ainda não venceu o prazo configurado.
- `expirado`: o histórico foi removido e a recuperação começará com uma amostra nova.

**Um tracker ausente nunca é reenviado usando coordenadas antigas**, mesmo no estado `ausente`. Os demais trackers válidos continuam sendo enviados. Não há bundle OSC contendo apenas a cabeça quando todos os trackers estão inválidos.

O novo campo **Expirar histórico do tracker após perda (s)** aceita segundos finitos e não negativos, salva o valor nos parâmetros e apresenta feedback para entradas inválidas.

- **Padrão 0:** limpa o histórico assim que uma perda é observada. Quadros válidos consecutivos continuam usando suavização; zero não desliga o filtro.
- **Valor positivo:** mantém o histórico por até esse intervalo desde a última medição válida, sem reenviá-la. Uma medição que chega após o prazo começa um histórico novo, mesmo se não houve quadro intermediário indicando perda.
- **Reinício, cancelamento, EOF ou falha do vídeo:** limpam o estado local da entrada. Pausar vídeo congela sua linha temporal e não é tratado como oclusão. Na câmera, os timestamps continuam sendo os tempos de captura.

A expiração é avaliada durante o processamento dos quadros, usando o timestamp do arquivo ou da câmera. Não há um serviço que force o receptor a desativar o tracker enquanto o programa está sem novos quadros. O status descreve a análise local, não confirma conexão ou recebimento pelo VRChat.

A fórmula é `idade = tempo_atual − tempo_da_última_medição_válida`. Com última medição em 9,70 s e prazo 0,20 s, o histórico vence em 9,90 s. O código tolera erros numéricos de até 1 ns na comparação, para não atrasar a expiração por representação binária de valores como `0,3 − 0,1`.

O filtro exponencial existente permanece `s × anterior + (1 − s) × atual`. Para cada tracker, posição e âncora do pescoço são guardadas juntas, evitando misturar uma posição antiga do pé com o histórico atualizado de outra parte do corpo. Por exemplo, com `s=0,7`, posição anterior 1 m e nova 1,2 m, sai 1,06 m. Após expirar, não há anterior: a primeira posição válida inicia o histórico.

## Protocolos e limites da expiração

OSC conserva `/tracking/trackers/{id}/position` e `/rotation`, os mesmos IDs e a conversão existente dos ângulos. Mãos e preview completo continuam não suportados pelo backend OSC. Em SteamVR, os IDs seguem a ordem dos dispositivos criados; ao desabilitar o quadril, os pés usam os slots 0/1. A seleção de quais trackers enviar não muda o layout dos outros.

Ao alterar o conjunto de dispositivos — quadril ou mãos habilitados — reinicie o SteamVR e recalibre. O driver pode manter os dispositivos criados pela configuração anterior; este aplicativo não consulta nem altera seus papéis remotos.

Foi inspecionado o [Simple OpenVR Bridge Driver no commit c440e117](https://github.com/ju1ce/Simple-OpenVR-Bridge-Driver/tree/c440e117ec141ba3109501617214c4578250c3ba), referenciado como submódulo pelo projeto ApriltagTrackers. Em `VRDriver.cpp`, o último `0.8` do comando `updatepose` é lido como `smoothing`, **não como TTL**. Em `TrackerDevice.cpp`, a previsão é limitada a 0,2 s e `Update` pode deixar de publicar novas poses; isso não demonstra que o dispositivo ficará imediatamente inativo no headset. A versão instalada no equipamento do usuário não foi verificada.

A página oficial `https://docs.vrchat.com/docs/osc-trackers` retornou HTTP 403 neste ambiente. Nenhum endereço OSC de desativação foi inventado. A expiração desta feature é local: remove o histórico e interrompe novas atualizações do tracker perdido. O receptor pode continuar mostrando a última posição, dependendo de seu comportamento. Esse efeito precisa de teste físico antes do merge.

## Arquivos e explicação do código

| Arquivo | Funções e alteração |
|---|---|
| `bin/tracker_math.py` e `bin/helpers.py` | Separam a orientação de cada tracker sem mudar as fórmulas anteriores |
| `bin/independent_trackers.py` | `prepare_trackers` valida grupos; `TrackerLifecycle` controla tempos/estados; `enabled_names` e `tracker_mask` mantêm papéis e seleção |
| `bin/backends.py` | Filtra os envios; mantém histórico OSC por tracker; `expire_trackers` limpa só os históricos vencidos; não confirma um histórico novo antes de um envio bem-sucedido |
| `bin/mediapipepose.py` | Usa o mesmo caminho para câmera e arquivo; aplica expiração antes do envio; exibe `Q`, `PD`, `PE`, `ME`, `MD` e seus estados |
| `bin/parameters.py` e `bin/inference_gui.py` | Validam, persistem e permitem ajustar o prazo local |
| `tests/test_tracker_math.py` e fixtures | Regressões numéricas contra a implementação anterior |
| `tests/test_independent_trackers.py` | Perdas localizadas, tempos, recuperação, protocolos, UDP real e pipeline de AVI |
| `tests/test_pose_validation.py` | Preserva os testes anteriores, adaptando a inspeção do histórico e a entrada comum agora usada no laço |

É uma abordagem de grupos de pontos, dicionários e tempo decorrido. Foi escolhida para ser explicável e testável sem prever posições ocultas, adicionar filtros duplicados ou migrar a API do MediaPipe. O custo de processamento pode aumentar nos quadros parciais, que antes eram descartados rapidamente; não se afirma aumento de FPS.

## Testes e comparação

Com o ambiente Python 3.12 e as dependências de `requirements-study.txt` instaladas, execute da pasta `tracking/`:

```bash
python -m unittest discover -s tests -v
python -m pip check
python -m compileall -q bin tests tools
git diff --check
pyinstaller --noconfirm bin/mediapipepose_linux.spec
./dist/mediapipepose/mediapipepose --check-runtime
```

No Windows, use a spec `bin/mediapipepose.spec` e o executável `.exe`. Os jobs Linux/Windows continuam configurados na CI.

**Resultado local: 83 testes aprovados, zero falhas e zero skips**, sendo 35 novos testes além dos 48 da etapa anterior. Dependências, compilação, diff, build Linux e smoke do binário com inferência real aprovados. Os testes de vídeo anteriores continuam executando OpenCV e MediaPipe reais. O novo cenário de oclusão usa AVI real e landmarks controlados para verificar deterministicamente perda e recuperação; ele não é apresentado como uma detecção corporal real.

| Mesmos landmarks de teste | Validação anterior | Nova validação |
|---|---|---|
| Todos os pontos necessários válidos | Envia todos os trackers | Preserva posições/orientações e valores dos pacotes da referência |
| Tornozelo esquerdo com baixa visibilidade | Rejeita a pose inteira | Envia quadril e pé direito; omite pé esquerdo |
| Ambos os tornozelos com baixa visibilidade | Rejeita a pose inteira | Mantém o quadril quando a âncora é válida |
| Âncora comum inválida | Rejeita a pose inteira | Não envia trackers que dependem dela |
| Pé reaparece após expirar | Histórico global podia permanecer antigo | Só o pé recuperado inicia histórico novo; demais históricos continuam |

Foram comparadas orientações em precisão dupla com tolerância 1e-12 e pacotes OSC com tolerância compatível com seus floats de 32 bits. O teste de transporte usa UDP local real e confirma a ausência do endereço do pé perdido. O teste AVI percorre a aplicação, verifica a recuperação sem mistura com o histórico expirado e confirma a liberação do arquivo no EOF. Mensagens SteamVR são verificadas com o driver substituído; não houve teste com um headset.

Para avaliação manual, use o mesmo vídeo de corpo inteiro e os mesmos parâmetros em ambos os branches. Oculte apenas um pé, confira os estados na imagem e os trackers no receptor; depois repita com prazo 0 e 0,2 s. Verifique também recuperação, movimento rápido, pausa, reinício e encerramento. Um receptor ainda mostrar uma pose antiga não significa que o aplicativo a reenviou: confirme os pacotes ou os comandos recebidos.

## Limitações e apresentação acadêmica

Continuam pendentes Windows, GUI real, câmera física, SteamVR e VRChat. A API do GitHub também negou a consulta aos resultados de Actions. **Merge não aprovado; `main` e `develop` não foram alteradas.** O experimento manual `bin/tests/pipetest.py`, dependente de hardware e contendo `assert 0`, não foi contabilizado como teste aprovado.

Não foram medidos jitter real, latência no headset, precisão espacial ou FPS de câmera. Visibilidade alta não garante coordenadas corretas; uma câmera não mede a profundidade real. O prazo zero pode tornar a recuperação mais abrupta; prazos positivos podem trazer atraso da suavização ao recuperar. Não foi adicionado um limitador de velocidade que pudesse eliminar movimentos reais.

Para apresentar: “Antes, um tornozelo oculto interrompia a atualização de toda a pose. Separei os pontos necessários a cada tracker e uso visibilidade, coordenadas finitas e geometria para decidir o que enviar. Cada tracker possui estado e histórico próprios. Não invento movimentos para uma articulação oculta: paro de enviar esse tracker e mantenho os demais válidos. Os testes demonstram esse comportamento, mas ainda preciso validar seu efeito no equipamento VR.”

Depois de resolver as pendências de integração, a próxima etapa da lista é experimentar pré-processamento opcional de iluminação com os mesmos vídeos, preservando a imagem original e medindo os resultados antes de adotar qualquer filtro.
