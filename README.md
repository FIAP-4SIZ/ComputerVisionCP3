# ComputerVisionCP3 — rastreamento de movimento

Projeto acadêmico FIAP 4SIZ com Python 3.12, OpenCV e MediaPipe: análise por câmera ou vídeo, observação de partes do corpo e flexão dos dedos para parâmetros de avatar VRChat via OSC. Derivado da aplicação MIT de [ju1ce](https://github.com/ju1ce/Mediapipe-VR-Fullbody-Tracking); [licença preservada](tracking/LICENSE).

**Protótipo experimental.** O código das melhorias está em branches de funcionalidades e PRs em rascunho. `main` e `develop` não recebem features com validações pendentes. CI aprovada não comprova funcionamento com webcam, SteamVR ou avatar real.

Para VRChat Steam **sem headset**, consulte primeiro o [modo desktop e teste de pulo](tracking/docs/guides/VRCHAT_DESKTOP.md).

## Começar

Instale Python **3.12** de 64 bits. Python 3.14 não é compatível com as dependências fixadas. A partir da raiz do repositório:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r tracking/requirements.txt
.venv/bin/python tracking/run.py
```

No Windows (CMD):

```cmd
py -3.12 -m venv .venv312
.venv312\Scripts\python.exe -m pip install -r tracking\requirements.txt
.venv312\Scripts\python.exe tracking\run.py
```

Também é possível executar `tracking\install_libraries.bat` e depois `tracking\mediapipepose.bat`. O instalador usa `.venv312` e preserva outros ambientes. Não é necessário executar como administrador nem mudar a política do PowerShell. Para empacotar, use [requirements-build.txt](tracking/requirements-build.txt).

Na primeira tela, escolha **Somente análise**, câmera **0** ou **Arquivo de vídeo**, e **Salvar e continuar**. Peitoral/partes do corpo podem ser analisados sem calibração de corpo inteiro. Para dedos, marque **Rastrear dedos**. A integração do avatar exige configurar os parâmetros OSC; não é automática.

## Recursos e limites

- Câmera ao vivo e vídeo sequencial com timestamps, progresso, pausa, retomada, reinício e cancelamento.
- Pontos visíveis e regiões parciais, com dependências verificadas antes de enviar trackers.
- Mãos independentes do corpo, cinco flexões por mão, confirmação temporal e rejeição de dados incoerentes.
- Ajustes opcionais de iluminação e comparação com a imagem original preservada.
- Telas Tk e interface web em português; formulários com rolagem para telas menores.
- SteamVR e OSC corporais preservados. A feature de dedos usa parâmetros customizados do avatar; não implementa esqueleto de dedos no driver SteamVR.

Uma câmera não mede profundidade real. Partes ocultas não devem ser tratadas como observações confiáveis. As regras de validação podem rejeitar movimentos reais; não há demonstração de ganho de precisão em usuários sem avaliação anotada.

## Encontrar arquivos e testes

| Pasta | Conteúdo |
|---|---|
| [tracking/bin](tracking/bin/) | Aplicação, fontes, validação, interfaces e backends; caminhos preservados |
| [tracking/tests](tracking/tests/) | Testes automatizados e fixtures de regressão |
| [tracking/tools](tracking/tools/) | Comparações, métricas e validação de widgets reais |
| [tracking/docs](tracking/docs/README.md) | Guias, arquitetura, relatórios e referências históricas |
| [tracking/evaluation](tracking/evaluation/) | Resultados experimentais, sem vídeos pessoais |
| [tracking/examples](tracking/examples/README.md) | Experimento manual legado de SteamVR, separado da suíte |
| [.github](.github/) | CI Linux/Windows e modelos de revisão/relato |

```bash
cd tracking
python -m unittest discover -s tests -v
python -m pip check
python -m compileall -q bin tools tests run.py
```

Consulte o [guia de documentação](tracking/docs/README.md), o [fluxo de branches](DEVELOPMENT.md) e o [relatório de validação](tracking/docs/reports/VALIDATION_REPORT.md). A [proposta acadêmica original](tracking/docs/reference/ACADEMIC_PROPOSAL.md) e o [README de origem](tracking/docs/reference/UPSTREAM_README.md) estão preservados como histórico, não como instruções atuais.

**Integrantes:** Mauro rm553574, Lucas rm552877, Fernando rm553499.
