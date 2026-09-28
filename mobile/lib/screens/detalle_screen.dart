import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../formato.dart';
import '../models.dart';
import '../services/api.dart';
import '../state/busqueda.dart';

/// Detalle de parqueadero: tarifas, horario, HU 10 (calificar) y HU 11 (leer reseñas).
class DetalleScreen extends StatefulWidget {
  final int parqueaderoId;
  const DetalleScreen({super.key, required this.parqueaderoId});

  @override
  State<DetalleScreen> createState() => _DetalleScreenState();
}

class _DetalleScreenState extends State<DetalleScreen> {
  Parqueadero? _p;
  List<Resena> _resenas = [];
  String? _error;
  bool _visitado = false;

  Api get _api => context.read<Api>();

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  Future<void> _cargar() async {
    final b = context.read<Busqueda>();
    try {
      final p = await _api.parqueadero(widget.parqueaderoId, lat: b.lat, lon: b.lon);
      final rs = await _api.resenas(widget.parqueaderoId);
      setState(() {
        _p = p;
        _resenas = rs;
        _error = null;
      });
    } on ApiException catch (e) {
      setState(() => _error = e.mensaje);
    }
  }

  void _snack(String t) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t)));

  Future<void> _marcarVisitado() async {
    try {
      await _api.marcarVisitado(widget.parqueaderoId);
      setState(() => _visitado = true);
      _snack('Marcado como visitado. ¡Ya puedes calificarlo!');
    } on ApiException catch (e) {
      _snack(e.mensaje);
    }
  }

  Future<void> _calificar() async {
    var estrellas = 0;
    final comentario = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, set) => AlertDialog(
          title: const Text('Califica este parqueadero'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 1; i <= 5; i++)
                  IconButton(
                    tooltip: '$i estrellas',
                    icon: Icon(i <= estrellas ? Icons.star : Icons.star_border, color: Colors.amber.shade700, size: 32),
                    onPressed: () => set(() => estrellas = i),
                  ),
              ],
            ),
            TextField(
              controller: comentario,
              maxLines: 3,
              maxLength: 1000,
              decoration: const InputDecoration(hintText: 'Comentario (opcional)'),
            ),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
            FilledButton(onPressed: estrellas == 0 ? null : () => Navigator.pop(ctx, true), child: const Text('Publicar')),
          ],
        ),
      ),
    );
    if (ok != true) return;
    try {
      await _api.calificar(widget.parqueaderoId, estrellas, comentario.text.trim());
      _snack('¡Gracias! Tu reseña fue publicada.');
      _cargar();
    } on ApiException catch (e) {
      // RF-06: si no lo marcó como visitado el backend responde 'sin_visita'
      _snack(e.mensaje);
    }
  }

  Future<void> _reportar(Resena r) async {
    final motivo = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reportar reseña'),
        content: TextField(controller: motivo, decoration: const InputDecoration(hintText: 'Motivo del reporte')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Reportar')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _api.reportarResena(r.id, motivo.text.trim());
      _snack('Gracias, revisaremos el reporte.');
    } on ApiException catch (e) {
      _snack(e.mensaje);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final p = _p;
    return Scaffold(
      appBar: AppBar(title: Text(p?.nombre ?? 'Parqueadero')),
      body: _error != null
          ? Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(_error!),
              TextButton(onPressed: _cargar, child: const Text('Reintentar')),
            ]))
          : p == null
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: _cargar,
                  child: ListView(padding: const EdgeInsets.all(16), children: [
                    Text(p.direccion, style: t.textTheme.bodyLarge),
                    if (p.distanciaM != null) Text('A ${distancia(p.distanciaM)} de tu destino', style: t.textTheme.bodySmall),
                    const SizedBox(height: 16),
                    Row(children: [
                      Expanded(child: _Dato('Por hora', tarifa(p.tarifaHora))),
                      Expanded(child: _Dato('Por día', tarifa(p.tarifaDia))),
                    ]),
                    const SizedBox(height: 8),
                    Row(children: [
                      Expanded(
                          child: _Dato('Horario',
                              p.horario + (p.abiertoAhora == null ? '' : (p.abiertoAhora! ? ' · Abierto' : ' · Cerrado')))),
                      Expanded(
                          child: _Dato(
                              'Cupos estimados',
                              p.capacidadDisponible == null
                                  ? 'Sin dato'
                                  : '${p.capacidadDisponible} de ${p.capacidadTotal ?? '?'}')),
                    ]),
                    Text('La disponibilidad es estimada y no garantiza un cupo.', style: t.textTheme.bodySmall),
                    const SizedBox(height: 16),
                    Row(children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _visitado ? null : _marcarVisitado,
                          icon: Icon(_visitado ? Icons.check : Icons.flag_outlined),
                          label: Text(_visitado ? 'Visitado' : 'Marcar visitado'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: _calificar,
                          icon: const Icon(Icons.star_outline),
                          label: const Text('Calificar'),
                        ),
                      ),
                    ]),
                    const Divider(height: 32),
                    Row(children: [
                      Text('Reseñas', style: t.textTheme.titleMedium),
                      const Spacer(),
                      if (p.calificacion != null)
                        Text('★ ${p.calificacion!.toStringAsFixed(1)} · ${p.totalResenas}', style: t.textTheme.titleMedium),
                    ]),
                    const SizedBox(height: 8),
                    if (_resenas.isEmpty)
                      const Padding(padding: EdgeInsets.symmetric(vertical: 24), child: Center(child: Text('Aún sin reseñas')))
                    else
                      for (final r in _resenas)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Row(children: [
                            Text(r.autor),
                            const SizedBox(width: 8),
                            Text('★' * r.calificacion, style: TextStyle(color: Colors.amber.shade700)),
                          ]),
                          subtitle: Text([if (r.comentario != null) r.comentario!, fechaCorta(r.fecha)].join('\n')),
                          trailing: IconButton(
                            tooltip: 'Reportar',
                            icon: const Icon(Icons.flag_outlined, size: 20),
                            onPressed: () => _reportar(r),
                          ),
                        ),
                  ]),
                ),
    );
  }
}

class _Dato extends StatelessWidget {
  final String etiqueta;
  final String valor;
  const _Dato(this.etiqueta, this.valor);

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(etiqueta, style: t.textTheme.bodySmall),
        Text(valor, style: t.textTheme.titleMedium),
      ]),
    );
  }
}
