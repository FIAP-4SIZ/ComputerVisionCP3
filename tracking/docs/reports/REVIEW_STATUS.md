# Revisão e integração no GitHub

Todos os commits estão em FIAP-4SIZ/ComputerVisionCP3. Os PRs são rascunhos, comparados com a base imediatamente anterior para não misturar os diffs das features:

| PR | Branch | Base |
|---|---|---|
| [1](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/1) | feature/video-input | develop |
| [2](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/2) | feature/pose-validation | feature/video-input |
| [3](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/3) | feature/per-tracker-validation | feature/pose-validation |
| [4](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/4) | feature/lighting-comparison | feature/per-tracker-validation |
| [5](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/5) | feature/desktop-validation | feature/lighting-comparison |
| [6](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/6) | feature/partial-body-analysis | feature/desktop-validation |
| [7](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/7) | feature/vrchat-fingers | feature/partial-body-analysis |
| [8](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/8) | feature/observed-pose-validation | feature/vrchat-fingers |
| [9](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/9) | feature/portuguese-ui | feature/observed-pose-validation |
| [10](https://github.com/FIAP-4SIZ/ComputerVisionCP3/pull/10) | feature/repository-organization | feature/portuguese-ui |

Novos commits: `a474140` (confiabilidade), `c9a230e` (interface), `29b8234` (organização), seguidos da correção UTF-8 e do relógio determinístico da comparação legada. Consulte o histórico do PR para os hashes finais e seus checks; não transferir aprovação de um commit para outro sem verificá-los.

CI de confiabilidade e interface já confirmada em Ubuntu/Windows no [relatório](VALIDATION_REPORT.md). A primeira CI da organização identificou leitura CP1252 no teste de links; foi corrigida e a execução seguinte também revelou relógio de FPS intermitente na fixture legada em Windows, corrigido no teste sem modificar a fixture. Conferir a nova execução antes de aprovar. A CI atual também testa o instalador/atalho CMD no Windows e widgets reais em display virtual Linux e disponibiliza artefatos do executável para teste manual; isso não substitui webcam/headset.

Nenhum merge para develop/main. Nenhum branch antigo removido, nenhum force-push, nenhuma alteração de branch padrão. Tópicos do repositório não puderam ser atualizados: a API respondeu HTTP 403, Resource not accessible by integration; a descrição não foi alterada após essa negativa. Os modelos de issues e PR estão versionados neste branch; sua exibição global no GitHub depende da integração na branch padrão.

Próxima validação: usar a versão atual no Windows com câmera/vídeo e avatar configurado, anotando rejeições, falsos positivos, FPS e atraso. Posteriormente, calibrar a flexão aberta/fechada por usuário com base nos dados, sem escolher ajustes só pela aparência.
