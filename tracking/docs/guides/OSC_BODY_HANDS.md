# MediaPipe → OSC → VRChat: corpo e dedos

Esta implementação amplia o **remetente Python**. Corpo usa OSC Trackers; dedos usam OSC Avatar Parameters. Receber um pacote não prova que o cliente aplicou IK/animações. Não há endpoint documentado de ossos dos dedos ou de punhos na API OSC Trackers.

## O que mudou e por quê

| Aspecto | Antes deste branch | Agora |
|---|---|---|
| Corpo | Quadril e dois pés | Os mesmos três; opção para peito, dois joelhos e dois cotovelos |
| Dedos | Dez flexões com nomes MP fixos | Dez flexões e até dez aberturas laterais; nomes/escalas configuráveis |
| Ausência | Validação de pontos e flags MP | Mantida; histórico dos novos trackers descartado na perda/pausa |
| Diagnóstico OSC | Teste de pulo | Monitor UDP local de endereços e últimos valores |
| Recursos | Socket OSC não fechado explicitamente | Fechamento idempotente no encerramento |

Nenhuma dependência nova. Câmera, vídeos sequenciais, pré-processamento opcional e imagem original continuam no pipeline existente. Os cinco trackers extras ficam **desligados por padrão**: a documentação recomenda validar quadril/pés antes de aumentar a quantidade. Não houve medição de melhoria de precisão.

## Configurar no Windows

Na pasta que contém seu clone, preserve seus arquivos locais e use o ambiente Python 3.12 já instalado:

```bat
git fetch origin
git switch feature/vrchat-osc-body-hands
cd tracking
..\.venv\Scripts\python.exe run.py
```

Se seu ambiente se chama `.venv312`, substitua `.venv` nos comandos. O executável construído de um branch antigo não contém estas alterações; execute o código acima ou refaça o build.

Na configuração:

1. Escolha a câmera correta ou um arquivo de vídeo.
2. Escolha **VRChat OSC**, IP `127.0.0.1`, porta `9000`.
3. Para dedos, ative **Rastrear dedos**. Perfil vazio usa MP; para outro contrato, selecione um JSON conforme a próxima seção.
4. Comece com três trackers. Depois de validar alinhamento/calibração, marque **OSC: incluir peito, joelhos e cotovelos** para avaliar os adicionais.
5. No VRChat, habilite OSC. Use OSC Debug para separar recepção de aplicação no avatar. Teste em mundo privado, diante do espelho, primeiro parado e depois com movimentos lentos.

Para corpo, não é necessário editar o avatar no Unity. Verifique no seu cliente a disponibilidade de **Calibrate FBT**, a identificação dos trackers e o alinhamento. IDs não são papéis fixos impostos pelo protocolo: a associação é feita na calibração. Caso o desktop sem headset não apresente esse fluxo, não declare FBT funcionando só porque OSC Debug recebeu dados. Esse modo ainda precisa ser validado no cliente do usuário.

### Recebo valores no OSC Debug, mas o avatar não se move

Recepção é uma etapa diferente da calibração/aplicação de IK. Em teste do usuário no desktop, a opção **Calibrate FBT** foi relatada como disponível, mas ainda não utilizada; isso não confirma movimento após calibração. Para investigar:

1. Confira **Rotação da imagem (horária)**. Pessoa e ambiente devem aparecer em pé. O padrão foi corrigido para `None` (sem rotação): `0` é a constante OpenCV para girar 90°. Instalações que já salvaram 90° conservam sua escolha; selecione explicitamente **0** na interface para corrigir, sem apagar outras configurações.
2. Enquadre quadril e pés para começar com os três trackers recomendados. `PD:expirado`/`PE:expirado` indica ausência de atualização válida dos pés. Valores antigos no console não provam que o tracker está sendo atualizado agora.
3. Ajuste escala/alinhamento no remetente quando necessário. **Recalibrar**, no aplicativo Python, não substitui a calibração do receptor.
4. No VRChat, feche o OSC Debug, clique em **Calibrate FBT**, confira as esferas e siga a confirmação exibida pelo cliente. A documentação oficial descreve confirmação com os dois botões Interact dos controles VR; não presumimos uma tecla equivalente no desktop sem verificar o que sua versão apresenta.
5. Só então teste o movimento. Registre se a calibração concluiu e quais regiões respondem. Se o desktop não fornecer confirmação utilizável, isso é uma limitação operacional a investigar; não será corrigida enviando mais trackers ou trocando os nomes MP.

