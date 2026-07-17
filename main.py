# ==============================================================================
# DASHBOARD DE TELEMETRÍA APPS - FÓRMULA SAE
# ==============================================================================
# Este script levanta un servidor web local para visualizar en tiempo real
# los datos del pedal del acelerador (APPS) enviados desde un ESP32 vía USB.
# Además, graba los primeros 3 minutos de telemetría y genera un reporte gráfico.
# ==============================================================================

import serial           # Permite la comunicación por el puerto USB (COM)
import json             # Sirve para decodificar los datos estructurados del ESP32
import threading        # Permite ejecutar tareas en segundo plano (leer USB y web al mismo tiempo)
import time             # Para llevar el control de los 3 minutos
import os               # Para verificar si la imagen de la gráfica ya existe en la carpeta
from flask import Flask, render_template_string, jsonify, send_file # Herramientas para el servidor web

# Configuramos Matplotlib para que dibuje "en el fondo" sin abrir ventanas que traben el servidor
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt

# Inicializamos la aplicación web
app = Flask(__name__)

# --- CONFIGURACIÓN DE HARDWARE ---
PUERTO_SERIAL = 'COM9'  # IMPORTANTE: Cambiar si Windows asigna otro puerto al conectar el ESP32
BAUD_RATE = 115200      # Velocidad de comunicación (debe coincidir exactamente con el Arduino)

# --- VARIABLES GLOBALES DE ESTADO ---
# Aquí guardamos la "foto" del instante actual para que la web la lea
datos_actuales = {"s1": 0, "s2": 0, "falla": False}
conexion_serial = None

# --- VARIABLES PARA EL REPORTE HISTÓRICO (3 MINUTOS) ---
tiempo_inicio = time.time() # Guardamos la hora exacta en la que arrancó el programa
historial_tiempo = []       # Eje X de la gráfica (Segundos)
historial_s1 = []           # Eje Y del Sensor 1 (Porcentaje)
historial_s2 = []           # Eje Y del Sensor 2 (Porcentaje)
historial_falla = []        # Historial de alertas de seguridad (Booleanos)
grafica_generada = False    # Bandera para saber si ya terminamos el reporte

def generar_grafica():
    """
    Toma todo el historial guardado en las listas y dibuja una gráfica profesional.
    Pinta zonas rojas si hubo falla de seguridad y verdes si todo estuvo OK.
    """
    print("\n[DAQ] Generando gráfica de los primeros 3 minutos...")
    
    # Creamos un lienzo de 10x5 pulgadas
    plt.figure(figsize=(10, 5))
    
    # Dibujamos las líneas de ambos sensores
    plt.plot(historial_tiempo, historial_s1, label='Sensor 1 (Canal A)', color='#00e5ff', linewidth=2)
    plt.plot(historial_tiempo, historial_s2, label='Sensor 2 (Canal B)', color='#ff9100', linewidth=2)
    
    # Magia visual: Recorremos el historial de tiempo para pintar el fondo
    for i in range(len(historial_tiempo) - 1):
        # Si en ese milisegundo hubo falla, pintamos rojo, si no, verde claro
        color_fondo = 'red' if historial_falla[i] else 'lightgreen'
        # axvspan pinta un rectángulo vertical en la gráfica
        plt.axvspan(historial_tiempo[i], historial_tiempo[i+1], color=color_fondo, alpha=0.3, lw=0)

    # Añadimos títulos y formato
    plt.title('Comportamiento APPS - Ventana de 3 Minutos', fontsize=14, fontweight='bold')
    plt.xlabel('Tiempo (Segundos)', fontsize=12)
    plt.ylabel('Aceleración (%)', fontsize=12)
    plt.ylim(0, 105) # El eje Y va de 0 a 105% para tener un poco de margen arriba
    plt.legend(loc='upper right')
    plt.grid(True, linestyle='--', alpha=0.6) # Cuadrícula de fondo
    
    # Ajustamos márgenes y guardamos la imagen físicamente en la carpeta
    plt.tight_layout()
    plt.savefig('grafica_3_minutos.png')
    plt.close() # Liberamos memoria
    print("[DAQ] ¡ÉXITO! Gráfica guardada. Mostrando en el Dashboard...\n")

