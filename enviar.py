#ESTE CODIGO ES UNICAMENTE PARA PROBAR EL ENVIAR ORDENES
import paho.mqtt.publish as publish

BROKER = "broker.hivemq.com"
PUERTO = 1883

TOPIC = "ds8/1gs133/estacionamiento/P02/cmd"

MENSAJE = '{"LED":"APAGAR"}'

try:
    publish.single(
        TOPIC,
        MENSAJE,
        hostname=BROKER,
        port=PUERTO
    )

    print("ORDEN ENVIADA CORRECTAMENTE")

except Exception as error:
    print("ERROR AL ENVIAR LA ORDEN:", error)
