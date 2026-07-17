// ==============================================================================
// MÓDULO DE ADQUISICIÓN DE DATOS - SENSOR APPS (Acelerador)
// ==============================================================================
// Este código lee dos potenciómetros que simulan el Sensor de Posición del Pedal 
// del Acelerador (APPS). Implementa redundancia, filtrado de ruido y una 
// comprobación de seguridad estricta basada en las reglas de Fórmula SAE:
// "Si hay una asimetría >10% por más de 100ms, se debe cortar la potencia".
// ==============================================================================

// --- ASIGNACIÓN DE PINES (ESP32) ---
// Usamos pines ADC (Convertidor Analógico-Digital) para leer los voltajes.
const int pinSensor1 = 32; // Canal A (Main) del pedal
const int pinSensor2 = 35; // Canal B (Redundant) del pedal
const int pinFalla = 25;   // Pin de salida para el LED/Relé que corta el motor

// --- CALIBRACIÓN MECÁNICA (12-bits) ---
// El ESP32 tiene un ADC de 12 bits, por lo que lee voltajes (0 a 3.3V) 
// transformándolos en valores enteros de 0 a 4095.
const int minS1 = 0, maxS1 = 4095; 
const int minS2 = 0, maxS2 = 4095; 

// --- REGLAS DE SEGURIDAD (FSAE / EV.5.5) ---
const float margenError = 10.0;        // Diferencia máxima permitida entre sensores (10%)
const unsigned long tiempoFalla = 100; // Tiempo máximo permitido de asimetría (100 milisegundos)
unsigned long inicioFalla = 0;         // Marca de tiempo para contar los 100ms
bool fallaActiva = false;              // Estado global del sistema (Failsafe)

void setup() {
  // Inicializamos el puerto serial a alta velocidad (115200 baudios) 
  // para enviar telemetría en tiempo real sin crear cuellos de botella.
  Serial.begin(115200);
  
  // Configuramos el pin de seguridad como salida y lo apagamos por defecto
  pinMode(pinFalla, OUTPUT);
  digitalWrite(pinFalla, LOW);
}

void loop() {
  // 1. ADQUISICIÓN DE DATOS CRUDOS
  int lectura1 = analogRead(pinSensor1);
  int lectura2 = analogRead(pinSensor2);

  // 2. FILTRO DE BANDA MUERTA (Deadband Failsafe)
  // Ningún sensor mecánico baja exactamente a 0 ohms. Si la lectura es menor 
  // a 50 (aprox. 1.2% del pedal), lo forzamos a 0 para evitar que el coche 
  // acelere solo en pits debido al ruido eléctrico residual.
  if (lectura1 < 50) lectura1 = 0;
  if (lectura2 < 50) lectura2 = 0;

  // 3. TRANSFORMACIÓN DE SEÑAL (Mapeo a Porcentaje)
  // Usamos cast (float) para conservar los decimales exactos.
  // La función constrain() limita la lectura a nuestros topes por si hay picos de voltaje.
  float porcentaje1 = ((float)constrain(lectura1, minS1, maxS1) - minS1) * 100.0 / (float)(maxS1 - minS1);
  float porcentaje2 = ((float)constrain(lectura2, minS2, maxS2) - minS2) * 100.0 / (float)(maxS2 - minS2);

  // 4. LÓGICA DE PLAUSIBILIDAD Y SEGURIDAD (FSAE Rule EV.5.5)
  // Comprobamos si la diferencia absoluta entre ambos canales supera el 10%
  if (abs(porcentaje1 - porcentaje2) > margenError) {
    
    // Si la falla acaba de empezar, guardamos el "timestamp" actual
    if (inicioFalla == 0) {
      inicioFalla = millis(); 
    } 
    // Si la falla persiste y ya pasaron más de 100ms, activamos el corte de motor
    else if (millis() - inicioFalla >= tiempoFalla) {
      fallaActiva = true; 
    }
    
  } else {
    // Si los sensores vuelven a ser simétricos (diferencia < 10%), 
    // reseteamos el temporizador y desactivamos la falla.
    inicioFalla = 0; 
    fallaActiva = false;
  }

  // 5. ACTUACIÓN DE HARDWARE
  // Encendemos o apagamos el pin de seguridad físico según el estado lógico
  digitalWrite(pinFalla, fallaActiva ? HIGH : LOW);

  // 6. TRANSMISIÓN DE TELEMETRÍA (Formato JSON)
  // Empaquetamos los datos en un string JSON para que el script de Python 
  // (Dashboard) pueda parsearlos y graficarlos fácilmente.
  Serial.print("{\"s1\":"); Serial.print(porcentaje1);
  Serial.print(",\"s2\":"); Serial.print(porcentaje2);
  Serial.print(",\"falla\":"); Serial.print(fallaActiva ? "true" : "false");
  Serial.println("}");

  // Frecuencia de muestreo: Esperamos 20ms (Equivale a mandar datos a 50Hz)
  delay(20); 
}