def leer_serial():
    """
    Esta función corre en un "Hilo" (Thread) separado. 
    Su único trabajo es escuchar el puerto USB constantemente sin pausar la página web.
    """
    global datos_actuales, conexion_serial, grafica_generada
    try:
        # Abrimos la comunicación con el ESP32
        conexion_serial = serial.Serial(PUERTO_SERIAL, BAUD_RATE, timeout=1)
        
        while True: # Ciclo infinito escuchando datos
            # Leemos una línea de texto del USB, la decodificamos y le quitamos espacios extra
            linea = conexion_serial.readline().decode('utf-8').strip()
            
            if linea:
                try:
                    # Convertimos el texto en un diccionario de Python
                    # Ejemplo recibido: {"s1": 45.2, "s2": 45.2, "falla": false}
                    datos_actuales = json.loads(linea)
                    
                    # Calculamos cuántos segundos han pasado desde que iniciamos
                    tiempo_transcurrido = time.time() - tiempo_inicio
                    
                    # FASE 1: Recopilación (0 a 180 segundos)
                    if not grafica_generada and tiempo_transcurrido <= 180:
                        historial_tiempo.append(tiempo_transcurrido)
                        historial_s1.append(datos_actuales['s1'])
                        historial_s2.append(datos_actuales['s2'])
                        historial_falla.append(datos_actuales['falla'])
                        
                    # FASE 2: Generación del reporte (Justo al pasar el minuto 3)
                    elif not grafica_generada and tiempo_transcurrido > 180:
                        generar_grafica()
                        grafica_generada = True # Evita que se vuelva a generar infinitamente
                        
                except json.JSONDecodeError:
                    # Si el ESP32 mandó basura o un texto a medias, lo ignoramos para no crashear
                    pass
    except Exception as e:
        print(f"Error crítico en el puerto serial: {e}")

# --- INICIO DEL HILO DE ADQUISICIÓN ---
# Le decimos a Python que ejecute leer_serial() en el fondo y que, 
# si cerramos el programa, mate este hilo también (daemon=True)
thread = threading.Thread(target=leer_serial, daemon=True)
thread.start()

