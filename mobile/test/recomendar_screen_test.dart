import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:provider/provider.dart';
import 'package:smartpark/models.dart';
import 'package:smartpark/screens/recomendar_screen.dart';
import 'package:smartpark/services/api.dart';
import 'package:smartpark/state/busqueda.dart';

class _ApiConOrigenCapturado extends Api {
  List<double?>? origen;

  @override
  Future<Map<String, dynamic>> perfilesRecomendacion() async {
    throw const FormatException('usar perfiles locales en esta prueba');
  }

  @override
  Future<Recomendacion> recomendar({
    required double destinoLat,
    required double destinoLon,
    double? origenLat,
    double? origenLon,
    double horas = 2,
    double? radio,
    String? perfil,
    Map<String, double>? pesos,
  }) async {
    origen = [origenLat, origenLon];
    return Recomendacion('equilibrado', const {}, horas, const [], null);
  }
}

Position _ubicacionPrueba() => Position(
      longitude: -74.1,
      latitude: 4.6,
      timestamp: DateTime(2026),
      accuracy: 5,
      altitude: 0,
      altitudeAccuracy: 1,
      heading: 0,
      headingAccuracy: 1,
      speed: 0,
      speedAccuracy: 1,
    );

Future<List<double?>?> _calcularOrigen(
    WidgetTester tester, bool modoTrayecto) async {
  final api = _ApiConOrigenCapturado();
  final busqueda = Busqueda(api)
    ..destino = Destino('Unicentro', 4.7, -74.0)
    ..miUbicacion = _ubicacionPrueba()
    ..cambiarModoTrayecto(modoTrayecto);

  await tester.pumpWidget(
    MultiProvider(
      providers: [
        Provider<Api>.value(value: api),
        ChangeNotifierProvider<Busqueda>.value(value: busqueda),
      ],
      child: const MaterialApp(
        home: RecomendarScreen(onIrAlMapa: _sinAccion),
      ),
    ),
  );
  await tester.tap(find.text('Calcular mejor opción'));
  await tester.pumpAndSettle();
  return api.origen;
}

void _sinAccion() {}

void main() {
  testWidgets('el modo de punto no usa el GPS como origen del trayecto',
      (tester) async {
    final origen = await _calcularOrigen(tester, false);

    expect(origen, [null, null]);
  });

  testWidgets('el modo trayecto envía la ubicación actual como origen',
      (tester) async {
    final origen = await _calcularOrigen(tester, true);

    expect(origen, [4.6, -74.1]);
  });
}
