# Relatório de validação e integração

## Feature de vídeo

Repositório de entrega: `FIAP-4SIZ/ComputerVisionCP3`. Branch `feature/video-input`. Importação da base é um pré-requisito: este repositório continha somente README, que foi preservado e recebeu apenas uma seção de navegação. A licença MIT e a origem dos arquivos estão registradas em `DEVELOPMENT.md`.

Implementado: câmera/arquivo na GUI, seleção local, backend sem VR, processamento sequencial sem descarte de frames de arquivo, timestamps monotônicos com fallback sinalizado, progresso, pausa/retomada/reinício/cancelamento, tratamento de EOF/erros/ausência de pessoa e encerramento dos recursos. O pipeline de inferência e transformação é o mesmo da câmera. A revisão corrigiu também a pausa que chegava entre leitura e análise.

Arquivos principais: `bin/video_source.py`, `bin/mediapipepose.py`, `bin/helpers.py`, `bin/init_gui.py`, `bin/inference_gui.py`, `bin/parameters.py` e `bin/backends.py`. Specs, documentação, testes e CI atualizados no mesmo branch.

Validação executada:

| Verificação | Resultado |
|---|---|
| Suíte da base importada | 8 aprovados antes da implementação |
| Suíte final de vídeo | 29 aprovados, zero falhas e zero skips |
| OpenCV + MediaPipe reais | AVI gerado, leitura sequencial e ausência de pessoa; laço da aplicação com controles e GUI substituída |
| Regressão geométrica | 29 posições e três quaternions iguais ao original no cenário da fixture |
| Dependências | `pip check` aprovado |
| Sintaxe | `compileall` aprovado |
| Espaços/conflitos no diff | `git diff --check` aprovado |
| Build e runtime Linux | PyInstaller concluído; executável com `--check-runtime` aprovado com inferência real |
| Windows | Não executado nesta máquina Linux; CI configurada |
| Lint/tipagem | Não havia ferramentas configuradas; não apresentados como aprovados |
| Desktop real, câmera física e VR | Não executados; sem display, dispositivo de vídeo, SteamVR ou VRChat |

As falhas encontradas no build herdado foram investigadas: paths fixos da antiga CI e bibliotecas Tcl/Tk não coletadas no Python standalone. As specs passaram a localizar módulos/modelos/templates e bibliotecas no ambiente ativo. O teste `--check-runtime` faz inferência real no executável sem exigir webcam ou janela.

A API do GitHub retornou `Forbidden` ao consultar execuções de Actions. Publicar um branch não é evidência de execução ou aprovação da CI. Os resultados Windows precisam ser verificados por alguém com acesso às execuções.

O experimento antigo `bin/tests/pipetest.py` não foi executado: exige driver/SteamVR e contém `assert 0` incondicional. Não foi removido, desabilitado nem contabilizado como teste aprovado. Testes novos usam mocks para esse equipamento e exercitam o decoder e a inferência reais onde possível.

**Integração bloqueada:** não foi feito merge, nem atualização de `main`/`develop`. Windows e validações com equipamento permanecem pendentes. Commits e branches publicados para revisão não representam aprovação de integração.

Próxima melhoria definida pelo diagnóstico: validação de visibilidade/coordenadas/rotações, em `feature/pose-validation`, sem adicionar outro filtro. A política inicial deve ser simples e explicável antes de avaliar uma retenção independente por tracker.