# ==============================================================================
# CÓDIGO FRONTEND (HTML + CSS + JAVASCRIPT)
# Este bloque es la interfaz gráfica que ve el usuario en su navegador.
# ==============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Dashboard APPS - Fórmula SAE</title>
    <style>
        /* Diseño oscuro estilo telemetría de pista */
        body { font-family: 'Segoe UI', sans-serif; background: #121212; color: white; text-align: center; padding: 20px; }
        .container { background: #1e1e1e; padding: 30px; border-radius: 15px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 80%; max-width: 800px; margin-bottom: 20px;}
        
        /* Estilos de las barras de aceleración */
        .bar-bg { background: #333; border-radius: 10px; height: 30px; width: 100%; margin: 10px 0 20px 0; overflow: hidden;}
        .bar-fill { background: #00e5ff; height: 100%; width: 0%; transition: width 0.1s; }
        .falla-alerta { background: #ff1744 !important; } /* Clase dinámica para cambiar a rojo */
        
        /* Caja central de estado (Verde / Rojo) */
        .status { padding: 15px; border-radius: 10px; font-weight: bold; font-size: 1.2em; margin-top: 20px;}
        .status.ok { background: #00c853; color: white; }
        .status.error { background: #d50000; color: white; animation: blink 1s infinite; }
        
        /* Panel oculto para el reporte de 3 minutos */
        .grafica-panel { background: #2a2a2a; padding: 20px; border-radius: 10px; margin-top: 20px; display: none; }
        .grafica-panel img { max-width: 100%; border-radius: 8px; }
        .contador { font-size: 0.9em; color: #aaa; margin-top: 15px; }
        
        /* Animación de parpadeo de seguridad */
        @keyframes blink { 50% { opacity: 0.7; } }
    </style>
</head>
<body>
    <div class="container">
        <h2>Monitor APPS en Vivo</h2>
        
        <div style="text-align: left;">Sensor 1 (Canal A): <span id="val1">0</span>%</div>
        <div class="bar-bg"><div id="bar1" class="bar-fill"></div></div>

        <div style="text-align: left;">Sensor 2 (Canal B): <span id="val2">0</span>%</div>
        <div class="bar-bg"><div id="bar2" class="bar-fill"></div></div>

        <div id="status-box" class="status ok">SISTEMA OK</div>
        
        <div id="mensaje-tiempo" class="contador">Recopilando datos... La gráfica se generará en el minuto 3.</div>

        <div id="panel-grafica" class="grafica-panel">
            <h3 style="margin-top: 0; color: #00e5ff;">Reporte Automático (0 a 3 min)</h3>
            <img id="img-grafica" src="" alt="Gráfica de Telemetría">
        </div>
    </div>

    <script>
        // BUCLE 1: Telemetría en Vivo (Ejecutado cada 50 milisegundos)
        setInterval(() => {
            fetch('/data') // Hacemos una petición al servidor Flask
                .then(response => response.json())
                .then(data => {
                    // Actualizamos los números en pantalla
                    document.getElementById('val1').innerText = data.s1.toFixed(1);
                    // Modificamos el ancho de la barra CSS para simular movimiento
                    document.getElementById('bar1').style.width = data.s1 + '%';
                    
                    document.getElementById('val2').innerText = data.s2.toFixed(1);
                    document.getElementById('bar2').style.width = data.s2 + '%';

                    // Lógica Visual de Alarma (Si falla es True)
                    const statusBox = document.getElementById('status-box');
                    if(data.falla) {
                        statusBox.className = 'status error';
                        statusBox.innerText = '¡FALLA APPS (>100ms)! MOTOR APAGADO';
                        document.getElementById('bar1').classList.add('falla-alerta');
                        document.getElementById('bar2').classList.add('falla-alerta');
                    } else {
                        statusBox.className = 'status ok';
                        statusBox.innerText = 'SISTEMA OK';
                        document.getElementById('bar1').classList.remove('falla-alerta');
                        document.getElementById('bar2').classList.remove('falla-alerta');
                    }
                });
        }, 50);

        // BUCLE 2: Verificador de Gráfica (Ejecutado cada 2 segundos)
        setInterval(() => {
            fetch('/estado_grafica')
                .then(response => response.json())
                .then(data => {
                    // Si el servidor nos dice que la gráfica ya está lista (True)
                    if(data.lista) {
                        // Escondemos el mensaje de espera
                        document.getElementById('mensaje-tiempo').style.display = 'none';
                        const panel = document.getElementById('panel-grafica');
                        
                        // Hacemos visible el panel
                        if (panel.style.display !== 'block') {
                            panel.style.display = 'block';
                            // TRUCO DE CACHÉ: Le pegamos un número aleatorio a la URL para forzar al navegador
                            // a descargar la imagen nueva en lugar de cargar una versión vieja guardada.
                            document.getElementById('img-grafica').src = '/obtener_grafica?t=' + new Date().getTime();
                        }
                    }
                });
        }, 2000);
    </script>
</body>
</html>
"""

# ==============================================================================
# RUTAS DEL SERVIDOR WEB (FLASK ROUTING)
# ==============================================================================

@app.route('/')
def index():
    """Ruta principal: Cuando entras a 127.0.0.1:5000, te entrega el código HTML."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/data')
def get_data():
    """Ruta de datos: Entrega el JSON más reciente atrapado del puerto USB."""
    return jsonify(datos_actuales)

@app.route('/estado_grafica')
def estado_grafica():
    """Ruta de estado: Responde con un booleano indicando si la gráfica ya se procesó."""
    return jsonify({"lista": grafica_generada})

@app.route('/obtener_grafica')
def obtener_grafica():
    """Ruta de descarga: Envía el archivo PNG físico hacia la página web para ser mostrado."""
    if os.path.exists('grafica_3_minutos.png'):
        return send_file('grafica_3_minutos.png', mimetype='image/png')
    return "Gráfica no encontrada", 404

# --- INICIO DEL SERVIDOR LOCAL ---
if __name__ == '__main__':
    # host='0.0.0.0' permite que otros dispositivos en tu red Wi-Fi (como tu celular) 
    # puedan ver el Dashboard ingresando tu IP local.
    app.run(host='0.0.0.0', port=5000)