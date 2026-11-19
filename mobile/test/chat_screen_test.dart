import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:smartpark/screens/chat_screen.dart';
import 'package:smartpark/services/api.dart';
import 'package:smartpark/state/busqueda.dart';

class _FakeApi extends Api {
  @override
  Future<Map<String, dynamic>> chat(String mensaje,
          {double? lat, double? lon}) async =>
      {
        'respuesta':
            'Te recomiendo la mejor opción: tarifa \$5.000, puntaje 92,5.',
        'parqueadero_recomendado': _parqueadero(1, 'Mejor opción'),
        'alternativas': [
          _parqueadero(2, 'Alternativa Uno'),
          _parqueadero(3, 'Alternativa Dos'),
        ],
        'destino': {'nombre': 'Unicentro', 'latitud': 4.7, 'longitud': -74.0},
      };

  static Map<String, dynamic> _parqueadero(int id, String nombre) => {
        'id': id,
        'nombre': nombre,
        'direccion': 'Unicentro',
        'latitud': 4.7,
        'longitud': -74.0,
        'tarifa_hora': 5000,
        'fuente': 'directorio_local',
      };
}

void main() {
  testWidgets('muestra las alternativas devueltas por el backend',
      (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          Provider<Api>.value(value: api),
          ChangeNotifierProvider<Busqueda>(create: (_) => Busqueda(api)),
        ],
        child: MaterialApp(home: ChatScreen(onVerEnMapa: () {})),
      ),
    );

    await tester.enterText(
        find.byType(TextField), 'parqueadero cerca de Unicentro');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    expect(find.text('Otras opciones:'), findsOneWidget);
    expect(find.textContaining('Alternativa Uno'), findsOneWidget);
    expect(find.textContaining('Alternativa Dos'), findsOneWidget);

    final richText = tester.widget<RichText>(find.byWidgetPredicate(
      (widget) =>
          widget is RichText &&
          widget.text.toPlainText().contains('tarifa \$5.000'),
    ));
    final numerosEnNegrita = <String>[];
    void recoger(TextSpan span) {
      if (span.style?.fontWeight == FontWeight.bold) {
        numerosEnNegrita.add(span.text ?? '');
      }
      for (final hijo in span.children ?? const <InlineSpan>[]) {
        if (hijo is TextSpan) recoger(hijo);
      }
    }

    recoger(richText.text as TextSpan);
    expect(numerosEnNegrita, contains('5.000'));
  });
}
