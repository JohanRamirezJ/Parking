import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../formato.dart';
import '../models.dart';
import '../state/busqueda.dart';
import 'detalle_screen.dart';

/// HU 8 (comparar tarifas y ordenar) y HU 9 (filtrar por rango de tarifa).
class ListaScreen extends StatelessWidget {
  const ListaScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final b = context.watch<Busqueda>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Comparar parqueaderos'),
        actions: [
          IconButton(
            tooltip: 'Filtrar por tarifa',
            icon: Badge(
              isLabelVisible: b.tarifaMin != null || b.tarifaMax != null,
              child: const Icon(Icons.tune),
            ),
            onPressed: () => _filtro(context, b),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'distancia', label: Text('Distancia'), icon: Icon(Icons.near_me)),
                ButtonSegment(value: 'tarifa', label: Text('Tarifa'), icon: Icon(Icons.attach_money)),
                ButtonSegment(value: 'calificacion', label: Text('Calificación'), icon: Icon(Icons.star)),
              ],
              selected: {b.orden},
              onSelectionChanged: (s) => b.cambiarOrden(s.first),
            ),
          ),
          if (b.tarifaMin != null || b.tarifaMax != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: InputChip(
                label: Text('Tarifa/hora: ${b.tarifaMin != null ? tarifa(b.tarifaMin) : '\$0'} – '
                    '${b.tarifaMax != null ? tarifa(b.tarifaMax) : 'sin límite'}'),
                onDeleted: () => b.cambiarRangoTarifa(null, null),
              ),
            ),
          Expanded(child: _cuerpo(context, b)),
        ],
      ),
    );
  }

  Widget _cuerpo(BuildContext context, Busqueda b) {
    if (b.cargando) return const Center(child: CircularProgressIndicator());
    if (b.error != null) {
      return _Vacio(icono: Icons.cloud_off, texto: b.error!, accion: ('Reintentar', b.buscar));
    }
    if (!b.tieneReferencia) {
      return const _Vacio(icono: Icons.search, texto: 'Busca un destino o activa tu ubicación en la pestaña Mapa.');
    }
    if (b.resultados.isEmpty) {
      return _Vacio(
        icono: Icons.local_parking,
        texto: b.mensaje ?? 'No hay resultados',
        accion: b.sugerirAmpliar
            ? ('Ampliar radio', () {
                b.cambiarRadio(b.radio * 2);
                b.buscar();
              })
            : null,
      );
    }
    return RefreshIndicator(
      onRefresh: b.buscar,
      child: ListView.separated(
        padding: const EdgeInsets.all(12),
        itemCount: b.resultados.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (_, i) => _Tarjeta(b.resultados[i], destacado: i == 0 && b.orden == 'tarifa'),
      ),
    );
  }

  Future<void> _filtro(BuildContext context, Busqueda b) async {
    var rango = RangeValues(b.tarifaMin ?? 0, b.tarifaMax ?? 20000);
    final r = await showModalBottomSheet<RangeValues>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, set) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Tarifa por hora', style: Theme.of(ctx).textTheme.titleMedium),
              Text('${tarifa(rango.start)} – ${rango.end >= 20000 ? 'sin límite' : tarifa(rango.end)}'),
              RangeSlider(
                values: rango,
                min: 0,
                max: 20000,
                divisions: 40,
                onChanged: (v) => set(() => rango = v),
              ),
              Row(children: [
                TextButton(onPressed: () => Navigator.pop(ctx, const RangeValues(-1, -1)), child: const Text('Quitar filtro')),
                const Spacer(),
                FilledButton(onPressed: () => Navigator.pop(ctx, rango), child: const Text('Aplicar')),
              ]),
            ]),
          ),
        ),
      ),
    );
    if (r == null) return;
    if (r.start < 0) {
      b.cambiarRangoTarifa(null, null);
    } else {
      b.cambiarRangoTarifa(r.start > 0 ? r.start : null, r.end < 20000 ? r.end : null);
    }
  }
}

class _Tarjeta extends StatelessWidget {
  final Parqueadero p;
  final bool destacado;
  const _Tarjeta(this.p, {this.destacado = false});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final sinTarifa = p.tarifaHora == null;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => DetalleScreen(parqueaderoId: p.id))),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (destacado)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text('MÁS ECONÓMICO',
                        style: t.textTheme.labelSmall?.copyWith(color: t.colorScheme.primary, fontWeight: FontWeight.bold)),
                  ),
                Text(p.nombre, style: t.textTheme.titleMedium),
                Text('${distancia(p.distanciaM)} · ${p.horario}', style: t.textTheme.bodySmall),
                const SizedBox(height: 4),
                Row(children: [
                  Icon(Icons.star, size: 16, color: Colors.amber.shade700),
                  Text(p.calificacion != null ? ' ${p.calificacion!.toStringAsFixed(1)} (${p.totalResenas})' : ' Sin reseñas',
                      style: t.textTheme.bodySmall),
                  if (p.abiertoAhora == false) ...[
                    const SizedBox(width: 8),
                    Text('Cerrado ahora', style: t.textTheme.bodySmall?.copyWith(color: t.colorScheme.error)),
                  ],
                  if (p.capacidadDisponible != null) ...[
                    const SizedBox(width: 8),
                    Text('~${p.capacidadDisponible} cupos', style: t.textTheme.bodySmall),
                  ],
                ]),
              ]),
            ),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(tarifa(p.tarifaHora),
                  style: sinTarifa
                      ? t.textTheme.bodySmall?.copyWith(fontStyle: FontStyle.italic)
                      : t.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              if (!sinTarifa) Text('por hora', style: t.textTheme.bodySmall),
              if (p.tarifaDia != null) Text('${tarifa(p.tarifaDia)}/día', style: t.textTheme.bodySmall),
            ]),
          ]),
        ),
      ),
    );
  }
}

class _Vacio extends StatelessWidget {
  final IconData icono;
  final String texto;
  final (String, VoidCallback)? accion;
  const _Vacio({required this.icono, required this.texto, this.accion});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icono, size: 48, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text(texto, textAlign: TextAlign.center),
            if (accion != null) ...[
              const SizedBox(height: 12),
              OutlinedButton(onPressed: accion!.$2, child: Text(accion!.$1)),
            ],
          ]),
        ),
      );
}
