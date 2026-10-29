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

## Validação de poses

Branch `feature/pose-validation`, dependente do branch de vídeo, sem merge para `develop`. Implementa a prioridade já definida em `ESTUDO_PDI.md`; especificação e explicação acadêmica em `POSE_VALIDATION.md`.

Implementado: checagem dos 33 landmarks, coordenadas finitas, visibilidade nos pontos necessários, limiar ajustável/persistido, rejeição de geometria/quaternions inválidos, aviso e valores de visibilidade na imagem, invalidação de dados de calibração obsoletos e proteção dos backends. OSC inicia o histórico na primeira pose válida e preserva a fórmula de suavização existente; entradas rejeitadas não contaminam o histórico.

Arquivos principais: `bin/pose_validation.py`, `bin/mediapipepose.py`, `bin/backends.py`, `bin/parameters.py`, `bin/inference_gui.py`, `tests/test_pose_validation.py` e fixture de `tests/test_first_improvement.py`.

| Verificação | Resultado |
|---|---|
| Suíte completa após a melhoria | 48 aprovados, zero falhas e zero skips |
| Câmera: pipeline e falhas de leitura | Regressões automatizadas com hardware substituído |
| Vídeo: leitura, MediaPipe e controles | Integrações reais de decoder/inferência, GUI substituída |
| Histórico OSC e mensagens inválidas | Testes aprovados; respostas HMD inválidas também não geram trackers |
| Persistência do limiar | Teste de salvar/recarregar aprovado |
| Dependências, sintaxe e diff | `pip check`, `compileall` e `git diff --check` aprovados |
| Build/runtime Linux | PyInstaller e executável `--check-runtime` aprovados na revisão final, com inferência real |
| Windows, GUI física e VR | Pendentes; integração não aprovada |

Ensaio real adicional: 30 quadros do vídeo da aula retornaram pose e timestamps crescentes. Nenhum passou no limiar 0,5 para trackers, com os pés fora do enquadramento. É uma demonstração de rejeição conservadora; não é medição de precisão, jitter ou estabilidade em equipamento VR.

Próxima melhoria recomendada: validação e expiração independentes por tracker, para preservar quadril/pé visíveis durante oclusão localizada. Antes de implementá-la, verificar no receptor OSC e no driver o efeito de interromper cada tracker e definir o tempo máximo de retenção com testes de movimento.

O estado de integração permanece **bloqueado** pelos mesmos itens externos da feature de vídeo. Nenhum teste não executado foi considerado aprovado. Não houve merge para `develop` ou `main`.

## Histórico rastreável

Todos os commits desta entrega estão no repositório acadêmico:

- `f399d0c`: importa a base necessária, licença e regressões.
- `4c39eb6`: implementa arquivo de vídeo e controles com testes.
- `277bafa`: documenta o recurso, configura CI e corrige paths de empacotamento.
- `53b4166`: corrige a corrida de pausa, sinaliza timestamps estimados e registra resultados de vídeo.
- `e60c3ce`: valida poses, protege histórico/backends e inclui testes de confiança/protocolo.

O commit documental final registra este relatório e a especificação acadêmica. `feature/pose-validation` incorpora `feature/video-input` como pré-requisito; isso não é merge para `develop`. A branch `develop` não existia no remoto inspecionado e não foi criada/atualizada com alterações não aprovadas.

## Validação independente por tracker

Branch: `feature/per-tracker-validation`, baseada em `feature/pose-validation`, exclusivamente no repositório acadêmico. Especificação, conceitos de PDI, instruções e avaliação em `PER_TRACKER_VALIDATION.md`.

Escopo: quadril, pés e mãos possuem dependências e estados próprios. Um pé inválido não bloqueia os trackers que ainda possuem dados suficientes. O emissor nunca reenvia a posição antiga de um tracker perdido. O histórico OSC é independente e expira conforme prazo ajustável/persistido, com padrão zero (limpar ao observar perda). IDs, eixos e fórmulas de orientação foram preservados; slots SteamVR acompanham a ordem de criação, inclusive com quadril desabilitado. Preview do esqueleto completo mantém a validação conservadora.

