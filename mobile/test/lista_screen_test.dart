import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:smartpark/models.dart';
import 'package:smartpark/screens/lista_screen.dart';
import 'package:smartpark/services/api.dart';
import 'package:smartpark/state/busqueda.dart';

void main() {
  testWidgets('la lista no desborda con texto ampliado y ventana estrecha',
      (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final busqueda = Busqueda(Api())
      ..destino = Destino('Unicentro', 4.7, -74.0)
      ..resultados = [
        Parqueadero(
          id: 1,
          nombre: 'Parqueadero de prueba con un nombre largo',
          direccion: 'Unicentro',
          latitud: 4.7,
          longitud: -74.0,
          horarioApertura: '06:00',
          horarioCierre: '23:00',
          abiertoAhora: false,
          capacidadDisponible: 18,
          calificacion: 4.7,
          totalResenas: 50,
          tarifaHora: 5000,
          tarifaDia: 25000,
          distanciaM: 350,
        ),
      ];

    await tester.pumpWidget(
      ChangeNotifierProvider<Busqueda>.value(
        value: busqueda,
        child: MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: const TextScaler.linear(1.5)),
            child: child!,
          ),
          home: const ListaScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(
        find.text('Parqueadero de prueba con un nombre largo'), findsOneWidget);
  });
}
