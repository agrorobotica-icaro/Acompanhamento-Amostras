# Painel de Acompanhamento de Ordens de Serviço

Aplicação em Streamlit para acompanhar pedidos de químico simples de Fertilidade (F) e PAV. O painel procura os arquivos em uma pasta informada pelo usuário e apresenta o status das OS e a seleção das análises químicas.

## O que a aplicação faz

### Informações gerais

- Procura planilhas de químico simples nas subpastas da pasta selecionada.
- Identifica a OS pelo nome da pasta de primeiro nível dentro da pasta selecionada.
- Considera uma combinação de OS, Unidade, Fazenda e tipo concluída quando encontra o arquivo preenchido correspondente.
- Exibe gráficos separados para Fertilidade (F) e PAV.
- Permite pesquisar por OS, Unidade e Fazenda, filtrar por tipo e status, e baixar os resultados em CSV.

### Análises Químicas

Apresenta, em gráficos separados para Fertilidade (F) e PAV, a porcentagem de linhas com `X` em cada análise, calculada sobre o total de linhas daquela OS. O eixo horizontal mostra as OS em ordem numérica.

É possível filtrar as OS, Unidades, Fazendas e análises exibidas. Por exemplo, para acompanhar somente matéria orgânica, selecione apenas `MO` no filtro **Análises**. As curvas usam interpolação cúbica para suavizar a visualização; os valores observados continuam sendo os percentuais calculados para cada OS.

As análises acompanhadas são:

`CHN`, `K_P_Mehlich`, `Macro`, `Micro`, `MO`, `pH_CaCl2`, `pH_H2O`, `P_Resina`, `S_ICP`, `S_Turbidimetria` e `Textura`.

## Arquivos reconhecidos

O painel procura nomes como:

- `F2026001S_QUIMICO_SIMPLES.xlsx`
- `F2026001S_QUIMICO_SIMPLES_PREENCHIDA.xlsx`
- `PAV2026001S_QUIMICO_SIMPLES.xlsx`
- `PAV2026001S_QUIMICO_SIMPLES_PREENCHIDA.xlsx`

O prefixo `F` identifica Fertilidade e `PAV` identifica PAV. A presença de `_PREENCHIDA` indica que o documento foi concluído. A busca percorre as subpastas. A pasta de primeiro nível dentro da pasta selecionada é usada como identificação da OS.

## Estrutura de pastas

Organize as planilhas dentro de uma pasta principal, com uma subpasta para cada OS. Exemplo:

```text
ENTRADAS/
├── OS_001/
│   ├── F2026001S_QUIMICO_SIMPLES.xlsx
│   ├── F2026001S_QUIMICO_SIMPLES_PREENCHIDA.xlsx
│   └── PAV2026001S_QUIMICO_SIMPLES.xlsx
└── OS_002/
    └── F2026002S_QUIMICO_SIMPLES.xlsx
```

As planilhas devem conter as colunas `Unidade` e `Fazenda` para que essas informações apareçam identificadas. Para o gráfico de Análises Químicas, as colunas de análise devem usar os nomes listados acima; o valor `X` significa que a análise foi requisitada e uma célula vazia significa que não foi selecionada.

## Instalação

Com Python instalado, abra o terminal na pasta do projeto e execute:

```bash
pip install -r requirements.txt
```

## Como executar

Na pasta do projeto, execute:

```bash
streamlit run painel_os_quimico_simples.py
```

O navegador abrirá o painel. Na lateral, informe o caminho da pasta principal que contém as subpastas das OS e clique em **Buscar documentos**.

## Arquivos do projeto

- `painel_os_quimico_simples.py`: código da aplicação.
- `requirements.txt`: dependências necessárias.
- `logo_agrorobotica.png`: logo exibida no painel; deve permanecer na mesma pasta do código.

## Acesso à pasta

O caminho informado precisa existir e estar acessível pela máquina que executa o Streamlit. Se a aplicação estiver hospedada na nuvem, o ambiente de hospedagem também precisa ter acesso à pasta do servidor; informar um caminho local do computador do usuário, por si só, não compartilha os arquivos com a aplicação.