| Verificação | Resultado nesta etapa |
|---|---|
| Suíte anterior antes das alterações | 48 aprovados |
| Suíte final | 83 aprovados, zero falhas e zero skips; 35 testes novos |
| Regressão das orientações | Referências do commit `968bbf1`, incluindo pernas retas e seus fallbacks |
| Regressão OSC com todos os trackers válidos | Mesmos valores da referência dentro da precisão do protocolo float32 |
| Oclusão em AVI real | Decoder real; inferência controlada; quadril/pé válido continuam, pé perdido é omitido e volta com histórico limpo |
| Integrações MediaPipe reais anteriores | Continuam executadas, com vídeo sintético sem pessoa |
| Transporte UDP local | Pacote real decodificado; endereço do pé inválido não é enviado |
| Estado e tempo | Perda, expiração no limite, precisão decimal, recuperação, reinício, EOF e entradas inválidas cobertos |
| SteamVR | Comandos verificados com driver substituído, incluindo mãos, quadril desabilitado e preview |
| Dependências/sintaxe/diff | `pip check`, `compileall`, `git diff --check` aprovados |
| Linux | Build PyInstaller e smoke do binário com inferência real aprovados |
| Windows, GUI real, câmera e VR | Não executados; pendências de integração |
| Lint/tipagem | Não configurados no projeto, não contabilizados como aprovados |

Inspeção do driver de referência `c440e117`: o argumento final `0.8` de `updatepose` é suavização, não TTL. A expiração implementada é local; não promete desativação imediata do avatar/receptor. Documentação oficial OSC retornou HTTP 403; consulta à API de Actions retornou `Forbidden`. Não se inferiu aprovação da CI a partir do push.

Commits desta melhoria:

- `1917fc2`: extrai cálculos independentes e adiciona referências congeladas de regressão.
- `a88dfb2`: implementa máscaras, estados, expiração, histórico independente, GUI e testes.
- O commit documental seguinte registra decisões e resultados finais.

**Sem merge para `develop` ou `main` e sem aprovação de integração.** Não foram medidos precisão, jitter ou FPS real; a comparação de oclusões usa entradas controladas. Após os testes com equipamento e a CI Windows, a próxima melhoria da lista é a comparação opcional de pré-processamento de iluminação, usando o mesmo vídeo e conservando a imagem original.

## Comparação opcional de iluminação

Branch `feature/lighting-comparison`, baseada em `feature/per-tracker-validation`, no repositório `FIAP-4SIZ/ComputerVisionCP3`. A etapa implementa a próxima melhoria já definida, com especificação, instruções e explicação acadêmica em `LIGHTING_COMPARISON.md`.

Escopo: original como padrão, brilho/contraste manual ou equalização de luminância sem combinação automática, preservação do BGR anterior ao ajuste, comparação visual e comparação offline dos mesmos quadros/timestamps. Não há nova dependência, filtro de ruído ou migração de API. A aplicação executa o MediaPipe apenas na entrada ativa; o painel original é explicitamente rotulado sem inferência. Ao mudar o ajuste efetivo, detector, históricos locais e janela de FPS são reiniciados; trocar só a visualização não provoca reset.

Arquivos principais: `bin/lighting.py`, `bin/mediapipepose.py`, `bin/parameters.py`, `bin/inference_gui.py`, `bin/video_source.py`, `tools/compare_lighting.py`, `tests/test_lighting.py`, `tests/test_lighting_comparison.py` e testes de persistência existentes. O relatório real do ensaio está em `evaluation/lighting_jeff_60.json`.

| Verificação | Resultado |
|---|---|
| Suíte anterior sem alterações | 83 aprovados |
| Suíte final | 109 aprovados, zero falhas e zero skips; 26 novos testes |
| Modo desligado | Pixels e conversão BGR/RGB preservados; regressões anteriores continuam aprovadas |
| Fórmula e histograma | Identidade, clipping, ausência de valor absoluto, equalização só de Y e não combinação de modos cobertos |
| GUI/configuração | Aplicação, erros, restauração, persistência e leitura de opções antigas/inválidas cobertas com widgets substituídos |
| Pipeline | Original intacto, uma inferência por quadro, pausa e reset de históricos/métricas quando necessário |
| Comparação offline | AVI real, detectores independentes, hashes de quadros/timestamps, EOF/prefixo, saída sem sobrescrita e falhas com liberação de recursos |
| MediaPipe real | Executado nos testes gerados e no vídeo da aula |
| Dependências/sintaxe/diff | `pip check`, `compileall` e `git diff --check` aprovados |
| Linux | Build PyInstaller e smoke do binário com inferência real aprovados na revisão final |
| Windows, GUI real, câmera e VR | Pendentes; sem aprovação de integração |
| Lint/tipagem | Não configurados; não contabilizados como aprovados |

