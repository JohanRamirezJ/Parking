import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:smartpark/screens/mapa_screen.dart';
import 'package:smartpark/services/api.dart';
import 'package:smartpark/state/busqueda.dart';

void _sinAccion() {}

void main() {
  testWidgets('los iconos de modo muestran una descripción temporal',
      (tester) async {
    final busqueda = Busqueda(Api());

    await tester.pumpWidget(
      ChangeNotifierProvider<Busqueda>.value(
        value: busqueda,
        child: const MaterialApp(
          home: MapaScreen(
            onVerLista: _sinAccion,
            onVerRecomendacion: _sinAccion,
          ),
        ),
      ),
    );

    expect(find.byType(ChoiceChip), findsNothing);
    await tester.tap(find.byTooltip('Desde mi ubicación'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.textContaining('el GPS será el origen'), findsOneWidget);

    await tester.tap(find.byTooltip('Cerca de mí'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(
      find.text(
          'Cerca de mí: busca parqueaderos alrededor de tu ubicación actual.'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });
}