Para dedos, valores `MP_*` no console também não comprovam que o avatar possui os parâmetros/animações correspondentes. Corpo calibrado e parâmetros de dedos são contratos independentes.

Para dedos, o avatar precisa **já possuir parâmetros e animações correspondentes**. Um avatar público preparado pode funcionar sem Unity do usuário. Um avatar público genérico não recebe novas animações por este programa. Na configuração OSC gerada pelo VRChat, confira os nomes/endereço de `input` e tipo `Float`/`Bool`; editar esse JSON não adiciona animações ao avatar. Selfie Expression é outra implementação, interna do VRChat, e pode disputar a webcam; feche-a durante este teste.

## Contrato corporal

| ID escolhido pelo remetente | Região/posição estimada | Pontos exigidos além dos dois ombros |
|---|---|---|
| 1 | Quadril do pipeline original | Quadris |
| 2 / 3 | Pé direito / esquerdo | Dependências originais por perna/rotação |
| 4 | Peito: 75% centro dos ombros + 25% centro dos quadris | Ambos os quadris |
| 5 / 6 | Joelho direito / esquerdo | Ambos os quadris e joelho/tornozelo do lado |
| 7 / 8 | Cotovelo esquerdo / direito | Cotovelo e punho do lado |

Cada ID recebe `/tracking/trackers/<id>/position` e `/rotation`, com três **floats**. Posições em metros estimados após escala; rotações em graus Euler ZXY convertidas ao referencial Unity. A referência `/tracking/trackers/head/position` continua em zero para o alinhamento relativo existente; não é rastreamento de cabeça nem substituição comprovada de HMD. Não anexamos timestamps extras a mensagens cujo contrato exige somente três números.

`osc_body.prepare_extra_trackers` verifica visibilidade na imagem e no mundo, enquadramento, valores finitos e geometria não degenerada. Aplica sinais e rotações na mesma ordem da pose original. Constrói eixos ortogonais usando direção do membro e largura dos ombros; se os eixos forem colineares, omite o tracker. Peito interpolado não é landmark medido diretamente. Com apenas braços visíveis, cotovelos podem ser enviados sem inventar quadris/pernas; só ombros não bastam para determinar orientação do peito.

`VRChatOSCBackend.updatepose` reúne os trackers válidos num único bundle corporal. Reutiliza a suavização exponencial de posições/âncora existente, sem outro filtro. Exemplo: peso antigo `w=0,7`, posição antiga `1`, atual `2` → `0,7×1 + 0,3×2 = 1,3`. Peso maior suaviza mais e atrasa mais. Rotações não receberam outro filtro.

## Contrato de mãos e perfil JSON

Por padrão, para cada lado `Left`/`Right` e dedo `Thumb`, `Index`, `Middle`, `Ring`, `Little`:

- `/avatar/parameters/MP_Left_Index`: flexão Float, `0` aberto e `1` flexionado.
- `/avatar/parameters/MP_Left_Index_Spread`: abertura lateral aproximada Float, `0..1`.
- `/avatar/parameters/MP_Left_Tracked`: Bool, válido/ausente; idem direita.

Todos os dez dedos têm canais independentes. Isso não equivale a enviar cada osso/articulação da mão, posição de punho ou esqueleto SteamVR. O avatar decide como animar cada valor. Modelos Hands e Pose processam a mesma imagem RGB; mãos não dependem de quadris visíveis.

Copie [o exemplo completo de vinte canais](../../config/osc-hands-example.json). Altere nomes, limites e escalas segundo o contrato real do avatar. Exemplo mínimo para um avatar que **já** reconheça `leftIndex` e `leftTracked`:

```json
{
  "channels": [
    {
      "side": "Left",
      "finger": "Index",
      "source": "curl",
      "address": "/avatar/parameters/leftIndex",
      "scale": -1,
      "offset": 1,
      "min": 0,
      "max": 1
    }
  ],
  "tracked": {"Left": "/avatar/parameters/leftTracked"}
}
```

