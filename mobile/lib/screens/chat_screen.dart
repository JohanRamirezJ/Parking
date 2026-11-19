import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../formato.dart';
import '../models.dart';
import '../services/api.dart';
import '../state/busqueda.dart';
import 'detalle_screen.dart';

/// Chat con IA (RF-12): recomendación de parqueadero en lenguaje natural.
class ChatScreen extends StatefulWidget {
  final VoidCallback onVerEnMapa;
  const ChatScreen({super.key, required this.onVerEnMapa});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _Mensaje {
  final bool deUsuario;
  final String texto;
  final Parqueadero? recomendado;
  final List<Parqueadero> alternativas;
  final Map<String, dynamic>? destino;
  _Mensaje(this.deUsuario, this.texto,
      {this.recomendado, this.alternativas = const [], this.destino});
}

TextSpan _textoConNumeros(String texto, TextStyle estilo, Color colorNumero) {
  final partes = <InlineSpan>[];
  final numeros = RegExp(r'\d+(?:[.,]\d+)*').allMatches(texto);
  var inicio = 0;
  for (final numero in numeros) {
    if (numero.start > inicio) {
      partes.add(TextSpan(text: texto.substring(inicio, numero.start)));
    }
    partes.add(TextSpan(
      text: numero.group(0),
      style: estilo.copyWith(
        color: colorNumero,
        fontWeight: FontWeight.bold,
      ),
    ));
    inicio = numero.end;
  }
  if (inicio < texto.length) {
    partes.add(TextSpan(text: texto.substring(inicio)));
  }
  return TextSpan(style: estilo, children: partes);
}

class _ChatScreenState extends State<ChatScreen> {
  final _texto = TextEditingController();
  final _scroll = ScrollController();
  final List<_Mensaje> _mensajes = [
    _Mensaje(
        false,
        '¡Hola! Cuéntame a dónde vas y qué prefieres. Por ejemplo: '
        '"parqueadero barato cerca del Hospital San Ignacio" o "el mejor calificado en Chapinero por menos de 6 mil".'),
  ];
  bool _enviando = false;

  static const _sugerencias = [
    'Barato cerca del Centro Andino',
    'Abierto ahora cerca de Unicentro',
    'Mejor calificado en Chapinero',
  ];

  Future<void> _enviar([String? texto]) async {
    final msg = (texto ?? _texto.text).trim();
    if (msg.isEmpty || _enviando) return;
    _texto.clear();
    setState(() {
      _mensajes.add(_Mensaje(true, msg));
      _enviando = true;
    });
    _bajar();
    final b = context.read<Busqueda>();
    if (kDebugMode) {
      debugPrint(
          '[SmartPark chat] Enviando consulta al backend; ubicación incluida: ${b.tieneReferencia}.');
    }
    try {
      final r = await context.read<Api>().chat(msg,
          lat: b.tieneReferencia ? b.lat : null,
          lon: b.tieneReferencia ? b.lon : null);
      if (kDebugMode) {
        final avisoIa = r['aviso_ia'] ?? 'ninguno';
        final avisoOsm = r['aviso_osm'] ?? 'ninguno';
        final iaUsada = r['ia_usada'] == true;
        final interpretacionIaUsada = r['interpretacion_ia_usada'] == true;
        final proveedor = r['proveedor_ia'] ?? 'ninguno';
        final estadoIa = iaUsada
            ? 'el modelo respondió'
            : avisoIa != 'ninguno'
                ? 'falló; se usó respuesta de respaldo'
                : proveedor == 'ninguno'
                    ? r['parqueadero_recomendado'] == null
                        ? 'no ejecutada (sin recomendación)'
                        : 'no configurada; se usó plantilla'
                    : 'sin respuesta generativa';
        debugPrint(
            '[SmartPark chat] fuente=${r['fuente_datos'] ?? 'no indicada'}; '
            'IA=$estadoIa; '
            'interpretacionIA=$interpretacionIaUsada; '
            'proveedor=$proveedor; '
            'modelo=${r['modelo_ia'] ?? 'ninguno'}; '
            'avisoIA=$avisoIa; avisoOverpass=$avisoOsm');
      }
      final rec = r['parqueadero_recomendado'];
      final alternativas = (r['alternativas'] as List)
          .map((x) => Parqueadero.fromJson(Map<String, dynamic>.from(x as Map)))
          .toList();
      setState(() => _mensajes.add(_Mensaje(
          false, (r['respuesta'] as String).replaceAll('**', ''),
          recomendado: rec == null
              ? null
              : Parqueadero.fromJson(Map<String, dynamic>.from(rec)),
          alternativas: alternativas,
          destino: r['destino'] == null
              ? null
              : Map<String, dynamic>.from(r['destino']))));
    } on ApiException catch (e) {
      if (kDebugMode) {
        debugPrint(
            '[SmartPark chat] Error del backend: HTTP ${e.status} (${e.codigo}): ${e.mensaje}');
      }
      setState(() =>
          _mensajes.add(_Mensaje(false, 'No pude responder: ${e.mensaje}')));
    } finally {
      if (mounted) setState(() => _enviando = false);
      _bajar();
    }
  }

