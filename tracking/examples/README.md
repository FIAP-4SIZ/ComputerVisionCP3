# Experimentos manuais legados

`steamvr_pipe_experiment.py` é o antigo `bin/tests/pipetest.py`, preservado sem alterações. Exige driver e SteamVR, envia comandos ao driver e contém `assert 0` incondicional. Não é uma suíte de testes nem um exemplo pronto de uso. O atalho `pipetest.bat` aponta para o novo caminho e informa essa condição antes de executar.

Os testes automatizados suportados ficam em `../tests`. Separar este experimento não desabilita teste algum: ele nunca fazia parte de `unittest discover -s tests`.
