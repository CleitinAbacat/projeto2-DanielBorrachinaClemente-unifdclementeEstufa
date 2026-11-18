# Estufa inteligente na plataforma FIWARE — Grupo `unifdclementeEstufa`

> Modelo de documentação do repositório do Projeto 2 (CCM520 – Internet das Coisas). Substitua tudo o que está entre `< >` e apague as instruções em itálico. O objetivo é que **outra pessoa consiga reproduzir o projeto** só com este README.

**Integrantes:** `Daniel Borrachina Clemente (22.124.078-1)`
**Link do Wokwi:** https://wokwi.com/projects/480789036221929473

## 1. Descrição

A estufa monitora temperatura e umidade do ar (DHT22), umidade do solo e luminosidade (sensores analógicos) e aciona um relé (irrigação/ventilação) e um servomotor (abertura da janela de sombreamento). A ESP32 publica as medidas e recebe comandos pelo broker MQTT público da HiveMQ. Uma ponte MQTT leva esses tópicos até o Mosquitto local, onde o IoT Agent JSON traduz as mensagens para entidades NGSI-v2 no Orion. A partir do Orion, as aplicações consomem o contexto sem usar MQTT: o Cygnus grava o histórico no MySQL, o Grafana exibe o painel e um serviço externo recebe alertas de solo seco.

## 2. Arquitetura

```
                     Internet                    |                 Computador do grupo (Docker)
                                                 |
 ESP32 / Wokwi --MQTT :1883--> broker.hivemq.com <==ponte MQTT :1883==> Mosquitto :1883
  (estufa001)                   (público)        |  (só tópicos da       |  MQTT
                                                 |   API key do grupo)   v
                                                 |                    IoT Agent JSON :4041
                                                 |                       |  NGSI-v2 HTTP
                                                 |                       v
                                                 |                    Orion :1026 <--> MongoDB :27017
                                                 |                       |  notificações HTTP
                                                 |          +------------+-------------+
                                                 |          v                          v
                                                 |   Cygnus :5050              consumidor :3000
                                                 |          |  SQL                (alerta-estufa)
                                                 |          v
                                                 |   MySQL :3306 --SQL--> Grafana :3000
```

Postman: provisionamento no IoT Agent (`:4041`) e comandos/consultas no Orion (`:1026`).

## 3. Hardware

| Componente | Pino da ESP32 | Observação |
| --- | --- | --- |
| DHT22 | GPIO4 | alimentação 3V3 |
| Umidade do solo | GPIO34 (ADC1_CH6) | no Wokwi, simulado por potenciômetro; alimentação 3V3 |
| LDR | GPIO35 (ADC1_CH7) | módulo fotoresistor, saída AO; alimentação 3V3 |
| Relé | GPIO26 | alimentação 5V |
| Servomotor | GPIO27 (PWM 50 Hz) | alimentação 5V (Vin) |

**Calibração:** os dois sensores analógicos são lidos pelo ADC de 12 bits da ESP32 (0 a 4095), com atenuação de 11 dB para cobrir a faixa de 0 a 3,3 V. Nos dois casos, leitura menor corresponde a percentual maior (solo mais úmido ou ambiente mais claro), por isso a conversão é linear e invertida:

```
percentual = 100 × (ADC_SECO_ESCURO − leitura) / (ADC_SECO_ESCURO − ADC_MOLHADO_CLARO)
```

com o resultado limitado a 0–100 % e arredondado em uma casa. Na simulação do Wokwi foram usados os extremos do ADC: `ADC_SECO_ESCURO = 4095` (solo seco / escuro → 0 %) e `ADC_MOLHADO_CLARO = 0` (solo encharcado / claro → 100 %). Em hardware real, esses dois valores devem ser substituídos pelas leituras medidas com o sensor no ar (seco) e na água (encharcado), e com o LDR coberto e sob luz direta.

## 4. Identificadores

| Item | Valor |
| --- | --- |
| API key | `unifdclementeEstufa` |
| Client id da ponte | `ponte_unifdclementeEstufa` |
| `fiware-service` / `fiware-servicepath` | `fei` / `/estufa` |
| `device_id` | `estufa001` |
| Entidade | `urn:ngsi-ld:Greenhouse:001` (`Greenhouse`) |
| Client id MQTT da ESP32 | `esp32_unifdclementeEstufa_estufa001` |

## 5. Modelo de dados

### 5.1 Medidas

| `object_id` (firmware) | Atributo NGSI | Tipo | Unidade / faixa |
| --- | --- | --- | --- |
| `t` | `temperature` | Number | °C |
| `h` | `relativeHumidity` | Number | % |
| `s` | `soilMoisture` | Number | % |
| `l` | `illuminance` | Number | % |
| `r` | `relayState` | Number | 0/1 |
| `a` | `windowAngle` | Number | 0–180 |
| `i` | `samplingInterval` | Number | s |

Exemplo de payload publicado: `{"t": 24.0, "h": 40.0, "s": 100, "l": 75.6, "r": 0, "a": 0, "i": 3}`

Atributos estáticos: `name` (Text, "Estufa inteligente") e `location` (geo:json, Point `[-46.565, -23.645]`).

