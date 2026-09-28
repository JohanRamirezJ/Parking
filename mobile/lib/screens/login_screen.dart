import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api.dart';
import '../state/sesion.dart';

/// HU 1 (registro) y HU 2 (inicio de sesión).
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _nombre = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _registro = false;
  bool _enviando = false;
  String? _error;
  Map<String, dynamic> _erroresCampo = {};

  Future<void> _enviar() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _enviando = true;
      _error = null;
      _erroresCampo = {};
    });
    final sesion = context.read<Sesion>();
    try {
      if (_registro) {
        await sesion.registro(_nombre.text.trim(), _email.text.trim(), _password.text);
      } else {
        await sesion.login(_email.text.trim(), _password.text);
      }
    } on ApiException catch (e) {
      setState(() {
        _error = e.mensaje;
        _erroresCampo = e.detalles;
      });
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final aviso = context.watch<Sesion>().avisoSesion;
    final tema = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _form,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Icon(Icons.local_parking_rounded, size: 64, color: tema.colorScheme.primary),
                    const SizedBox(height: 8),
                    Text('SmartPark', textAlign: TextAlign.center, style: tema.textTheme.headlineMedium),
                    Text('Encuentra y compara parqueaderos en Bogotá',
                        textAlign: TextAlign.center, style: tema.textTheme.bodyMedium),
                    const SizedBox(height: 32),
                    if (aviso != null && _error == null) _Banner(aviso, tema.colorScheme.tertiaryContainer),
                    if (_error != null) _Banner(_error!, tema.colorScheme.errorContainer),
                    if (_registro) ...[
                      TextFormField(
                        controller: _nombre,
                        decoration: InputDecoration(labelText: 'Nombre', errorText: _erroresCampo['nombre']),
                        textCapitalization: TextCapitalization.words,
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Escribe tu nombre' : null,
                      ),
                      const SizedBox(height: 12),
                    ],
                    TextFormField(
                      controller: _email,
                      decoration: InputDecoration(labelText: 'Correo', errorText: _erroresCampo['email']),
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      validator: (v) => (v == null || !v.contains('@')) ? 'Correo inválido' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _password,
                      decoration: InputDecoration(labelText: 'Contraseña', errorText: _erroresCampo['password']),
                      obscureText: true,
                      validator: (v) => (v == null || (_registro && v.length < 8))
                          ? 'Mínimo 8 caracteres'
                          : (v.isEmpty ? 'Escribe tu contraseña' : null),
                      onFieldSubmitted: (_) => _enviar(),
                    ),
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: _enviando ? null : _enviar,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: _enviando
                            ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                            : Text(_registro ? 'Crear cuenta' : 'Iniciar sesión'),
                      ),
                    ),
                    TextButton(
                      onPressed: () => setState(() {
                        _registro = !_registro;
                        _error = null;
                        _erroresCampo = {};
                      }),
                      child: Text(_registro ? '¿Ya tienes cuenta? Inicia sesión' : '¿No tienes cuenta? Regístrate'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  final String texto;
  final Color color;
  const _Banner(this.texto, this.color);

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(8)),
        child: Text(texto),
      );
}
