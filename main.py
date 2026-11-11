
from machine import Pin, time_pulse_us
import time
import json
from umqtt.simple import MQTTClient
import network

# =========================================
# BROKER
# =========================================
BROKER = "broker.hivemq.com"
PUERTO = 1883
WIFI = ""
PASSWORD = ""
CLIENTE = None
ESPERA = 2
CLIENTE_ID = "ESTACIONAMIENTO_P01"
TOPIC = "ds8/1gs133/estacionamiento/P01"
ORDENES = TOPIC + "/cmd"
ESTADO = TOPIC+"/estado"
TELEMETRIA=TOPIC + "/telemetria"
MENSAJE=""

# ==========================================
# PINES
# ==========================================

LED_PIN = 2
TRIG_PIN = 19
ECHO_PIN = 18
OUT_PIN = 21

led = Pin(LED_PIN, Pin.OUT)
trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)
out = Pin(OUT_PIN, Pin.IN)

LED_ESTADO = 1

estacionamientos = []
proceso = True

# ==========================================
# MEDIR DISTANCIA CON HC-SR04
# ==========================================

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


# ==========================================
# DETECCION INFRARROJA
# ==========================================

def determinar_deteccion():
    try:
        valor = out.value()

        if valor == 0:
            print("INFRARROJO: OBJETO DETECTADO")
        else:
            print("INFRARROJO: NO DETECTA OBJETO")

        return valor

    except Exception as e:
        print("Error en el sensor infrarrojo:", e)
        return None


# ==========================================
# REGISTRAR ESTADO
# ==========================================

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
            "DETECION_OBJETO": "TRUE",
            "LED": LED_ESTADO
        }

    else:

        print("Estado: LIBRE")

        LED_ESTADO = 1
        led.value(LED_ESTADO)

        estado = {
            "ESTADO": "LIBRE",
            "DISTANCIA_CM": round(distancia, 2),
            "DETECION_OBJETO": "TRUE" if valor == 0 else "FALSE",
            "LED": LED_ESTADO
        }

    estacionamientos.append(estado)

    return estacionamientos



# =========================================
# RECIBIR MENSAJES MQTT
# =========================================

def recibido(topic, msg):

    try:
        # Decodificar el topic y el mensaje
        topico = topic.decode()
        mensaje = msg.decode()

        print("MENSAJE RECIBIDO:", mensaje)
        print("TOPIC:", topico)

        # Validar que el mensaje sea JSON
        try:
            datos = json.loads(mensaje)

        except (ValueError, TypeError):
            print("ERROR: MENSAJE JSON INVALIDO")
            return

        # Validar que el JSON sea un diccionario
        if not isinstance(datos, dict):
            print("ERROR: EL MENSAJE DEBE SER UN OBJETO JSON")
            return

        # Validar que exista la orden LED
        if "LED" not in datos:
            print("ERROR: NO SE ENCONTRO EL CAMPO LED")
            return

        orden = datos["LED"]

        # Validar el comando
        if orden == "PARPADEAR":

            print("ORDEN RECIBIDA: PARPADEAR")

            for i in range(3):
                led.value(0)
                time.sleep_ms(300)

                led.value(1)
                time.sleep_ms(300)

            # Restaurar el estado anterior del LED
            led.value(LED_ESTADO)

            print("PARPADEO COMPLETADO")

        else:
            print("ERROR: COMANDO DESCONOCIDO")

    except Exception as e:
        print("ERROR PROCESANDO MENSAJE:", e)
        
        
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

def conectarBROKER(CLIENTE_ID, ESTADO, ESPERA):

    ESPERA = 2

    while ESPERA <= 60:

        try:
            print("INTENTANDO CONEXION A BROKER...")

            CLIENTE = MQTTClient(CLIENTE_ID,BROKER,port=PUERTO,keepalive=30 )

            CLIENTE.set_last_will(ESTADO,b"OFFLINE",retain=True)

            CLIENTE.set_callback(recibido)

            CLIENTE.connect()

            CLIENTE.subscribe(ORDENES)

            CLIENTE.publish(ESTADO,b"ONLINE",retain=True)

            print("CONEXION CON BROKER ESTABLECIDA")

            return CLIENTE

        except Exception as e:

            print("ERROR DE CONEXION BROKER:", e)

            try:
                CLIENTE.disconnect()
            except:
                pass

            print("NUEVO INTENTO EN:", ESPERA, "SEGUNDOS")

            time.sleep(ESPERA)

            ESPERA = min(ESPERA * 2, 60)

    print("NO SE PUDO ESTABLECER CONEXION CON BROKER")

    return None


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

        CLIENTE = conectarBROKER(CLIENTE_ID, ESTADO,ESPERA)

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


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

print("======== SISTEMA DE ESTACIONAMIENTO ========")

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
        CLIENTE = None