### 5.2 Comandos

| Comando | Valores aceitos | Resposta de sucesso | Respostas de erro |
| --- | --- | --- | --- |
| `setRelay` | 0 ou 1 | `OK` | `ERRO: setRelay aceita 0 ou 1`, `ERRO: valor invalido` |
| `setServo` | 0 a 180 | `OK` | `ERRO: setServo aceita 0 a 180`, `ERRO: valor invalido` |
| `setInterval` | 2 a 10 (s) | `OK` | `ERRO: setInterval aceita 2 a 10 segundos`, `ERRO: valor invalido` |
| `setSending` | 0 ou 1 | `OK` | `ERRO: setSending aceita 0 ou 1`, `ERRO: valor invalido` |

Comando com outro nome recebe `ERRO: comando desconhecido`.

### 5.3 Tópicos MQTT

| Sentido | Tópico |
| --- | --- |
| Medidas | `/json/unifdclementeEstufa/estufa001/attrs` |
| Comandos | `/unifdclementeEstufa/estufa001/cmd` |
| Resultado | `/json/unifdclementeEstufa/estufa001/cmdexe` |

### 5.4 Ponte com o broker público

| Padrão | Direção | Por quê |
| --- | --- | --- |
| `/json/unifdclementeEstufa/estufa001/attrs` | `in` | a estufa publica as medidas no broker público; elas precisam chegar ao IoT Agent, no broker local |
| `/json/unifdclementeEstufa/estufa001/cmdexe` | `in` | a estufa publica a resposta dos comandos no broker público; o IoT Agent precisa dela para atualizar `_status`/`_info` |
| `/unifdclementeEstufa/estufa001/cmd` | `out` | o IoT Agent publica os comandos no broker local; eles precisam chegar à estufa, que assina o broker público |

Nenhuma linha usa `both` nem o curinga `#` sozinho: `#` traria o tráfego de todo o broker público para o computador, e `both` poderia devolver mensagens pela ponte, criando laços.

## 6. Como reproduzir

Pré-requisitos: Docker Desktop, Postman (ou Newman), um cliente MQTT (HiveMQ WebSocket Client) e uma conta no Wokwi ou uma ESP32 com MicroPython.

1. **Clone o repositório** e entre na pasta `plataforma/`.
2. **Confira a ponte:** em `plataforma/mosquitto/mosquitto.conf`, o `remote_clientid` e as 3 linhas `topic` usam a API key `unifdclementeEstufa`.
3. **Suba o ambiente:** `docker compose up -d`, depois `docker compose ps`. Devem aparecer 9 contêineres `healthy`.
4. **Verifique a ponte:** `docker compose logs mosquitto` deve mostrar `Connecting bridge hivemq` uma única vez.
5. **Teste a ponte nos dois sentidos:** com `docker exec -it mosquitto mosquitto_sub -v -t "#"` aberto, publique `oi` em `/json/unifdclementeEstufa/estufa001/attrs` pelo HiveMQ WebSocket Client: a mensagem aparece no terminal. Depois rode `docker exec mosquitto mosquitto_pub -t "/unifdclementeEstufa/estufa001/cmd" -m oi`: a mensagem aparece no Web Client (assinando `/unifdclementeEstufa/#`).
6. **Grave o firmware:** abra o projeto do Wokwi (link no topo) ou grave `firmware/main_esqueleto.py` como `main.py` na ESP32 (preencha `SSID` e `SENHA`). O Shell deve mostrar `MQTT conectado` e uma linha `medidas -> {...}` a cada 3 s.
7. **Importe a coleção** `postman/Projeto 2.postman_collection.json` e confira a variável `apikey` = `unifdclementeEstufa`.
8. **Rode a coleção** com a estufa ligada, na ordem das pastas: 0 (reset), Etapa 1 (ambiente), Etapa 2 (grupo e dispositivo), Etapa 3 (comandos), Etapa 4 (subscrições e painel). No terminal: `npx newman run "postman/Projeto 2.postman_collection.json"`.
9. **Grafana:** em http://localhost:3000 (`admin`/`admin`), crie a fonte de dados MySQL (host `mysql-db:3306`, banco `fei`, usuário `grafana`, senha `grafana2026`) e importe `plataforma/painel-estufa.json` em *Dashboards → New → Import*. O painel "Estufa inteligente" deve mostrar as medidas sendo atualizadas a cada 5 s.

## 7. Subscrições

| Subscrição | Condição | Destino | Atributos e formato | Por que assim |
| --- | --- | --- | --- | --- |
| Histórico | mudança em qualquer um dos 7 atributos de medida | `http://cygnus:5050/notify` | os 7 atributos de medida, `normalized` | o Cygnus exige `normalized`, que traz o tipo e os metadados de cada atributo, para gravar uma linha por atributo no MySQL; atributos de comando e estáticos ficam de fora para não poluir o histórico |
| Alerta de solo seco | `soilMoisture<30`, `throttling` 60 s | `http://consumidor:3000/alerta-estufa` | `soilMoisture`, `relayState`, `TimeInstant`, `keyValues` | o serviço externo só precisa dos valores, então `keyValues` deixa o corpo simples; o `throttling` evita uma notificação a cada medida enquanto o solo continua seco |

