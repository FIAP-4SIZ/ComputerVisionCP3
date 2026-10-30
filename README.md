# ComputerVisionCP3 — projeto acadêmico encerrado

Projeto FIAP 4SIZ de processamento digital de imagens e visão computacional com Python, OpenCV e MediaPipe. Encerrado em **30 de outubro de 2026** como protótipo experimental, sem entrega de full-body tracking funcional no avatar do VRChat.

## Resultado

- Captura e detecção corporal/mãos executadas no Windows.
- Pulo no VRChat por OSC confirmado pelo usuário, inclusive acionado pelo gesto de levantar os braços.
- Abertura do menu rápido do VRChat por OSC confirmada; seleção de opções não validada.
- Transporte de ambas as mãos do MediaPipe ao receptor SteamVR confirmado em dois ensaios.
- Corpo inteiro e dedos controlando corretamente o avatar **não foram comprovados**. Persistiram avatar deitado, ausência de apontador e falhas no editor de bindings.

Leia o [relatório final](docs/ENCERRAMENTO.md), que separa implementação, testes automatizados e observações no equipamento real.

## Código preservado

O [snapshot final experimental](https://github.com/FIAP-4SIZ/ComputerVisionCP3/tree/2da615937084d2790c4757b425f6179ed83b8c10) contém o código completo. As branches e os PRs foram preservados como histórico; seu encerramento não significa aprovação técnica ou merge.

A `main` e a `develop` recebem somente esta documentação de encerramento. As features com validação física pendente não foram integradas.

- [Instalação, execução e organização do protótipo](https://github.com/FIAP-4SIZ/ComputerVisionCP3/blob/2da615937084d2790c4757b425f6179ed83b8c10/README.md)
- [Testes automatizados](https://github.com/FIAP-4SIZ/ComputerVisionCP3/blob/2da615937084d2790c4757b425f6179ed83b8c10/tracking/tests)
- [Relatório técnico acumulado](https://github.com/FIAP-4SIZ/ComputerVisionCP3/blob/2da615937084d2790c4757b425f6179ed83b8c10/tracking/docs/reports/VALIDATION_REPORT.md)
- [Guias e referências](https://github.com/FIAP-4SIZ/ComputerVisionCP3/blob/2da615937084d2790c4757b425f6179ed83b8c10/tracking/docs/README.md)
- [Proposta acadêmica original](docs/PROPOSTA_ORIGINAL.md)

Para reproduzir o snapshot, use Python 3.12 e comece pelo destino **Somente análise**. Não instale automaticamente o driver/HMD virtual: a integração VR permaneceu experimental e foi abandonada ao encerrar o projeto.

## Créditos

Base MIT: [ju1ce/Mediapipe-VR-Fullbody-Tracking](https://github.com/ju1ce/Mediapipe-VR-Fullbody-Tracking), com [licença preservada](https://github.com/FIAP-4SIZ/ComputerVisionCP3/blob/2da615937084d2790c4757b425f6179ed83b8c10/tracking/LICENSE).

**Integrantes:** Mauro rm553574, Lucas rm552877, Fernando rm553499.