  void _bajar() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) {
          _scroll.animateTo(_scroll.position.maxScrollExtent,
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeOut);
        }
      });

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Asistente SmartPark')),
      body: Column(children: [
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.all(12),
            itemCount: _mensajes.length + (_enviando ? 1 : 0),
            itemBuilder: (_, i) {
              if (i == _mensajes.length) {
                return const Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                        padding: EdgeInsets.all(12),
                        child: Text('Buscando opciones…')));
              }
              final m = _mensajes[i];
              return Align(
                alignment:
                    m.deUsuario ? Alignment.centerRight : Alignment.centerLeft,
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.82),
                  child: Card(
                    color: m.deUsuario
                        ? t.colorScheme.primary
                        : t.colorScheme.surfaceContainerHighest,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (m.deUsuario)
                              Text(m.texto,
                                  style:
                                      TextStyle(color: t.colorScheme.onPrimary))
                            else
                              Text.rich(_textoConNumeros(
                                m.texto,
                                t.textTheme.bodyMedium ?? const TextStyle(),
                                t.colorScheme.primary,
                              )),
                            if (m.recomendado != null) ...[
                              const SizedBox(height: 8),
                              Wrap(spacing: 8, children: [
                                if (m.recomendado!.fuente == 'openstreetmap')
                                  Chip(
                                    avatar: const Icon(Icons.local_parking,
                                        size: 18),
                                    label: Text(
                                        '${m.recomendado!.nombre} · ${tarifa(m.recomendado!.tarifaHora)}'),
                                  )
                                else
                                  ActionChip(
                                    avatar: const Icon(Icons.info_outline,
                                        size: 18),
                                    label: Text(
                                        '${m.recomendado!.nombre} · ${tarifa(m.recomendado!.tarifaHora)}'),
                                    onPressed: () => Navigator.push(
                                        context,
                                        MaterialPageRoute(
                                            builder: (_) => DetalleScreen(
                                                parqueaderoId:
                                                    m.recomendado!.id))),
                                  ),
                                if (m.destino != null &&
                                    m.recomendado!.fuente != 'openstreetmap')
                                  ActionChip(
                                    avatar: const Icon(Icons.map_outlined,
                                        size: 18),
                                    label: const Text('Ver en el mapa'),
                                    onPressed: () {
                                      context.read<Busqueda>().fijarDestino(
                                          Destino(
                                              m.destino!['nombre'],
                                              (m.destino!['latitud'] as num)
                                                  .toDouble(),
                                              (m.destino!['longitud'] as num)
                                                  .toDouble()));
                                      widget.onVerEnMapa();
                                    },
                                  ),
                              ]),
                            ],
                            if (m.alternativas.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              const Text('Otras opciones:'),
                              Wrap(
                                spacing: 8,
                                children: [
                                  for (final p in m.alternativas)
                                    if (p.fuente == 'openstreetmap')
                                      Chip(
                                        avatar: const Icon(Icons.local_parking,
                                            size: 18),
                                        label: Text(
                                            '${p.nombre} · ${tarifa(p.tarifaHora)}'),
                                      )
                                    else
                                      ActionChip(
                                        avatar: const Icon(Icons.info_outline,
                                            size: 18),
                                        label: Text(
                                            '${p.nombre} · ${tarifa(p.tarifaHora)}'),
                                        onPressed: () => Navigator.push(
                                            context,
                                            MaterialPageRoute(
                                                builder: (_) => DetalleScreen(
                                                    parqueaderoId: p.id))),
                                      ),
                                ],
                              ),
                            ],
                          ]),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        if (_mensajes.length == 1)
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                for (final s in _sugerencias)
                  Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ActionChip(
                          label: Text(s), onPressed: () => _enviar(s))),
              ],
            ),
          ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _texto,
                  maxLength: 500,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _enviar(),
                  decoration: const InputDecoration(
                      hintText: 'Escribe tu consulta…', counterText: ''),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                  onPressed: _enviando ? null : _enviar,
                  icon: const Icon(Icons.send)),
            ]),
          ),
        ),
      ]),
    );
  }
}
