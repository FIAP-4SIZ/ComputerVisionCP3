# Análise com enquadramento parcial

Somente análise funciona sem calibrar: peito/ombros, braços presentes, pessoa sentada e corpo inteiro são observados no plano da imagem. O estado abaixo dos trackers diferencia peitoral, corpo completo, enquadramento parcial e ausência de pontos. O esqueleto só desenha pontos com coordenadas finitas, visibility suficiente e x/y dentro de [0,1]. Braços são independentes. Nenhuma coordenada oculta é inventada.

`bin/body_observation.py` filtra os 33 pontos normalizados de Pose e agrupa ombros, braços, quadris, joelhos e pés. A inclinação entre ombros é calculada no plano normalizado, não é orientação 3D nem medida de profundidade. `bin/mediapipepose.py` aplica a observação a câmera e vídeo no mesmo laço, preservando os cálculos existentes dos trackers. `bin/inference_gui.py` esclarece que a calibração VR continua exigindo corpo inteiro. Não foi relaxada a validação 3D.

Conceitos: coordenadas normalizadas, níveis de visibilidade, pontos de referência e conexões de esqueleto. Uma câmera só pode observar a área enquadrada. O tórax não fornece medição das pernas. A presença dos ombros é um indicador de enquadramento, não uma classificação de postura.

Teste: execute com backend Somente análise, câmera 0 (ou vídeo). Mostre só os ombros/peito, acrescente os braços, oculte uma mão, afaste-se até mostrar pés. Confira estados, ausência de conexões com pontos ocultos e recuperação. Não precisa clicar em calibrar. O desenho mudou; os trackers e a calibração corporal mantêm suas restrições anteriores. Sem pose estimada pelo modelo, não haverá pontos.

Validação automatizada Linux: 118 testes aprovados (9 novos), incluindo ausência de pose, peitoral, oclusão/recuperação, limites da imagem, valores inválidos, desenho e regressão do pipeline da câmera. Dependências e compilação aprovadas. Testes reais anteriores do Windows pertencem à versão anterior: este código precisa de novo build/teste Windows. Câmera física e VR continuam pendentes; não há aprovação de merge. Não se mediu ganho de precisão.
