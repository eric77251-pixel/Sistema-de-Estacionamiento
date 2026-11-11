import paho.mqtt.client as mqtt
import json
import csv
import os
import time
import math
from datetime import datetime, timezone

# ==========================================
# CONFIGURACION MQTT
# ==========================================

BROKER = "broker.hivemq.com"
PUERTO = 1883
CLIENTE_ID = "BACKEND_ESTACIONAMIENTO"

TOPIC_BASE = "ds8/1gs133/estacionamiento"
TOPIC_TELEMETRIA = TOPIC_BASE + "/+/telemetria"
TOPIC_ESTADO = TOPIC_BASE + "/+/estado"
TOPIC_DASHBOARD = TOPIC_BASE + "/dashboard"

# ==========================================
# CONFIGURACION DEL SISTEMA
# ==========================================

ESTACIONAMIENTOS = ["P01", "P02", "P03"]

ARCHIVO_CSV = "estacionamiento.csv"
ARCHIVO_EVENTOS = "eventos_estacionamiento.csv"

# El ESP32 publica aproximadamente cada 5 segundos.
# El silencio permitido es 4 veces ese intervalo.
INTERVALO_PUBLICACION = 0.5
TIEMPO_MAX_SILENCIO = INTERVALO_PUBLICACION * 4

# Rango físico máximo habitual del HC-SR04.
DISTANCIA_MIN_CM = 0
DISTANCIA_MAX_CM = 400

# Última lectura válida de cada espacio.
estados = {
    identificador: None for identificador in ESTACIONAMIENTOS
}

# Estado que se envía al dashboard.
estado_dispositivos = {
    identificador: "SIN_DATOS" for identificador in ESTACIONAMIENTOS
}

# Momento de la última telemetría válida o, inicialmente,
# del mensaje ONLINE que inicia el periodo de espera.
ultimo_mensaje = {
    identificador: None for identificador in ESTACIONAMIENTOS
}

# Estado utilizado para registrar cambios en el CSV de eventos.
# None significa que todavía no se ha determinado un estado.
estado_monitor = {
    identificador: None for identificador in ESTACIONAMIENTOS
}


# ==========================================
# FECHA Y HORA
# ==========================================

def obtener_fecha():
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


# ==========================================
# PREPARAR ARCHIVOS CSV
# ==========================================

def preparar_csv():
    if not os.path.exists(ARCHIVO_CSV):
        with open(
            ARCHIVO_CSV,
            "w",
            newline="",
            encoding="utf-8"
        ) as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow([
                "FECHA",
                "ESTACIONAMIENTO",
                "ESTADO",
                "DISTANCIA_CM",
                "DETECION_OBJETO",
                "LED"
            ])

        print("ARCHIVO CSV DE TELEMETRIA CREADO")


def preparar_csv_eventos():
    if not os.path.exists(ARCHIVO_EVENTOS):
        with open(
            ARCHIVO_EVENTOS,
            "w",
            newline="",
            encoding="utf-8"
        ) as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow([
                "FECHA",
                "TIPO",
                "GRAVEDAD",
                "DETALLE"
            ])

        print("ARCHIVO CSV DE EVENTOS CREADO")


# ==========================================
# GUARDAR LECTURAS Y EVENTOS
# ==========================================

