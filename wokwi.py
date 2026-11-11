#El siguiente codigo corresponde al codigo necesario para el desarrollo en wokwi como simulador
#Anted de ejecutar el codigo es necesario copiar el contenido diagram.json, en la seccion diagram de wokwi

from machine import Pin, time_pulse_us
import time
import json
import random
import network
from umqtt.simple import MQTTClient

# PINES
LED_PIN = 2
led = Pin(LED_PIN, Pin.OUT)
TRIG_PIN = 17
ECHO_PIN = 18
trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)

LED_ESTADO = 1
# =========================================
# BROKER
# =========================================
BROKER = "broker.hivemq.com"
PUERTO = 1883
WIFI = "Wokwi-GUEST"
PASSWORD = ""
CLIENTE = None
ESPERA = 2
CLIENTE_ID = "ESTACIONAMIENTO_P02"
TOPIC = "ds8/1gs133/estacionamiento/P02"
ORDENES = TOPIC + "/cmd"
ESTADO = TOPIC+"/estado"
TELEMETRIA=TOPIC + "/telemetria"
MENSAJE=""

estacionamientos=[]
proceso=True


def medir_distancia():
    trig.value(0)
    time.sleep_us(2)

    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    try:
        duracion = time_pulse_us(echo, 1, 30000)

        if duracion < 0:
            return None

        distancia = (duracion * 0.0343) / 2
        return distancia

    except Exception as e:
        print("Error al medir distancia:", e)
        return None

def determinar_deteccion():
    valor = numero = random.randint(0, 1)
    if valor == 0:
        print("INFRARROJO: OBJETO DETECTADO")
    else:
        print("INFRARROJO: NO DETECTA OBJETO")

    return valor



def registrar_estado(estacionamientos, distancia, valor):

    global LED_ESTADO

    if distancia is None or valor is None:
        print("No se puede determinar el estado de los sensores")
        return estacionamientos

    if distancia <= 250 and valor == 0:

        print("Estado: OCUPADO")

        LED_ESTADO = 0
        led.value(LED_ESTADO)

        estado = {
            "ESTADO": "OCUPADO",
            "DISTANCIA_CM": round(distancia, 2),
            "DETECION_OBJETO": "TRUE"
        }

    else:

        print("Estado: LIBRE")

        LED_ESTADO = 1
        led.value(LED_ESTADO)

        estado = {
            "ESTADO": "LIBRE",
            "DISTANCIA_CM": round(distancia, 2),
            "DETECION_OBJETO": "TRUE" if valor == 0 else "FALSE"
        }

    estacionamientos.append(estado)

    return estacionamientos

def recibido(topic, msg):

    try:
        topico = topic.decode()
        mensaje = msg.decode()

        print("======== ORDEN RECIBIDA ========")
        print("TOPICO:", topico)
        print("MENSAJE:", mensaje)

        try:
            datos = json.loads(mensaje)

        except ValueError:
            print("ERROR: EL MENSAJE NO CONTIENE JSON VALIDO")
            return

        if not isinstance(datos, dict):
            print("ERROR: FORMATO JSON INCORRECTO")
            return

        orden = datos.get("LED")

        if orden == "PARPADEAR":

            print("EJECUTANDO ORDEN: PARPADEAR 3 VECES")

            for i in range(3):
                led.value(0)
                time.sleep_ms(300)

                led.value(1)
                time.sleep_ms(300)

            # Recuperar el estado normal del LED
            led.value(LED_ESTADO)

            print("PARPADEO FINALIZADO")
            print("LED RESTABLECIDO")

        else:
            print("ORDEN NO RECONOCIDA")

    except Exception as e:
        print("ERROR AL RECIBIR ORDEN:", e)
        
        
def publicarTelemetria(datos):

    try:
        mensaje = json.dumps(datos)

        CLIENTE.publish(
            TELEMETRIA,
            mensaje
        )

        print("TELEMETRIA PUBLICADA")
        print("TOPICO:", TELEMETRIA)
        print("MENSAJE:", mensaje)

    except Exception as e:
        print("ERROR AL PUBLICAR TELEMETRIA:", e)
        raise

# =========================================
# CONEXION WIFI
# =========================================

def conectarWIFI(WIFI, PASSWORD, ESPERA):

    wlan = network.WLAN(network.STA_IF)

    if wlan.isconnected():
        return True

    wlan.active(True)
    wlan.connect(WIFI, PASSWORD)

    while ESPERA < 60:
        print("INTENTANDO ESTABLECER CONEXION")

        if wlan.isconnected():
            print("CONEXION ESTABLECIDA")
            return True

        time.sleep(ESPERA)
        ESPERA = min(ESPERA * 2, 60)
    print("NO SE HA PODIDO ESTABLECER CONEXION")
    wlan.disconnect()
    return False


# =========================================
# CONEXION BROKER
# =========================================

def conectarBROKER(CLIENTE_ID, ESTADO):

    CLIENTE = MQTTClient(
        CLIENTE_ID,
        BROKER,
        port=PUERTO,
        keepalive=30
    )

    CLIENTE.set_last_will(
        ESTADO,
        b"OFFLINE",
        retain=True
    )

    CLIENTE.set_callback(recibido)
    CLIENTE.connect()
    CLIENTE.subscribe(ORDENES)
    CLIENTE.publish(ESTADO, b"ONLINE", retain=True)

    return CLIENTE


# =========================================
# CONEXION GENERAL
# =========================================

def conectar(WIFI, PASSWORD, CLIENTE_ID, ESTADO, ESPERA):
    global CLIENTE

    try:
        print("INICIANDO CONEXION A WIFI...")

        if not conectarWIFI(WIFI, PASSWORD, ESPERA):
            return False

        print("INICIANDO CONEXION A BROKER...")

        CLIENTE = conectarBROKER(CLIENTE_ID, ESTADO)

        if CLIENTE is not None:
            print("CONEXION MQTT ESTABLECIDA")
            return True

    except Exception as e:
        print("ERROR DE CONEXION MQTT:", e)

        if CLIENTE is not None:
            try:
                CLIENTE.disconnect()
            except Exception:
                pass

        CLIENTE = None

    return False


print("================================ SISTEMA DE ESTACIONAMIENTO ================================")

ultimo_tiempo = time.ticks_ms()
ultimo_tiempo = time.ticks_ms()

while proceso:

    if CLIENTE is None:
        conectar(WIFI, PASSWORD, CLIENTE_ID, ESTADO, ESPERA)
        continue

    try:
        CLIENTE.check_msg()

        ahora = time.ticks_ms()

        if time.ticks_diff(ahora, ultimo_tiempo) >= 500:

            ultimo_tiempo = ahora

            print("======== SISTEMA DE ESTACIONAMIENTO ========")

            distancia = medir_distancia()
            valor = determinar_deteccion()

            if distancia is not None and valor is not None:

                print("Distancia: {:.2f} cm".format(distancia))

                estacionamientos = registrar_estado(
                    estacionamientos,
                    distancia,
                    valor
                )

                if estacionamientos:
                    print(json.dumps(estacionamientos[-1]))
                    publicarTelemetria(estacionamientos[-1])

            else:
                print("Error: no se pudo obtener una medicion valida")
                led.value(0)

    except Exception as e:

        print("Error en la comunicacion MQTT:", e)

        try:
            CLIENTE.disconnect()
        except:
            pass

        CLIENTE = None