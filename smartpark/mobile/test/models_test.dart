import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:smartpark/formato.dart';
import 'package:smartpark/models.dart';

void main() {
  setUpAll(() => initializeDateFormatting('es'));

  test('Parqueadero.fromJson con y sin tarifa', () {
    final p = Parqueadero.fromJson({
      'id': 1, 'nombre': 'P', 'direccion': 'Calle 1', 'latitud': 4.6, 'longitud': -74.0,
      'horario_apertura': '00:00', 'horario_cierre': '00:00', 'tarifa_hora': null, 'tarifa_dia': 30000,
      'distancia_m': 350, 'total_resenas': 0,
    });
    expect(p.tarifaHora, isNull);
    expect(tarifa(p.tarifaHora), 'Tarifa no disponible'); // RF-05
    expect(p.horario, 'Abierto 24 horas');
    expect(distancia(p.distanciaM), '350 m');
    expect(distancia(1500), '1.5 km');
  });
}
