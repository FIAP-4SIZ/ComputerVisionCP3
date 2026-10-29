# Confiabilidade e enquadramentos parciais

## Problema e mudança

Antes o desenho filtrava pontos fora do quadro, mas a validação VR só olhava coordenadas espaciais/visibility. Agora `prepare_trackers` também recebe landmarks normalizados da imagem: cada dependência precisa estar dentro do quadro, ter coordenadas finitas e atingir o limiar na imagem e na pose espacial. Ponto não observado invalida apenas os trackers dependentes. Sem imagem, nenhuma estimativa espacial do laço é enviada. As funções matemáticas antigas continuam aceitando chamadas sem imagem para compatibilidade; a aplicação sempre fornece essa informação.

O enquadramento distingue cabeça, peitoral, tronco, braços e pernas/quadris. São grupos de pontos observados, não classificação de postura: pernas fora da imagem não comprovam que a pessoa está sentada. Ombros/peito sem pernas funcionam em Somente análise; mãos e dedos via OSC continuam independentes dos quadris. Enviar quadris/pés ou calibrar escala requer suas dependências observáveis.

## Inventar menos posições de mãos

Hands continua estimando pontos, inclusive sob oclusão; nenhuma regra simples garante ausência de falso positivo. A classificação esquerda/direita não é confiança individual das articulações. Foram adicionadas regras conservadoras, sem novo modelo:

- Pontuação mínima de lateralidade 0,75, além da validação de coordenadas.
- Palma com largura de pelo menos 12 pixels e área não degenerada.
- Segmentos não colapsados e proporções grosseiramente coerentes em relação à palma estimada.
- Duas detecções plausíveis com o mesmo lado são ambíguas: rejeitar o lado, em vez de escolher arbitrariamente.
- Dois quadros consecutivos antes de ativar uma mão. Perda, pausa, espelhamento ou ajuste reiniciam essa confirmação.
- Salto do punho maior que 2,5 larguras de palma entre quadros exige nova confirmação. O ponto candidato é atualizado, permitindo recuperar em nova posição sem congelar para sempre.

Pontuação, tamanho mínimo, quadros de confirmação e salto máximo são ajustáveis na interface com dedos ativados; ficam em `saved_params.json`. Dados inválidos não mudam a configuração anterior. Não se aplicou outro filtro de suavização.

Custo: operações sobre 21 pontos por mão, além do mesmo detector Hands. Confirmação acrescenta `(N-1)/FPS` segundos antes da primeira aceitação: por exemplo, N=2 a 30 FPS acrescenta aproximadamente 33 ms; o FPS real deve ser medido. Movimentos rápidos, mãos pequenas/de perfil e mudanças fortes de iluminação podem ser rejeitados. Diminuir a confirmação ou aumentar salto facilita movimentos rápidos, mas pode aceitar mais falsos positivos. `Tracked=false` exige que o avatar respeite o contrato OSC já documentado.

## Arquivos

`bin/independent_trackers.py` cruza imagem e estimativa espacial. `bin/body_observation.py` reconhece grupos parciais. `bin/hand_quality.py` concentra regras e parâmetros. `bin/finger_tracking.py` confirma detecções e recupera perdas. `bin/parameters.py` valida/persiste opções e `bin/inference_gui.py` permite ajustá-las. `bin/mediapipepose.py` conecta os mesmos controles para câmera e vídeo. Testes existentes tiveram suas imagens sintéticas completadas; fixtures matemáticas originais e comparações de coordenadas foram preservadas.

## Comparação e validação

| Mesmo cenário controlado | Antes | Agora |
|---|---|---|
| Tornozelo fora da imagem, visibility espacial alta | Poderia enviar pé estimado | Pé rejeitado; quadril e outro pé continuam se válidos |
| Estimativa espacial sem pose na imagem | Poderia enviar trackers | Nenhum tracker aceito |
| Detecção de mão isolada em um quadro | Ativava imediatamente | Aguarda confirmação ajustável |
| Duas mãos com mesmo lado | Escolhia maior score | Lado rejeitado como ambíguo |
| Salto grande do punho | Enviava imediatamente | Reconfirma e permite recuperação |

A tabela descreve casos automatizados, não acurácia medida em pessoas. Suíte Linux: **145 testes aprovados**, incluindo 11 novos; dependências, compilação e GUI real em Xvfb aprovadas. A configuração das mãos aumenta o tamanho de conteúdo da GUI para 624×1080 no display 1920×1200; a etapa de interface deve fornecer rolagem para telas menores.

Ensaio MediaPipe real com a imagem pública `right_hands.jpg` já documentada em VRCHAT_FINGERS.md: a imagem inteira contém duas mãos direitas, corretamente rejeitadas por ambiguidade. No recorte da metade esquerda (360×382), sequência de três inferências estáticas: primeira não aceita, segunda e terceira aceitam mão direita, pontuação 0,9806. Repetir imagem estática não valida movimento, jitter ou oclusão real. Nenhum ganho de precisão é afirmado.

No Windows, execute a suíte e reconstrua o executável. Repita câmera/vídeo com: tronco, cabeça, só um braço, uma mão escondida, mãos cruzadas, entrada/saída do quadro, diferentes distâncias e movimentos rápidos. Compare falsos positivos anotados, detecções perdidas, FPS e atraso sob as mesmas condições. Hardware/avatar e nova validação Windows continuam pendentes; sem merge aprovado.

Para apresentar: “Separei pontos observáveis de estimativas espaciais. Validei dependências por tracker e confirmei as mãos ao longo de quadros, sem criar articulações ausentes. As regras reduzem certos envios inconsistentes nos testes, mas têm custo em rejeições e atraso; precisão real depende de avaliação anotada.”
