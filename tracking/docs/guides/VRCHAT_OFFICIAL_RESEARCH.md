# Auditoria da documentação oficial do VRChat — 29/10/2026

## Escopo e método

Foi consultado o índice oficial `https://docs.vrchat.com/llms.txt`: 282 páginas Markdown distintas. As 282 foram obtidas, sem erros, e pesquisadas por OSC, trackers, desktop, mãos, dedos, skeletal input, calibração, perda de rastreamento e Selfie Expression. As páginas diretamente relevantes foram lidas integralmente; notas de versão relevantes foram examinadas. Isso é busca no conjunto completo indexado, não afirmação de leitura linha a linha de todas as notas históricas. O manifesto de URLs/tamanhos/SHA-256 está em `../../evaluation/vrchat_docs_audit.json`, sem copiar o corpus para o repositório.

Também foi consultada a página Selfie Expression da wiki oficial e o guia oficial de drivers no repositório de documentação dos criadores. Inicialmente o site havia retornado 403; nesta pesquisa as páginas oficiais e suas versões `.md` ficaram acessíveis. Resultados antigos baseados somente em impossibilidade de acesso não devem fundamentar limitações do cliente.

## Correções das conclusões anteriores

1. **OSC corporal não exige Unity ou avatar customizado.** A nota de lançamento declara “This works with any avatar” e distingue OSC Trackers dos parâmetros de avatar. O programa remetente pode ser Python; a página de trackers diz que Unity não é necessário.
2. **Desktop com webcam e mãos/dedos existe nativamente.** Selfie Expression funciona em desktop e pode mover cabeça, braços, mãos e dedos em avatares compatíveis, sem preparar parâmetros MP_* no Unity. A restrição inicial VRC+ foi removida em setembro de 2025.
3. **Não são a mesma interface.** Endpoints de trackers corporais, parâmetros customizados, Selfie Expression interno e esqueleto SteamVR são mecanismos distintos. Não se deve usar a limitação de um para negar a existência dos outros.
4. **A wiki Settings marca a calibração FBT como VR Only.** Na investigação posterior do teste do usuário, foi consultada também a [tabela Tracking & IK do menu rápido](https://wiki.vrchat.com/wiki/Settings#Tracking_.26_IK). O bloco que contém Allow FullBody Tracking FBT e Calibrate FBT tem o requisito explícito **[VR Only] [At least one full body tracker must be on]**. Isso corrige a hipótese inicial de que bastaria encontrar/calibrar esse botão no desktop comum. Recepção OSC e opções globais visíveis não ativam por si só esse fluxo. Não confundir com Selfie Expression, que possui suporte próprio para desktop.
5. O guia de drivers cita **MediaPipe hand tracking** como exemplo possível de `VRSkeletalTracking_Full`. Esse enum descreve a fidelidade estrutural fornecida à interface; não é certificado de precisão nem medição real de profundidade. Cinco floats de flexão não equivalem ao esqueleto completo.

## Interfaces e dados realmente documentados

| Interface | O que recebe/faz | Implicação para o projeto |
|---|---|---|
| OSC Trackers | Até oito trackers corporais; posição e rotação | Backend OSC existente é caminho válido para corpo; não precisa inventar parâmetros no avatar |
| Head OSC | Posição/rotação opcionais como referência de alinhamento | Não é prova de substituição de um HMD: a descrição trata de alinhar espaços |
| OSC Avatar Parameters | Valores para parâmetros já existentes no avatar | Nossos MP_Left_*/MP_Right_* precisam de animações/contrato correspondente |
| OSC Input | Botões/axes, como Jump | Pulo confirmado pelo usuário é controle de jogo, não FBT |
| Selfie Expression | Rastreamento nativo por webcam no desktop | Alternativa imediata para testar cabeça/mãos/dedos sem Unity ou headset; não é execução do nosso MediaPipe |
| SteamVR Skeletal Input | Esqueleto das mãos via driver e bindings | Caminho documentado para nosso modelo controlar dedos sem parâmetros customizados por avatar |

### Corpo OSC

Endereços: `/tracking/trackers/1/position` e `/rotation`, até ID 8. Cada mensagem contém **três floats**. As regiões listadas são quadril, peito, dois pés, dois joelhos e dois cotovelos/braços superiores. A página não define IDs fixos por região. Não foi encontrado endpoint de osso de dedo nessa API.

Coordenadas: sistema Unity canhoto, Y para cima, metros, Euler em graus aplicado na ordem Z, X, Y. Não enviar pixels ou normalizados diretamente. A página recomenda começar com pés/quadril; mais trackers podem piorar o resultado se a qualidade não for suficiente.

`/tracking/trackers/head/position` alinha o espaço ao osso da cabeça do avatar (não aos olhos). Head rotation alinha yaw. A menção a timeout de dez segundos está no tratamento de head rotation em streaming; não é garantia de descarte imediato de qualquer tracker corporal. A seção Auto-center contém aviso oficial de que está desatualizada.

### Mãos e dedos

O guia SteamVR Input 2.0 descreve Skeletal Input para poses de mão e hand tracking. O guia de drivers liga os esqueletos às ações `SkeletonLeftHand` e `SkeletonRightHand`, usando a faixa `WithoutController`. Não é necessário que cada avatar declare nossos parâmetros MP_*.

O guia também desaconselha disfarçar o dispositivo como um controle Index/Touch: recomenda um perfil próprio para hand tracking, evitando conflitos e cliques duplicados. Portanto, um driver novo não deve apenas fingir ser Knuckles.

## Testar agora no Windows sem headset e sem Unity

Para testar a funcionalidade nativa do cliente, separadamente do projeto:

1. Feche nosso aplicativo e outros programas que usam a webcam, para evitar disputa de captura.
2. Abra VRChat Steam em desktop. No menu principal, vá a **Settings → Tracking & IK**.
3. Ative **Enable Selfie Expression** e selecione a webcam correta.
4. Escolha **Balanced**, High Quality ou Best Quality. **Performance desativa hand tracking.**
5. Ative **Selfie Expression Also Moves Hands**.
6. Observe o avatar no espelho e teste cabeça, braços, mãos e cada dedo, com boa iluminação e enquadramento. A wiki indica webcam com suporte a proporção 4:3; experimente 640×480 quando houver escolha.

A wiki descreve o recurso para upper body; isso não é rastreamento confirmado de quadris/pernas. O comportamento depende do avatar e das opções de qualidade. Não é necessário assinar VRC+ para o recurso já liberado a todos.

Não testar simultaneamente duas aplicações disputando a mesma webcam. Uma combinação de corpo do nosso MediaPipe com Selfie Expression não foi validada; deve investigar disponibilidade de captura e compatibilidade de IK antes de propor divisão de câmera ou instalar software adicional.

## Validação do nosso OSC corporal: próximo experimento

Atualização do diagnóstico no desktop: o usuário encontrou modelos de tracker e espelho/configurações de calibração, não o botão que inicia FBT. A wiki Settings explicitamente restringe esse bloco ao modo VR. Portanto, não continuar pedindo tentativas nesse menu como se fosse apenas uma calibração esquecida. O remetente OSC ampliado não é uma integração de corpo inteiro validada para desktop sem headset. Avaliar modo VR com HMD real ou virtual exige uma etapa própria; o HMD virtual de desenvolvimento ainda não foi implementado/validado por este projeto.

Sem alterar o cliente ou o avatar, usar OSC Debug para conferir recepção dos endereços corporais já emitidos pelo backend. Confirmar separadamente: recepção, modelos de trackers, disponibilização de Calibrate FBT, alinhamento, movimento do avatar e perda/recuperação. Registrar versão do cliente e modo desktop/VR em cada tentativa. Receber pacotes não prova que IK os aplicou.

Antes de ampliar de três para oito trackers: verificar escala/calibração, transformar posições corretamente, respeitar validade por ponto e medir estabilidade. Não publicar todos automaticamente. Dedos continuam exigindo escolher uma interface que os suporte de fato.

## Fontes principais

- [Índice oficial completo](https://docs.vrchat.com/llms.txt).
- [OSC Trackers](https://docs.vrchat.com/docs/osc-trackers).
- [Lançamento do OSC corporal — 2022.4.1p3](https://docs.vrchat.com/docs/vrchat-202241p3).
- [OSC Avatar Parameters](https://docs.vrchat.com/docs/osc-avatar-parameters).
- [OSC Input](https://docs.vrchat.com/docs/osc-as-input-controller).
- [OSC Debugging](https://docs.vrchat.com/docs/osc-debugging).
- [OSCQuery](https://docs.vrchat.com/docs/oscquery).
- [Full-Body Tracking](https://docs.vrchat.com/docs/full-body-tracking) e [IK 2.0](https://docs.vrchat.com/docs/ik-20-features-and-options).
- [SteamVR Input 2.0](https://docs.vrchat.com/docs/steamvr-input-20).
- [Guia oficial de drivers esqueléticos](https://github.com/vrchat-community/creator-docs/blob/main/Docs/docs/platforms/pc/steamvr-drivers.md).
- [Selfie Expression — wiki oficial](https://wiki.vrchat.com/wiki/Selfie_Expression).
- [Estreia PC — 2025.1.3](https://docs.vrchat.com/docs/vrchat-202513).
- [Liberação para todos — 2025.3.2p1](https://docs.vrchat.com/docs/vrchat-202532p1).
- [Atualização atual de face tracking — 2026.4.1](https://docs.vrchat.com/docs/vrchat-202641): não confundir o novo OSC de expressões faciais com ossos dos dedos.

## Limites da auditoria

Documentação é evidência de interface suportada, não substitui execução no computador do usuário. Algumas páginas conservam trechos históricos/desatualizados; por isso foram cruzadas com notas posteriores. Não foi confirmado corpo inteiro OSC no desktop, native Selfie Expression no computador do usuário ou driver/HMD virtual. Nenhuma nova integração foi declarada concluída ou aprovada para merge.