def guardar_csv(id_estacionamiento, datos):
    with open(
        ARCHIVO_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow([
            obtener_fecha(),
            id_estacionamiento,
            datos["ESTADO"],
            datos["DISTANCIA_CM"],
            datos["DETECION_OBJETO"],
            datos["LED"]
        ])


def guardar_evento(tipo, gravedad, detalle):
    with open(
        ARCHIVO_EVENTOS,
        "a",
        newline="",
        encoding="utf-8"
    ) as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow([
            obtener_fecha(),
            tipo,
            gravedad,
            detalle
        ])


# ==========================================
# CAMBIAR ESTADO DEL MONITOR
# ==========================================

def cambiar_estado_monitor(id_estacionamiento, nuevo_estado):
    estado_anterior = estado_monitor[id_estacionamiento]

    # Registrar solamente cuando el estado realmente cambia.
    if estado_anterior == nuevo_estado:
        return

    estado_monitor[id_estacionamiento] = nuevo_estado

    if nuevo_estado == "ONLINE":
        gravedad = "INFO"
    elif nuevo_estado == "SIN_DATOS":
        gravedad = "WARNING"
    else:
        gravedad = "ERROR"

    if estado_anterior is None:
        detalle = f"{id_estacionamiento}: estado inicial {nuevo_estado}"
    else:
        detalle = (
            f"{id_estacionamiento}: "
            f"{estado_anterior} -> {nuevo_estado}"
        )

    guardar_evento(nuevo_estado, gravedad, detalle)
    print("CAMBIO DE ESTADO:", detalle)


# ==========================================
# VALIDAR DATOS RECIBIDOS
# ==========================================

def validar_datos(datos):
    if not isinstance(datos, dict):
        return False

    # Comprobar que estén presentes los campos requeridos.
    campos_requeridos = [
        "ESTADO",
        "DISTANCIA_CM",
        "DETECION_OBJETO"
    ]

    for campo in campos_requeridos:
        if campo not in datos:
            return False

    estado = datos["ESTADO"]
    distancia = datos["DISTANCIA_CM"]
    deteccion = datos["DETECION_OBJETO"]

    if estado not in ["LIBRE", "OCUPADO"]:
        return False

    # bool es una subclase de int en Python; se rechaza explícitamente.
    if isinstance(distancia, bool):
        return False

    if not isinstance(distancia, (int, float)):
        return False

    if not math.isfinite(distancia):
        return False

    if not (DISTANCIA_MIN_CM <= distancia <= DISTANCIA_MAX_CM):
        return False

    # El ESP32 envía estos valores como cadenas de texto.
    if deteccion not in ["TRUE", "FALSE"]:
        return False
    
    if "LED" not in datos:
        print("ERROR: FALTA EL CAMPO LED")
        return

    if datos["LED"] not in (0, 1) or isinstance(datos["LED"], bool):
        print("ERROR: ESTADO DEL LED INVALIDO")
        return

    return True


# ==========================================
# ACTUALIZAR DASHBOARD
# ==========================================

def actualizar_dashboard(cliente):
    disponibles = 0
    ocupados = 0
    espacios = []

    for identificador in ESTACIONAMIENTOS:
        lectura = estados[identificador]

        # Si todavía no hay una lectura, el espacio queda sin datos.
        if lectura is None:
            continue

        disponible = lectura["ESTADO"] == "LIBRE"

        if disponible:
            disponibles += 1
        else:
            ocupados += 1

        espacios.append({
            "id": identificador,
            "available": disponible
        })

    dispositivos = []

    for identificador in ESTACIONAMIENTOS:
        dispositivos.append({
            "id": identificador,
            "status": estado_dispositivos[identificador]
        })

    resumen = {
        "parking_lot_id": "LOT001",
        "timestamp": obtener_fecha(),
        "total_spaces": len(ESTACIONAMIENTOS),
        "available_spaces": disponibles,
        "occupied_spaces": ocupados,
        "spaces": espacios,
        "devices": dispositivos
    }

    mensaje = json.dumps(resumen)

    resultado = cliente.publish(
        TOPIC_DASHBOARD,
        mensaje,
        qos=0,
        retain=True
    )

    if resultado.rc == mqtt.MQTT_ERR_SUCCESS:
        print("\nDASHBOARD ACTUALIZADO")
        print(json.dumps(resumen, indent=4))
    else:
        print("ERROR AL PUBLICAR EN EL DASHBOARD")


# ==========================================
# MONITOREAR SILENCIO DE LOS DISPOSITIVOS
# ==========================================

def monitorear_dispositivos(cliente):
    ahora = time.time()

    for identificador in ESTACIONAMIENTOS:
        ultimo = ultimo_mensaje[identificador]

        if ultimo is None:
            continue

        # Si el broker notificó OFFLINE, no convertirlo en SIN_DATOS.
        if estado_dispositivos[identificador] == "OFFLINE":
            continue

        tiempo_silencio = ahora - ultimo

        if tiempo_silencio > TIEMPO_MAX_SILENCIO:
            if estado_monitor[identificador] != "SIN_DATOS":
                estado_dispositivos[identificador] = "SIN_DATOS"

                cambiar_estado_monitor(
                    identificador,
                    "SIN_DATOS"
                )

                actualizar_dashboard(cliente)


# ==========================================
# CONEXION AL BROKER
# ==========================================

def al_conectar(
    cliente,
    userdata,
    flags,
    reason_code,
    properties
):
    if reason_code == 0:
        print("CONEXION ESTABLECIDA CON HIVEMQ")

        cliente.subscribe(TOPIC_TELEMETRIA)
        cliente.subscribe(TOPIC_ESTADO)

        print("ESCUCHANDO TELEMETRIA:", TOPIC_TELEMETRIA)
        print("ESCUCHANDO ESTADOS:", TOPIC_ESTADO)
    else:
        print("ERROR DE CONEXION:", reason_code)


# ==========================================
# RECEPCION DE MENSAJES
# ==========================================

def al_recibir_mensaje(cliente, userdata, mensaje):
    try:
        topic = mensaje.topic
        contenido = mensaje.payload.decode("utf-8").strip()

        partes = topic.split("/")

        if len(partes) < 2:
            print("TOPIC NO VALIDO:", topic)
            return

        id_estacionamiento = partes[-2]
        tipo_mensaje = partes[-1]

        if id_estacionamiento not in ESTACIONAMIENTOS:
            print("ESTACIONAMIENTO DESCONOCIDO:", id_estacionamiento)
            return

        # ======================================
        # ESTADO DE CONEXION DEL ESP32
        # ======================================

        if tipo_mensaje == "estado":
            if contenido not in ["ONLINE", "OFFLINE"]:
                print("ESTADO DE CONEXION NO VALIDO:", contenido)
                return

            if contenido == "ONLINE":

                estado_dispositivos[id_estacionamiento] = "SIN_DATOS"

                ultimo_mensaje[id_estacionamiento] = time.time()

                cambiar_estado_monitor(
                id_estacionamiento,
                "SIN_DATOS"
                )
                print(
                    f"{id_estacionamiento} conectado al broker; "
                    "esperando telemetria..."
                )

            else:
                estado_dispositivos[id_estacionamiento] = "OFFLINE"
                ultimo_mensaje[id_estacionamiento] = None

                cambiar_estado_monitor(
                    id_estacionamiento,
                    "OFFLINE"
                )

            actualizar_dashboard(cliente)
            return

        # ======================================
        # RECEPCION DE TELEMETRIA
        # ======================================

        if tipo_mensaje == "telemetria":
            try:
                datos = json.loads(contenido)
            except json.JSONDecodeError:
                print(
                    "LECTURA DESCARTADA: JSON INVALIDO -",
                    id_estacionamiento
                )
                return

            if not validar_datos(datos):
                print(
                    "LECTURA DESCARTADA: DATOS O RANGOS INVALIDOS -",
                    id_estacionamiento
                )
                return

            # Actualizar únicamente después de validar el mensaje.
            estados[id_estacionamiento] = datos
            ultimo_mensaje[id_estacionamiento] = time.time()
            estado_dispositivos[id_estacionamiento] = "ONLINE"

            cambiar_estado_monitor(
                id_estacionamiento,
                "ONLINE"
            )

            print("\n================================")
            print("ESTACIONAMIENTO:", id_estacionamiento)
            print("ESTADO:", datos["ESTADO"])
            print("DISTANCIA:", datos["DISTANCIA_CM"], "CM")
            print("OBJETO:", datos["DETECION_OBJETO"])
            print("================================")

            guardar_csv(id_estacionamiento, datos)
            actualizar_dashboard(cliente)
            return

        print("TIPO DE MENSAJE DESCONOCIDO:", tipo_mensaje)

    except UnicodeDecodeError:
        print("MENSAJE DESCARTADO: NO ES TEXTO UTF-8")

    except Exception as error:
        print("ERROR AL PROCESAR MENSAJE:", error)


# ==========================================
# INICIAR BACKEND
# ==========================================

preparar_csv()
preparar_csv_eventos()

cliente = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=CLIENTE_ID
)

cliente.on_connect = al_conectar
cliente.on_message = al_recibir_mensaje

try:
    print("CONECTANDO CON HIVEMQ...")

    cliente.connect(BROKER, PUERTO, 60)

    while True:
        cliente.loop(timeout=1.0)
        monitorear_dispositivos(cliente)
        time.sleep(1)

except KeyboardInterrupt:
    print("\nBACKEND DETENIDO")
    cliente.disconnect()

except Exception as error:
    print("ERROR EN EL BACKEND:", error)
    cliente.disconnect()