Ensaio com os mesmos 60 quadros de `Jeff.mp4`, da referência acadêmica: SHA-256 do arquivo preservado e fingerprints dos quadros/timestamps idênticos. Brilho/contraste 1,2/+20 elevou os pixels com algum canal em 255 de 1,48% para 50,68%. Os três casos retornaram pose em 60/60 quadros, mas não produziram trackers válidos neste recorte sem pés enquadrados. A equalização também não demonstrou ganho de precisão; pequenas diferenças de visibilidade/FPS não são prova disso. Os tempos medidos e as limitações estão no relatório detalhado.

Commits de implementação:

- `f7b52a8`: controles, pré-processamento, original preservado e testes.
- `0e69c2b`: ferramenta de comparação, leitura sequencial sem espera e proteção dos arquivos.
- `a9a6c98`: reinicia a janela de métricas ao trocar a entrada de iluminação, sem reset ao mudar só a visualização.
- O commit documental final inclui o relatório experimental e os limites da integração.

**Integração bloqueada; nenhum merge para `develop` ou `main`.** Não há dispositivo de câmera, display ou Xvfb neste ambiente. A API do GitHub retornou `Forbidden` ao consultar Actions; não se inferiu aprovação da CI pelo push. O experimento manual de SteamVR continua não executado e não foi descrito como aprovado.

Próxima recomendação: obter vídeos de corpo inteiro com iluminação normal/escura/contraluz e referência anotada, repetindo o ensaio. Adotar um ajuste, ou acrescentar outra técnica, só depois de observar benefício medido para esse cenário.

## Validação posterior de desktop

Por autorização do usuário, `develop` foi criada/publicada a partir de `main` (`3732575`), sem merge de features. As afirmações anteriores sobre inexistência dessa branch descrevem o estado anterior.

Em `feature/desktop-validation`, foi adicionado `tools/validate_desktop.py`, que exige display e verifica widgets Tk reais e janela OpenCV real. Execução em Xvfb 1920×1200: controles aprovados, janela aprovada, layout 624×915 cabe na tela. A configuração inicial e os callbacks são automatizados; isso não equivale à execução completa com câmera/headset ou a teste Windows.

Suíte repetida: 109 testes aprovados sem skips. Dependências, compilação e smoke do binário Linux aprovados. Windows e webcam estão disponíveis no computador do usuário, mas aguardam resultados. VR não está disponível no equipamento informado. API de Actions segue negando a consulta. Roteiro e critérios em `DESKTOP_VALIDATION.md`.

**Nenhum merge para `develop`; integração não aprovada.**

Na tentativa Windows enviada pelo usuário, o ambiente foi criado com Python 3.14. A instalação falhou em `mediapipe==0.10.21`, seguida de oito erros de importação por dependências ausentes. Não houve execução funcional da suíte, build ou smoke Windows. Diagnóstico: pré-requisito de instalação; é necessário criar ambiente Python 3.12 separado e confirmar a instalação antes de repetir as etapas. O `pip check` sem conflitos dessa tentativa não foi contabilizado como validação do ambiente completo.

### Atualização: testes Windows aprovados

No log posterior fornecido pelo usuário, com Python 3.12.10: instalação concluída; 109 testes executados em 3,157 s com `OK`; `pip check` sem conflitos; build PyInstaller Windows concluído; executável com `--check-runtime` confirmou OpenCV, MediaPipe Pose e modelos disponíveis. Esses resultados substituem a pendência dos testes automatizados/build/runtime Windows, sem atribuir à nuvem sua execução.

A execução normal tentou conectar ao SteamVR e encerrou após dez tentativas, antes da captura. Próximo teste: câmera 0 com backend **Somente análise**. Ainda não há comprovação de imagem/landmarks da webcam, controles da aplicação completa no Windows, reprodução manual de vídeo ou recepção em VR. Os testes de componentes reais em Xvfb permanecem aprovados; CI remota não confirmada por falta de acesso à API. **Nenhuma feature integrada à develop; integração permanece bloqueada pelas validações pendentes.**
