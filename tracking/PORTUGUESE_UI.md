# Interface em português e telas menores

A configuração inicial, ajustes durante a execução, rótulos das mãos, estados do vídeo, título da janela OpenCV e interface web foram traduzidos para português. SteamVR, VRChat, OSC, nomes de parâmetros e rotas permanecem iguais para preservar compatibilidade. As mensagens das bibliotecas externas e os botões nativos do seletor de arquivos seguem o idioma do sistema/biblioteca. No desenho OpenCV, alguns textos usam português sem acentos por limitação da fonte Hershey; widgets Tk e HTML usam UTF-8.

As duas telas Tk usam `bin/scrollable_panel.py`: rolagem vertical/horizontal, roda do mouse, trackpad e Page Up/Page Down. Assim é possível acessar os controles inferiores sem depender da altura total do formulário. Os campos e callbacks existentes são preservados. A interface web declara `lang=pt-BR` e mantém os contratos HTTP anteriores; os endereços OSC e chaves de configuração não foram traduzidos.

Arquivos: `bin/init_gui.py`, `bin/inference_gui.py`, `bin/scrollable_panel.py`, `bin/templates/index.html`, `bin/webui.py`, `bin/video_source.py`, `bin/finger_tracking.py`, `bin/frame_metrics.py` e títulos/mensagens em `bin/mediapipepose.py`. Testes e ferramenta desktop foram atualizados para os novos rótulos.

Validação local: 149 testes aprovados (4 novos), controles HTTP Flask reais via cliente de teste, persistência e pipeline anteriores preservados. Widgets reais Tk/OpenCV em Xvfb aprovados; área solicitada 715×866 no display 1920×1200. Em janela redimensionada para 640×480, foi possível rolar até Sair; roda do mouse verificada. Sem teste de usabilidade, acessibilidade assistiva ou DPI no Windows nesta versão. Lint/tipagem não configurados; hardware continua pendente. Não há aprovação de merge.

Execute `python tools/validate_desktop.py` a partir de tracking com display disponível para repetir; não usa webcam ou headset. Teste também configuração avançada, vídeo, parâmetros das mãos e interface web no seu Windows. O guia das mãos explica os parâmetros de validação e os limites de movimento/enquadramento.
