import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../formato.dart';
import '../models.dart';
import '../services/api.dart';
import '../state/busqueda.dart';
import 'detalle_screen.dart';

/// Módulo de IA: puntaje integral (gasolina, rodamiento, tiempo, distancia, seguridad, precio)
/// con pesos de importancia que el usuario ajusta según su prioridad del momento.
class RecomendarScreen extends StatefulWidget {
  final VoidCallback onIrAlMapa;
  const RecomendarScreen({super.key, required this.onIrAlMapa});

  @override
  State<RecomendarScreen> createState() => _RecomendarScreenState();
}

const _criterios = <String, (String, IconData)>{
  'gasolina': ('Gasolina', Icons.local_gas_station_outlined),
  'rodamiento': ('Rodamiento', Icons.tire_repair_outlined),
  'tiempo': ('Tiempo', Icons.schedule),
  'distancia': ('Distancia a pie', Icons.directions_walk),
  'seguridad': ('Seguridad', Icons.shield_outlined),
  'precio': ('Precio', Icons.attach_money),
};

// Respaldo si el servidor no responde /recomendaciones/perfiles (mismos valores que el backend).
const _perfilesLocales = <String, (String, Map<String, double>)>{
  'equilibrado': ('Equilibrado', {'gasolina': 2, 'rodamiento': 1, 'tiempo': 3, 'distancia': 3, 'seguridad': 3, 'precio': 3}),
  'seguridad': ('De noche', {'gasolina': 1, 'rodamiento': 1, 'tiempo': 2, 'distancia': 3, 'seguridad': 8, 'precio': 2}),
  'precio': ('Muchas horas', {'gasolina': 1, 'rodamiento': 1, 'tiempo': 1, 'distancia': 2, 'seguridad': 3, 'precio': 8}),
  'tiempo': ('Tengo afán', {'gasolina': 1, 'rodamiento': 1, 'tiempo': 8, 'distancia': 4, 'seguridad': 2, 'precio': 2}),
  'vehiculo': ('Cuidar el carro', {'gasolina': 6, 'rodamiento': 5, 'tiempo': 2, 'distancia': 2, 'seguridad': 3, 'precio': 3}),
};

class _RecomendarScreenState extends State<RecomendarScreen> {
  Map<String, (String, Map<String, double>)> _perfiles = Map.of(_perfilesLocales);
  String _perfil = 'equilibrado';
  Map<String, double> _pesos = Map.of(_perfilesLocales['equilibrado']!.$2);
  double _horas = 2;
  bool _calculando = false;
  String? _error;
  Recomendacion? _resultado;

  Api get _api => context.read<Api>();

  @override
  void initState() {
    super.initState();
    _cargarPerfiles();
  }

  Future<void> _cargarPerfiles() async {
    try {
      final d = await _api.perfilesRecomendacion();
      final mapa = <String, (String, Map<String, double>)>{};
      for (final p in d['perfiles'] as List) {
        final pesos = Map<String, dynamic>.from(p['pesos']).map((k, v) => MapEntry(k, (v as num).toDouble()));
        mapa[p['clave']] = (p['nombre'] as String, pesos);
      }
      final prefs = await _api.preferencias();
      if (!mounted) return;
      setState(() {
        _perfiles = mapa;
        if (prefs['perfil'] == 'personalizado') {
          _perfil = 'personalizado';
          _pesos = Map<String, dynamic>.from(prefs['pesos']).map((k, v) => MapEntry(k, (v as num).toDouble()));
        }
      });
    } catch (_) {/* se usan los perfiles locales */}
  }

  void _elegirPerfil(String clave) => setState(() {
        _perfil = clave;
        _pesos = Map.of(_perfiles[clave]!.$2);
      });

  Future<void> _calcular() async {
    final b = context.read<Busqueda>();
    if (!b.tieneReferencia) {
      setState(() => _error = 'Primero elige un destino o activa tu ubicación en el Mapa.');
      return;
    }
    setState(() {
      _calculando = true;
      _error = null;
    });
    try {
      // Si hay destino y también ubicación del usuario, la ubicación es el origen del trayecto.
      final origen = b.destino != null ? b.miUbicacion : null;
      final r = await _api.recomendar(
        destinoLat: b.lat,
        destinoLon: b.lon,
        origenLat: origen?.latitude,
        origenLon: origen?.longitude,
        horas: _horas,
        radio: b.radio,
        pesos: _pesos,
      );
      setState(() => _resultado = r);
    } on ApiException catch (e) {
      setState(() => _error = e.mensaje);
    } finally {
      if (mounted) setState(() => _calculando = false);
    }
  }

  Future<void> _guardar() async {
    try {
      await _api.guardarPreferencias(_pesos);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Guardado. El asistente usará estas prioridades por defecto.')));
      }
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensaje)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final b = context.watch<Busqueda>();
    final total = _pesos.values.fold<double>(0, (a, v) => a + v);

