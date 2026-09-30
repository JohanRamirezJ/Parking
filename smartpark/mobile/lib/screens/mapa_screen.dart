import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../formato.dart';
import '../models.dart';
import '../state/busqueda.dart';
import 'detalle_screen.dart';

/// HU 5 (buscar destino), HU 6 (ver parqueaderos en mapa), HU 7 (ajustar radio).
class MapaScreen extends StatefulWidget {
  final VoidCallback onVerLista;
  const MapaScreen({super.key, required this.onVerLista});

  @override
  State<MapaScreen> createState() => _MapaScreenState();
}

class _MapaScreenState extends State<MapaScreen> {
  final _mapa = MapController();
  final _texto = TextEditingController();
  bool _buscandoDestino = false;
  double? _ultimoLat, _ultimoLon;

  double _zoomParaRadio(double r) => r <= 300 ? 16.5 : r <= 700 ? 15.5 : r <= 1500 ? 14.5 : r <= 3000 ? 13.5 : 12.5;

  Future<void> _buscarDestino() async {
    FocusScope.of(context).unfocus();
    setState(() => _buscandoDestino = true);
    final error = await context.read<Busqueda>().buscarDestino(_texto.text);
    if (!mounted) return;
    setState(() => _buscandoDestino = false);
    if (error != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error)));
    }
  }

  void _seguirReferencia(Busqueda b) {
    if (b.lat != _ultimoLat || b.lon != _ultimoLon) {
      _ultimoLat = b.lat;
      _ultimoLon = b.lon;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        try {
          _mapa.move(LatLng(b.lat, b.lon), _zoomParaRadio(b.radio));
        } catch (_) {/* el mapa aún no está listo */}
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final b = context.watch<Busqueda>();
    final tema = Theme.of(context);
    _seguirReferencia(b);
    final centro = LatLng(b.lat, b.lon);

    return Scaffold(
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapa,
            options: MapOptions(initialCenter: centro, initialZoom: _zoomParaRadio(b.radio)),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'co.smartpark.app',
              ),
              CircleLayer(circles: [
                CircleMarker(
                  point: centro,
                  radius: b.radio,
                  useRadiusInMeter: true,
                  color: tema.colorScheme.primary.withOpacity(0.08),
                  borderColor: tema.colorScheme.primary.withOpacity(0.6),
                  borderStrokeWidth: 1.5,
                ),
              ]),
              MarkerLayer(markers: [
                Marker(
                  point: centro,
                  width: 36,
                  height: 36,
                  child: Icon(b.destino != null ? Icons.place : Icons.my_location,
                      color: tema.colorScheme.error, size: 32),
                ),
                for (final p in b.resultados)
                  Marker(
                    point: LatLng(p.latitud, p.longitud),
                    width: 80,
                    height: 44,
                    child: _Pin(p, onTap: () => _abrirResumen(p)),
                  ),
              ]),
              const RichAttributionWidget(attributions: [TextSourceAttribution('OpenStreetMap contributors')]),
            ],
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  Material(
                    elevation: 3,
                    borderRadius: BorderRadius.circular(28),
                    child: TextField(
                      controller: _texto,
                      textInputAction: TextInputAction.search,
                      onSubmitted: (_) => _buscarDestino(),
                      decoration: InputDecoration(
                        hintText: '¿A dónde vas? Dirección o lugar',
                        border: InputBorder.none,
                        filled: true,
                        fillColor: tema.colorScheme.surface,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                        prefixIcon: const Icon(Icons.search),
                        suffixIcon: _buscandoDestino
                            ? const Padding(
                                padding: EdgeInsets.all(14),
                                child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)))
                            : IconButton(
                                tooltip: 'Usar mi ubicación',
                                icon: const Icon(Icons.my_location),
                                onPressed: () {
                                  _texto.clear();
                                  b.obtenerUbicacion();
                                },
                              ),
                      ),
                    ),
                  ),
                  if (b.errorUbicacion != null && b.destino == null)
                    _Aviso(b.errorUbicacion!, tema.colorScheme.errorContainer),
                  if (b.destino != null) _Aviso('Destino: ${b.destino!.nombre}', tema.colorScheme.secondaryContainer),
                ],
              ),
            ),
          ),
          Positioned(left: 12, right: 12, bottom: 12, child: _PanelRadio(onVerLista: widget.onVerLista)),
        ],
      ),
    );
  }

  void _abrirResumen(Parqueadero p) {
    showModalBottomSheet(
      context: context,
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(p.nombre, style: Theme.of(context).textTheme.titleLarge),
              Text('${p.direccion} · ${distancia(p.distanciaM)}'),
              const SizedBox(height: 8),
              Text('Por hora: ${tarifa(p.tarifaHora)}   ·   Por día: ${tarifa(p.tarifaDia)}'),
              Text(p.calificacion != null
                  ? '★ ${p.calificacion!.toStringAsFixed(1)} (${p.totalResenas} reseñas)'
                  : 'Aún sin reseñas'),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () {
                  Navigator.pop(context);
                  Navigator.push(context, MaterialPageRoute(builder: (_) => DetalleScreen(parqueaderoId: p.id)));
                },
                child: const Text('Ver detalle y reseñas'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Pin extends StatelessWidget {
  final Parqueadero p;
  final VoidCallback onTap;
  const _Pin(this.p, {required this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    final etiqueta = p.tarifaHora == null ? 'P' : '\$${(p.tarifaHora! / 1000).toStringAsFixed(1)}k';
    return GestureDetector(
      onTap: onTap,
      child: Column(children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: p.abiertoAhora == false ? c.outline : c.primary,
            borderRadius: BorderRadius.circular(12),
            boxShadow: const [BoxShadow(blurRadius: 3, color: Colors.black26)],
          ),
          child: Text(etiqueta, style: TextStyle(color: c.onPrimary, fontWeight: FontWeight.bold, fontSize: 12)),
        ),
        Icon(Icons.arrow_drop_down, color: p.abiertoAhora == false ? c.outline : c.primary, size: 18),
      ]),
    );
  }
}

class _Aviso extends StatelessWidget {
  final String texto;
  final Color color;
  const _Aviso(this.texto, this.color);
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        margin: const EdgeInsets.only(top: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(12)),
        child: Text(texto),
      );
}

