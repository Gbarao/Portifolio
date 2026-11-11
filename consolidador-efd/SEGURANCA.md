# Consolidador EFD: informações para a área de TI e segurança

Este documento serve para a equipe de TI avaliar e liberar o programa.

## O que é

Uma aplicação local de análise de arquivos da EFD ICMS/IPI e da
EFD-Contribuições (arquivos `.txt` do SPED). O código-fonte completo está
neste repositório, na pasta `consolidador-efd/`.

## Como o executável é produzido

- O `ConsolidadorEFD.exe` é gerado pelo PyInstaller, a partir deste código,
  por um fluxo do GitHub Actions (`.github/workflows/consolidador-efd-windows.yml`)
  executado em máquina Windows do próprio GitHub. O fluxo pode ser lido por
  completo.
- No mesmo fluxo, antes da publicação, rodam os testes automáticos, a carga de
  EFDs de teste pelo próprio executável e a verificação de que a interface
  responde.
- A publicação traz o arquivo `ConsolidadorEFD-windows.zip.sha256` com o hash
  SHA-256 do pacote, para conferência.
- O executável **não tem assinatura digital**. Por isso o Windows SmartScreen
  avisa na primeira execução. Se a política da empresa exigir assinatura, a
  própria TI pode gerar o executável a partir do código (comando abaixo) e
  assinar com o certificado da empresa.

```
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm empacotar/consolidador_efd.spec
```

## O que o programa faz no computador

- **Rede**: abre um servidor web apenas no endereço local (`localhost`), em uma
  porta livre escolhida na hora, para mostrar a interface no navegador do
  próprio usuário. Não aceita conexões de outras máquinas. O código do
  programa não faz conexões para a internet, e a coleta de estatísticas de uso
  do Streamlit está desligada.
- **Arquivos**: lê os `.txt` que o usuário escolher e grava a base de dados em
  `Documentos\Consolidador EFD` (banco DuckDB, configurações em JSON e
  backups, se o usuário fizer). Não altera os arquivos `.txt` lidos.
- **Processos**: durante a carga, abre cópias do próprio executável (uma por
  arquivo, até o número de núcleos) para ler os arquivos em paralelo. Elas
  terminam ao fim da leitura.
- **Privilégios**: não precisa de administrador, não instala nada, não altera
  o registro do Windows e não cria serviços.

## Alternativas, se o executável não puder ser liberado

1. **TI gera e assina o executável** a partir do código, com o comando acima.
2. **Versão em Python**: com Python 3.11 ou mais recente instalado, rodar
   `pip install -r requirements.txt` e `python iniciar.py`. O funcionamento
   é o mesmo.
3. **Máquina, servidor ou ambiente virtual aprovado**: o programa pode rodar
   em uma máquina liberada pela TI e ser usado pelo navegador dessa máquina.
