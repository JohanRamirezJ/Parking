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
  final Map<String, dynamic>? destino;
  _Mensaje(this.deUsuario, this.texto, {this.recomendado, this.destino});
}

class _ChatScreenState extends State<ChatScreen> {
  final _texto = TextEditingController();
  final _scroll = ScrollController();
  final List<_Mensaje> _mensajes = [
    _Mensaje(false, '¡Hola! Cuéntame a dónde vas y qué prefieres. Por ejemplo: '
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
    try {
      final r = await context.read<Api>().chat(msg,
          lat: b.tieneReferencia ? b.lat : null, lon: b.tieneReferencia ? b.lon : null);
      final rec = r['parqueadero_recomendado'];
      setState(() => _mensajes.add(_Mensaje(false, (r['respuesta'] as String).replaceAll('**', ''),
          recomendado: rec == null ? null : Parqueadero.fromJson(Map<String, dynamic>.from(rec)),
          destino: r['destino'] == null ? null : Map<String, dynamic>.from(r['destino']))));
    } on ApiException catch (e) {
      setState(() => _mensajes.add(_Mensaje(false, 'No pude responder: ${e.mensaje}')));
    } finally {
      if (mounted) setState(() => _enviando = false);
      _bajar();
    }
  }

  void _bajar() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) {
          _scroll.animateTo(_scroll.position.maxScrollExtent,
              duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
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
                    child: Padding(padding: EdgeInsets.all(12), child: Text('Buscando opciones…')));
              }
              final m = _mensajes[i];
              return Align(
                alignment: m.deUsuario ? Alignment.centerRight : Alignment.centerLeft,
                child: ConstrainedBox(
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.82),
                  child: Card(
                    color: m.deUsuario ? t.colorScheme.primary : t.colorScheme.surfaceContainerHighest,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(m.texto, style: TextStyle(color: m.deUsuario ? t.colorScheme.onPrimary : null)),
                        if (m.recomendado != null) ...[
                          const SizedBox(height: 8),
                          Wrap(spacing: 8, children: [
                            ActionChip(
                              avatar: const Icon(Icons.info_outline, size: 18),
                              label: Text('${m.recomendado!.nombre} · ${tarifa(m.recomendado!.tarifaHora)}'),
                              onPressed: () => Navigator.push(context,
                                  MaterialPageRoute(builder: (_) => DetalleScreen(parqueaderoId: m.recomendado!.id))),
                            ),
                            if (m.destino != null)
                              ActionChip(
                                avatar: const Icon(Icons.map_outlined, size: 18),
                                label: const Text('Ver en el mapa'),
                                onPressed: () {
                                  context.read<Busqueda>().fijarDestino(Destino(m.destino!['nombre'],
                                      (m.destino!['latitud'] as num).toDouble(), (m.destino!['longitud'] as num).toDouble()));
                                  widget.onVerEnMapa();
                                },
                              ),
                          ]),
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
                  Padding(padding: const EdgeInsets.only(right: 8), child: ActionChip(label: Text(s), onPressed: () => _enviar(s))),
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
                  decoration: const InputDecoration(hintText: 'Escribe tu consulta…', counterText: ''),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(onPressed: _enviando ? null : _enviar, icon: const Icon(Icons.send)),
            ]),
          ),
        ),
      ]),
    );
  }
}
