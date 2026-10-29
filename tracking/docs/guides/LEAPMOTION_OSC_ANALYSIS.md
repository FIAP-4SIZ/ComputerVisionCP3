# Análise do leapmotion-osc

Referência indicada pelo usuário, inspecionada no commit `c9452158b497ddc33454726f1c356432d74fd536`: README e `Assets/LeapmotionOSC/Scripts/LeapmotionOSC.cs`. Repositório MIT. Nenhum código ou binário externo foi incorporado.

## O que ele demonstra

É possível animar dedos pelo OSC de parâmetros de avatar. O remetente Unity lê um sensor Leap Motion/Ultraleap e envia 20 floats para `/avatar/parameters/`: dez valores relacionados à abertura/fechamento e dez de abertura lateral (Spread). O método UpdateFingers constrói os nomes `leftIndex`, `rightThumb`, etc. e usa Client.Send. Não usa endpoints de dedos do OSC Trackers.

O README exige explicitamente criar os 20 parâmetros no avatar e usar/criar um Animator Controller com Blend Trees. Recomenda camadas Gesture e um bool `leapmotion` para habilitar as animações. Também alerta que as animações fornecidas foram ajustadas para os avatares dos autores, não validadas universalmente.

Portanto, estar na lista oficial OSC Resources indica um exemplo comunitário útil; não torna seus nomes de parâmetros universais em todo avatar público. Um avatar público que já contenha esse contrato pode ser compatível sem edição pelo usuário. Um avatar público genérico não ganha essas animações só por receber pacotes.

## Diferenças em relação ao nosso projeto

| Aspecto | leapmotion-osc inspecionado | Nosso projeto atual |
|---|---|---|
| Fonte | Sensor Leap Motion e plugin Ultraleap | Webcam e MediaPipe Hands |
| Remetente | Aplicação Unity/C# | Python/python-osc |
| Parâmetros | leftIndex, rightIndex, ... e Spread | MP_Left_Index, MP_Right_Index, ... e Tracked |
| Fechamento | Distância ponta→palma multiplicada por 10 | Soma normalizada de ângulos de segmentos |
| Abertura lateral | Calculada por orientação relativa | Não implementada |
| Posição da mão | README diz que não é fornecida pelo projeto isoladamente | Trackers rígidos opcionais; não há driver esquelético novo |

Renomear mensagens não basta: distância e flexão têm escalas e sentidos diferentes; também é necessário calibrar o avatar e tratar Spread. O Python pode implementar um perfil de compatibilidade para um avatar que realmente suporte esses parâmetros, sem migrar a visão para Unity nem exigir Leap Motion. Isso não instala parâmetros/animações num avatar público que não os tenha.

## Dados inválidos e perdas

O callback inspecionado percorre apenas `frame.Hands`. Não há nesse arquivo mecanismo explícito de expiração/Tracked=false para uma mão ausente. Isso não prova como todas as partes do cliente/avatar reagem, mas impede presumir que esse exemplo resolve sozinho a retirada de detecções perdidas. Nossas verificações e flags não devem ser removidas ao adaptar o contrato.

## Próxima decisão técnica

- Avatar já preparado com os 20 parâmetros: verificar a configuração OSC/Animator e calibrar um adaptador específico de valores; testar perda/retorno.
- Avatar próprio editável: configurar Gesture/Blend Trees conforme o contrato, mantendo o projeto MediaPipe como remetente.
- Avatar público genérico sem contrato: avaliar Selfie Expression nativo ou Skeletal Input SteamVR; este repositório não elimina esse requisito.

O uso combinado de OSC Trackers para o corpo e parâmetros para dedos é uma possibilidade de arquitetura, mas precisa de calibração, suporte do avatar e validação do modo de execução. Não é integração pronta só pela existência do exemplo.

Fontes:

- [README no commit analisado](https://github.com/philfiru/leapmotion-osc/blob/c9452158b497ddc33454726f1c356432d74fd536/README.md).
- [Código remetente no mesmo commit](https://github.com/philfiru/leapmotion-osc/blob/c9452158b497ddc33454726f1c356432d74fd536/Assets/LeapmotionOSC/Scripts/LeapmotionOSC.cs).
- [Lista oficial OSC Resources](https://docs.vrchat.com/docs/osc-resources#hand-tracking).
