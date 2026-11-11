# Sistema-de-Estacionamiento
Sistema IoT para supervisar tres espacios de estacionamiento mediante sensores conectados a placas ESP32. Los dispositivos envían telemetría por MQTT; un backend en Python valida y consolida la información, y un dashboard web muestra la disponibilidad en tiempo real.
1. Arquitectura general
El proyecto contempla tres dispositivos ESP32 independientes:
- P01: estacionamiento 1.
- P02: estacionamiento 2.
- P03: estacionamiento 3.
Flujo de información:
1. El ESP32 obtiene la distancia mediante el sensor ultrasónico HC-SR04 y la detección digital del sensor infrarrojo FC-51.
2. El dispositivo determina si el espacio está LIBRE u OCUPADO.
3. El ESP32 publica el resultado en el broker MQTT HiveMQ.
4. backend.py recibe los mensajes, valida su estructura y sus valores, registra las lecturas y los eventos en archivos CSV y publica un resumen consolidado.
5. El dashboard web recibe el resumen por MQTT sobre WebSockets y actualiza los tres espacios.

Estructura del repositorio
Sistema de estacionamientos/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── main.py                         # Firmware para el ESP32 físico
├── wokwi.py                        # Variante para el simulador Wokwi
├── backend.py                      # Backend MQTT y consolidación de estados
├── enviar.py                       # Script auxiliar para enviar órdenes MQTT
├── diagram.json                    # Diagrama de conexiones de Wokwi
│
└── Dashboard_Adaptado/
    └── Dashboard/
        ├── app.ts                  
        ├── app.js                 
        ├── index.html
Los archivos estacionamiento.csv y eventos_estacionamiento.csv se generan automáticamente al iniciar el backend. No es necesario crearlos manualmente.

Requsisitos
Backend y scripts auxiliares
- Python 3.10 o superior recomendado.
- pip.
- Acceso a Internet para conectarse a HiveMQ.
Dashboard
- Node.js 18 o superior.
- npm (se instala junto con Node.js).
- Un navegador web moderno.
Dispositivos
- ESP32 con MicroPython.
- Biblioteca umqtt.simple disponible en el firmware.
- Conexión Wi-Fi con acceso a Internet.

Configuracion
Clona el repositorio o descarga el ZIP

Extraiga el contenido

instale paho-mqtt, utilizado por backend.py y enviar.py.

El proyecto utiliza el broker público de pruebas HiveMQ:

Parámetro	Valor

Broker	broker.hivemq.com

Puerto MQTT TCP	1883

Puerto MQTT WebSockets seguro	8884

Protocolo de los ESP32 y backend	MQTT sobre TCP

Protocolo del dashboard	MQTT sobre WebSockets

El prefijo de tópicos utilizado actualmente es: ds8/1gs133/estacionamiento

Configure las conexiones PIN para adaptarse a su propio dispositvo

Configure la variable PASSWORD y WIFI de acuerdo a su propia red
        ├── styles.css
        ├── package.json
        └── tsconfig.json