Fontes permitidas: `curl` e `spread`. Conversão: `saída = limitar(entrada × scale + offset, min, max)`. Exemplo: flexão `0,25`, escala `-1`, deslocamento `1` → abertura `0,75`. Padrões: escala 1, deslocamento 0, limites 0..1. `tracked` é opcional por lado; `enabled` opcional especifica um endereço Bool global, verdadeiro enquanto alguma mão está válida. Só endereços de `/avatar/parameters/` são aceitos. Perfis com nomes desconhecidos, endereços repetidos, comandos `/input`, NaN ou limites invertidos são rejeitados antes da câmera/modelos.

No leapmotion-osc, nomes como `leftIndex` e `leftIndexSpread` são específicos daquele contrato. A flexão original usa distância ponta→palma; aqui usamos ângulos. Renomear os endereços não torna essas grandezas equivalentes. Ajuste/calibre as animações e o perfil com o avatar real. Não incluímos um falso perfil universal Leap Motion.

### Conceitos de visão computacional

Flexão usa segmentos dos 21 keypoints 3D estimados pela API Hands: soma de dois ângulos / 180°. Dois ângulos de 45° dão flexão `0,5`. Produtos escalares calculam ângulos; normalizar segmentos remove dependência de escala.

Abertura lateral projeta os vetores punho→base e base→articulação seguinte no plano da palma. O ângulo entre eles é dividido por 45° e limitado a 1: 22,5° → `0,5`. Cada dedo usa sua direção própria. Essa medida simples é não assinada e não reproduz os ângulos anatômicos de um sensor de mão; polegar/oposição merecem avaliação específica. Se a palma/projeção degenera (por exemplo, mão de perfil ou dedo dobrado perpendicular à palma), esse canal é omitido. Valores antigos podem permanecer no avatar se seu Animator não tratar perda/validade.

Isso aplica BGR→RGB, keypoints, confiança/lateralidade, coordenadas normalizadas para enquadramento, vetores 3D estimados para geometria e análise quadro a quadro. Não mede profundidade real nem adiciona um modelo treinado próprio.

## Perda, pausa e posições inválidas

Trackers inválidos não recebem novas posições; não são enviados zeros como se fossem uma medição. A perda limpa a suavização do tracker adicional; retorno começa com uma amostra nova. Pausa limpa histórico e suspende os parâmetros de mãos; fim/reinício/cancelamento e ausência de quadros recentes conservam as proteções existentes.

Mão ausente envia `Tracked=false`, sem publicar flexões inventadas. **O avatar precisa respeitar essa flag.** Um perfil sem flags ou um Animator que as ignore pode manter o último valor. A API OSC Trackers consultada não documenta comando por tracker para esconder/desativar imediatamente o dispositivo; parar de enviar não garante desaparecimento visual no jogo. Não enviamos NaN, zeros artificiais ou IDs diferentes para contornar isso.

## Testar os pacotes sem VRChat

Num terminal, a partir de `tracking/`:

```bat
..\.venv\Scripts\python.exe tools\monitor_osc_tracking.py --seconds 30
```

Em outro terminal, inicie `run.py` e use temporariamente porta **9002**. Mostre corpo/mãos; retire uma mão e esconda uma perna; pause/retome. O monitor apresenta contagens, últimos valores e `last_seen_seconds`, instante da última atualização relativo ao início da observação. `Tracked=false` deve aparecer na perda; o instante do tracker oculto deve ficar anterior aos trackers que continuam visíveis. `last_values` sozinho não distingue um valor antigo de uma atualização recente. Volte para **9000** para VRChat. O monitor não ocupa a porta do jogo e não encaminha pacotes. Sem pacotes ou com mensagens malformadas/valores fora do contrato numérico retorna código 1.

Testes automatizados:

```bat
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe -m pip check
..\.venv\Scripts\python.exe -m compileall -q bin tools tests run.py
```

