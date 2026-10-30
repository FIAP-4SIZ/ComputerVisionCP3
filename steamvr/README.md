# Driver SteamVR de mãos MediaPipe

Camada OpenVR própria, separada da visão em Python. O repositório original
`ju1ce/Mediapipe-VR-Fullbody-Tracking`, commit
`789f8acd1525d6a2daad79ae82c4925f1e0cbc8c`, exigia headset/SteamVR ou VR via OSC.
Não fornecia dedos articulados. O bridge original
`ju1ce/Simple-OpenVR-Bridge-Driver`, commit
`e42e8354e297a2d36dfb5202271d5e6d3cdcedfd`, tem a criação do HMD comentada
em VRDriver.cpp e recebe poses rígidas, não os ossos de cada dedo.

Este driver acrescenta duas mãos com identificação própria
`fiap_mediapipe_hand`. Não se identifica como Index/Knuckles/Touch. Expõe
Skeletal Input de 31 ossos para a aplicação vincular às ações
`SkeletonLeftHand` e `SkeletonRightHand`; publica as faixas WithController e
WithoutController. O guia atual de drivers do VRChat cita MediaPipe como
fonte possível para Full, e desaconselha a falsa identificação de hardware.
Full é classificação da estrutura de dados; não significa profundidade medida.

A [integração Windows](../tracking/docs/guides/STEAMVR_WINDOWS.md) conecta
MediaPipe e driver, prepara HMD null de forma reversível e gera bindings a
partir do manifest de ações do VRChat. A referência do HMD virtual é simulada,
não a cabeça fisicamente medida de um usuário.

## Build e testes

Com CMake >= 3.20 e compilador C++17 (Windows: Visual Studio Build Tools com
Desktop development with C++; Linux: GCC):

```sh
cmake -S steamvr -B steamvr/build -DCMAKE_BUILD_TYPE=Release
cmake --build steamvr/build --config Release
ctest --test-dir steamvr/build -C Release --output-on-failure
```

Pacote em `steamvr/build/package/mediapipe_hands`; a CI publica
`steamvr-hands-Windows` e `steamvr-hands-Linux`. O SDK é somente o header
OpenVR pinado e sua licença, incluída no pacote. Nada é instalado/registrado
automaticamente ao compilar.

Os testes nativos verificam protocolo, NaN/Inf, quaternions, limites, perda,
sequência, reinício, wrap, timeout, comandos, socket real, colisão de porta,
handshake e fábrica/ABI da biblioteca compilada. Não simulam aprovação de
SteamVR/VRChat real. Sem runtime, não é possível confirmar ativação, bindings
ou movimento de avatar.

## Contrato Python → driver

UDP exclusivamente `127.0.0.1:39570`; não é OSC e não recebe na porta 9000.
Um datagrama por mão tem 916 bytes, little-endian explícito:

| Campo | Tipo |
|---|---|
| Magic `MPVRH001` | 8 bytes |
| Lado (0 esquerda, 1 direita) | uint32 |
| Sequência por mão | uint32 |
| Validade (0 ou 1) | uint32 |
| Pose relativa à cabeça: xyz, quaternion wxyz | 7 float32 |
| 31 ossos relativos ao pai: xyz, quaternion wxyz | 217 float32 |

Na perda, flag 0 invalida sem publicar zeros como posições medidas.
Pacote válido exige valores finitos, quaternion unitário e root identidade.
Limites: pose até 10 m por eixo e ossos até 1 m por eixo; limites de protocolo
e plausibilidade ampla, não avaliação de precisão. Após 500 ms sem pacote
aceito, `poseIsValid=false`. Repetidos/regressivos não renovam o timeout;
após expiração, sequência pode reiniciar. Wrap uint32 é aceito.

Posições de mão são relativas ao referencial de cabeça. O driver consulta
o HMD ativo para transladar à origem SteamVR. Sem HMD válido, as mãos ficam
inválidas. Não cria dedos a partir de curls nem inventa posição global de mão.

Controle explícito: `MPVRC001` + uint32 comando + uint32 valor. Comando 1
solicita pulso dos gatilhos por 0..500 ms; expira no driver independentemente
de novos pacotes. Só é aplicado a mão válida. Não há gesto automático de
clique. Comando 2/valor 0 retorna `MPVRA001`, versão uint32 1, máscara das mãos
válidas uint32 e flag HMD válido uint32. O handshake prova driver vivo,
não aplicação de IK pelo VRChat.

Comando 3/valor 0 consulta a matriz bruta 3×4 do HMD: `MPVRP001`, uint32
validade e 12 floats em ordem de linhas (60 bytes). O cliente usa essa referência
para manter a calibração de yaw/escala, em vez de inventar altura. Sem altura
válida positiva, autoescala é recusada. Comandos 1/2 e datagramas das mãos
mantêm o contrato anterior. Use o pacote atualizado para a consulta adicional.

## Integração e limites

É preciso registrar o pacote via `vrpathreg adddriver`, habilitá-lo em addons
SteamVR, fornecer um HMD real ou virtual e configurar os bindings do VRChat.
A camada Python fornece conversão das mãos e preparação reversível do HMD
null para desenvolvimento. Este componente sozinho não é um aplicativo de
rastreamento completo. No Windows a biblioteca e os testes usam CRT estático,
evitando exigir uma instalação adicional de runtime C++ no PC do estudante.

Corpo pode continuar por OSC Trackers, como na versão original alternativa,
com VRChat iniciado em VR. Dedos por Skeletal Input não dependem dos
parâmetros MP_* no avatar. Avatares precisam ter rig humanoide/mãos compatíveis.
O perfil não cria animações nem ossos ausentes num avatar.

Referências:

- https://github.com/ju1ce/Mediapipe-VR-Fullbody-Tracking
- https://github.com/ju1ce/Simple-OpenVR-Bridge-Driver
- https://github.com/ValveSoftware/openvr/blob/0924064316de3effbcd1acf1e309182a2deb1c05/docs/Driver_API_Documentation.md
- https://github.com/vrchat-community/creator-docs/blob/main/Docs/docs/platforms/pc/steamvr-drivers.md