Os endereços usam os nomes dos serviços (`cygnus`, `consumidor`) porque quem envia as notificações é o Orion, de dentro da rede Docker.

## 8. Painel

![Painel Estufa inteligente](<caminho da captura de tela>)

Todas as consultas leem a tabela `estufa` do banco `fei`, filtram por `attrName` e usam `$__timeFilter(recvTime)` para respeitar o intervalo do painel. O painel atualiza a cada 5 s.

| Visualização | Tipo | Atributo(s) | O que mostra |
| --- | --- | --- | --- |
| Temperatura e umidade do ar | Time series | `temperature`, `relativeHumidity` | evolução das duas grandezas do DHT22 ao longo do tempo |
| Umidade do solo | Time series | `soilMoisture` | evolução da umidade do solo, para identificar quando irrigar |
| Relé | State timeline | `relayState` | períodos em que o relé ficou ligado (1) ou desligado (0) |
| Luminosidade | Gauge | `illuminance` | luminosidade atual, em % |

O JSON exportado está em `plataforma/painel-estufa.json`.

## 9. Testes

![Runner do Postman](<caminho da captura de tela>)

A coleção inteira foi executada com a estufa ligada: 47 requisições e 125 asserções, sem falhas. O resultado exportado está em `postman/resultado-runner.json`.

## 10. Decisões de projeto e limitações

**Decisões**

- **Chaves curtas no JSON** (`t`, `h`, `s`, `l`, `r`, `a`, `i`): reduzem o tamanho de cada mensagem. O provisionamento traduz cada chave para o nome do atributo NGSI.
- **Validação dos comandos no firmware:** o valor é convertido para inteiro (aceita `1`, `1.0` e `"1"`, recusa fracionários e booleanos) e conferido contra a faixa antes de qualquer mudança. Um valor inválido nunca altera o estado e sempre recebe `ERRO: <motivo>`.
- **Medida publicada logo após um comando:** o novo estado dos atuadores aparece no Orion na hora, sem esperar o próximo ciclo.
- **Laço principal não bloqueante:** usa `check_msg()` e comparação de tempo com `ticks_ms`, sem `time.sleep()` nem `wait_msg()`, para que medidas e comandos convivam.
- **Reconexão automática:** se o Wi-Fi ou o MQTT cair (`OSError`), o firmware tenta reconectar a cada 5 s e assina de novo o tópico de comandos.
- **Leitura do DHT22 com tratamento de falha:** se a leitura falhar, a medida daquele ciclo é descartada e o programa continua.

**Limitações**

- O broker público não tem autenticação nem criptografia: qualquer pessoa que conheça a API key pode ler as medidas ou publicar comandos falsos.
- A calibração usada é a da simulação (extremos do ADC), não a de um sensor físico.
- A plataforma depende do computador do grupo ligado e com acesso à internet para a ponte funcionar.

**Em um sistema real**, usaríamos um broker próprio com autenticação por usuário/senha ou certificado, TLS nas conexões, controle de acesso por tópico e a plataforma hospedada em servidor, não em um computador pessoal.

## 11. Uso de ferramentas de IA

Usamos o Claude Code como assistente durante a integração e a documentação. O apoio foi o seguinte:

- **Verificação de erros e diagnóstico:**
  - Identificou que a API key estava diferente entre o firmware, a ponte (`mosquitto.conf`) e a coleção Postman, e unificou o valor.
  - Identificou que os corpos das requisições 2.1 (grupo) e 2.2 (dispositivo) eram recusados pelo IoT Agent (`400 WRONG_SYNTAX`). Corrigiu o formato, acrescentando os envelopes `groups`/`devices` e a `apikey` do dispositivo, com base no exemplo da lâmpada.
  - Apontou um painel do Grafana que consultava o atributo errado (`relayState` no lugar de `soilMoisture`).
- **Orientação de ambiente:**
  - Passo a passo para habilitar a virtualização na BIOS e o Virtual Machine Platform, e para instalar e subir o Docker.
  - Passo a passo para escolher a API key, usar o HiveMQ WebSocket Client, o Postman e o Grafana.
- **Testes:**
  - Execução dos testes da ponte MQTT nos dois sentidos.
  - Execução da coleção Postman pela linha de comando (Newman) e leitura dos resultados.
  - Configuração da atualização automática do painel (5 s) pela API do Grafana e exportação de `plataforma/painel-estufa.json`.
- **Documentação:** revisao das tabelas técnicas deste README com dados do código e da coleção, e rascunho das seções 1, 2, 3 (calibração), 5.4, 6, 7, 8, 9 e 10, revisadas e editadas pelo grupo.

O relatório técnico (respostas R1 a R8) **não** foi escrito com IA. Salvo exceção para a imagem da arquitetura que foi gerada com base na arquitetura escrita pelo grupo (presente neste readme)

## 12. Referências

(Documentos das aulas)
(https://docs.wokwi.com/)
(https://fiware-tutorials.readthedocs.io/en/latest/getting-started.html)
(https://learning.postman.com/)