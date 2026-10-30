# Relatório de encerramento

Data: 30/10/2026. Projeto acadêmico encerrado por decisão do usuário.

## Objetivo e resultado

Investigou-se rastreamento corporal por webcam ou vídeo, com técnicas de PDI e MediaPipe, para análise e eventual controle de um avatar no VRChat. O ambiente real foi Windows com webcam, sem headset físico e com avatar público, sem projeto Unity.

Foi construído e testado um protótipo de análise e transporte. O objetivo completo de controlar corpo inteiro e dedos no avatar não foi atingido. O acúmulo de HMD virtual, driver próprio, OSC, calibração e ferramentas de diagnóstico elevou a complexidade sem entregar uma experiência utilizável.

## Evidências no Windows

| Item | Resultado observado |
|---|---|
| Instalação | Python 3.14 incompatível com MediaPipe fixado; adotado Python 3.12 |
| Captura e inferência | Usuário executou câmera e detecção; ambas as mãos chegaram a ME:ok/MD:ok |
| Pulo OSC | Confirmado após habilitar OSC no VRChat; gesto de braços também confirmado |
| Menu OSC | Menu abriu; interação/seleção não aprovada |
| HMD virtual | Driver respondeu com hmd_valid=true; isso não demonstrou alinhamento correto no jogo |
| Ensaio de mãos 1 | 48 amostras, máscara 3 em 30; HMD válido em 48 |
| Ensaio de mãos 2 | 50 amostras, máscara 3 em 46; HMD válido em 50 |
| Avatar | Continuou deitado após referência Standing Only passar de 0 para 177 cm |
| Apontador | Não apareceu no teste relatado |
| Binding UI | Binding próprio selecionado; Editar abriu janela preta, navegador ficou branco |
| Resolução | Usuário continuou relatando resolução interna inadequada |

Máscara 3 indica recepção de ambas as mãos válidas simultaneamente no receptor, não precisão dos dedos, aplicação pelo SteamVR ou movimento no avatar. A diferença entre ensaios não demonstra ganho de qualidade: condições não foram controladas e não houve comparação anotada.

## Funcionalidades implementadas e limites de comprovação

O snapshot contém entrada por câmera/vídeo sequencial, timestamps e controles de reprodução; pré-processamento opcional de iluminação preservando a imagem original; validação por visibilidade e por tracker; análise de enquadramentos parciais; detecção Hands e flexões dos dedos; interfaces em português; saídas OSC e integração experimental de esqueleto SteamVR.

Implementação e testes automatizados dessas funções não equivalem à aprovação de todos os fluxos numa sessão real. Não foram concluídos ensaios controlados de iluminação, jitter, movimentos rápidos, oclusões e latência no avatar. Não há resultado que sustente afirmar aumento de precisão.

## Verificação automatizada

Na revisão final experimental 2da615937084d2790c4757b425f6179ed83b8c10 foram registrados 311 testes Python e quatro CTests locais aprovados, além de pip check, compileall, diff check, build PyInstaller Linux e runtime Pose/Hands. Os oito checks de push/PR Windows e Linux do PR #27 foram consultados e estavam aprovados. Os testes incluem mocks, UDP real, decoder C++ e integração MediaPipe com imagem de referência.

Esses resultados validam os cenários automatizados cobertos. Não aprovam webcam física no runner, interação VRChat, FBT no avatar ou todos os dedos. A documentação de encerramento é validada separadamente; sua integração não aprova os experimentos.

## Conceitos aplicados

- Imagens como matrizes e conversão BGR para RGB antes da inferência.
- Brilho/contraste e equalização opcionais, com comparação da imagem original.
- Coordenadas normalizadas, pixels e coordenadas espaciais estimadas com finalidades distintas.
- Keypoints, visibilidade, associação de punhos e confirmação temporal.
- Suavização existente, rejeição de valores inválidos e expiração para perda de observação.
- Vetores, rotações e hierarquia de ossos para serialização do esqueleto.
- Medições de tempo por etapa e FPS no protótipo, sem benchmark final controlado no VRChat.

A câmera monocular não mede profundidade real. Pontos ocultos e ossos interpolados não são novas observações. Não foram aplicadas todas as técnicas de PDI indiscriminadamente.

## Encerramento do SteamVR no computador do usuário

Após solicitar remoção, o usuário executou o diagnóstico e mostrou external_drivers=[]: nosso addon não estava mais registrado naquele instante. null_driver=true apenas indica arquivo oficial presente.

Não foram fornecidas as três respostas restored=true, portanto não se afirma restauração integral de steamvr.vrsettings. A preparação de cômodo foi alterada manualmente e não é coberta pelos backups do instalador. Não foi confirmada a remoção das opções de resolução do VRChat. Preservar backups e pacote até resolver eventuais pendências; nenhum estado Windows foi alterado remotamente pela nuvem.

## Decisão de encerramento e alternativas pesquisadas

As features não serão integradas como solução funcional. PRs de experimentos são fechados sem merge, mantendo commits e branches para consulta. Nenhuma instalação adicional está sendo proposta como parte da entrega final.

Foram pesquisados Driver4VR/tVR (webcam e VR no monitor; pago, combinação com dedos não comprovada), AprilTag Trackers (marcadores no quadril e pernas), MocapForAll (duas ou mais câmeras) e VMT (poses/esqueleto por OSC, alternativa ao driver próprio). Nenhum foi validado no computador do usuário neste projeto. Selfie Expression foi descartado pelo usuário por não atender pernas/corpo inteiro.

Fontes:

- https://docs.vrchat.com/docs/osc-trackers
- https://store.steampowered.com/app/1366950/Driver4VR/
- https://github.com/ju1ce/April-Tag-VR-FullBody-Tracker
- https://store.steampowered.com/app/1759710/MocapForAll/
- https://github.com/gpsnmeajp/VirtualMotionTracker

## Resumo para apresentação

“O projeto aplicou PDI e MediaPipe à análise de movimento por câmera e vídeo. Foram implementadas validação de pontos, comparação de iluminação e transmissão de poses. No Windows, demonstramos comandos OSC no VRChat e recepção simultânea das mãos no driver. A etapa de controlar corpo inteiro e dedos no avatar não foi concluída. A principal conclusão é que detectar e transmitir keypoints não garante alinhamento, calibração ou integração com o sistema de animação do jogo.”
