import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../formato.dart';
import '../services/api.dart';
import '../state/sesion.dart';

/// HU 3: editar perfil. También muestra las notificaciones de moderación (RF-10).
class PerfilScreen extends StatefulWidget {
  const PerfilScreen({super.key});

  @override
  State<PerfilScreen> createState() => _PerfilScreenState();
}

class _PerfilScreenState extends State<PerfilScreen> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _nombre;
  late final TextEditingController _telefono;
  Map<String, dynamic> _errores = {};
  bool _guardando = false;
  List<dynamic> _notificaciones = [];

  @override
  void initState() {
    super.initState();
    final u = context.read<Sesion>().usuario!;
    _nombre = TextEditingController(text: u.nombre);
    _telefono = TextEditingController(text: u.telefono ?? '');
    _cargarNotificaciones();
  }

  Future<void> _cargarNotificaciones() async {
    try {
      final n = await context.read<Api>().notificaciones();
      if (mounted) setState(() => _notificaciones = n);
    } catch (_) {}
  }

  Future<void> _guardar() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _guardando = true;
      _errores = {};
    });
    final sesion = context.read<Sesion>();
    try {
      final u = await context.read<Api>().editarPerfil({'nombre': _nombre.text.trim(), 'telefono': _telefono.text.trim()});
      sesion.actualizarUsuario(u);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Perfil actualizado')));
    } on ApiException catch (e) {
      setState(() => _errores = e.detalles);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensaje)));
    } finally {
      if (mounted) setState(() => _guardando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sesion = context.watch<Sesion>();
    final u = sesion.usuario!;
    return Scaffold(
      appBar: AppBar(title: const Text('Mi perfil'), actions: [
        IconButton(tooltip: 'Cerrar sesión', icon: const Icon(Icons.logout), onPressed: () => sesion.cerrar()),
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Center(
          child: CircleAvatar(
            radius: 40,
            child: Text(u.nombre.isNotEmpty ? u.nombre[0].toUpperCase() : '?', style: const TextStyle(fontSize: 32)),
          ),
        ),
        const SizedBox(height: 8),
        Center(child: Text(u.email)),
        const SizedBox(height: 24),
        Form(
          key: _form,
          child: Column(children: [
            TextFormField(
              controller: _nombre,
              decoration: InputDecoration(labelText: 'Nombre', errorText: _errores['nombre']),
              validator: (v) => (v == null || v.trim().isEmpty) ? 'El nombre es obligatorio' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _telefono,
              keyboardType: TextInputType.phone,
              decoration: InputDecoration(labelText: 'Teléfono', errorText: _errores['telefono']),
              validator: (v) =>
                  (v != null && v.isNotEmpty && !RegExp(r'^\+?[0-9 ]{7,15}$').hasMatch(v)) ? 'Teléfono inválido' : null,
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(onPressed: _guardando ? null : _guardar, child: const Text('Guardar cambios')),
            ),
          ]),
        ),
        if (_notificaciones.isNotEmpty) ...[
          const Divider(height: 40),
          Text('Notificaciones', style: Theme.of(context).textTheme.titleMedium),
          for (final n in _notificaciones)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.info_outline),
              title: Text(n['mensaje']),
              subtitle: Text(fechaCorta(DateTime.parse(n['fecha']))),
            ),
        ],
      ]),
    );
  }
}