class _PanelRadio extends StatelessWidget {
  final VoidCallback onVerLista;
  const _PanelRadio({required this.onVerLista});

  @override
  Widget build(BuildContext context) {
    final b = context.watch<Busqueda>();
    final enLimite = b.radio <= Config.radioMin || b.radio >= Config.radioMax;
    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(children: [
              Text('Radio: ${distancia(b.radio.round())}', style: const TextStyle(fontWeight: FontWeight.w600)),
              const Spacer(),
              if (b.cargando)
                const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              else
                TextButton(onPressed: onVerLista, child: Text('${b.resultados.length} resultados · Comparar')),
            ]),
            Slider(
              value: b.radio,
              min: Config.radioMin,
              max: Config.radioMax,
              divisions: 48,
              label: distancia(b.radio.round()),
              onChanged: b.cambiarRadio,
              onChangeEnd: (_) => b.buscar(),
            ),
            if (enLimite)
              Text(b.radio >= Config.radioMax ? 'Radio máximo alcanzado (5 km)' : 'Radio mínimo alcanzado (200 m)',
                  style: Theme.of(context).textTheme.bodySmall),
            if (b.error != null)
              Text(b.error!, style: TextStyle(color: Theme.of(context).colorScheme.error))
            else if (!b.cargando && b.resultados.isEmpty && b.mensaje != null)
              Row(children: [
                Expanded(child: Text(b.mensaje!)),
                if (b.sugerirAmpliar)
                  TextButton(
                    onPressed: () {
                      b.cambiarRadio(b.radio * 2);
                      b.buscar();
                    },
                    child: const Text('Ampliar'),
                  ),
              ]),
          ],
        ),
      ),
    );
  }
}
