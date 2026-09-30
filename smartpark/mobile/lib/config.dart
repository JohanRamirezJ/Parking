/// Configuración de la app.
///
/// La URL del backend se pasa al compilar:
///   flutter run --dart-define=API_URL=http://192.168.1.50:5000
/// Por defecto apunta al emulador de Android (10.0.2.2 = localhost del PC).
class Config {
  static const apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:5000');

  // Límites de radio — deben coincidir con el backend (HU 7)
  static const radioMin = 200.0;
  static const radioMax = 5000.0;
  static const radioDefecto = 1000.0;

  // Centro de Bogotá, usado si el usuario aún no tiene ubicación
  static const bogotaLat = 4.6533;
  static const bogotaLon = -74.0836;
}
