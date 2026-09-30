import 'package:intl/intl.dart';

final _cop = NumberFormat.currency(locale: 'es_CO', symbol: '\$', decimalDigits: 0);

/// RF-05: nunca mostrar un dato erróneo cuando no hay tarifa.
String tarifa(double? v) => v == null ? 'Tarifa no disponible' : _cop.format(v);

String distancia(int? m) {
  if (m == null) return '';
  return m < 1000 ? '$m m' : '${(m / 1000).toStringAsFixed(1)} km';
}

String fechaCorta(DateTime f) => DateFormat('d MMM yyyy', 'es').format(f.toLocal());
