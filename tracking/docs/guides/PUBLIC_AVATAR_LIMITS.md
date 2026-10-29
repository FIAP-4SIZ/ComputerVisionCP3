# Avatar público no desktop: escopo confirmado

O usuário confirmou pulo por gesto no VRChat Steam Windows, sem headset, após ativar OSC. A escolha é continuar com avatar público, sem Unity. Nesse cenário, o aplicativo pode enviar comandos de jogo suportados, como `/input/Jump`. Não pode instalar animações no avatar público, animar livremente cada osso/dedo ou esconder sua malha quando a câmera perde um ponto. Um tracker OSC ou parâmetro customizado de dedos não converte automaticamente um avatar público em full body tracking desktop.

A regra solicitada de não mostrar posições inválidas é aplicada ao envio: não comandar o jogo com dados rejeitados. Não significa fazer um membro do avatar desaparecer. Um avatar próprio pode respeitar `Tracked=false` para retornar às suas animações ou alternar objetos; um avatar público sem acesso ao projeto não pode receber essa configuração do aplicativo Python.

## Proteções adicionais

- Perder pontos durante um gesto libera o botão e desarma a ação. Recuperar a pose com braços ainda levantados não dispara outro pulo: abaixar os braços válidos é necessário para rearmar.
- O pulso de pulo também é liberado pelo relógio do laço, sem depender de outro quadro recebido.
- Sem novos quadros por dois segundos, a aplicação suspende flags de mãos, descarta calibração anterior e expira estado local dos trackers uma vez por interrupção. O limite evita invalidar imediatamente câmeras lentas; não mede a qualidade de cada pixel.
- Antes do envio dos dedos, NaN/infinito, valores fora de [0,1], dedos faltantes e lado incoerente resultam em `Tracked=false`, sem flexões daquele quadro.

Isso não elimina todos os falsos positivos do modelo. Pausa do processo inteiro, inferência nativa bloqueada ou perda UDP podem impedir a liberação no receptor. O protocolo de trackers corporais existente não garante remover imediatamente uma pose antiga no SteamVR/VRChat. Não foi inventado um comando de desativação que o receptor não suporta.

Código em `bin/freshness.py`, `bin/desktop_osc.py`, `bin/finger_tracking.py` e `bin/mediapipepose.py`. Regressões em `tests/test_invalid_tracking_guard.py`. Teste físico: acione um pulo, esconda os braços e reapareça com eles levantados; não deve haver novo pulo até abaixar e levantar novamente. Pause e retome; confira se não há botão preso. Simule ausência de quadros sem desligar o processo; o estado deve suspender após o limite.

O objetivo de rastreamento corporal/dedos completo permanece incompatível com as restrições de avatar público e ausência de Unity neste modo desktop. Não foi declarado implementado. O próximo passo depende de mudar essa restrição ou escolher explicitamente mais comandos desktop, com critérios de detecção e validação próprios.
