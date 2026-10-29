# Aplicação de rastreamento

A [raiz do projeto](../README.md) contém instalação, execução e testes atualizados. Use `python tracking/run.py` da raiz ou `python run.py` desta pasta. O lançador resolve os módulos e mantém configurações relativas a esta pasta, mesmo quando iniciado de outro diretório.

Comece em **Somente análise**, câmera 0 ou arquivo de vídeo. Ative os dedos somente se precisar deles. A documentação está organizada no [índice](docs/README.md). Para VRChat, leia o [contrato dos parâmetros OSC dos dedos](docs/guides/VRCHAT_FINGERS.md); para evitar estimativas sem suporte, leia [confiabilidade e poses parciais](docs/guides/OBSERVED_QUALITY.md).

`bin/` permanece no caminho original para preservar imports, scripts e specs PyInstaller. Os requirements antigos agora encaminham para `requirements-study.txt`: há uma única definição das versões de execução. `requirements-build.txt` acrescenta o PyInstaller fixado.
