# SteamVR: corpo e dedos sem headset físico — diagnóstico

> Atualização: veja a [auditoria oficial](VRCHAT_OFFICIAL_RESEARCH.md). OSC Trackers corporal não exige avatar customizado; Selfie Expression oferece mãos/dedos nativos no desktop. Nossos parâmetros MP_* são outra interface. Não generalizar suas limitações para todo o VRChat.

Alvo escolhido pelo usuário: SteamVR e VRChat, com investigação de HMD virtual de desenvolvimento. O pulo OSC desktop já foi confirmado; não é evidência de full body tracking ou dedos via SteamVR. Não há suporte completo implementado nesta etapa.

## O que existe e o que falta

| Componente | Estado confirmado no código |
|---|---|
| Corpo MediaPipe | Landmarks e validação por tracker, com dependências e calibração |
| Bridge SteamVR atual | addtracker/updatepose/getdevicepose; trackers rígidos |
| Mãos atuais no bridge | Posição/orientação dos punhos; não são dedos articulados |
| Dedos MediaPipe Hands | 21 pontos e flexões; hoje publicados como parâmetros OSC customizados, não esqueleto SteamVR |
| HMD do bridge | Adição de HMD está comentada no VRDriver.cpp inspecionado; não presumir HMD virtual operacional |
| SteamVR Skeletal Input | Exige componentes e transforms de ossos no driver; não implementado pelo protocolo textual atual |
| Invalidar no receptor | Exige poseIsValid/result no driver e política de timeout; parar de enviar não equivale a remover uma pose antiga |

## Primeira verificação no Windows

Instale SteamVR pela biblioteca da Steam e execute-o uma vez. Sem headset, ele pode apresentar “headset não encontrado”: isso não confirma falha da webcam. Não instale um driver aleatório ou sobrescreva configurações globais. Do checkout deste branch, pasta tracking:

```cmd
..\.venv\Scripts\python.exe tools\check_steamvr.py
```

O diagnóstico lê `%LOCALAPPDATA%\openvr\openvrpaths.vrpath`, aponta runtime, binários, presença do driver null e manifests externos. Não inicia SteamVR, instala drivers, grava configurações ou envia poses. Presença de driver_null.dll não significa que foi ativado ou que VRChat aceitará esse ambiente. Se o arquivo estiver em outro local, passe `--paths "caminho"`.

Compatibilidade Windows: `external_drivers: null` é aceito como nenhum addon externo, assim como campo ausente ou `[]`. A versão anterior rejeitava esse formato com “Lista inválida: external_drivers”. Não edite o arquivo OpenVR para contornar isso; atualize o diagnóstico. Strings/objetos/booleanos nesse campo continuam inválidos e a mensagem informa o tipo encontrado.

Envie o resultado para definirmos o próximo passo concreto. Não precisamos de credenciais Steam/VRChat. O computador na nuvem não tem SteamVR/HMD; mocks e builds não comprovam compatibilidade com o cliente.

## Plano de integração, em branches separados

1. Validar um HMD virtual de desenvolvimento na instalação detectada: pose válida, origem, altura e renderização. Preparar alteração revisável e backup/rollback antes de aplicar configurações no Windows. A cabeça virtual é referência simulada, não uma medição real da cabeça.
2. Adicionar driver com controladores esquerdo/direito e Skeletal Input, usando exemplos/documentação oficiais Valve. Precisamos de fonte, licença, versão OpenVR e build Windows reproduzível. Não enviar comandos de esqueleto fictícios ao bridge antigo.
3. Definir contrato Python→driver: posições/rotações dos trackers, dados das mãos, timestamps, validade e expiração. Dispositivo perdido deve ser marcado inválido pelo driver; não reter a última pose como se fosse observada.
4. Converter os 21 pontos Hands à hierarquia esperada do SteamVR. Origem, eixos, unidades, orientação e ossos auxiliares precisam ser explicitados. O guia de drivers do VRChat cita MediaPipe hand tracking como exemplo possível de VRSkeletalTracking_Full: essa classificação descreve o esqueleto fornecido, não uma garantia de precisão ou medição real de profundidade. Atribuir o nível conforme os dados efetivamente fornecidos, não apenas para habilitar recursos. Não inventar confiança individual que Hands não fornece.
5. Testar calibração de corpo, papéis dos dispositivos, ossos de cada dedo e perda/recuperação primeiro no SteamVR, depois no VRChat iniciado em VR. A versão do cliente, bindings, avatar e ambiente virtual podem limitar o resultado.

Python/OpenCV/MediaPipe permanecem responsáveis pela visão. O driver necessário é uma camada C++ de integração OpenVR, não uma rede neural nova. Será uma parte adicional que precisa ser explicada separadamente no trabalho acadêmico.

## Referências inspecionadas

- [Bridge utilizado originalmente](https://github.com/ju1ce/Simple-OpenVR-Bridge-Driver): protocolo e HMD comentado no início de VRDriver.cpp. Arquivos externos não foram copiados para o projeto nesta etapa.
- [API oficial de drivers OpenVR](https://github.com/ValveSoftware/openvr/blob/master/docs/Driver_API_Documentation.md): CreateSkeletonComponent, UpdateSkeletonComponent e validade das poses.
- [Exemplo Valve de simulação de esqueleto](https://github.com/ValveSoftware/openvr/tree/master/samples/drivers/drivers/handskeletonsimulation): exemplo de driver, não rastreamento de câmera pronto nem integração já validada com VRChat.

Não foi aprovado merge. Rastreamento completo só poderá ser declarado funcional depois da execução real dessas verificações no ambiente do usuário.
