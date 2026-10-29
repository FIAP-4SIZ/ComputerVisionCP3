
# Computer Vision CP3 4SIZ

## MediaPipe VRChat Full Body Tracking

## 📌 Sobre o projeto

Este projeto tem como objetivo desenvolver um sistema de rastreamento corporal (*Full Body Tracking*) para o VRChat utilizando o MediaPipe e uma câmera convencional.

A proposta é identificar os movimentos do corpo humano em tempo real, utilizando visão computacional para detectar pontos importantes. O sistema processa as informações de movimento e busca utilizá-las para controlar os movimentos de um avatar dentro do VRChat.

O foco principal é explorar uma alternativa mais acessível aos equipamentos tradicionais de Full Body Tracking, que geralmente dependem de sensores específicos ou dispositivos adicionais.

## 🎯 Objetivos

- Utilizar o MediaPipe para detectar os pontos do corpo humano através de uma câmera.
- Processar os pontos detectados para calcular posições e movimentos das articulações.
- Converter os dados capturados em informações que possam ser utilizadas por um sistema de rastreamento corporal.
- Integrar o sistema com o VRChat para movimentar um avatar de acordo com os movimentos reais do usuário.
- Desenvolver uma solução experimental de baixo custo para Full Body Tracking.

## 🛠️ Tecnologias utilizadas

- **Python:** linguagem principal para o desenvolvimento e processamento dos dados.
- **MediaPipe:** biblioteca utilizada para detecção e rastreamento dos pontos do corpo humano.
- **OpenCV:** captura e processamento das imagens da câmera.
- **VRChat:** ambiente virtual onde os movimentos do avatar serão reproduzidos.
- **OSC (Open Sound Control):** protocolo que poderá ser utilizado na comunicação com aplicações compatíveis, dependendo da solução de rastreamento implementada.

## ⚙️ Funcionamento do sistema

O funcionamento do projeto pode ser dividido em algumas etapas:

1. **Captura de imagem:** uma câmera captura os movimentos do usuário.
2. **Detecção corporal:** o MediaPipe identifica os principais pontos do corpo na imagem.
3. **Processamento dos dados:** o sistema organiza os pontos detectados e calcula as informações necessárias para representar os movimentos das articulações.
4. **Conversão dos movimentos:** os dados são convertidos para um formato compatível com a solução de rastreamento escolhida.
5. **Envio das informações:** os dados de movimento são enviados para uma aplicação intermediária ou sistema compatível.
6. **Movimentação do avatar:** o sistema de rastreamento utiliza as informações recebidas para reproduzir os movimentos no avatar do VRChat.

O MediaPipe, por si só, não controla diretamente o avatar no VRChat. Para que a integração funcione, será necessário desenvolver ou utilizar uma camada intermediária que converta os dados capturados em informações aceitas pelo sistema de rastreamento.

## 📊 Diagrama de funcionalidade

O diagrama abaixo representa o fluxo principal de funcionamento proposto para o sistema.

![Diagrama de fluxo do MediaPipe VRChat Full Body Tracking](https://github.com/user-attachments/assets/a44822bc-7b79-4d45-9ece-b22b28438b44)

## 🚧 Etapas de desenvolvimento

O desenvolvimento será realizado de forma incremental, começando pela detecção corporal e avançando até a integração com o VRChat.

- [ ] Configurar o ambiente de desenvolvimento.
- [ ] Implementar a captura de imagens com OpenCV.
- [ ] Integrar o MediaPipe para detectar os pontos do corpo.
- [ ] Processar os pontos e calcular os movimentos das articulações.
- [ ] Desenvolver a conversão dos dados para rastreamento corporal.
- [ ] Implementar a comunicação com a solução de tracking escolhida.
- [ ] Testar a movimentação do avatar no VRChat.
- [ ] Avaliar a precisão, a latência e as limitações do sistema.

## ⚠️ Limitações previstas

Por utilizar uma câmera convencional, o sistema pode apresentar limitações relacionadas à iluminação, oclusão de partes do corpo e posicionamento do usuário.

Além disso, a estimativa dos pontos corporais realizada pelo MediaPipe não garante, por si só, a obtenção de todas as informações tridimensionais necessárias para um rastreamento corporal preciso. Poderá ser necessário realizar calibração, estimar a posição das articulações e aplicar filtros para reduzir oscilações nos movimentos.

A compatibilidade com o VRChat também dependerá da implementação da comunicação e do sistema intermediário utilizado para interpretar os dados de rastreamento.

## 📚 Considerações finais

O projeto busca demonstrar como técnicas de visão computacional podem ser aplicadas ao rastreamento corporal em ambientes virtuais. A utilização do MediaPipe pode reduzir a dependência de equipamentos especializados, tornando o desenvolvimento de uma solução de Full Body Tracking mais acessível.

O resultado esperado é um protótipo funcional capaz de capturar os movimentos do usuário e utilizá-los para movimentar um avatar no VRChat, respeitando as limitações técnicas da abordagem proposta.

---

**Integrantes:** Mauro rm553574, Lucas rm552877, Fernando rm553499 

## Aplicação e desenvolvimento incremental

A implementação está em [`tracking/`](tracking/), derivada do projeto MIT de ju1ce, com atribuição e licença preservadas. O código mantém Python, OpenCV e MediaPipe.

- [Instalação, câmera e arquivo de vídeo](tracking/VIDEO_INPUT.md).
- [Validação de landmarks e limites da confiança](tracking/POSE_VALIDATION.md).
- [Validação e expiração independentes por tracker](tracking/PER_TRACKER_VALIDATION.md).
- [Comparação opcional de iluminação, preservando o vídeo original](tracking/LIGHTING_COMPARISON.md).
- [Resultados e pendências de integração](tracking/VALIDATION_REPORT.md).
- [Arquitetura e estudo de PDI](tracking/ESTUDO_PDI.md).
- [Branches e verificações de integração](DEVELOPMENT.md).

O modo de arquivo oferece análise sequencial, timestamps, progresso e controles de reprodução. **Somente análise** permite executá-lo sem headset. A aprovação de integração depende das verificações documentadas; a presença do código não significa que testes com equipamento VR foram concluídos.
