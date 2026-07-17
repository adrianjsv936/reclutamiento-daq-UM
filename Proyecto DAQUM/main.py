import serial
import json
import threading
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# ¡No olvides confirmar tu puerto COM!
PUERTO_SERIAL = 'COM9' 
BAUD_RATE = 115200

datos_actuales = {"s1": 0, "s2": 0, "falla": False}
conexion_serial = None

def leer_serial():
    global datos_actuales, conexion_serial
    try:
        conexion_serial = serial.Serial(PUERTO_SERIAL, BAUD_RATE, timeout=1)
        while True:
            linea = conexion_serial.readline().decode('utf-8').strip()
            if linea:
                try:
                    datos_actuales = json.loads(linea)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print(f"Error serial: {e}")

thread = threading.Thread(target=leer_serial, daemon=True)
thread.start()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Dashboard APPS - Fórmula SAE</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #121212; color: white; text-align: center; padding: 20px; }
        .container { background: #1e1e1e; padding: 30px; border-radius: 15px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 80%; max-width: 600px; }
        .bar-bg { background: #333; border-radius: 10px; height: 30px; width: 100%; margin: 10px 0 20px 0; overflow: hidden;}
        .bar-fill { background: #00e5ff; height: 100%; width: 0%; transition: width 0.1s; }
        .falla-alerta { background: #ff1744 !important; }
        .status { padding: 15px; border-radius: 10px; font-weight: bold; font-size: 1.2em; margin-top: 20px;}
        .status.ok { background: #00c853; color: white; }
        .status.error { background: #d50000; color: white; animation: blink 1s infinite; }
        .panel-control { background: #2a2a2a; padding: 20px; border-radius: 10px; margin-top: 20px; text-align: left; }
        input[type=range] { width: 100%; margin-top: 10px; }
        button { margin-top: 15px; padding: 10px 20px; background: #00e5ff; border: none; font-weight: bold; border-radius: 5px; cursor: pointer; width: 100%; }
        button:hover { background: #00b8cc; }
        @keyframes blink { 50% { opacity: 0.7; } }
    </style>
</head>
<body>
    <div class="container">
        <h2>Monitor APPS (Acelerador)</h2>
        
        <div style="text-align: left;">Sensor 1 (Canal A): <span id="val1">0</span>%</div>
        <div class="bar-bg"><div id="bar1" class="bar-fill"></div></div>

        <div style="text-align: left;">Sensor 2 (Canal B): <span id="val2">0</span>%</div>
        <div class="bar-bg"><div id="bar2" class="bar-fill"></div></div>

        <div id="status-box" class="status ok">SISTEMA OK</div>

        <div class="panel-control">
            <h3 style="margin-top: 0;">Ajuste de Asimetría Dinámica</h3>
            <div>
                <label>Escala Máxima S1: <span id="lbl-s1">4095</span></label>
                <input type="range" id="slider-s1" min="1000" max="4095" value="4095">
            </div>
            <div style="margin-top: 15px;">
                <label>Escala Máxima S2: <span id="lbl-s2">2047</span></label>
                <input type="range" id="slider-s2" min="1000" max="4095" value="2047">
            </div>
            <button onclick="enviarEscalas()">Actualizar Parámetros</button>
        </div>
    </div>

    <script>
        // Actualizar etiquetas de los sliders al moverlos
        document.getElementById('slider-s1').oninput = function() { document.getElementById('lbl-s1').innerText = this.value; }
        document.getElementById('slider-s2').oninput = function() { document.getElementById('lbl-s2').innerText = this.value; }

        function enviarEscalas() {
            const s1_max = document.getElementById('slider-s1').value;
            const s2_max = document.getElementById('slider-s2').value;
            
            fetch('/set_scale', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ s1_max: s1_max, s2_max: s2_max })
            });
        }

        setInterval(() => {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('val1').innerText = data.s1.toFixed(1);
                    document.getElementById('bar1').style.width = data.s1 + '%';
                    document.getElementById('val2').innerText = data.s2.toFixed(1);
                    document.getElementById('bar2').style.width = data.s2 + '%';

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
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/data')
def get_data():
    return jsonify(datos_actuales)

@app.route('/set_scale', methods=['POST'])
def set_scale():
    # Recibe los datos de los sliders y los envía a la ESP32
    data = request.json
    if conexion_serial and conexion_serial.is_open:
        cmd1 = f"S1:{data['s1_max']}\n"
        cmd2 = f"S2:{data['s2_max']}\n"
        conexion_serial.write(cmd1.encode('utf-8'))
        conexion_serial.write(cmd2.encode('utf-8'))
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)