    return Scaffold(
      appBar: AppBar(title: const Text('Recomendación inteligente')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Card(
          child: ListTile(
            leading: const Icon(Icons.place_outlined),
            title: Text(b.destino?.nombre ?? (b.miUbicacion != null ? 'Cerca de tu ubicación' : 'Sin destino')),
            subtitle: Text('Radio ${distancia(b.radio.round())}'),
            trailing: TextButton(onPressed: widget.onIrAlMapa, child: const Text('Cambiar')),
          ),
        ),
        const SizedBox(height: 16),
        Text('¿Cuánto tiempo lo dejas?', style: t.textTheme.titleSmall),
        Wrap(spacing: 8, children: [
          for (final (h, etiqueta) in const [(1.0, '1 h'), (2.0, '2 h'), (4.0, '4 h'), (8.0, '8 h'), (10.0, 'Todo el día')])
            ChoiceChip(label: Text(etiqueta), selected: _horas == h, onSelected: (_) => setState(() => _horas = h)),
        ]),
        const SizedBox(height: 16),
        Text('¿Qué te importa hoy?', style: t.textTheme.titleSmall),
        Wrap(spacing: 8, runSpacing: 4, children: [
          for (final e in _perfiles.entries)
            ChoiceChip(label: Text(e.value.$1), selected: _perfil == e.key, onSelected: (_) => _elegirPerfil(e.key)),
          if (_perfil == 'personalizado') const Chip(label: Text('Personalizado')),
        ]),
        const SizedBox(height: 8),
        Card(
          child: ExpansionTile(
            title: const Text('Ajustar importancia de cada factor'),
            subtitle: Text(_criterios.keys
                .where((k) => (_pesos[k] ?? 0) > 0)
                .map((k) => '${_criterios[k]!.$1} ${total == 0 ? 0 : (100 * _pesos[k]! / total).round()}%')
                .join(' · ')),
            children: [
              for (final e in _criterios.entries)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(children: [
                    Icon(e.value.$2, size: 20),
                    const SizedBox(width: 8),
                    SizedBox(width: 110, child: Text(e.value.$1)),
                    Expanded(
                      child: Slider(
                        value: _pesos[e.key] ?? 0,
                        min: 0,
                        max: 10,
                        divisions: 10,
                        label: '${(_pesos[e.key] ?? 0).round()}',
                        onChanged: (v) => setState(() {
                          _pesos[e.key] = v;
                          _perfil = 'personalizado';
                        }),
                      ),
                    ),
                    SizedBox(width: 24, child: Text('${(_pesos[e.key] ?? 0).round()}', textAlign: TextAlign.end)),
                  ]),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Row(children: [
                  Expanded(
                    child: Text('0 = no me importa · 10 = muy importante',
                        style: t.textTheme.bodySmall),
                  ),
                  TextButton.icon(onPressed: total == 0 ? null : _guardar, icon: const Icon(Icons.save_outlined), label: const Text('Guardar')),
                ]),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: _calculando || total == 0 ? null : _calcular,
          icon: _calculando
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.auto_awesome),
          label: const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Text('Calcular mejor opción')),
        ),
        if (total == 0)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('Sube al menos un factor por encima de 0.', style: TextStyle(color: t.colorScheme.error)),
          ),
        if (_error != null)
          Padding(padding: const EdgeInsets.only(top: 12), child: Text(_error!, style: TextStyle(color: t.colorScheme.error))),
        if (_resultado != null) ...[
          const SizedBox(height: 20),
          if (_resultado!.resultados.isEmpty)
            Text(_resultado!.mensaje ?? 'No hay resultados')
          else
            for (final o in _resultado!.resultados) _TarjetaOpcion(o),
          const SizedBox(height: 8),
          Text('Gasolina y rodamiento se estiman con un carro particular promedio; el tiempo es aproximado.',
              style: t.textTheme.bodySmall),
        ],
      ]),
    );
  }
}

class _TarjetaOpcion extends StatelessWidget {
  final OpcionRecomendada o;
  const _TarjetaOpcion(this.o);

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final p = o.parqueadero;
    final mejor = o.posicion == 1;
    return Card(
      color: mejor ? t.colorScheme.primaryContainer : null,
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => DetalleScreen(parqueaderoId: p.id))),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              CircleAvatar(radius: 14, child: Text('${o.posicion}', style: const TextStyle(fontSize: 13))),
              const SizedBox(width: 10),
              Expanded(child: Text(p.nombre, style: t.textTheme.titleMedium)),
              Text('${o.puntaje.round()}', style: t.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
              Text('/100', style: t.textTheme.bodySmall),
            ]),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(value: o.puntaje / 100, minHeight: 6),
            ),
            const SizedBox(height: 8),
            Text(o.justificacion),
            const SizedBox(height: 4),
            Text('Costo total estimado: ${tarifa(o.costoTotal.toDouble())} (parqueo + gasolina + rodamiento)',
                style: t.textTheme.bodySmall),
            for (final a in o.alertas)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(children: [
                  Icon(Icons.info_outline, size: 16, color: t.colorScheme.tertiary),
                  const SizedBox(width: 4),
                  Expanded(child: Text(a, style: t.textTheme.bodySmall)),
                ]),
              ),
            Theme(
              data: t.copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('Ver desglose del puntaje'),
                children: [
                  for (final c in o.criterios)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(children: [
                        Icon(_criterios[c.clave]?.$2 ?? Icons.circle, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          flex: 3,
                          child: Text('${_criterios[c.clave]?.$1 ?? c.clave}: ${c.texto}${c.estimado ? ' (estimado)' : ''}'),
                        ),
                        Expanded(flex: 2, child: LinearProgressIndicator(value: c.puntaje)),
                        SizedBox(
                          width: 70,
                          child: Text('+${c.aporte.toStringAsFixed(1)}', textAlign: TextAlign.end, style: t.textTheme.bodySmall),
                        ),
                      ]),
                    ),
                ],
              ),
            ),
          ]),
        ),
      ),
    );
  }
}