Testes incluem UDP real, oito trackers, corpo e dedos no mesmo destino, perda/retorno, NaN, confidência baixa, fora de quadro, eixos degenerados, escala/transformações, perfis inválidos, flags, pausa da câmera, fechamento e regressões do pipeline original. Testes MediaPipe reais da suíte verificam inicialização e ausência de pessoa em quadros vazios; detecções positivas nos testes de contrato usam mocks. Não substituem validação com webcam/pessoa no jogo.

Foi executado também um [ensaio positivo com modelos e UDP reais](../../evaluation/osc_body_hands_integration.json), com as imagens públicas [pose.jpg](https://storage.googleapis.com/mediapipe-assets/pose.jpg) e [right_hands.jpg](https://storage.googleapis.com/mediapipe-assets/right_hands.jpg) do MediaPipe. Resultado: oito trackers (17 mensagens incluindo referência de cabeça), uma mão confirmada no segundo quadro repetido (12 mensagens incluindo flags) e flags falsas na suspensão. A imagem de mãos contém duas mãos direitas; o ensaio positivo recorta explicitamente a metade esquerda, sem alterar o arquivo original. As imagens são distintas e estáticas: não demonstra sincronia de uma pessoa, jitter, FPS de movimento ou precisão anatômica. Os SHA-256 completos constam no resultado; os arquivos de imagem não foram adicionados ao repositório.

Para reproduzir esse ensaio no CMD, em `tracking/`:

```bat
curl.exe --fail --location https://storage.googleapis.com/mediapipe-assets/pose.jpg -o "%TEMP%\osc-pose.jpg"
curl.exe --fail --location https://storage.googleapis.com/mediapipe-assets/right_hands.jpg -o "%TEMP%\osc-hands.jpg"
..\.venv\Scripts\python.exe tools\validate_osc_models.py --pose-image "%TEMP%\osc-pose.jpg" --hand-image "%TEMP%\osc-hands.jpg" --hand-left-half --output "%TEMP%\osc-integration.json"
```

O programa não baixa arquivos automaticamente e falha se não detectar todos os oito trackers ou uma mão confirmada. Confira o hash antes de comparar resultados; nenhuma imagem de teste substitui sua webcam e seu avatar.

Para avaliar no VRChat, registre versão do cliente, desktop/VR, avatar e perfil, recepção no OSC Debug, associação/calibração corporal, cada dedo aberto/fechado e perda/retorno. Compare três e oito trackers no mesmo vídeo e com a mesma iluminação. Use FPS/tempos exibidos; não confunda tempo de um teste sintético sem inferência com FPS de webcam.

## Arquivos e apresentação acadêmica

- `bin/osc_body.py`: dependências visíveis, eixos e trackers adicionais.
- `bin/backends.py`: bundle corporal, suavização reaproveitada e socket.
- `bin/finger_tracking.py`: abertura lateral e publicação pelo perfil.
- `bin/osc_hands.py`: validação, transformação e nomes de parâmetros.
- `bin/mediapipepose.py`, `parameters.py`, `init_gui.py`: conexão com o laço/controles existentes.
- `config/osc-hands-example.json`: contrato editável completo.
- `tools/monitor_osc_tracking.py`, `tools/validate_osc_models.py`, `tools/validate_desktop.py`: diagnóstico, integração positiva e GUI real.
- `tests/test_osc_body_hands.py` e regressão em `test_independent_trackers.py`: verificações automatizadas.

Para apresentar: “MediaPipe estima keypoints em uma imagem RGB. Verifico enquadramento, visibilidade e geometria antes de converter a pose ao espaço do receptor. Corpo e dedos usam contratos OSC distintos. Reaproveitei o filtro exponencial, tornei o mapeamento dos dedos ajustável e testei os pacotes UDP e a perda de pontos. A validação da animação no VRChat depende da calibração e do suporte do avatar.”

Limitações/próximos trabalhos: calibrar escala e rotações com gravação de referência; medir jitter e atraso com pessoa real; validar oito trackers e desktop no VRChat; selecionar um avatar público com contrato conhecido; validar polegar e spread; investigar Skeletal Input para avatar genérico e posição/orientação das mãos. Não há driver SteamVR novo nesta feature. Consulte também a [auditoria das interfaces oficiais](VRCHAT_OFFICIAL_RESEARCH.md).
