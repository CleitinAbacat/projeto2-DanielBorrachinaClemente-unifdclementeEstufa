"""
Lampada inteligente simulada (Python 3 + paho-mqtt 2.x) integrada ao IoT Agent JSON.
"""

import json
import math
import os
import random
import time

import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_BROKER", "localhost")
PORTA = 1883
API_KEY = os.getenv("API_KEY", "lampada2026")
DEVICE_ID = os.getenv("DEVICE_ID", "lampada001")
INTERVALO = int(os.getenv("INTERVALO", "5"))

TOPICO_MEDIDAS = f"/json/{API_KEY}/{DEVICE_ID}/attrs"
TOPICO_COMANDOS = f"/{API_KEY}/{DEVICE_ID}/cmd"
TOPICO_RESULTADO = f"/json/{API_KEY}/{DEVICE_ID}/cmdexe"

estado = 0 # 0 apagada, 1 acesa


def luminosidade():
    # Dia acelerado: 1 minuto real = 1 hora
    hora = (time.time() / 60) % 24
    sol = max(0.0, math.sin(math.pi * (hora - 6) / 12))
    valor = 5 + 60 * sol + (30 if estado else 0) + random.uniform(-3, 3)
    return round(min(100.0, max(0.0, valor)), 1)


def publicar_medidas(cliente):
    medidas = {"s": estado, "l": luminosidade()}
    cliente.publish(TOPICO_MEDIDAS, json.dumps(medidas))
    print("medidas   ->", TOPICO_MEDIDAS, medidas, flush=True)
    with open("/tmp/vivo", "w") as arquivo: # verifica se o docker ta suavao
        arquivo.write(str(time.time()))


def executar(nome, valor):
    global estado
    if nome != "setLight":
        return "ERRO: comando desconhecido"
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return "ERRO: valor deve ser 0 ou 1"
    if valor not in (0, 1):
        return "ERRO: valor deve ser 0 ou 1"
    estado = valor
    return "OK"


def ao_conectar(cliente, userdata, flags, codigo, propriedades=None):
    print("conectado ao broker", BROKER, "- assinando", TOPICO_COMANDOS, flush=True)
    cliente.subscribe(TOPICO_COMANDOS)


def ao_receber(cliente, userdata, msg):
    print("comando   <-", msg.topic, msg.payload, flush=True)
    try:
        comandos = json.loads(msg.payload)
    except ValueError:
        return
    if not isinstance(comandos, dict):
        return
    resultado = {nome: executar(nome, valor) for nome, valor in comandos.items()}
    cliente.publish(TOPICO_RESULTADO, json.dumps(resultado))
    print("resultado ->", TOPICO_RESULTADO, resultado, flush=True)
    publicar_medidas(cliente)


cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim_{API_KEY}_{DEVICE_ID}")
cliente.on_connect = ao_conectar
cliente.on_message = ao_receber

# Aguarda o broker ficar disponivel
while True:
    try:
        cliente.connect(BROKER, PORTA, keepalive=60)
        break
    except OSError as erro:
        print("broker indisponivel, tentando de novo:", erro, flush=True)
        time.sleep(3)

cliente.loop_start()
while True:
    publicar_medidas(cliente)
    time.sleep(INTERVALO)
