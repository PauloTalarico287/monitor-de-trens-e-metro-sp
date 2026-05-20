# Monitor Metro e Trem SP — Mural Local

Monitora automaticamente o status de todas as linhas de metrô e trem de São Paulo,
gera alertas por território e grava no Google Sheets.

## Estrutura do repositório

```
.
├── .github/
│   └── workflows/
│       └── monitor.yml      # Agendamento do GitHub Actions
├── data/
│   └── status.json          # Último status coletado (atualizado automaticamente)
├── monitor.py               # Coleta status de todas as linhas
├── sheets_writer.py         # Grava alertas no Google Sheets
└── README.md
```

## Configuração dos Secrets

Vá em **Settings → Secrets and variables → Actions → New repository secret**
e adicione os dois secrets abaixo:

### `GOOGLE_CREDENTIALS`
Conteúdo completo do arquivo `credentials.json` da Service Account.
Copie e cole o JSON inteiro como valor do secret.

### `SPREADSHEET_ID`
ID da planilha do Google Sheets.
Extraia da URL: `https://docs.google.com/spreadsheets/d/**ID_AQUI**/edit`

## Frequência de execução

O workflow roda automaticamente a cada 30 minutos
entre 4h e 23h30 (horário de Brasília).

Para rodar manualmente: **Actions → Monitor Metro e Trem SP → Run workflow**

## Territórios monitorados (Mural Local)

| Território    | Linha              |
|---------------|--------------------|
| Suzano        | Linha 11-Coral     |
| Mauá          | Linha 10-Turquesa  |
| Osasco        | Linhas 8 e 9       |
| Guarulhos     | Linha 13-Jade      |
| Capão Redondo | Linha 5-Lilás      |
| Itaim Paulista| Linha 12-Safira    |
| Grajaú        | Linha 9-Esmeralda  |
| São Mateus    | Linha 15-Prata     |
| Jaçanã        | Linha 1-Azul       |
| Paraisópolis  | Linha 4-Amarela    |
